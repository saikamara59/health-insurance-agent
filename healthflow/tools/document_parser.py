import re

from healthflow.models.schemas import DocumentSection

KNOWN_HEADERS = [
    "INPATIENT HOSPITAL CARE",
    "OUTPATIENT SERVICES",
    "PRESCRIPTION DRUG COVERAGE",
    "PRESCRIPTION DRUGS",
    "MENTAL HEALTH SERVICES",
    "MENTAL HEALTH",
    "PREVENTIVE CARE",
    "EMERGENCY CARE",
    "URGENT CARE",
    "DENTAL SERVICES",
    "VISION SERVICES",
    "HEARING SERVICES",
    "SKILLED NURSING FACILITY",
    "REHABILITATION SERVICES",
    "DIAGNOSTIC SERVICES",
    "DURABLE MEDICAL EQUIPMENT",
    "AMBULANCE SERVICES",
    "PRIOR AUTHORIZATION",
    "OUT-OF-NETWORK COVERAGE",
    "ANNUAL DEDUCTIBLE",
    "MAXIMUM OUT-OF-POCKET",
    "SUMMARY OF BENEFITS",
]

_HEADER_PATTERN = re.compile(r"^([A-Z][A-Z \-/]{2,})$", re.MULTILINE)


class DocumentParser:
    def parse(self, text: str) -> list[DocumentSection]:
        if not text.strip():
            return [DocumentSection(title="Full Document", content="")]

        headers: list[tuple[int, str]] = []
        for match in _HEADER_PATTERN.finditer(text):
            header_text = match.group(1).strip()
            if len(header_text) >= 3:
                headers.append((match.start(), header_text))

        valid_headers: list[tuple[int, str]] = []
        for pos, header in headers:
            header_upper = header.upper()
            is_known = any(known in header_upper for known in KNOWN_HEADERS)
            is_title_like = len(header.split()) >= 2 and len(header) <= 60
            if is_known or is_title_like:
                valid_headers.append((pos, header))

        if not valid_headers:
            return [DocumentSection(title="Full Document", content=text.strip())]

        sections: list[DocumentSection] = []
        for i, (pos, header) in enumerate(valid_headers):
            content_start = text.index("\n", pos) + 1 if "\n" in text[pos:] else len(text)
            content_end = valid_headers[i + 1][0] if i + 1 < len(valid_headers) else len(text)
            content = text[content_start:content_end].strip()

            if header.upper() == "SUMMARY OF BENEFITS":
                continue

            if content:
                sections.append(DocumentSection(title=header, content=content))

        if not sections:
            return [DocumentSection(title="Full Document", content=text.strip())]

        return sections

    # Maps common abbreviations/shorthand to expanded terms for matching
    _KEYWORD_EXPANSIONS: dict[str, list[str]] = {
        "er": ["emergency"],
        "rx": ["prescription", "drug"],
        "oop": ["out-of-pocket"],
        "snf": ["skilled nursing"],
        "dme": ["durable medical equipment"],
    }

    def find_relevant_sections(
        self,
        sections: list[DocumentSection],
        question: str,
        max_sections: int = 3,
    ) -> list[DocumentSection]:
        # Strip punctuation from each word before splitting into keywords
        cleaned = re.sub(r"[^\w\s]", "", question.lower())
        question_words = set(cleaned.split())
        stop_words = {
            "what", "is", "the", "a", "an", "does", "do", "how", "much",
            "my", "this", "that", "for", "of", "in", "and", "or", "to",
            "it", "i", "me", "are", "will", "be", "can", "have", "has",
        }
        keywords = question_words - stop_words

        # Expand abbreviations into additional search terms
        expanded: set[str] = set(keywords)
        for kw in keywords:
            if kw in self._KEYWORD_EXPANSIONS:
                expanded.update(self._KEYWORD_EXPANSIONS[kw])
        keywords = expanded

        scored: list[tuple[float, int, DocumentSection]] = []
        for idx, section in enumerate(sections):
            searchable = (section.title + " " + section.content).lower()
            score = sum(1 for kw in keywords if kw in searchable)
            scored.append((score, idx, section))

        scored.sort(key=lambda x: (-x[0], x[1]))

        top = scored[:max_sections]
        if all(s[0] == 0 for s in top):
            return [s for s in sections[:max_sections]]

        return [section for _, _, section in top]
