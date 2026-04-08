# HealthFlow Phase 4: Claims Denial Appeal Agent — Design Spec

## Overview

Add a claims denial appeal feature where users paste a denial letter, the agent extracts denial details, looks up applicable CMS coverage rules from a curated database, and generates a formal appeal letter template. PHI is regex-redacted before any text reaches Claude. The appeal letter uses placeholders for personal info that the user fills in.

## New Endpoint

| Method | Path | Description |
|--------|------|-------------|
| POST | /appeal | Parse a denial letter and generate a formal appeal letter |

## Data Flow (PHI Safety)

```
User input → PHI Redactor (regex, no LLM) → Redacted text → Denial Parser (regex)
→ Denial Code DB lookup → Appeal Writer (template) → Claude (refine argument only,
  receives ONLY redacted text) → Harness output filter → Response
```

PHI never reaches Claude. The redactor runs first, and all downstream components work with redacted text only.

## Request/Response Models

**Request:**

```python
class AppealRequest(BaseModel):
    denial_text: str          # Pasted denial letter, max 50,000 chars
    additional_context: str   # Optional user context, max 1,000 chars
```

Validation: `denial_text` non-empty and max 50,000 chars. `additional_context` optional, max 1,000 chars.

**Response:**

```python
class DenialAnalysis(BaseModel):
    denial_reason_code: str | None     # e.g. "CO-4"
    denial_reason: str                 # Human-readable reason
    treatment_denied: str              # What was denied
    policy_section_cited: str | None   # Policy reference if found
    appeal_deadline: str | None        # Deadline info if found
    denial_date: str | None            # Date of denial if found

class CoverageArgument(BaseModel):
    cms_rule: str                      # Applicable CMS coverage rule
    common_appeal_grounds: list[str]   # Typical appeal arguments
    success_precedents: list[str]      # Known precedents

class AppealResponse(BaseModel):
    session_id: str
    denial_analysis: DenialAnalysis
    coverage_argument: CoverageArgument
    appeal_letter: str                 # Full appeal letter template with placeholders
    disclaimer: str
```

## New/Modified Files

### New: `healthflow/tools/phi_redactor.py`

Regex-based PHI redaction. Runs BEFORE any text reaches Claude or is logged.

**Patterns redacted:**
- Names after "Patient:", "Member:", "Name:", "Dear" → `[PATIENT_NAME]`
- DOB patterns (MM/DD/YYYY, MM-DD-YYYY, Month DD, YYYY) → `[DOB]`
- Member/Policy ID patterns (alphanumeric after "Member ID:", "Policy #:", "ID:", "Subscriber ID:") → `[MEMBER_ID]`
- SSN patterns (XXX-XX-XXXX) → `[SSN]`
- Phone patterns (XXX-XXX-XXXX, (XXX) XXX-XXXX) → `[PHONE]`
- Address patterns (lines with street number + street name + city/state/zip) → `[ADDRESS]`
- Dates (keep as-is but track — they're not PHI in denial context)

**Interface:**
- `PHIRedactor.redact(text: str) -> tuple[str, list[dict]]`
- Returns `(redacted_text, redaction_log)` where `redaction_log` is a list of `{"placeholder": str, "pattern": str, "position": int}` for audit

### New: `healthflow/tools/denial_codes.py`

Curated database of ~25 common CARC (Claim Adjustment Reason Code) and RARC codes.

Each entry:
```python
{
    "code": "CO-50",
    "description": "These are non-covered services because this is not deemed a medical necessity",
    "category": "Medical Necessity",
    "cms_rule": "Medicare covers services when medically necessary as defined in Section 1862(a)(1)(A) of the Social Security Act. Documentation must demonstrate the service is reasonable and necessary for diagnosis or treatment.",
    "appeal_grounds": [
        "Provide detailed clinical documentation supporting medical necessity",
        "Include physician letter explaining why the service is required",
        "Reference applicable Local Coverage Determination (LCD) or National Coverage Determination (NCD)",
        "Submit supporting lab results, imaging, or specialist notes"
    ],
    "precedents": [
        "CMS Manual Chapter 13 §13.5.1 — Redetermination rights",
        "42 CFR §405.940-405.958 — Medicare appeals process"
    ]
}
```

**Interface:**
- `DenialCodeDB.lookup(code: str) -> dict | None`
- `DenialCodeDB.search_by_keyword(keyword: str) -> dict | None` — fallback fuzzy search when exact code not found

Codes included (~25): CO-4, CO-11, CO-16, CO-18, CO-22, CO-27, CO-29, CO-45, CO-50, CO-96, CO-97, CO-109, CO-119, CO-167, CO-197, CO-242, CO-252, PR-1, PR-2, PR-3, PR-96, PR-204, OA-18, OA-23, N-30

### New: `healthflow/tools/denial_parser.py`

Extracts denial details from redacted text using regex + keyword matching.

**Extraction targets:**
- Denial reason code: regex for CO-\d+, PR-\d+, OA-\d+, CARC \d+, N-\d+ patterns
- Treatment denied: keywords after "denied", "not covered", "not approved" + following noun phrase
- Policy section cited: patterns like "LCD L\d+", "NCD \d+", "Section \d+", "CFR §\d+"
- Appeal deadline: patterns like "\d+ days", "within \d+ days", date patterns near "appeal", "deadline", "file"
- Denial date: date patterns near "denial", "denied", "determination"

**Interface:**
- `DenialParser.parse(redacted_text: str) -> DenialAnalysis`
- Returns best-effort extraction — fields can be None if not found

### New: `healthflow/tools/appeal_writer.py`

Generates a formal appeal letter template using denial analysis + coverage argument. No Claude call — pure template generation.

**Letter structure:**
1. Header: Date, Appeals Committee address placeholder
2. RE: line with claim details
3. Opening: formal appeal statement
4. Denial summary: what was denied and why
5. Coverage argument: why the denial should be overturned, citing CMS rules
6. Supporting evidence section: placeholder for documentation to attach
7. Request: specific ask (overturn denial, reprocess claim)
8. Closing: contact info placeholders, signature line

All personal info uses placeholders: `[PATIENT_NAME]`, `[DOB]`, `[MEMBER_ID]`, `[PROVIDER_NAME]`, `[CLAIM_NUMBER]`

**Interface:**
- `AppealWriter.generate(analysis: DenialAnalysis, argument: CoverageArgument) -> str`

### New: `healthflow/agents/appeal_agent.py`

Orchestrates the full flow.

**Flow:**
1. PHI redaction on denial_text and additional_context
2. Parse denial details from redacted text
3. Look up denial code in curated database
4. If code found: use curated appeal grounds and precedents
5. If code not found: search by keyword, fall back to generic appeal template
6. Generate appeal letter via AppealWriter
7. Call Claude with redacted denial text + analysis to refine the coverage argument and suggest additional appeal points
8. Filter Claude output through harness
9. Return AppealResponse

**System prompt:** "You are a health insurance claims appeal assistant. Review denial details and suggest additional appeal arguments. Focus on coverage rules, documentation gaps, and procedural rights. Never give medical advice. Never guarantee appeal outcomes. All patient information has been redacted — do not ask for or reference real patient details."

### Modified: `healthflow/models/schemas.py`

Add: `AppealRequest`, `AppealResponse`, `DenialAnalysis`, `CoverageArgument`

### Modified: `healthflow/api/routes.py`

Add `POST /appeal` endpoint:
- Receives AppealRequest
- Runs appeal agent
- Saves session
- Returns AppealResponse with disclaimer

### Modified: `healthflow/cli.py`

Add `appeal` command:
- Options: `--denial-text` (or prompted), `--context` (optional)
- POSTs to `/appeal`
- Displays denial analysis, coverage argument, and full appeal letter

## Guardrails

- PHI redacted via regex before any LLM call — audit log records redaction count
- Every response includes disclaimer: "This appeal letter template is for educational and informational purposes only. It does not constitute legal advice and does not guarantee appeal success. Consult a healthcare advocate or attorney for formal appeals."
- Harness output filter blocks medical advice (reused from existing)
- Audit log: `denial_parsed` event (redacted text only), `appeal_generated` event, `phi_redacted` event (count and types of PHI found, NOT the actual PHI)

## Testing

### `healthflow/tests/test_phi_redactor.py`
1. Redacts patient name after "Patient:"
2. Redacts DOB in MM/DD/YYYY format
3. Redacts member ID after "Member ID:"
4. Redacts SSN pattern
5. Redacts phone number
6. Returns redaction log with positions
7. Handles text with no PHI (returns unchanged)
8. Handles multiple PHI instances

### `healthflow/tests/test_denial_parser.py`
1. Extracts CO-xx denial code
2. Extracts PR-xx denial code
3. Extracts treatment denied
4. Extracts policy section cited
5. Extracts appeal deadline
6. Handles letter with no recognizable code
7. Handles letter with multiple codes (returns first)

### `healthflow/tests/test_denial_codes.py`
1. Lookup known code (CO-50)
2. Lookup unknown code returns None
3. Keyword search finds relevant code
4. All codes have required fields

### `healthflow/tests/test_appeal_writer.py`
1. Generated letter contains denial details
2. Generated letter contains coverage argument
3. Generated letter has PHI placeholders
4. Generated letter has formal structure (date, RE, closing)

### `healthflow/tests/test_appeal_agent.py`
1. Agent orchestrates full flow (mocked Claude)
2. Claude receives only redacted text
3. System prompt prohibits medical advice
4. Unknown denial code uses fallback

### `healthflow/tests/test_appeal_route.py`
1. POST /appeal valid request
2. POST /appeal empty denial text → 422
3. POST /appeal response has disclaimer
4. Response contains appeal letter

### `healthflow/tests/test_appeal_integration.py`
1. End-to-end with realistic denial letter
2. PHI is not present in response
3. Medical advice filtered from Claude output

## What This Does NOT Do

- No guarantee of appeal success
- No legal advice
- No storage of original (unredacted) text
- No file upload (paste only, matching Phase 2 approach)
- No medical advice
- No PII/PHI stored or logged
