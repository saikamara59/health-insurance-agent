# Coverage Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/translate` endpoint that answers specific questions about pasted Summary of Benefits documents in plain English.

**Architecture:** New document parser splits SoB text into sections, a translation agent sends relevant sections + user question to Claude, existing harness filters the output. Follows the same pattern as the comparison agent.

**Tech Stack:** Python, FastAPI, Anthropic SDK, Pydantic, pytest

---

### Task 1: Add Pydantic Models for Translation

**Files:**
- Modify: `healthflow/models/schemas.py`
- Create: `healthflow/tests/test_translate_schemas.py`

- [ ] **Step 1: Write tests for the new models**

Create `healthflow/tests/test_translate_schemas.py`:

```python
import pytest
from healthflow.models.schemas import (
    DocumentSection,
    TranslateRequest,
    TranslateResponse,
)


def test_translate_request_valid():
    req = TranslateRequest(
        document_text="SUMMARY OF BENEFITS\nInpatient: $250 copay",
        question="What is the inpatient copay?",
    )
    assert req.document_text.startswith("SUMMARY")
    assert req.question == "What is the inpatient copay?"


def test_translate_request_empty_document():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="", question="What is covered?")


def test_translate_request_empty_question():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="Some document text", question="")


def test_translate_request_whitespace_only_document():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="   ", question="What is covered?")


def test_translate_request_whitespace_only_question():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="Some doc", question="   ")


def test_translate_request_document_too_long():
    with pytest.raises(ValueError, match="50,000"):
        TranslateRequest(document_text="x" * 50001, question="What is covered?")


def test_translate_request_question_too_long():
    with pytest.raises(ValueError, match="500"):
        TranslateRequest(document_text="Some doc", question="x" * 501)


def test_document_section_model():
    section = DocumentSection(title="Inpatient Care", content="$250 copay per day")
    assert section.title == "Inpatient Care"
    assert section.content == "$250 copay per day"


def test_translate_response_model():
    resp = TranslateResponse(
        session_id="abc-123",
        question="What is the copay?",
        answer="The copay is $250 per day.",
        relevant_sections=["Inpatient Care"],
        disclaimer="Not medical advice.",
    )
    assert resp.answer == "The copay is $250 per day."
    assert len(resp.relevant_sections) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translate_schemas.py -v
```

Expected: FAIL — `ImportError: cannot import name 'DocumentSection'`

- [ ] **Step 3: Add models to schemas.py**

Append the following to the end of `healthflow/models/schemas.py` (after the `EstimateResponse` class):

```python


class DocumentSection(BaseModel):
    title: str
    content: str


class TranslateRequest(BaseModel):
    document_text: str = Field(..., description="Pasted Summary of Benefits text")
    question: str = Field(..., description="Specific question about the document")

    @field_validator("document_text")
    @classmethod
    def validate_document_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Document text cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Document text must be at most 50,000 characters")
        return v

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be empty")
        if len(v) > 500:
            raise ValueError("Question must be at most 500 characters")
        return v


class TranslateResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    relevant_sections: list[str]
    disclaimer: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translate_schemas.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All existing + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add healthflow/models/schemas.py healthflow/tests/test_translate_schemas.py
git commit -m "feat: add Pydantic models for coverage translation endpoint"
```

---

### Task 2: Document Parser

**Files:**
- Create: `healthflow/tools/document_parser.py`
- Create: `healthflow/tests/test_document_parser.py`

- [ ] **Step 1: Write tests for document parser**

Create `healthflow/tests/test_document_parser.py`:

```python
from healthflow.tools.document_parser import DocumentParser


SAMPLE_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
You pay $0 copay per day for days 6-90.
Prior authorization required.

OUTPATIENT SERVICES
Doctor office visits: $20 copay
Specialist visits: $40 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
Tier 3 (Non-Preferred): $90 copay
Tier 4 (Specialty): 25% coinsurance

EMERGENCY CARE
Emergency room: $90 copay (waived if admitted)
Ambulance: $250 copay

MENTAL HEALTH SERVICES
Outpatient: $40 copay per visit
Inpatient: $250 copay per day

PREVENTIVE CARE
Annual wellness visit: $0 copay
Flu shot: $0 copay
"""

SAMPLE_NO_HEADERS = """This plan covers hospital stays at $250 per day.
Doctor visits are $20 and specialists are $40.
Generic drugs cost $10 per prescription.
"""


def test_parse_document_with_headers():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    assert len(sections) >= 5
    titles = [s.title for s in sections]
    assert "INPATIENT HOSPITAL CARE" in titles
    assert "OUTPATIENT SERVICES" in titles
    assert "PRESCRIPTION DRUG COVERAGE" in titles


def test_parse_document_section_content():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    inpatient = next(s for s in sections if s.title == "INPATIENT HOSPITAL CARE")
    assert "$250 copay" in inpatient.content
    assert "Prior authorization" in inpatient.content


def test_parse_document_no_headers():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_NO_HEADERS)
    assert len(sections) == 1
    assert sections[0].title == "Full Document"
    assert "$250 per day" in sections[0].content


def test_parse_empty_document():
    parser = DocumentParser()
    sections = parser.parse("")
    assert len(sections) == 1
    assert sections[0].title == "Full Document"


def test_find_relevant_sections_by_keyword():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "What is the ER copay?")
    titles = [s.title for s in relevant]
    assert "EMERGENCY CARE" in titles


def test_find_relevant_sections_drug_question():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "How much do generic drugs cost?")
    titles = [s.title for s in relevant]
    assert "PRESCRIPTION DRUG COVERAGE" in titles


def test_find_relevant_sections_max_limit():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(sections, "copay", max_sections=2)
    assert len(relevant) <= 2


def test_find_relevant_sections_no_match_returns_first():
    parser = DocumentParser()
    sections = parser.parse(SAMPLE_SOB)
    relevant = parser.find_relevant_sections(
        sections, "xyzzy something completely unrelated"
    )
    assert len(relevant) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_document_parser.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement document parser**

Create `healthflow/tools/document_parser.py`:

```python
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

# Regex: line that is all-caps, at least 3 chars, optionally with hyphens/spaces
_HEADER_PATTERN = re.compile(r"^([A-Z][A-Z \-/]{2,})$", re.MULTILINE)


class DocumentParser:
    def parse(self, text: str) -> list[DocumentSection]:
        if not text.strip():
            return [DocumentSection(title="Full Document", content="")]

        # Find all header-like lines
        headers: list[tuple[int, str]] = []
        for match in _HEADER_PATTERN.finditer(text):
            header_text = match.group(1).strip()
            if len(header_text) >= 3:
                headers.append((match.start(), header_text))

        # Filter to only recognized headers or lines that look like section titles
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
            # Content starts after the header line
            content_start = text.index("\n", pos) + 1 if "\n" in text[pos:] else len(text)
            content_end = valid_headers[i + 1][0] if i + 1 < len(valid_headers) else len(text)
            content = text[content_start:content_end].strip()

            # Skip "SUMMARY OF BENEFITS" as a section — it's just the document title
            if header.upper() == "SUMMARY OF BENEFITS":
                continue

            if content:
                sections.append(DocumentSection(title=header, content=content))

        if not sections:
            return [DocumentSection(title="Full Document", content=text.strip())]

        return sections

    def find_relevant_sections(
        self,
        sections: list[DocumentSection],
        question: str,
        max_sections: int = 3,
    ) -> list[DocumentSection]:
        question_words = set(question.lower().split())
        # Remove common stop words
        stop_words = {
            "what", "is", "the", "a", "an", "does", "do", "how", "much",
            "my", "this", "that", "for", "of", "in", "and", "or", "to",
            "it", "i", "me", "are", "will", "be", "can", "have", "has",
        }
        keywords = question_words - stop_words

        scored: list[tuple[float, int, DocumentSection]] = []
        for idx, section in enumerate(sections):
            searchable = (section.title + " " + section.content).lower()
            score = sum(1 for kw in keywords if kw in searchable)
            scored.append((score, idx, section))

        scored.sort(key=lambda x: (-x[0], x[1]))

        # If no keywords matched, return first N sections as fallback
        top = scored[:max_sections]
        if all(s[0] == 0 for s in top):
            return [s for s in sections[:max_sections]]

        return [section for _, _, section in top]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_document_parser.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tools/document_parser.py healthflow/tests/test_document_parser.py
git commit -m "feat: add document parser with section splitting and relevance matching"
```

---

### Task 3: Translation Agent

**Files:**
- Create: `healthflow/agents/translation_agent.py`
- Create: `healthflow/tests/test_translation_agent.py`

- [ ] **Step 1: Write tests for translation agent**

Create `healthflow/tests/test_translation_agent.py`:

```python
from unittest.mock import MagicMock, patch
from healthflow.agents.translation_agent import TranslationAgent
from healthflow.models.schemas import DocumentSection


SAMPLE_SECTIONS = [
    DocumentSection(
        title="EMERGENCY CARE",
        content="Emergency room: $90 copay (waived if admitted)\nAmbulance: $250 copay",
    ),
    DocumentSection(
        title="INPATIENT HOSPITAL CARE",
        content="You pay $250 copay per day for days 1-5.\nPrior authorization required.",
    ),
]


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_returns_answer(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The ER copay is $90.")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    answer, section_titles = agent.translate(
        sections=SAMPLE_SECTIONS,
        question="What is the ER copay?",
    )

    assert "ER copay" in answer or "$90" in answer
    mock_client.messages.create.assert_called_once()


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_returns_section_titles(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The answer is...")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    _, section_titles = agent.translate(
        sections=SAMPLE_SECTIONS,
        question="What is the ER copay?",
    )

    assert "EMERGENCY CARE" in section_titles
    assert "INPATIENT HOSPITAL CARE" in section_titles


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_sends_system_prompt_no_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="test?")

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()
    assert "plain" in system.lower() or "clear" in system.lower()


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_includes_sections_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="What is the ER copay?")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "EMERGENCY CARE" in user_msg
    assert "$90 copay" in user_msg


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_includes_question_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="What is the ER copay?")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "What is the ER copay?" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translation_agent.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement translation agent**

Create `healthflow/agents/translation_agent.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translation_agent.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/agents/translation_agent.py healthflow/tests/test_translation_agent.py
git commit -m "feat: add translation agent for SoB document Q&A"
```

---

### Task 4: Add /translate API Route

**Files:**
- Modify: `healthflow/api/routes.py`
- Create: `healthflow/tests/test_translate_route.py`

- [ ] **Step 1: Write tests for the translate route**

Create `healthflow/tests/test_translate_route.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)

SAMPLE_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
Prior authorization required.

EMERGENCY CARE
Emergency room: $90 copay (waived if admitted)
Ambulance: $250 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
"""


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "The ER copay is $90. If you are admitted, the copay is waived.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": SAMPLE_SOB,
            "question": "What is the ER copay?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "session_id" in data
    assert "relevant_sections" in data
    assert "disclaimer" in data
    assert data["question"] == "What is the ER copay?"


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_filters_medical_advice(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Your ER copay is $90. Also, you should take aspirin before going.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": SAMPLE_SOB,
            "question": "What is the ER copay?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "you should take" not in data["answer"].lower()


def test_translate_empty_document():
    response = client.post(
        "/translate",
        json={"document_text": "", "question": "What is covered?"},
    )
    assert response.status_code == 422


def test_translate_empty_question():
    response = client.post(
        "/translate",
        json={"document_text": SAMPLE_SOB, "question": ""},
    )
    assert response.status_code == 422


def test_translate_document_too_long():
    response = client.post(
        "/translate",
        json={"document_text": "x" * 50001, "question": "What is covered?"},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = ("Answer text.", ["EMERGENCY CARE"])
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={"document_text": SAMPLE_SOB, "question": "ER copay?"},
    )
    data = response.json()
    assert "not medical advice" in data["disclaimer"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translate_route.py -v
```

Expected: FAIL — route not found (404)

- [ ] **Step 3: Add the /translate route to routes.py**

Add the following imports to the top of `healthflow/api/routes.py`, alongside the existing imports:

```python
from healthflow.agents.translation_agent import TranslationAgent
from healthflow.tools.document_parser import DocumentParser
```

Add `TranslateRequest` and `TranslateResponse` to the existing import from `healthflow.models.schemas`:

```python
from healthflow.models.schemas import (
    CompareRequest,
    CompareResponse,
    CostDetails,
    EstimateRequest,
    EstimateResponse,
    PlanSummary,
    TranslateRequest,
    TranslateResponse,
)
```

Add `document_parser` to the module-level instances (after the existing `session_store = InMemoryStore()` line):

```python
document_parser = DocumentParser()
```

Add the route at the end of the file (after the `estimate_cost` function):

```python


@router.post("/translate", response_model=TranslateResponse)
def translate_coverage(request: TranslateRequest):
    harness.audit.log("tool_called", {"tool": "document_parser", "doc_length": len(request.document_text)})

    sections = document_parser.parse(request.document_text)
    relevant = document_parser.find_relevant_sections(sections, request.question)

    agent = TranslationAgent()
    raw_answer, section_titles = agent.translate(
        sections=relevant,
        question=request.question,
    )

    answer = harness.filter_output(raw_answer)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "question": request.question,
        "section_titles": section_titles,
    })

    return TranslateResponse(
        session_id=session_id,
        question=request.question,
        answer=answer,
        relevant_sections=section_titles,
        disclaimer=DISCLAIMER,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translate_route.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add healthflow/api/routes.py healthflow/tests/test_translate_route.py
git commit -m "feat: add /translate endpoint for SoB document Q&A"
```

---

### Task 5: End-to-End Integration Test

**Files:**
- Create: `healthflow/tests/test_translate_integration.py`

- [ ] **Step 1: Write integration tests**

Create `healthflow/tests/test_translate_integration.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)

FULL_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
You pay $0 copay per day for days 6-90.
Prior authorization is required for non-emergency admissions.

OUTPATIENT SERVICES
Primary care doctor visit: $20 copay
Specialist visit: $40 copay
Diagnostic tests (lab work): $20 copay
X-rays: $30 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
Tier 3 (Non-Preferred Brand): $90 copay
Tier 4 (Specialty): 25% coinsurance up to $250 max

EMERGENCY CARE
Emergency room visit: $90 copay (waived if admitted within 24 hours)
Worldwide emergency coverage: same as in-network

MENTAL HEALTH SERVICES
Outpatient individual therapy: $40 copay per visit
Outpatient group therapy: $20 copay per visit
Inpatient mental health: $250 copay per day for days 1-5

PREVENTIVE CARE
Annual wellness visit: $0 copay
Flu shot: $0 copay
Colorectal cancer screening: $0 copay
Mammogram: $0 copay

DENTAL SERVICES
Preventive dental (cleaning, exam, X-rays): $0 copay
Comprehensive dental (fillings, extractions): 50% coinsurance
"""


@patch("healthflow.api.routes.TranslationAgent")
def test_full_translate_pipeline(mock_agent_cls):
    """End-to-end: document parsing → section matching → agent → output filter → response"""
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Your ER copay is $90. However, if you are admitted to the hospital "
        "within 24 hours of your ER visit, the $90 copay is waived. "
        "This plan also covers emergency visits worldwide at the same rate.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much does an ER visit cost?",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Response structure
    assert "session_id" in data
    assert data["question"] == "How much does an ER visit cost?"
    assert "$90" in data["answer"]
    assert len(data["relevant_sections"]) >= 1
    assert "not medical advice" in data["disclaimer"].lower()

    # Agent was called with relevant sections
    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "EMERGENCY CARE" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_drug_question(mock_agent_cls):
    """Verify drug-related questions match prescription sections."""
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Generic drugs cost $10 per prescription.",
        ["PRESCRIPTION DRUG COVERAGE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much do generic prescriptions cost?",
        },
    )

    assert response.status_code == 200
    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "PRESCRIPTION DRUG COVERAGE" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_mental_health_question(mock_agent_cls):
    """Verify mental health questions match the right section."""
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Therapy visits cost $40 per session.",
        ["MENTAL HEALTH SERVICES"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "Does this plan cover therapy?",
        },
    )

    assert response.status_code == 200
    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "MENTAL HEALTH SERVICES" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_output_filtered(mock_agent_cls):
    """Verify medical advice is filtered from translation output."""
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Therapy costs $40. I recommend treatment immediately for your symptoms.",
        ["MENTAL HEALTH SERVICES"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much is therapy?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "i recommend treatment" not in data["answer"].lower()
```

- [ ] **Step 2: Run integration tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_translate_integration.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Run the full test suite**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add healthflow/tests/test_translate_integration.py
git commit -m "test: add end-to-end integration tests for coverage translation"
```

---

### Task 6: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the /translate endpoint documentation to README.md**

After the `### POST /estimate` section in README.md, add:

```markdown
### POST /translate

Answer a question about a pasted Summary of Benefits document in plain English.

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "INPATIENT HOSPITAL CARE\nYou pay $250 copay per day for days 1-5.\n\nEMERGENCY CARE\nEmergency room: $90 copay (waived if admitted)",
    "question": "How much does an ER visit cost?"
  }'
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add /translate endpoint to README"
```
