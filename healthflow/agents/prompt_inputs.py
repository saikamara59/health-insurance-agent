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
