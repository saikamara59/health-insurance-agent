import anthropic

from healthflow.logs.audit import AuditLogger
from healthflow.models.schemas import DocumentSection

SYSTEM_PROMPT = (
    "You are an insurance document translator. Your job is to read health insurance "
    "plan documents and answer questions about coverage in plain, clear English. "
    "Translate insurance jargon into simple language. Answer only the specific question "
    "asked. If the document doesn't contain enough information to answer, say so. "
    "Never give medical advice, recommend treatments, or diagnose conditions."
)


class TranslationAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.audit = AuditLogger()

    def translate(
        self,
        sections: list[DocumentSection],
        question: str,
    ) -> tuple[str, list[str]]:
        user_prompt = self._build_prompt(sections, question)
        section_titles = [s.title for s in sections]

        self.audit.log(
            "tool_called",
            {"tool": "claude_api", "model": "claude-sonnet-4-6", "task": "translate"},
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        answer = response.content[0].text
        self.audit.log("recommendation_generated", {"length": len(answer), "task": "translate"})
        return answer, section_titles

    def _build_prompt(
        self,
        sections: list[DocumentSection],
        question: str,
    ) -> str:
        lines = [
            "Below are relevant sections from a health insurance Summary of Benefits document.",
            "",
        ]

        for section in sections:
            lines.append(f"## {section.title}")
            lines.append(section.content)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"Question: {question}")
        lines.append("")
        lines.append(
            "Answer this question in plain English based on the document sections above. "
            "Be specific about dollar amounts, copays, and conditions. "
            "If the information is not in the document, say so clearly."
        )

        return "\n".join(lines)
