# PHI Redaction in LLM Prompts

**Date:** 2026-05-14
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation (sub-project #1 of 5)

## Problem

Every HealthFlow agent builds a text prompt and sends it to Anthropic's API. That prompt is assembled from data in `healthflow.db` — client age, zip code, medications, procedures, doctors, and (for the appeal and translation agents) free-text documents. The moment that text reaches `client.messages.create(...)`, it has left HealthFlow's servers — a HIPAA **disclosure** of protected health information to a third party.

HIPAA permits that disclosure only under a signed **Business Associate Agreement (BAA)** with the third party. This project assumes **no BAA with Anthropic**. So any text crossing that boundary must first be **de-identified**: the identifiers that tie data to a specific individual must be removed.

Today:
- `appeal_agent.py` redacts its free-text inputs via the existing `PHIRedactor` — correctly.
- `translation_agent.py` sends `DocumentSection.content` to Claude **unredacted** — a personalized Summary of Benefits or denial letter could carry the patient's name straight through.
- The other three agents (`comparison`, `cost_calculator`, `network`) already take typed, structured inputs with no free-text patient fields — they happen to be safe, but nothing *enforces* that they stay safe.
- There is no structural guarantee. "Remember to redact" is a convention, not a constraint. The next agent, or the next free-text field added to an existing agent, can silently leak PHI.

## Goal

Make PHI redaction a **structural property of the agent layer**, not a thing developers must remember:

- Every agent's prompt-building method accepts **only** a typed `PromptInput` dataclass. There is no code path from a raw string to a prompt body that does not pass through a `PromptInput` constructor.
- Each `PromptInput` constructor redacts every free-text field via `PHIRedactor` at construction time. The dataclass is `frozen=True`, so a redacted value cannot be replaced with a raw one afterward.
- `translation_agent.py`'s document content and question are redacted (closing the current leak).
- `appeal_agent.py`'s explicit `self.redactor.redact(...)` calls are replaced by `AppealPromptInput`'s constructor — the redaction still happens, but now via the uniform mechanism.
- A test suite proves redaction is applied, and a static check proves no agent bypasses the typed layer.

## Threat model (settled during brainstorming)

**No BAA assumed.** Strip patient identifiers; allow de-identified medical content.

| Data | Treatment | Why |
|---|---|---|
| Patient name, DOB, SSN, address, phone, member ID, email | **Redact** | HIPAA's 18 identifiers — these tie data to an individual |
| Medication names, procedure names | **Allow** | Not among HIPAA's 18 identifiers; de-identified once names/DOB/etc. are gone (safe-harbor standard) |
| Doctor names, NPIs | **Allow** | Professional identifiers, published in the public NPPES registry — not the patient's PHI |
| Age, income level, zip code | **Allow as structured fields** | Already passed as typed primitives, never as free text; age + income alone are not identifying |

## Non-Goals

- **No change to prompt strategy.** Agents send the same conceptual content; only patient identifiers are scrubbed.
- **No structured-data redactor.** Medication-class mapping ("Ozempic" → "[GLP-1]") is explicitly out of scope — the threat model allows medication names.
- **No audit-log code changes.** Current `audit.log(...)` payloads contain only doctor names + NPIs (allowed) and counters/lengths (safe). The spec verifies this by reading; no redaction layer is added to the audit logger in this sub-project. (PHI access audit logging is sub-project #3, separate spec.)
- **No BAA procurement, no admin RBAC, no encryption.** Other sub-projects.

## Design

### New module: `healthflow/agents/prompt_inputs.py`

Five frozen dataclasses, one per agent, plus a small `_redact_field` helper:

```python
@dataclass(frozen=True)
class TranslationPromptInput:
    sections: tuple[RedactedSection, ...]
    question: str

    def __post_init__(self):
        object.__setattr__(self, "question", _redact_field(self.question))
        object.__setattr__(
            self, "sections",
            tuple(RedactedSection(s.title, _redact_field(s.content)) for s in self.sections),
        )
```

`_redact_field(text: str) -> str` wraps `PHIRedactor().redact(text)` and returns only the redacted string (the redaction log is captured separately for the audit count — see below). The helper exists so the `object.__setattr__` pattern (required because the dataclass is frozen) appears once, not five times.

**Per-agent free-text fields:**

| PromptInput | Redacted free-text fields | Pass-through structured fields |
|---|---|---|
| `ComparisonPromptInput` | (none) | `plans`, `age`, `income_level`, `medications`, `procedures` |
| `CostPromptInput` | (none) | `plans`, `usage` |
| `NetworkPromptInput` | (none) | `plans`, `providers`, `prescriptions` |
| `TranslationPromptInput` | `question`, `sections[].content` | `sections[].title` |
| `AppealPromptInput` | `denial_text`, `additional_context` | `analysis`, `argument` |

Three of the five do no redaction work — they are typed wrappers that document and enforce the contract. They exist for **consistency** (every agent looks the same) and **future-proofing** (the day a free-text field is added to Comparison, the redacting layer is already there).

### Redaction count for the audit logger

`PHIRedactor.redact()` returns `(redacted_text, log)`. Each `PromptInput` that redacts captures the combined log length and the distinct placeholder types, and exposes them as a read-only property `redaction_summary -> dict` (e.g. `{"count": 3, "types": ["[PATIENT_NAME]", "[DOB]"]}`). The agent then calls `audit.log("phi_redacted", input.redaction_summary)` — preserving the existing `phi_redacted` audit event that `appeal_agent.py` emits today, now uniformly across redacting agents. Non-redacting PromptInputs expose `redaction_summary` as `{"count": 0, "types": []}`.

### Modified files

| File | Change |
|---|---|
| `healthflow/agents/prompt_inputs.py` | NEW — 5 dataclasses, `RedactedSection`, `_redact_field` helper |
| `healthflow/tools/phi_redactor.py` | Add one email-address regex pattern (`[EMAIL]` placeholder) |
| `healthflow/agents/comparison_agent.py` | `_build_prompt` takes `ComparisonPromptInput`; `recommend()` constructs it |
| `healthflow/agents/cost_calculator_agent.py` | Same pattern with `CostPromptInput` |
| `healthflow/agents/network_agent.py` | Same pattern with `NetworkPromptInput` |
| `healthflow/agents/translation_agent.py` | Same pattern with `TranslationPromptInput`; **this one actually redacts** |
| `healthflow/agents/appeal_agent.py` | Replace the explicit `self.redactor.redact(...)` calls with a single `AppealPromptInput(...)` construction; the `phi_redacted` audit event sources its data from `input.redaction_summary` |

**Note on `appeal_agent.py`:** `process_appeal` uses its redacted text for *two* downstream consumers — `self.parser.parse(redacted_denial)` (step 2) and `_refine_with_claude(...)` (step 7). `AppealPromptInput` therefore stores the redacted denial text and redacted additional context as readable fields (`redacted_denial`, `redacted_context`); the agent reads those fields for both the parse step and the prompt step. The `PromptInput` is not "prompt-only" here — it is the single redaction boundary, and everything downstream consumes its already-redacted fields.

Public entry points (`recommend()`, `calculate()`, `verify()`, `translate()`, `process_appeal()`) keep their existing signatures — they accept the same raw arguments as today and construct the `PromptInput` internally before calling `_build_prompt` (and, for appeal, before the parse step). Callers (the FastAPI routes) are unchanged.

### Data flow after the change

```
API route → agent.recommend(raw args)
              → ComparisonPromptInput(raw args)   ← redaction happens HERE, in __post_init__
              → agent._build_prompt(typed input)  ← can only receive the typed object
              → client.messages.create(prompt)    ← prompt is already clean
```

### Test plan

1. **`healthflow/tests/agents/test_prompt_inputs.py` (NEW)** — one unit test per dataclass:
   - For `Translation` and `Appeal`: construct with PHI in free-text fields (`Patient: John Doe`, `DOB: 01/01/1950`, `john@example.com`); assert the stored fields contain `[PATIENT_NAME]`, `[DOB]`, `[EMAIL]`; assert `redaction_summary["count"]` is correct.
   - For `Comparison`, `Cost`, `Network`: construct with valid structured data; assert fields pass through unchanged and `redaction_summary == {"count": 0, "types": []}`.
2. **Agent-level redaction-applied tests** — extend `test_translation_agent.py` and `test_appeal_agent.py`: mock the Anthropic client, feed PHI-bearing input through the public entry point, assert the intercepted `user_prompt` contains placeholders, not raw identifiers.
3. **`healthflow/tests/agents/test_no_raw_prompt_path.py` (NEW)** — an `ast`-based static check: walk all five agent modules, find every call to a `_build_prompt` method, assert the argument is a `PromptInput` construction or a variable (never a raw string/list literal). Locks in the structural guarantee. If this test proves noisy on dynamic call patterns, it may be dropped — the type annotation on `_build_prompt` is the primary enforcement.
4. **`healthflow/tests/tools/test_phi_redactor.py`** — extend with an email-pattern test.

Existing agent tests keep their assertions where they don't involve PHI; tests that asserted on raw text in redacting agents (`translation`, `appeal`) are updated to expect redacted strings.

### Rollout

1. Add `prompt_inputs.py` + `test_prompt_inputs.py`. New types exist, not yet wired in; suite green.
2. Add the email pattern to `PHIRedactor` + its test.
3. Migrate one agent at a time, one commit each, suite green after each: `translation` first (highest PHI risk), then `appeal`, then `comparison` / `cost` / `network`.
4. Add the agent-level redaction-applied tests.
5. Add the `ast` static check.
6. Update the `healthflow-security` skill: new rule — "Never call an agent's `_build_prompt` directly. Construct the agent's `PromptInput` and pass it in. Free-text fields are redacted by the `PromptInput` constructor; structured fields (medications, procedures, doctor names/NPIs) pass through by design."

### Risks

| Risk | Mitigation |
|---|---|
| `frozen=True` + redaction in `__post_init__` needs `object.__setattr__` — easy to get subtly wrong | The `_redact_field` helper encapsulates the pattern; the dataclasses call it consistently. Unit tests in group #1 catch a broken constructor immediately. |
| Existing `translation` / `appeal` tests assert on un-redacted text | Audited during rollout step 3; assertions updated to expect redacted output as part of the same commit that migrates the agent. |
| The `ast` static check false-positives on dynamic call sites | Test group #3 is explicitly droppable — the `_build_prompt` type annotation is the real enforcement; the `ast` check is belt-and-suspenders. |
| `PHIRedactor`'s regexes miss a PHI shape (it is heuristic, not exhaustive) | Out of scope to make the regex exhaustive here. The email pattern is the one known gap being closed. Improving redactor coverage is a follow-up; the typed layer means any future pattern added to `PHIRedactor` is automatically applied everywhere. |

## Acceptance

This sub-project is done when:

1. `healthflow/agents/prompt_inputs.py` exists with five `PromptInput` dataclasses and the `_redact_field` helper.
2. All five agents' `_build_prompt` methods accept only their typed `PromptInput`; public entry-point signatures are unchanged.
3. `translation_agent.py` redacts `DocumentSection.content` and the question; `appeal_agent.py` redacts via `AppealPromptInput` instead of inline calls.
4. `PHIRedactor` has an email pattern.
5. `test_prompt_inputs.py` and the agent-level redaction-applied tests pass; the full suite is green.
6. The `healthflow-security` skill documents the new rule.

## Out of Scope

- PHI access audit log (sub-project #3) — logging *who read which patient's data when*.
- Auth hardening (sub-project #4).
- Encryption at rest (sub-project #5).
- Admin RBAC (in-flight follow-up from the multi-tenancy work).
- Making `PHIRedactor`'s regex coverage exhaustive — only the email gap is closed here.
