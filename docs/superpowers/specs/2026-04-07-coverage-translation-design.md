# HealthFlow Phase 2: Coverage Translation — Design Spec

## Overview

Add a targeted Q&A feature where users paste their plan's Summary of Benefits (SoB) document and ask a specific question. The agent answers that question in plain English by finding the relevant sections and translating the insurance language. No PHI — just document analysis.

## New Endpoint

| Method | Path | Description |
|--------|------|-------------|
| POST | /translate | Answer a question about a pasted Summary of Benefits document |

## Request/Response

**Request:**

```python
class TranslateRequest(BaseModel):
    document_text: str   # Pasted SoB content, max 50,000 chars
    question: str        # Specific question, max 500 chars
```

**Response:**

```python
class DocumentSection(BaseModel):
    title: str
    content: str

class TranslateResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    relevant_sections: list[str]   # Section titles that were used
    disclaimer: str
```

## New/Modified Files

### New: `healthflow/tools/document_parser.py`

Takes raw SoB text, cleans it (normalize whitespace), and splits into labeled sections.

**Section detection:**
- Scans for common SoB section headers using regex patterns matching lines that are all-caps, bold-style, or match known header patterns
- Known headers: "Inpatient Hospital Care", "Outpatient Services", "Prescription Drugs", "Prescription Drug Coverage", "Mental Health Services", "Preventive Care", "Emergency Care", "Urgent Care", "Dental Services", "Vision Services", "Hearing Services", "Skilled Nursing Facility", "Rehabilitation Services", "Diagnostic Services", "Durable Medical Equipment", "Ambulance Services", "Prior Authorization", "Out-of-Network Coverage", "Annual Deductible", "Maximum Out-of-Pocket"
- Falls back to splitting on blank-line-separated blocks if no headers detected

**Interface:**
- `DocumentParser.parse(text: str) -> list[DocumentSection]`
- Returns list of `DocumentSection(title=str, content=str)`
- If no sections detected, returns single section with title "Full Document"

**Relevant section matching:**
- `DocumentParser.find_relevant_sections(sections: list[DocumentSection], question: str, max_sections: int = 3) -> list[DocumentSection]`
- Keyword-matches question against section titles and content
- Scores each section by keyword overlap count
- Returns top `max_sections` sections sorted by relevance score
- If no matches found, returns first 3 sections as fallback

### New: `healthflow/agents/translation_agent.py`

Takes parsed sections + user question, builds a prompt for Claude.

**System prompt:** "You are an insurance document translator. Your job is to read health insurance plan documents and answer questions about coverage in plain, clear English. Translate insurance jargon into simple language. Answer only the specific question asked. If the document doesn't contain enough information to answer, say so. Never give medical advice, recommend treatments, or diagnose conditions."

**Prompt construction:**
- Includes only the relevant sections (from document parser's `find_relevant_sections`)
- Formats sections with headers
- Appends the user's question
- Asks for a clear, direct answer

**Interface:**
- `TranslationAgent.translate(sections: list[DocumentSection], question: str) -> tuple[str, list[str]]`
- Returns `(answer_text, list_of_section_titles_used)`
- Uses claude-sonnet-4-6, max_tokens=1024
- Logs via AuditLogger

### Modified: `healthflow/models/schemas.py`

Add three new models:
- `TranslateRequest` with validators (document_text non-empty and max 50,000 chars, question non-empty and max 500 chars)
- `TranslateResponse`
- `DocumentSection`

### Modified: `healthflow/api/routes.py`

Add `POST /translate` endpoint:
- Accepts `TranslateRequest`
- Parses document via `DocumentParser`
- Finds relevant sections
- Calls `TranslationAgent.translate()`
- Filters output through harness
- Saves session
- Returns `TranslateResponse`

### Modified: `healthflow/agents/harness.py`

Reuse existing output filter (medical advice patterns + disclaimer). No changes needed — the existing `filter_output` method works for translation responses too.

Input validation for the new request is handled by Pydantic validators on `TranslateRequest`.

## Testing

### `healthflow/tests/test_document_parser.py`

1. Parse document with clear section headers — correct sections returned
2. Parse document with no headers — returns single "Full Document" section
3. Find relevant sections matches question keywords to section titles
4. Find relevant sections returns max_sections limit
5. Find relevant sections falls back when no keyword matches
6. Empty document handling

### `healthflow/tests/test_translation_agent.py`

1. Agent returns answer text (mocked Claude)
2. Agent sends system prompt constraining to document translation
3. Agent includes relevant sections in prompt
4. Agent includes user question in prompt

### `healthflow/tests/test_routes.py` (additions)

1. POST /translate with valid request returns 200
2. POST /translate with empty document returns 422
3. POST /translate with empty question returns 422
4. POST /translate response has disclaimer

### `healthflow/tests/test_comparison.py` (additions)

1. End-to-end translate pipeline with mocked Claude
2. Output filtering applied to translate response

## What This Does NOT Do

- No file upload or PDF parsing (text paste only)
- No document storage or caching
- No multi-turn conversation about the document
- No PHI extraction or storage
- No medical advice
