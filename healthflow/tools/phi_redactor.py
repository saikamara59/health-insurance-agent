import re


class PHIRedactor:
    """Regex-based PHI redaction. Runs BEFORE any text reaches Claude or is logged."""

    PATTERNS = [
        # SSN must come before phone to avoid partial matches
        {
            "placeholder": "[SSN]",
            "pattern": "ssn",
            "regex": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        },
        # Names after Patient:, Member:, Name:, Dear
        {
            "placeholder": "[PATIENT_NAME]",
            "pattern": "name_label",
            "regex": re.compile(
                r"(?:Patient|Member|Name)\s*:[^\S\n]*([A-Z][a-z]+(?:[^\S\n]+[A-Z][a-z]+)+)",
            ),
        },
        {
            "placeholder": "[PATIENT_NAME]",
            "pattern": "dear_name",
            "regex": re.compile(
                r"Dear[^\S\n]+([A-Z][a-z]+(?:[^\S\n]+[A-Z][a-z]+)+)",
            ),
        },
        # DOB patterns
        {
            "placeholder": "[DOB]",
            "pattern": "dob",
            "regex": re.compile(
                r"(?:DOB|Date of Birth|Birth Date)\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                re.IGNORECASE,
            ),
        },
        # Member/Policy/Subscriber ID
        {
            "placeholder": "[MEMBER_ID]",
            "pattern": "member_id",
            "regex": re.compile(
                r"(?:Member ID|Policy #|ID|Subscriber ID)\s*:\s*([A-Za-z0-9][\w-]+)",
                re.IGNORECASE,
            ),
        },
        # Phone numbers
        {
            "placeholder": "[PHONE]",
            "pattern": "phone",
            "regex": re.compile(r"\(?\d{3}\)?[\s-]\d{3}-\d{4}"),
        },
        # Email addresses. Heuristic — matches the common shape; may over-match
        # strings like package coordinates or @mentions with a TLD-shaped
        # suffix. Acceptable for insurance documents; low false-positive risk.
        {
            "placeholder": "[EMAIL]",
            "pattern": "email",
            "regex": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
            ),
        },
    ]

    def redact(self, text: str) -> tuple[str, list[dict]]:
        """Redact PHI from text.

        Returns:
            (redacted_text, redaction_log) where redaction_log entries have
            placeholder, pattern, and position keys.
        """
        redacted = text
        log: list[dict] = []

        for pat_info in self.PATTERNS:
            placeholder = pat_info["placeholder"]
            pattern_name = pat_info["pattern"]
            regex = pat_info["regex"]

            # For labeled patterns (name_label, dear_name, dob, member_id),
            # we replace only the captured group, keeping the label intact.
            if pattern_name in ("name_label", "dear_name", "dob", "member_id"):
                offset = 0
                for match in list(regex.finditer(redacted)):
                    if match.lastindex and match.lastindex >= 1:
                        group_start = match.start(1) + offset
                        group_end = match.end(1) + offset
                        original = match.group(1)
                        redacted = (
                            redacted[:group_start]
                            + placeholder
                            + redacted[group_end:]
                        )
                        log.append({
                            "placeholder": placeholder,
                            "pattern": pattern_name,
                            "position": match.start(1),
                        })
                        offset += len(placeholder) - len(original)
            else:
                for match in reversed(list(regex.finditer(redacted))):
                    log.append({
                        "placeholder": placeholder,
                        "pattern": pattern_name,
                        "position": match.start(),
                    })
                    redacted = (
                        redacted[: match.start()]
                        + placeholder
                        + redacted[match.end() :]
                    )

        # Sort log by position for consistent output
        log.sort(key=lambda x: x["position"])
        return redacted, log
