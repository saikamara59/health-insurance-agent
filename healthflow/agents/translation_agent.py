import anthropic

from healthflow.agents.harness import CLAUDE_MODEL, extract_text
from healthflow.agents.prompt_inputs import RedactedSection, TranslationPromptInput
from healthflow.logs.audit import AuditLogger
from healthflow.logs.invocation import invocation
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
        with invocation(agent="translation", event_type="translate", model=CLAUDE_MODEL) as inv:
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
            inv.details = {"length": len(answer), "section_count": len(section_titles)}
            return answer, section_titles

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
