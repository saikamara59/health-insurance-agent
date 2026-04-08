import re

from healthflow.models.schemas import DenialAnalysis


class DenialParser:
    """Extracts denial details from redacted text using regex and keyword matching."""

    # Denial code patterns
    CODE_PATTERN = re.compile(r"\b(CO-\d+|PR-\d+|OA-\d+|N-\d+)\b", re.IGNORECASE)

    # Treatment denied patterns
    TREATMENT_PATTERNS = [
        re.compile(r"denied[:\s]+([^.;\n]{3,80})", re.IGNORECASE),
        re.compile(r"([^.;\n]{3,80}?)\s+(?:is|are)\s+not\s+covered", re.IGNORECASE),
        re.compile(r"not covered[:\s]+([^.;\n]{3,80})", re.IGNORECASE),
        re.compile(r"not approved[:\s]+([^.;\n]{3,80})", re.IGNORECASE),
        re.compile(r"(?:service|procedure|treatment)\s+(?:has been\s+)?denied[:\s]*([^.;\n]{3,80})", re.IGNORECASE),
        re.compile(r"(?:following|these)\s+(?:service|procedure|treatment)s?\s+(?:has|have)\s+been\s+denied[:\s]*([^.;\n]{3,80})", re.IGNORECASE),
    ]

    # Policy section patterns
    POLICY_PATTERNS = [
        re.compile(r"(LCD\s*L\d+)", re.IGNORECASE),
        re.compile(r"(NCD\s*\d[\d.]*)", re.IGNORECASE),
        re.compile(r"((?:42\s+)?CFR\s*§?\s*\d[\d.]*(?:-[\d.]+)?)", re.IGNORECASE),
        re.compile(r"(Section\s+\d[\d.]*(?:\([a-z]\))*)", re.IGNORECASE),
    ]

    # Appeal deadline patterns
    DEADLINE_PATTERNS = [
        re.compile(r"(\d+)\s*(?:calendar\s+)?days.*?(?:appeal|deadline|file|submit)", re.IGNORECASE),
        re.compile(r"(?:appeal|deadline|file|submit).*?(\d+)\s*(?:calendar\s+)?days", re.IGNORECASE),
        re.compile(r"within\s+(\d+)\s*(?:calendar\s+)?days", re.IGNORECASE),
    ]

    # Denial date patterns
    DATE_NEAR_DENIAL = re.compile(
        r"(?:date\s+of\s+denial|denial\s+date|date\s+of\s+determination|denied\s+on)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        re.IGNORECASE,
    )
    GENERAL_DATE_NEAR_DENIAL = re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?:.{0,40})(?:denial|denied|determination)",
        re.IGNORECASE,
    )

    def parse(self, redacted_text: str) -> DenialAnalysis:
        """Parse denial details from redacted text. Returns best-effort extraction."""
        denial_reason_code = self._extract_code(redacted_text)
        denial_reason = self._extract_reason(redacted_text, denial_reason_code)
        treatment_denied = self._extract_treatment(redacted_text)
        policy_section_cited = self._extract_policy(redacted_text)
        appeal_deadline = self._extract_deadline(redacted_text)
        denial_date = self._extract_date(redacted_text)

        return DenialAnalysis(
            denial_reason_code=denial_reason_code,
            denial_reason=denial_reason,
            treatment_denied=treatment_denied,
            policy_section_cited=policy_section_cited,
            appeal_deadline=appeal_deadline,
            denial_date=denial_date,
        )

    def _extract_code(self, text: str) -> str | None:
        match = self.CODE_PATTERN.search(text)
        return match.group(1).upper() if match else None

    def _extract_reason(self, text: str, code: str | None) -> str:
        if code:
            # Try to find text near the code
            pattern = re.compile(
                rf"{re.escape(code)}[:\s.-]+([^.;\n]{{5,120}})", re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        # Fallback: look for "reason:" or "because"
        reason_match = re.search(r"(?:reason|because)[:\s]+([^.;\n]{5,120})", text, re.IGNORECASE)
        if reason_match:
            return reason_match.group(1).strip()
        return "Denial reason not specified in letter"

    def _extract_treatment(self, text: str) -> str:
        for pattern in self.TREATMENT_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip().rstrip(",;:")
        return "Treatment details not specified in letter"

    def _extract_policy(self, text: str) -> str | None:
        for pattern in self.POLICY_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_deadline(self, text: str) -> str | None:
        for pattern in self.DEADLINE_PATTERNS:
            match = pattern.search(text)
            if match:
                days = match.group(1)
                return f"{days} days"
        return None

    def _extract_date(self, text: str) -> str | None:
        match = self.DATE_NEAR_DENIAL.search(text)
        if match:
            return match.group(1)
        match = self.GENERAL_DATE_NEAR_DENIAL.search(text)
        if match:
            return match.group(1)
        return None
