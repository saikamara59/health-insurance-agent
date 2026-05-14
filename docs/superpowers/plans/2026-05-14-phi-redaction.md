# PHI Redaction in LLM Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PHI redaction a structural property of the agent layer — every agent's `_build_prompt` method accepts only a typed `PromptInput` dataclass whose constructor redacts free-text fields via the existing `PHIRedactor`, so no code path from a raw string to a prompt body can bypass redaction.

**Architecture:** A new `healthflow/agents/prompt_inputs.py` defines five `frozen=True` dataclasses (one per agent) plus a `RedactedSection` helper type, a `_redact_field` function, and a `_summarize` function. Each dataclass's `__post_init__` redacts its free-text fields at construction time. Agent public entry points (`recommend()`, `translate()`, etc.) keep their existing signatures and construct the `PromptInput` internally before calling `_build_prompt`. Three of the five dataclasses have no free-text fields — they are typed wrappers that document and enforce the contract uniformly.

**Tech Stack:** Python 3.14, `dataclasses` (stdlib), the existing `healthflow/tools/phi_redactor.py` regex redactor, `anthropic` SDK, pytest, `ast` (stdlib, for the static-check test).

**Spec:** [docs/superpowers/specs/2026-05-14-phi-redaction-design.md](../specs/2026-05-14-phi-redaction-design.md)

---

## Background: why frozen dataclasses + `object.__setattr__`

This plan uses a Python pattern that is worth understanding before implementing:

- `@dataclass(frozen=True)` makes instances **immutable** — after construction you cannot do `instance.field = new_value`. This is a safety property: once a field is redacted, nothing can replace it with the raw value.
- But the **constructor itself** needs to write the redacted value. Frozen dataclasses block normal assignment everywhere, including inside `__post_init__`. The escape hatch is `object.__setattr__(self, "field", value)` — Python's low-level "bypass the frozen check" write. It is a known, accepted pattern for exactly this case.
- **Subtle point:** `object.__setattr__` is only needed when you **reassign an attribute**. Mutating a mutable object that an attribute already points to — e.g. `self._redaction_log.append(...)` — is *not* reassignment, so it works on a frozen dataclass without the escape hatch. The plan relies on this: redacted strings are reassigned (need `object.__setattr__`), but the redaction-log list is mutated in place (plain `.extend()` works).
- **`InitVar`** (`from dataclasses import InitVar`) declares a **constructor-only parameter**: it shows up in `__init__` and is passed to `__post_init__`, but it is *not* stored as an instance attribute. `AppealPromptInput` uses this so the **raw** denial text never persists on the instance — it goes into `__post_init__`, gets redacted, and the only thing stored is the redacted result. (`TranslationPromptInput` instead overwrites its `question`/`sections` fields in place via `object.__setattr__` — also fine, because the raw value is *replaced*, not kept alongside. Two valid patterns; each is the cleanest for its case.)

---

## File Structure

```
healthflow/
  agents/
    prompt_inputs.py            (NEW — 5 dataclasses, RedactedSection, _redact_field, _summarize)
    comparison_agent.py         (MODIFIED — _build_prompt takes ComparisonPromptInput)
    cost_calculator_agent.py    (MODIFIED — _build_prompt takes CostPromptInput)
    network_agent.py            (MODIFIED — _build_prompt takes NetworkPromptInput)
    translation_agent.py        (MODIFIED — _build_prompt takes TranslationPromptInput; actually redacts)
    appeal_agent.py             (MODIFIED — AppealPromptInput is the single redaction boundary)
  tools/
    phi_redactor.py             (MODIFIED — add [EMAIL] pattern)
  tests/
    agents/
      test_prompt_inputs.py     (NEW — one unit test per dataclass)
      test_no_raw_prompt_path.py (NEW — ast static check)
      test_translation_agent.py (MODIFIED — add redaction-applied test)
      test_appeal_agent.py      (MODIFIED — add redaction-applied test)
    tools/
      test_phi_redactor.py      (MODIFIED — add email-pattern test)
.claude/skills/
  healthflow-security/
    SKILL.md                    (MODIFIED — new rule about PromptInput)
```

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b phi-redaction/agent-layer
git branch --show-current
```

Expected: `phi-redaction/agent-layer`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `489 tests collected in X.XXs`. Record the actual number.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: all 489 tests pass. (There is a known-flaky `test_tampered_token_raises`; if exactly that one test fails on the first run, re-run once before declaring failure.)

No commit for this task.

---

## Task 2: Add `[EMAIL]` pattern to `PHIRedactor`

**Files:**
- Modify: `healthflow/tools/phi_redactor.py`
- Test: `healthflow/tests/tools/test_phi_redactor.py`

The `PromptInput` unit tests (Task 3) assert that email addresses are redacted, so this pattern must exist first.

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/tools/test_phi_redactor.py`:

```python
def test_redacts_email_address():
    redactor = PHIRedactor()
    redacted, log = redactor.redact("Contact the member at jane.doe@example.com for details.")
    assert "jane.doe@example.com" not in redacted
    assert "[EMAIL]" in redacted
    assert any(entry["placeholder"] == "[EMAIL]" for entry in log)


def test_email_redaction_leaves_non_email_text_intact():
    redactor = PHIRedactor()
    redacted, _ = redactor.redact("The plan covers 80% after deductible.")
    assert redacted == "The plan covers 80% after deductible."
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest healthflow/tests/tools/test_phi_redactor.py::test_redacts_email_address -v
```

Expected: FAIL — `[EMAIL]` not in redacted output (pattern doesn't exist yet).

- [ ] **Step 3: Add the email pattern**

Edit `healthflow/tools/phi_redactor.py`. In the `PATTERNS` list, add this entry after the `phone` entry (the last one):

```python
        # Email addresses
        {
            "placeholder": "[EMAIL]",
            "pattern": "email",
            "regex": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
            ),
        },
```

The `email` pattern name is NOT in the `("name_label", "dear_name", "dob", "member_id")` tuple in the `redact` method, so it falls through to the `else` branch — the whole match is replaced with `[EMAIL]`. That is the correct behavior (the entire email is PHI, not just a captured group).

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/tools/test_phi_redactor.py -v
```

Expected: all `test_phi_redactor.py` tests pass, including the 2 new ones.

- [ ] **Step 5: Verify total count is now 489 + 2 = 491**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `491 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/tools/phi_redactor.py healthflow/tests/tools/test_phi_redactor.py
git commit -m "phi_redactor: add [EMAIL] redaction pattern"
```

No `Co-Authored-By` trailer.

---

## Task 3: Create `prompt_inputs.py` with the five dataclasses

**Files:**
- Create: `healthflow/agents/prompt_inputs.py`
- Test: `healthflow/tests/agents/test_prompt_inputs.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/agents/test_prompt_inputs.py`:

```python
"""Unit tests for the typed PromptInput layer.

Each agent's prompt-builder accepts only a PromptInput dataclass whose
constructor redacts free-text fields. These tests prove redaction is
applied at construction and structured fields pass through unchanged.
"""
from healthflow.agents.prompt_inputs import (
    AppealPromptInput,
    ComparisonPromptInput,
    CostPromptInput,
    NetworkPromptInput,
    RedactedSection,
    TranslationPromptInput,
)


# --- Translation: actually redacts ---

def test_translation_prompt_input_redacts_question_and_sections():
    raw_sections = [
        RedactedSection(title="Coverage", content="Patient: John Doe has coverage."),
        RedactedSection(title="Contact", content="Reach them at john@example.com."),
    ]
    pi = TranslationPromptInput(
        sections=tuple(raw_sections),
        question="Does Dear Jane Doe have a copay?",
    )
    # Free-text redacted.
    assert "John Doe" not in pi.sections[0].content
    assert "[PATIENT_NAME]" in pi.sections[0].content
    assert "john@example.com" not in pi.sections[1].content
    assert "[EMAIL]" in pi.sections[1].content
    assert "Jane Doe" not in pi.question
    assert "[PATIENT_NAME]" in pi.question
    # Section titles pass through (assumed safe — they are headings).
    assert pi.sections[0].title == "Coverage"
    # Redaction summary reflects what was redacted.
    summary = pi.redaction_summary
    assert summary["count"] >= 3
    assert "[PATIENT_NAME]" in summary["types"]
    assert "[EMAIL]" in summary["types"]


# --- Appeal: actually redacts ---

def test_appeal_prompt_input_redacts_denial_and_context():
    pi = AppealPromptInput(
        denial_text="Patient: Mary Smith was denied. DOB: 01/02/1955.",
        additional_context="Member ID: ABC-12345 called about this.",
    )
    assert "Mary Smith" not in pi.redacted_denial
    assert "[PATIENT_NAME]" in pi.redacted_denial
    assert "01/02/1955" not in pi.redacted_denial
    assert "[DOB]" in pi.redacted_denial
    assert "ABC-12345" not in pi.redacted_context
    assert "[MEMBER_ID]" in pi.redacted_context
    summary = pi.redaction_summary
    assert summary["count"] >= 3
    assert set(summary["types"]) >= {"[PATIENT_NAME]", "[DOB]", "[MEMBER_ID]"}


def test_appeal_prompt_input_handles_empty_context():
    pi = AppealPromptInput(denial_text="Claim denied for procedure.", additional_context="")
    assert pi.redacted_context == ""
    assert pi.redaction_summary["count"] == 0


# --- Comparison / Cost / Network: typed wrappers, no free text ---

def test_comparison_prompt_input_passes_structured_fields_through():
    pi = ComparisonPromptInput(
        plans=["plan-a", "plan-b"],   # real PlanSummary objects in production; opaque here
        age=67,
        income_level="low",
        medications=["Metformin", "Lisinopril"],
        procedures=["Annual physical"],
    )
    assert pi.age == 67
    assert pi.income_level == "low"
    assert pi.medications == ["Metformin", "Lisinopril"]
    assert pi.procedures == ["Annual physical"]
    assert pi.redaction_summary == {"count": 0, "types": []}


def test_cost_prompt_input_passes_structured_fields_through():
    pi = CostPromptInput(results=["result-a"], usage="usage-obj")
    assert pi.results == ["result-a"]
    assert pi.usage == "usage-obj"
    assert pi.redaction_summary == {"count": 0, "types": []}


def test_network_prompt_input_passes_structured_fields_through():
    pi = NetworkPromptInput(plan_results=["net-result-a"])
    assert pi.plan_results == ["net-result-a"]
    assert pi.redaction_summary == {"count": 0, "types": []}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_prompt_inputs.py -v
```

Expected: ImportError — `healthflow.agents.prompt_inputs` does not exist.

- [ ] **Step 3: Create `prompt_inputs.py`**

Create `healthflow/agents/prompt_inputs.py`:

```python
"""Typed prompt inputs for the agent layer — the single PHI redaction boundary.

Every agent's `_build_prompt` method accepts ONLY one of these dataclasses.
There is no code path from a raw string to a prompt body that does not pass
through a PromptInput constructor, and each constructor redacts its free-text
fields via PHIRedactor at construction time. The dataclasses are frozen, so a
redacted value cannot be replaced with a raw one afterward.

Three of the five (Comparison, Cost, Network) have no free-text fields — they
are typed wrappers that enforce the contract uniformly and make the layer
ready for the day someone adds a free-text field.

See docs/superpowers/specs/2026-05-14-phi-redaction-design.md for the threat
model (no BAA assumed: redact patient identifiers, allow de-identified medical
content like medication/procedure names and doctor names/NPIs).
"""
from dataclasses import dataclass, field, InitVar
from typing import Any

from healthflow.tools.phi_redactor import PHIRedactor

# Module-level singleton — PHIRedactor compiles its regexes at class-definition
# time, so constructing one per call would be wasteful.
_REDACTOR = PHIRedactor()


def _redact_field(text: str) -> tuple[str, list[dict]]:
    """Redact PHI from a free-text field.

    Returns (redacted_text, redaction_log). The log is a list of dicts with
    'placeholder', 'pattern', 'position' keys — see PHIRedactor.redact.
    """
    return _REDACTOR.redact(text)


def _summarize(log: list[dict]) -> dict:
    """Turn a redaction log into a compact summary for the audit logger."""
    return {
        "count": len(log),
        "types": sorted({entry["placeholder"] for entry in log}),
    }


@dataclass(frozen=True)
class RedactedSection:
    """A document section whose content has already been redacted.

    `title` is assumed safe (section headings, not patient data). `content`
    is redacted by the TranslationPromptInput constructor before a
    RedactedSection is stored.
    """
    title: str
    content: str


@dataclass(frozen=True)
class TranslationPromptInput:
    """Input for TranslationAgent._build_prompt. Redacts question + section content."""
    sections: tuple[RedactedSection, ...]
    question: str
    _redaction_log: list[dict] = field(
        default_factory=list, init=False, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        # Reassigning frozen-dataclass attributes requires object.__setattr__.
        q_redacted, q_log = _redact_field(self.question)
        object.__setattr__(self, "question", q_redacted)
        # Mutating the list the attribute points at does NOT need the escape
        # hatch — it is not a reassignment.
        self._redaction_log.extend(q_log)

        redacted_sections = []
        for section in self.sections:
            c_redacted, c_log = _redact_field(section.content)
            redacted_sections.append(RedactedSection(section.title, c_redacted))
            self._redaction_log.extend(c_log)
        object.__setattr__(self, "sections", tuple(redacted_sections))

    @property
    def redaction_summary(self) -> dict:
        return _summarize(self._redaction_log)


@dataclass(frozen=True)
class AppealPromptInput:
    """Input for AppealAgent. The single redaction boundary for the appeal flow.

    `denial_text` / `additional_context` are InitVar — constructor-only
    parameters. The RAW text is passed to __post_init__, redacted, and then
    discarded; only `redacted_denial` / `redacted_context` persist on the
    instance. `process_appeal` consumes `redacted_denial` for BOTH the denial
    parser and the Claude refine prompt — this dataclass is not prompt-only.
    """
    denial_text: InitVar[str]
    additional_context: InitVar[str]
    redacted_denial: str = field(init=False, default="")
    redacted_context: str = field(init=False, default="")
    _redaction_log: list[dict] = field(
        default_factory=list, init=False, compare=False, repr=False
    )

    def __post_init__(self, denial_text: str, additional_context: str) -> None:
        # InitVar params arrive here as arguments (in declaration order), not
        # as self.* attributes — so the raw text never becomes a stored field.
        denial_redacted, denial_log = _redact_field(denial_text)
        object.__setattr__(self, "redacted_denial", denial_redacted)
        self._redaction_log.extend(denial_log)

        context_redacted, context_log = _redact_field(additional_context)
        object.__setattr__(self, "redacted_context", context_redacted)
        self._redaction_log.extend(context_log)

    @property
    def redaction_summary(self) -> dict:
        return _summarize(self._redaction_log)


@dataclass(frozen=True)
class ComparisonPromptInput:
    """Input for ComparisonAgent._build_prompt. No free-text fields — typed wrapper."""
    plans: list[Any]            # list[PlanSummary] in production
    age: int
    income_level: str
    medications: list[str]
    procedures: list[str]

    @property
    def redaction_summary(self) -> dict:
        return {"count": 0, "types": []}


@dataclass(frozen=True)
class CostPromptInput:
    """Input for CostCalculatorAgent._build_prompt. No free-text fields — typed wrapper."""
    results: list[Any]          # list[PlanCostResult] in production
    usage: Any                  # UsageInput in production

    @property
    def redaction_summary(self) -> dict:
        return {"count": 0, "types": []}


@dataclass(frozen=True)
class NetworkPromptInput:
    """Input for NetworkAgent._build_prompt. No free-text fields — typed wrapper.

    Wraps `plan_results` (list[PlanNetworkResult]) — what _build_prompt actually
    consumes. Provider names + NPIs inside plan_results are professional
    identifiers (public NPPES registry data), not patient PHI, so they pass
    through by design.
    """
    plan_results: list[Any]     # list[PlanNetworkResult] in production

    @property
    def redaction_summary(self) -> dict:
        return {"count": 0, "types": []}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_prompt_inputs.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Verify total count is now 491 + 7 = 498**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `498 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/agents/prompt_inputs.py healthflow/tests/agents/test_prompt_inputs.py
git commit -m "Add typed PromptInput layer for agent PHI redaction boundary"
```

---

## Task 4: Migrate `translation_agent.py`

**Files:**
- Modify: `healthflow/agents/translation_agent.py`
- Modify: `healthflow/tests/agents/test_translation_agent.py` (if existing tests assert on raw text)

This is the agent with the live PHI leak — `DocumentSection.content` currently reaches Claude unredacted. After this task it goes through `TranslationPromptInput`.

- [ ] **Step 1: Modify `translation_agent.py`**

Edit `healthflow/agents/translation_agent.py`. Add the import near the top:

```python
from healthflow.agents.prompt_inputs import RedactedSection, TranslationPromptInput
```

Change the `translate` method to construct the `TranslationPromptInput` and emit a `phi_redacted` audit event. Replace the current `translate` body:

```python
    def translate(
        self,
        sections: list[DocumentSection],
        question: str,
    ) -> tuple[str, list[str]]:
        prompt_input = TranslationPromptInput(
            sections=tuple(
                RedactedSection(title=s.title, content=s.content) for s in sections
            ),
            question=question,
        )
        section_titles = [s.title for s in prompt_input.sections]

        self.audit.log("phi_redacted", prompt_input.redaction_summary)

        user_prompt = self._build_prompt(prompt_input)

        self.audit.log(
            "tool_called",
            {"tool": "claude_api", "model": CLAUDE_MODEL, "task": "translate"},
        )

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        answer = extract_text(response)
        self.audit.log("recommendation_generated", {"length": len(answer), "task": "translate"})
        return answer, section_titles
```

Change `_build_prompt` to take the typed input:

```python
    def _build_prompt(self, prompt_input: TranslationPromptInput) -> str:
        lines = [
            "Below are relevant sections from a health insurance Summary of Benefits document.",
            "",
        ]

        for section in prompt_input.sections:
            lines.append(f"## {section.title}")
            lines.append(section.content)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"Question: {prompt_input.question}")
        lines.append("")
        lines.append(
            "Answer this question in plain English based on the document sections above. "
            "Be specific about dollar amounts, copays, and conditions. "
            "If the information is not in the document, say so clearly."
        )

        return "\n".join(lines)
```

- [ ] **Step 2: Run translation agent tests to find assertion breakage**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_translation_agent.py -v 2>&1 | tail -20
```

Expected: most tests pass. If a test fails because it asserted on raw (un-redacted) text in the prompt, that's expected — the prompt is now redacted. Update those assertions to expect redacted output (e.g. a test that passed `content="Patient: John Doe ..."` and asserted `"John Doe" in prompt` should now assert `"[PATIENT_NAME]" in prompt`). If a test fails for an unrelated reason, surface it.

- [ ] **Step 3: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 498 passed (no count change — only assertion updates, no new tests yet).

- [ ] **Step 4: Commit**

```bash
git add healthflow/agents/translation_agent.py healthflow/tests/agents/test_translation_agent.py
git commit -m "translation_agent: redact document content + question via TranslationPromptInput"
```

(If `test_translation_agent.py` needed no changes, omit it from the `git add`.)

---

## Task 5: Migrate `appeal_agent.py`

**Files:**
- Modify: `healthflow/agents/appeal_agent.py`
- Modify: `healthflow/tests/agents/test_appeal_agent.py` (if existing tests assert on raw text)

`appeal_agent` already redacts via `self.redactor.redact(...)`. This task replaces those inline calls with a single `AppealPromptInput` construction. The redacted fields feed BOTH the parser (step 2) and the Claude refine call (step 7).

- [ ] **Step 1: Modify `appeal_agent.py`**

Edit `healthflow/agents/appeal_agent.py`.

Replace the import line `from healthflow.tools.phi_redactor import PHIRedactor` with:

```python
from healthflow.agents.prompt_inputs import AppealPromptInput
```

In `__init__`, remove the line `self.redactor = PHIRedactor()` (the redactor is now used inside `AppealPromptInput`).

Replace Step 1 of `process_appeal` (the two `self.redactor.redact(...)` calls and the `phi_redacted` audit log) with:

```python
        # Step 1: Redact PHI — AppealPromptInput is the single redaction boundary.
        prompt_input = AppealPromptInput(
            denial_text=denial_text,
            additional_context=additional_context,
        )
        redacted_denial = prompt_input.redacted_denial
        redacted_context = prompt_input.redacted_context

        self.audit.log("phi_redacted", prompt_input.redaction_summary)
```

The rest of `process_appeal` continues to use the local `redacted_denial` and `redacted_context` variables exactly as before — `self.parser.parse(redacted_denial)` at step 2, `self._refine_with_claude(redacted_denial, redacted_context, ...)` at step 7. No other change to `process_appeal`.

`_refine_with_claude` keeps its current signature `(self, redacted_denial, redacted_context, analysis, argument)` — it already receives redacted strings; that contract is unchanged.

- [ ] **Step 2: Run appeal agent tests to find assertion breakage**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_appeal_agent.py healthflow/tests/agents/test_appeal_integration.py -v 2>&1 | tail -20
```

Expected: tests pass. The redaction behavior is identical to before (same `PHIRedactor`, same patterns) — only the call site moved. If a test mocked `PHIRedactor` or `self.redactor` directly, it needs updating to either mock at the `prompt_inputs` level or assert on the redacted output. Surface any test that needs more than a small fix.

- [ ] **Step 3: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 498 passed.

- [ ] **Step 4: Commit**

```bash
git add healthflow/agents/appeal_agent.py healthflow/tests/agents/test_appeal_agent.py
git commit -m "appeal_agent: route redaction through AppealPromptInput boundary"
```

(Adjust `git add` to only include files actually changed.)

---

## Task 6: Migrate `comparison_agent.py`

**Files:**
- Modify: `healthflow/agents/comparison_agent.py`

No redaction work — `ComparisonPromptInput` is a typed wrapper. The migration makes `_build_prompt` accept only the typed object.

- [ ] **Step 1: Modify `comparison_agent.py`**

Edit `healthflow/agents/comparison_agent.py`. Add the import near the top:

```python
from healthflow.agents.prompt_inputs import ComparisonPromptInput
```

In `recommend`, replace the `user_prompt = self._build_prompt(...)` line with:

```python
        prompt_input = ComparisonPromptInput(
            plans=plans,
            age=age,
            income_level=income_level,
            medications=medications or [],
            procedures=procedures or [],
        )
        user_prompt = self._build_prompt(prompt_input)
```

Change `_build_prompt`'s signature and body to read from the typed input:

```python
    def _build_prompt(self, prompt_input: ComparisonPromptInput) -> str:
        plans = prompt_input.plans
        age = prompt_input.age
        income_level = prompt_input.income_level
        medications = prompt_input.medications
        procedures = prompt_input.procedures

        lines = [
            f"Compare these Medicare Advantage plans for a {age}-year-old with {income_level} income.",
            "",
            "## Plans",
            "",
        ]

        for i, plan in enumerate(plans, 1):
            lines.append(f"### Plan {i}: {plan.plan_name} ({plan.plan_id})")
            lines.append(f"- Type: {plan.plan_type}")
            lines.append(f"- Monthly Premium: ${plan.monthly_premium:.2f}")
            lines.append(f"- Annual Deductible: ${plan.annual_deductible:.2f}")
            lines.append(f"- Out-of-Pocket Max: ${plan.out_of_pocket_max:.2f}")
            lines.append(f"- Star Rating: {plan.star_rating}/5.0")
            lines.append(f"- Drug Coverage: {'Yes' if plan.drug_coverage else 'No'}")

            if plan.estimated_medication_costs:
                lines.append("- Medication Costs:")
                for med, cost in plan.estimated_medication_costs.items():
                    lines.append(f"  - {med}: ${cost:.2f}/month")

            if plan.estimated_procedure_costs:
                lines.append("- Procedure Costs:")
                for proc, cost in plan.estimated_procedure_costs.items():
                    lines.append(f"  - {proc}: ${cost:.2f}")

            lines.append("")

        if medications:
            lines.append(f"The user takes these medications: {', '.join(medications)}")
        if procedures:
            lines.append(f"The user needs these procedures: {', '.join(procedures)}")

        lines.append("")
        lines.append(
            "Provide a clear comparison and recommend the best plan for this user's "
            "situation. Focus on total estimated costs and value. Do NOT give any medical advice."
        )

        return "\n".join(lines)
```

Note: the local-variable unpacking at the top of `_build_prompt` keeps the rest of the body byte-for-byte identical to the original — lower risk than rewriting every reference.

- [ ] **Step 2: Run comparison agent tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_comparison_agent.py healthflow/tests/api/test_comparison.py -v 2>&1 | tail -15
make test-quick 2>&1 | tail -3
```

Expected: all pass; full suite 498. The public `recommend()` signature is unchanged, so route-level tests are unaffected.

- [ ] **Step 3: Commit**

```bash
git add healthflow/agents/comparison_agent.py
git commit -m "comparison_agent: _build_prompt takes ComparisonPromptInput"
```

---

## Task 7: Migrate `cost_calculator_agent.py`

**Files:**
- Modify: `healthflow/agents/cost_calculator_agent.py`

No redaction work — typed wrapper. `_build_prompt` currently takes `(results, usage)`.

- [ ] **Step 1: Modify `cost_calculator_agent.py`**

Edit `healthflow/agents/cost_calculator_agent.py`. Add the import near the top:

```python
from healthflow.agents.prompt_inputs import CostPromptInput
```

In `calculate`, replace the `user_prompt = self._build_prompt(results, usage)` line with:

```python
        prompt_input = CostPromptInput(results=results, usage=usage)
        user_prompt = self._build_prompt(prompt_input)
```

Change `_build_prompt`'s signature and add unpacking at the top of the body:

```python
    def _build_prompt(self, prompt_input: CostPromptInput) -> str:
        results = prompt_input.results
        usage = prompt_input.usage

        lines = [
            "Compare these Medicare Advantage plans by estimated annual out-of-pocket cost.",
            "",
            f"User's expected usage: {usage.doctor_visits_per_year} doctor visits/year",
        ]
```

Everything after that first `lines = [...]` block stays byte-for-byte identical to the current `_build_prompt` body (the `results` and `usage` local variables now come from the unpacking instead of the parameters).

- [ ] **Step 2: Run cost agent tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_cost_calculator_agent.py healthflow/tests/api/test_calculate_route.py healthflow/tests/api/test_calculate_integration.py -v 2>&1 | tail -15
make test-quick 2>&1 | tail -3
```

Expected: all pass; full suite 498.

- [ ] **Step 3: Commit**

```bash
git add healthflow/agents/cost_calculator_agent.py
git commit -m "cost_calculator_agent: _build_prompt takes CostPromptInput"
```

---

## Task 8: Migrate `network_agent.py`

**Files:**
- Modify: `healthflow/agents/network_agent.py`

No redaction work — typed wrapper. `_build_prompt` currently takes `(plan_results)`, called from `_get_recommendation`.

- [ ] **Step 1: Modify `network_agent.py`**

Edit `healthflow/agents/network_agent.py`. Add the import near the top:

```python
from healthflow.agents.prompt_inputs import NetworkPromptInput
```

In `_get_recommendation`, replace the `user_prompt = self._build_prompt(plan_results)` line with:

```python
        prompt_input = NetworkPromptInput(plan_results=plan_results)
        user_prompt = self._build_prompt(prompt_input)
```

Change `_build_prompt`'s signature and add unpacking at the top of the body:

```python
    def _build_prompt(self, prompt_input: NetworkPromptInput) -> str:
        plan_results = prompt_input.plan_results

        lines = ["Network verification results:\n"]
        for pr in plan_results:
```

Everything after `lines = ["Network verification results:\n"]` stays byte-for-byte identical to the current body.

- [ ] **Step 2: Run network agent tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_network_agent.py healthflow/tests/api/test_verify_route.py healthflow/tests/api/test_verify_integration.py -v 2>&1 | tail -15
make test-quick 2>&1 | tail -3
```

Expected: all pass; full suite 498.

- [ ] **Step 3: Commit**

```bash
git add healthflow/agents/network_agent.py
git commit -m "network_agent: _build_prompt takes NetworkPromptInput"
```

---

## Task 9: Agent-level redaction-applied tests

**Files:**
- Modify: `healthflow/tests/agents/test_translation_agent.py`
- Modify: `healthflow/tests/agents/test_appeal_agent.py`

Task 3 proved the `PromptInput` constructors redact. This task proves the redaction survives end-to-end through the agent's public entry point — i.e. the prompt that reaches `client.messages.create` is redacted.

- [ ] **Step 1: Add the translation agent redaction-applied test**

Append to `healthflow/tests/agents/test_translation_agent.py` (match the file's existing import style and mocking pattern — it likely already uses `unittest.mock`):

```python
from unittest.mock import MagicMock, patch

from healthflow.agents.translation_agent import TranslationAgent
from healthflow.models.schemas import DocumentSection


def test_translate_sends_redacted_prompt_to_claude():
    """The user_prompt reaching client.messages.create must be redacted."""
    agent = TranslationAgent()
    sections = [
        DocumentSection(title="Eligibility", content="Patient: Robert Frost is eligible."),
    ]

    with patch.object(agent.client.messages, "create") as mock_create:
        mock_create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Answer.")]
        )
        agent.translate(sections=sections, question="Dear Robert Frost, what is the copay?")

    sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert "Robert Frost" not in sent_prompt
    assert "[PATIENT_NAME]" in sent_prompt
```

If the file already imports `MagicMock`/`patch`/`DocumentSection`/`TranslationAgent`, don't duplicate the imports — just add the test function.

- [ ] **Step 2: Add the appeal agent redaction-applied test**

Append to `healthflow/tests/agents/test_appeal_agent.py`:

```python
from unittest.mock import MagicMock, patch

from healthflow.agents.appeal_agent import AppealAgent


def test_process_appeal_sends_redacted_text_to_claude():
    """The denial text reaching client.messages.create must be redacted."""
    agent = AppealAgent()

    with patch.object(agent.client.messages, "create") as mock_create:
        mock_create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Refined advice.")]
        )
        agent.process_appeal(
            denial_text="Patient: Emily Dickinson denied. DOB: 03/04/1950.",
            additional_context="",
        )

    sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert "Emily Dickinson" not in sent_prompt
    assert "[PATIENT_NAME]" in sent_prompt
    assert "03/04/1950" not in sent_prompt
    assert "[DOB]" in sent_prompt
```

If the file already imports these names, don't duplicate.

- [ ] **Step 3: Run the new tests**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_translation_agent.py::test_translate_sends_redacted_prompt_to_claude healthflow/tests/agents/test_appeal_agent.py::test_process_appeal_sends_redacted_text_to_claude -v
```

Expected: 2 passed. If a test fails because the mock path is wrong (e.g. the agent constructs its Anthropic client differently), inspect the agent's `__init__` and adjust the `patch.object` target. Both agents do `self.client = anthropic.Anthropic()` in `__init__`, so `patch.object(agent.client.messages, "create")` should work.

- [ ] **Step 4: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 500 passed (498 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/agents/test_translation_agent.py healthflow/tests/agents/test_appeal_agent.py
git commit -m "tests: prove redaction survives end-to-end through translate + appeal"
```

---

## Task 10: AST static check — no raw-text path to `_build_prompt`

**Files:**
- Create: `healthflow/tests/agents/test_no_raw_prompt_path.py`

This test walks each agent module's source with the `ast` module and asserts every call to a `_build_prompt` method passes a single variable argument (the constructed `PromptInput`), never a raw string/list/dict literal or multiple positional args. It locks in the structural guarantee against future regressions.

- [ ] **Step 1: Write the test**

Create `healthflow/tests/agents/test_no_raw_prompt_path.py`:

```python
"""Static guarantee: no agent calls _build_prompt with raw arguments.

Every _build_prompt call site must receive exactly one argument, and that
argument must be a Name (a variable holding a PromptInput) — never a literal,
never multiple positional args. This locks in the typed-layer contract: the
only way to reach a prompt body is through a PromptInput constructor.

If this test ever proves noisy on a legitimate dynamic call pattern, it can
be removed — the type annotation on each _build_prompt is the primary
enforcement; this is belt-and-suspenders.
"""
import ast
from pathlib import Path

import pytest

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agents"
_AGENT_FILES = [
    "comparison_agent.py",
    "cost_calculator_agent.py",
    "network_agent.py",
    "translation_agent.py",
    "appeal_agent.py",
]


@pytest.mark.parametrize("filename", _AGENT_FILES)
def test_build_prompt_called_only_with_a_single_variable(filename):
    source = (_AGENT_DIR / filename).read_text()
    tree = ast.parse(source, filename=filename)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match calls of the form `self._build_prompt(...)` or `<obj>._build_prompt(...)`.
        if not (isinstance(func, ast.Attribute) and func.attr == "_build_prompt"):
            continue
        # Exactly one positional arg, no keyword args.
        if len(node.args) != 1 or node.keywords:
            offenders.append((node.lineno, "must take exactly one positional arg"))
            continue
        arg = node.args[0]
        # The single arg must be a Name (a variable), not a literal/list/dict/call-chain.
        if not isinstance(arg, ast.Name):
            offenders.append((node.lineno, f"arg is {type(arg).__name__}, expected Name"))

    assert not offenders, (
        f"{filename}: _build_prompt called with raw arguments: {offenders}. "
        f"Construct a PromptInput and pass that variable instead."
    )
```

Note on the path: `Path(__file__).resolve().parent.parent.parent` walks from `healthflow/tests/agents/test_no_raw_prompt_path.py` up to `healthflow/`, then `/ "agents"`. Verify the depth is right when you run it — if the file lands one level deeper or shallower, adjust the `.parent` count (this is the same class of bug the test-folder reorg hit).

- [ ] **Step 2: Run the test**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/test_no_raw_prompt_path.py -v
```

Expected: 5 passed (one per agent file). If a file fails, either the migration in Tasks 4-8 missed a call site, or the `_AGENT_DIR` path is wrong. Fix whichever it is.

- [ ] **Step 3: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 505 passed (500 + 5 new parametrized cases).

- [ ] **Step 4: Commit**

```bash
git add healthflow/tests/agents/test_no_raw_prompt_path.py
git commit -m "tests: ast static check — no raw-text path to _build_prompt"
```

---

## Task 11: Update the `healthflow-security` skill

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Read the current skill structure**

```bash
cat .claude/skills/healthflow-security/SKILL.md
```

The file has YAML frontmatter, then sections. The first section is "PHI on the wire to Anthropic" (the one with the three `**Rule:**` lines about not passing whole Client objects). Don't touch the frontmatter.

- [ ] **Step 2: Replace the "PHI on the wire to Anthropic" rules with the enforced version**

The existing section's three `**Rule:**` lines describe the *convention* ("pass only the fields the prompt needs", "don't log prompt payloads", "prompt-building function should take a typed minimal struct"). The typed-struct rule is now *enforced*, not aspirational. Edit `.claude/skills/healthflow-security/SKILL.md`: keep the section heading and intro paragraph, and replace the three `**Rule:**` bullets with:

```markdown
**Rule:** Never call an agent's `_build_prompt` directly with raw arguments.
Construct the agent's `PromptInput` dataclass (in `healthflow/agents/prompt_inputs.py`)
and pass that. `_build_prompt` is type-annotated to accept only the
`PromptInput` — there is no path from a raw string to a prompt body that
skips the redaction boundary. A static `ast` test
(`tests/agents/test_no_raw_prompt_path.py`) enforces this.

**Rule:** Free-text fields on a `PromptInput` (denial text, document content,
questions) are redacted by the dataclass constructor via `PHIRedactor`.
Structured fields — medication names, procedure names, doctor names + NPIs —
pass through by design. Under the no-BAA threat model, medication/procedure
names are de-identified content (not among HIPAA's 18 identifiers) and doctor
NPIs are public NPPES registry data, not patient PHI.

**Rule:** When adding a new agent, add a `PromptInput` dataclass for it in
`prompt_inputs.py`. If it has free-text fields, redact them in `__post_init__`
using the `_redact_field` helper (frozen dataclass — reassigning a field needs
`object.__setattr__`; appending to `_redaction_log` does not). Emit the
`phi_redacted` audit event with `prompt_input.redaction_summary`.

**Rule:** Don't log raw prompt payloads. The `phi_redacted` audit event logs
only counts and placeholder types (`prompt_input.redaction_summary`), never
the redacted-or-raw text itself.
```

- [ ] **Step 3: Verify the frontmatter is intact**

```bash
head -10 .claude/skills/healthflow-security/SKILL.md
```

The `---` frontmatter block must be unchanged.

- [ ] **Step 4: Run the full suite (no behavior change expected)**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 505 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "skill: healthflow-security — document enforced PromptInput redaction boundary"
```

---

## Task 12: Final verification + push + PR

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: `505 passed`.

- [ ] **Step 2: Run `make check` (lint + tests + frontend build)**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; lint shows only the pre-existing errors (not introduced by this PR). If this PR introduced any new lint error, fix it before pushing.

- [ ] **Step 3: Hand-verify no agent imports `PHIRedactor` directly anymore**

```bash
grep -rn "PHIRedactor\|phi_redactor" healthflow/agents/ 2>&1 | grep -v __pycache__
```

Expected: only `healthflow/agents/prompt_inputs.py` should reference `PHIRedactor` (via the `from healthflow.tools.phi_redactor import PHIRedactor` import). No agent module (`comparison_agent.py`, `appeal_agent.py`, etc.) should import it directly — they go through `prompt_inputs.py`.

- [ ] **Step 4: Hand-verify the redaction boundary end-to-end**

```bash
.venv/bin/python -c "
from healthflow.agents.prompt_inputs import TranslationPromptInput, RedactedSection
pi = TranslationPromptInput(
    sections=(RedactedSection('T', 'Patient: Walt Whitman here.'),),
    question='Dear Walt Whitman question?',
)
assert 'Walt Whitman' not in pi.sections[0].content
assert 'Walt Whitman' not in pi.question
assert pi.redaction_summary['count'] >= 2
print('redaction boundary: OK')
"
```

Expected: `redaction boundary: OK`.

- [ ] **Step 5: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 10 commits (Tasks 1 and 12 don't commit):
- `skill: healthflow-security — document enforced PromptInput redaction boundary`
- `tests: ast static check — no raw-text path to _build_prompt`
- `tests: prove redaction survives end-to-end through translate + appeal`
- `network_agent: _build_prompt takes NetworkPromptInput`
- `cost_calculator_agent: _build_prompt takes CostPromptInput`
- `comparison_agent: _build_prompt takes ComparisonPromptInput`
- `appeal_agent: route redaction through AppealPromptInput boundary`
- `translation_agent: redact document content + question via TranslationPromptInput`
- `Add typed PromptInput layer for agent PHI redaction boundary`
- `phi_redactor: add [EMAIL] redaction pattern`

Each message terse, no `Co-Authored-By` trailer.

- [ ] **Step 6: Push the branch**

```bash
git push -u origin phi-redaction/agent-layer 2>&1 | tail -5
```

- [ ] **Step 7: Open the PR**

```bash
gh pr create --title "PHI redaction: typed PromptInput boundary across all 5 agents" --body "$(cat <<'EOF'
## Summary

Makes PHI redaction a structural property of the agent layer. Every agent's `_build_prompt` now accepts only a typed `PromptInput` dataclass whose constructor redacts free-text fields via `PHIRedactor`. There is no code path from a raw string to a prompt body that bypasses the redaction boundary.

- `healthflow/agents/prompt_inputs.py` (new) — five `frozen=True` dataclasses (`ComparisonPromptInput`, `CostPromptInput`, `NetworkPromptInput`, `TranslationPromptInput`, `AppealPromptInput`), a `RedactedSection` type, and `_redact_field` / `_summarize` helpers.
- `translation_agent.py` — **closes a live PHI leak**: `DocumentSection.content` and the question are now redacted before reaching Claude.
- `appeal_agent.py` — its existing inline `PHIRedactor` calls are replaced by `AppealPromptInput`, the single redaction boundary feeding both the denial parser and the Claude refine call.
- `comparison_agent.py`, `cost_calculator_agent.py`, `network_agent.py` — typed `PromptInput` wrappers; no free-text fields to redact, but the contract is now uniform and enforced.
- `phi_redactor.py` — added an `[EMAIL]` pattern.
- `.claude/skills/healthflow-security/SKILL.md` — the "pass a typed struct" rule is now documented as *enforced*, not aspirational.

**Threat model (no BAA assumed):** strip patient identifiers (name, DOB, SSN, address, phone, member ID, email); allow de-identified medical content — medication and procedure names, doctor names + NPIs.

Spec: [docs/superpowers/specs/2026-05-14-phi-redaction-design.md](./docs/superpowers/specs/2026-05-14-phi-redaction-design.md)
Plan: [docs/superpowers/plans/2026-05-14-phi-redaction.md](./docs/superpowers/plans/2026-05-14-phi-redaction.md)

## Test Plan

- [x] 16 new test cases: prompt-input unit tests (7), email-pattern (2), end-to-end redaction-applied (2), ast static check (5 parametrized over the agent files)
- [x] Full backend suite: 505/505 (was 489; +16)
- [x] No agent module imports `PHIRedactor` directly — all redaction goes through `prompt_inputs.py`
- [x] `ast` static check enforces no raw-text path to any `_build_prompt`
- [ ] CI green on this PR

## Out of scope / follow-ups

- PHI access audit log (sub-project #3) — logging *who read which patient's data when*. Next up.
- Auth hardening (sub-project #4), encryption at rest (sub-project #5).
- Making `PHIRedactor`'s regex coverage exhaustive — only the email gap was closed here. The typed layer means any future pattern added to `PHIRedactor` is automatically applied everywhere.
EOF
)" 2>&1 | tail -3
```

Expected: a GitHub PR URL. Capture and report it.

No new commit for this task.
