import re

from healthflow.logs.audit import AuditLogger

# Tiered models, picked per agent based on task complexity to control token cost.
# - OPUS: high-stakes reasoning over regulations / multi-step orchestration (appeals).
# - SONNET: nuanced extraction from unstructured policy text (translation).
# - HAIKU: summarization of already-computed structured data (comparison, cost, network).
CLAUDE_MODEL_OPUS = "claude-opus-4-7"
CLAUDE_MODEL_SONNET = "claude-sonnet-4-6"
CLAUDE_MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Backwards-compatible default; new code should import the tier it needs.
CLAUDE_MODEL = CLAUDE_MODEL_SONNET


def extract_text(response) -> str:
    """Pull the first text block out of an Anthropic Messages response.

    Skips non-text content blocks (e.g. tool_use) and tolerates empty content.
    """
    for block in getattr(response, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            return text
    return ""


class ValidationError(Exception):
    pass


MEDICAL_ADVICE_PATTERNS = [
    re.compile(r"you should take", re.IGNORECASE),
    re.compile(r"stop taking", re.IGNORECASE),
    re.compile(r"switch to", re.IGNORECASE),
    re.compile(r"increase dosage", re.IGNORECASE),
    re.compile(r"you might have", re.IGNORECASE),
    re.compile(r"symptoms suggest", re.IGNORECASE),
    re.compile(r"this could indicate", re.IGNORECASE),
    re.compile(r"I recommend treatment", re.IGNORECASE),
    re.compile(r"you need surgery", re.IGNORECASE),
    re.compile(r"seek emergency", re.IGNORECASE),
]

DISCLAIMER = (
    "\n\nDisclaimer: This is a plan comparison tool, not medical advice. "
    "Consult a licensed healthcare professional for medical decisions."
)


class Harness:
    def __init__(self) -> None:
        self.audit = AuditLogger()

    def validate_input(
        self,
        zip_code: str,
        age: int,
        income_level: str,
        medications: list[str] | None = None,
        procedures: list[str] | None = None,
    ) -> dict:
        medications = medications or []
        procedures = procedures or []

        if len(zip_code) != 5 or not zip_code.isdigit():
            raise ValidationError("Zip code must be exactly 5 digits")

        if not 18 <= age <= 120:
            raise ValidationError("Age must be between 18 and 120")

        if income_level not in {"low", "medium", "high"}:
            raise ValidationError(
                "Invalid income level. Must be one of: low, medium, high"
            )

        if len(medications) > 10:
            raise ValidationError("Maximum 10 medications allowed")

        if len(procedures) > 10:
            raise ValidationError("Maximum 10 procedures allowed")

        for med in medications:
            if not med.strip():
                raise ValidationError("Medication names cannot be empty")

        for proc in procedures:
            if not proc.strip():
                raise ValidationError("Procedure names cannot be empty")

        validated = {
            "zip_code": zip_code,
            "age": age,
            "income_level": income_level,
            "medications": medications,
            "procedures": procedures,
        }

        self.audit.log("input_validated", validated)
        return validated

    def filter_output(self, text: str) -> str:
        filtered = text
        for pattern in MEDICAL_ADVICE_PATTERNS:
            match = pattern.search(filtered)
            if match:
                self.audit.log(
                    "output_filtered",
                    {"pattern": pattern.pattern, "matched": match.group()},
                )
                filtered = pattern.sub("[REDACTED - not medical advice]", filtered)

        filtered += DISCLAIMER
        return filtered
