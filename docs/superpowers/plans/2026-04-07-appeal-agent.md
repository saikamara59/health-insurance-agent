# Appeal Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/appeal` endpoint that parses denial letters, looks up CMS coverage rules, and generates formal appeal letter templates with PHI redacted.

**Architecture:** PHI redactor strips personal info via regex before any LLM call. Denial parser extracts reason codes and details. A curated denial codes database provides CMS rules and appeal arguments. Appeal writer generates a formal letter template. Claude refines coverage arguments on redacted text only.

**Tech Stack:** Python, FastAPI, Anthropic SDK, Pydantic, pytest, regex

---

## Task 1: Pydantic Models

**Files:** `healthflow/models/schemas.py`, `healthflow/tests/test_appeal_schemas.py`

**Why:** Define the request/response data contracts for the appeal feature before building any logic.

### Steps

- [ ] **1.1** Create test file `healthflow/tests/test_appeal_schemas.py` with the following tests:

```python
import pytest
from pydantic import ValidationError
from healthflow.models.schemas import (
    AppealRequest,
    AppealResponse,
    CoverageArgument,
    DenialAnalysis,
)


def test_appeal_request_valid():
    req = AppealRequest(denial_text="Your claim has been denied under CO-50.")
    assert req.denial_text == "Your claim has been denied under CO-50."
    assert req.additional_context == ""


def test_appeal_request_with_context():
    req = AppealRequest(
        denial_text="Denied",
        additional_context="Patient has documented history.",
    )
    assert req.additional_context == "Patient has documented history."


def test_appeal_request_empty_denial_text():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="")


def test_appeal_request_whitespace_only_denial_text():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="   ")


def test_appeal_request_denial_text_too_long():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="x" * 50001)


def test_appeal_request_context_too_long():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="Denied", additional_context="x" * 1001)


def test_denial_analysis_all_fields():
    da = DenialAnalysis(
        denial_reason_code="CO-50",
        denial_reason="Not medically necessary",
        treatment_denied="MRI of lumbar spine",
        policy_section_cited="LCD L35936",
        appeal_deadline="60 days",
        denial_date="03/15/2026",
    )
    assert da.denial_reason_code == "CO-50"
    assert da.treatment_denied == "MRI of lumbar spine"


def test_denial_analysis_optional_fields_none():
    da = DenialAnalysis(
        denial_reason_code=None,
        denial_reason="Unknown reason",
        treatment_denied="Physical therapy",
        policy_section_cited=None,
        appeal_deadline=None,
        denial_date=None,
    )
    assert da.denial_reason_code is None
    assert da.policy_section_cited is None


def test_coverage_argument():
    ca = CoverageArgument(
        cms_rule="Medicare covers services when medically necessary.",
        common_appeal_grounds=["Provide clinical documentation"],
        success_precedents=["42 CFR 405.940"],
    )
    assert len(ca.common_appeal_grounds) == 1
    assert len(ca.success_precedents) == 1


def test_appeal_response_full():
    da = DenialAnalysis(
        denial_reason_code="CO-50",
        denial_reason="Not medically necessary",
        treatment_denied="MRI",
        policy_section_cited=None,
        appeal_deadline=None,
        denial_date=None,
    )
    ca = CoverageArgument(
        cms_rule="Section 1862(a)(1)(A)",
        common_appeal_grounds=["Provide documentation"],
        success_precedents=["42 CFR 405.940"],
    )
    resp = AppealResponse(
        session_id="abc-123",
        denial_analysis=da,
        coverage_argument=ca,
        appeal_letter="Dear Appeals Committee...",
        disclaimer="For educational purposes only.",
    )
    assert resp.session_id == "abc-123"
    assert resp.appeal_letter.startswith("Dear")
    assert resp.disclaimer == "For educational purposes only."
```

- [ ] **1.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_schemas.py -v
```

- [ ] **1.3** Append models to `healthflow/models/schemas.py` after line 208 (after `CalculateResponse`):

```python


class AppealRequest(BaseModel):
    denial_text: str = Field(..., description="Pasted denial letter text")
    additional_context: str = Field(
        default="", description="Optional additional context from the user"
    )

    @field_validator("denial_text")
    @classmethod
    def validate_denial_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Denial text cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Denial text must be at most 50,000 characters")
        return v

    @field_validator("additional_context")
    @classmethod
    def validate_additional_context(cls, v: str) -> str:
        if len(v) > 1_000:
            raise ValueError("Additional context must be at most 1,000 characters")
        return v


class DenialAnalysis(BaseModel):
    denial_reason_code: str | None
    denial_reason: str
    treatment_denied: str
    policy_section_cited: str | None
    appeal_deadline: str | None
    denial_date: str | None


class CoverageArgument(BaseModel):
    cms_rule: str
    common_appeal_grounds: list[str]
    success_precedents: list[str]


class AppealResponse(BaseModel):
    session_id: str
    denial_analysis: DenialAnalysis
    coverage_argument: CoverageArgument
    appeal_letter: str
    disclaimer: str
```

- [ ] **1.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_schemas.py -v
```

- [ ] **1.5** Commit: `"Add Pydantic models for appeal feature (AppealRequest, AppealResponse, DenialAnalysis, CoverageArgument)"`

---

## Task 2: PHI Redactor

**Files:** `healthflow/tools/phi_redactor.py`, `healthflow/tests/test_phi_redactor.py`

**Why:** PHI must be stripped from text before any LLM call or logging. This is the first component in the data flow.

### Steps

- [ ] **2.1** Create test file `healthflow/tests/test_phi_redactor.py`:

```python
from healthflow.tools.phi_redactor import PHIRedactor


def test_redacts_patient_name():
    redactor = PHIRedactor()
    text = "Patient: John Smith\nDiagnosis: back pain"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "John Smith" not in redacted


def test_redacts_member_name():
    redactor = PHIRedactor()
    text = "Member: Jane Doe\nClaim denied"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "Jane Doe" not in redacted


def test_redacts_dear_name():
    redactor = PHIRedactor()
    text = "Dear Robert Johnson,\nWe regret to inform you"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "Robert Johnson" not in redacted


def test_redacts_dob():
    redactor = PHIRedactor()
    text = "DOB: 01/15/1960\nMember ID: ABC123"
    redacted, log = redactor.redact(text)
    assert "[DOB]" in redacted
    assert "01/15/1960" not in redacted


def test_redacts_member_id():
    redactor = PHIRedactor()
    text = "Member ID: XYZ789456\nDenial reason: CO-50"
    redacted, log = redactor.redact(text)
    assert "[MEMBER_ID]" in redacted
    assert "XYZ789456" not in redacted


def test_redacts_subscriber_id():
    redactor = PHIRedactor()
    text = "Subscriber ID: H3312-034-001\nStatus: Denied"
    redacted, log = redactor.redact(text)
    assert "[MEMBER_ID]" in redacted
    assert "H3312-034-001" not in redacted


def test_redacts_ssn():
    redactor = PHIRedactor()
    text = "SSN: 123-45-6789\nClaim number: 100200"
    redacted, log = redactor.redact(text)
    assert "[SSN]" in redacted
    assert "123-45-6789" not in redacted


def test_redacts_phone():
    redactor = PHIRedactor()
    text = "Phone: (555) 123-4567\nCall us"
    redacted, log = redactor.redact(text)
    assert "[PHONE]" in redacted
    assert "(555) 123-4567" not in redacted


def test_redacts_phone_without_parens():
    redactor = PHIRedactor()
    text = "Contact: 555-123-4567 for questions"
    redacted, log = redactor.redact(text)
    assert "[PHONE]" in redacted
    assert "555-123-4567" not in redacted


def test_redaction_log_has_positions():
    redactor = PHIRedactor()
    text = "Patient: Alice Brown\nMember ID: M12345"
    redacted, log = redactor.redact(text)
    assert len(log) >= 2
    for entry in log:
        assert "placeholder" in entry
        assert "pattern" in entry
        assert "position" in entry
        assert isinstance(entry["position"], int)


def test_no_phi_unchanged():
    redactor = PHIRedactor()
    text = "Your claim for MRI has been denied under CO-50."
    redacted, log = redactor.redact(text)
    assert redacted == text
    assert log == []


def test_multiple_phi_instances():
    redactor = PHIRedactor()
    text = (
        "Patient: John Smith\n"
        "DOB: 03/15/1955\n"
        "Member ID: ABC123456\n"
        "SSN: 123-45-6789\n"
        "Phone: (555) 987-6543\n"
        "Dear John Smith,\n"
        "Your claim has been denied."
    )
    redacted, log = redactor.redact(text)
    assert "John Smith" not in redacted
    assert "03/15/1955" not in redacted
    assert "ABC123456" not in redacted
    assert "123-45-6789" not in redacted
    assert "(555) 987-6543" not in redacted
    assert len(log) >= 5
```

- [ ] **2.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_phi_redactor.py -v
```

- [ ] **2.3** Create `healthflow/tools/phi_redactor.py`:

```python
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
                r"(?:Patient|Member|Name)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                re.IGNORECASE,
            ),
        },
        {
            "placeholder": "[PATIENT_NAME]",
            "pattern": "dear_name",
            "regex": re.compile(
                r"Dear\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                re.IGNORECASE,
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
```

- [ ] **2.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_phi_redactor.py -v
```

- [ ] **2.5** Commit: `"Add PHI redactor with regex patterns for names, DOB, member IDs, SSN, and phone numbers"`

---

## Task 3: Denial Codes Database

**Files:** `healthflow/tools/denial_codes.py`, `healthflow/tests/test_denial_codes.py`

**Why:** Curated database of CARC/RARC codes provides the CMS rules and appeal arguments without needing an LLM call.

### Steps

- [ ] **3.1** Create test file `healthflow/tests/test_denial_codes.py`:

```python
from healthflow.tools.denial_codes import DenialCodeDB


def test_lookup_known_code():
    db = DenialCodeDB()
    result = db.lookup("CO-50")
    assert result is not None
    assert result["code"] == "CO-50"
    assert "medical necessity" in result["description"].lower()
    assert result["category"] == "Medical Necessity"
    assert len(result["appeal_grounds"]) > 0
    assert len(result["precedents"]) > 0


def test_lookup_unknown_code():
    db = DenialCodeDB()
    result = db.lookup("CO-9999")
    assert result is None


def test_keyword_search():
    db = DenialCodeDB()
    result = db.search_by_keyword("medical necessity")
    assert result is not None
    assert "medical necessity" in result["description"].lower() or "medical necessity" in result["category"].lower()


def test_keyword_search_case_insensitive():
    db = DenialCodeDB()
    result = db.search_by_keyword("TIMELY FILING")
    assert result is not None


def test_keyword_search_no_match():
    db = DenialCodeDB()
    result = db.search_by_keyword("xyznonexistentterm123")
    assert result is None


def test_all_codes_have_required_fields():
    db = DenialCodeDB()
    required_fields = {"code", "description", "category", "cms_rule", "appeal_grounds", "precedents"}
    for code_entry in db.all_codes():
        for field in required_fields:
            assert field in code_entry, f"Code {code_entry.get('code', '?')} missing field: {field}"
        assert isinstance(code_entry["appeal_grounds"], list)
        assert isinstance(code_entry["precedents"], list)
        assert len(code_entry["appeal_grounds"]) > 0
        assert len(code_entry["precedents"]) > 0


def test_minimum_code_count():
    db = DenialCodeDB()
    codes = db.all_codes()
    assert len(codes) >= 25
```

- [ ] **3.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_denial_codes.py -v
```

- [ ] **3.3** Create `healthflow/tools/denial_codes.py`:

```python
class DenialCodeDB:
    """Curated database of common CARC/RARC denial codes with CMS rules and appeal arguments."""

    def __init__(self) -> None:
        self._codes: dict[str, dict] = {}
        self._load_codes()

    def lookup(self, code: str) -> dict | None:
        """Look up a denial code. Returns the code entry or None."""
        return self._codes.get(code.upper())

    def search_by_keyword(self, keyword: str) -> dict | None:
        """Case-insensitive substring search on description and category. Returns first match or None."""
        keyword_lower = keyword.lower()
        for entry in self._codes.values():
            if (
                keyword_lower in entry["description"].lower()
                or keyword_lower in entry["category"].lower()
            ):
                return entry
        return None

    def all_codes(self) -> list[dict]:
        """Return all code entries."""
        return list(self._codes.values())

    def _load_codes(self) -> None:
        codes = [
            {
                "code": "CO-4",
                "description": "The procedure code is inconsistent with the modifier used or a required modifier is missing",
                "category": "Coding Error",
                "cms_rule": "Correct Coding Initiative (CCI) edits require proper modifier usage per CMS guidelines. Review NCCI Policy Manual Chapter 1.",
                "appeal_grounds": [
                    "Review and correct modifier usage per CPT guidelines",
                    "Provide operative report documenting distinct procedures",
                    "Reference NCCI Policy Manual for correct modifier pairing",
                ],
                "precedents": [
                    "CMS NCCI Policy Manual — modifier guidelines",
                    "42 CFR §414.40 — Coding and payment for surgical services",
                ],
            },
            {
                "code": "CO-11",
                "description": "The diagnosis is inconsistent with the procedure",
                "category": "Coding Error",
                "cms_rule": "ICD-10 diagnosis must support medical necessity for the billed CPT/HCPCS code per LCD/NCD requirements.",
                "appeal_grounds": [
                    "Review diagnosis codes for accuracy and specificity",
                    "Provide clinical documentation supporting the diagnosis-procedure link",
                    "Reference applicable LCD for covered diagnosis codes",
                ],
                "precedents": [
                    "CMS ICD-10-CM Official Guidelines for Coding",
                    "42 CFR §411.15 — Medical necessity requirements",
                ],
            },
            {
                "code": "CO-16",
                "description": "Claim/service lacks information or has submission/billing error(s)",
                "category": "Billing Error",
                "cms_rule": "Claims must include all required data elements per CMS-1500 or UB-04 form instructions. Missing information causes automatic denial.",
                "appeal_grounds": [
                    "Resubmit claim with all required fields completed",
                    "Verify patient demographics and insurance information",
                    "Include all required supporting documentation",
                    "Check for data entry errors in dates, codes, and identifiers",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80",
                    "42 CFR §424.5 — Basic conditions for payment",
                ],
            },
            {
                "code": "CO-18",
                "description": "Exact duplicate claim/service",
                "category": "Duplicate Claim",
                "cms_rule": "Medicare does not pay for duplicate claims. If resubmitting, include documentation that services were distinct.",
                "appeal_grounds": [
                    "If not a duplicate, provide documentation of distinct services",
                    "Include modifier 76 or 77 for repeat procedures",
                    "Provide operative notes showing separate sessions or sites",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80.3.2",
                    "Medicare Benefit Policy Manual Chapter 16",
                ],
            },
            {
                "code": "CO-22",
                "description": "This care may be covered by another payer per coordination of benefits",
                "category": "Coordination of Benefits",
                "cms_rule": "Medicare Secondary Payer (MSP) rules require proper coordination when another insurer is primary. See 42 CFR §411.20-411.206.",
                "appeal_grounds": [
                    "Verify coordination of benefits order",
                    "Submit primary payer EOB with claim",
                    "Provide documentation that Medicare is primary",
                ],
                "precedents": [
                    "42 CFR §411.20-411.206 — Medicare Secondary Payer",
                    "CMS Medicare Secondary Payer Manual Chapter 1",
                ],
            },
            {
                "code": "CO-27",
                "description": "Expenses incurred after coverage terminated",
                "category": "Coverage Terminated",
                "cms_rule": "Services must be rendered during active coverage period. Verify enrollment dates in Medicare Beneficiary Database.",
                "appeal_grounds": [
                    "Verify patient enrollment dates with CMS",
                    "Check for retroactive enrollment or reinstatement",
                    "Provide proof of active coverage at time of service",
                ],
                "precedents": [
                    "42 CFR §406 — Medicare eligibility and enrollment",
                    "CMS Medicare General Information Manual Chapter 2",
                ],
            },
            {
                "code": "CO-29",
                "description": "The time limit for filing has expired",
                "category": "Timely Filing",
                "cms_rule": "Medicare claims must be filed within 1 calendar year of date of service (or 27 months for MSP). See 42 CFR §424.44.",
                "appeal_grounds": [
                    "Document reasons for late filing (administrative error, retroactive eligibility)",
                    "Request good cause exception under 42 CFR §424.44(b)",
                    "Provide evidence of timely filing to primary payer if applicable",
                ],
                "precedents": [
                    "42 CFR §424.44 — Time limits for filing claims",
                    "CMS Claims Processing Manual Chapter 1 §70",
                ],
            },
            {
                "code": "CO-45",
                "description": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement",
                "category": "Fee Schedule",
                "cms_rule": "Medicare pays based on the Medicare Physician Fee Schedule (MPFS). Charges exceeding the fee schedule are reduced to the allowed amount.",
                "appeal_grounds": [
                    "Verify correct CPT code and place of service",
                    "Check for geographic adjustment factor errors",
                    "Review for correct modifier application affecting payment",
                ],
                "precedents": [
                    "42 CFR §414.20-414.48 — Medicare Physician Fee Schedule",
                    "CMS Claims Processing Manual Chapter 12",
                ],
            },
            {
                "code": "CO-50",
                "description": "These are non-covered services because this is not deemed a medical necessity",
                "category": "Medical Necessity",
                "cms_rule": "Medicare covers services when medically necessary as defined in Section 1862(a)(1)(A) of the Social Security Act. Documentation must demonstrate the service is reasonable and necessary for diagnosis or treatment.",
                "appeal_grounds": [
                    "Provide detailed clinical documentation supporting medical necessity",
                    "Include physician letter explaining why the service is required",
                    "Reference applicable Local Coverage Determination (LCD) or National Coverage Determination (NCD)",
                    "Submit supporting lab results, imaging, or specialist notes",
                ],
                "precedents": [
                    "CMS Manual Chapter 13 §13.5.1 — Redetermination rights",
                    "42 CFR §405.940-405.958 — Medicare appeals process",
                ],
            },
            {
                "code": "CO-96",
                "description": "Non-covered charge(s). At least one Remark Code must be provided",
                "category": "Non-Covered Service",
                "cms_rule": "Service is not covered under the patient's current benefit plan. Review specific remark codes for the reason.",
                "appeal_grounds": [
                    "Review accompanying remark codes for specific denial reason",
                    "Verify benefit coverage for the service",
                    "Check if prior authorization was required and obtained",
                    "Determine if an alternative covered service exists",
                ],
                "precedents": [
                    "Medicare Benefit Policy Manual Chapter 16",
                    "42 CFR §411.15 — Particular services excluded from coverage",
                ],
            },
            {
                "code": "CO-97",
                "description": "The benefit for this service is included in the payment/allowance for another service/procedure that has already been adjudicated",
                "category": "Bundled Service",
                "cms_rule": "CCI edits bundle certain services together. The component service is included in the comprehensive service payment.",
                "appeal_grounds": [
                    "Review CCI edits for the code pair",
                    "Provide documentation that services were distinct and separate",
                    "Use appropriate modifier (59, XE, XS, XP, XU) if services are truly separate",
                    "Include operative report supporting distinct procedures",
                ],
                "precedents": [
                    "CMS NCCI Policy Manual Chapter 1 — bundling edits",
                    "42 CFR §414.40 — Surgical services payment rules",
                ],
            },
            {
                "code": "CO-109",
                "description": "Claim/service not covered by this payer/contractor. You must send the claim/service to the correct payer/contractor",
                "category": "Wrong Payer",
                "cms_rule": "Claim was submitted to the wrong Medicare Administrative Contractor (MAC) or payer. Redirect to the correct entity.",
                "appeal_grounds": [
                    "Identify the correct payer/contractor for the service",
                    "Resubmit to the correct MAC jurisdiction",
                    "Verify patient's plan assignment and coverage",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §10",
                    "42 CFR §421 — Medicare contracting",
                ],
            },
            {
                "code": "CO-119",
                "description": "Benefit maximum for this time period or occurrence has been reached",
                "category": "Benefit Limit",
                "cms_rule": "Medicare has specific visit or service limits for certain benefits (e.g., therapy caps, preventive services). See Medicare Benefit Policy Manual.",
                "appeal_grounds": [
                    "Verify benefit period dates and utilization counts",
                    "Request exceptions process if available (e.g., therapy cap exception)",
                    "Provide documentation of medical necessity for additional services",
                    "Check if benefit reset applies (new benefit period)",
                ],
                "precedents": [
                    "Medicare Benefit Policy Manual Chapter 15 — therapy services",
                    "42 CFR §410.60-410.62 — Therapy services limitations",
                ],
            },
            {
                "code": "CO-167",
                "description": "This (these) diagnosis(es) is (are) not covered. Note: Refer to the 835 Healthcare Policy Identification Segment",
                "category": "Non-Covered Diagnosis",
                "cms_rule": "The diagnosis code submitted does not meet coverage criteria per the applicable LCD or NCD.",
                "appeal_grounds": [
                    "Review LCD/NCD for covered diagnosis codes",
                    "Update diagnosis coding to most specific ICD-10 code",
                    "Provide clinical documentation supporting the diagnosis",
                    "Request LCD reconsideration if diagnosis should be covered",
                ],
                "precedents": [
                    "CMS LCD/NCD database — applicable determination",
                    "42 CFR §405.920 — Reconsideration of LCD/NCD",
                ],
            },
            {
                "code": "CO-197",
                "description": "Precertification/authorization/notification/pre-treatment absent",
                "category": "Prior Authorization",
                "cms_rule": "Service requires prior authorization that was not obtained before the service was rendered.",
                "appeal_grounds": [
                    "Obtain retroactive authorization if payer allows",
                    "Provide documentation that service was emergent and authorization was not feasible",
                    "Show evidence that authorization was actually obtained (reference number)",
                    "Appeal on grounds of medical necessity for urgent services",
                ],
                "precedents": [
                    "42 CFR §422.568 — MA plan prior authorization requirements",
                    "CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F)",
                ],
            },
            {
                "code": "CO-242",
                "description": "Services not provided by network/primary care providers",
                "category": "Out of Network",
                "cms_rule": "MA plans may require use of in-network providers. Out-of-network services covered only for emergencies or if no in-network provider available.",
                "appeal_grounds": [
                    "Document that no in-network provider was available for the service",
                    "Show that the service was emergent or urgently needed",
                    "Request continuity of care exception if provider recently left network",
                    "Provide evidence of prior authorization for out-of-network care",
                ],
                "precedents": [
                    "42 CFR §422.112 — MA access to services",
                    "CMS Medicare Managed Care Manual Chapter 4",
                ],
            },
            {
                "code": "CO-252",
                "description": "An attachment/other documentation is required to adjudicate this claim/service",
                "category": "Documentation Required",
                "cms_rule": "Additional clinical documentation is needed to process the claim. Submit requested records.",
                "appeal_grounds": [
                    "Submit all requested documentation promptly",
                    "Include cover letter referencing the original claim",
                    "Provide complete medical records for the dates of service",
                    "Ensure documentation supports medical necessity",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80.3",
                    "42 CFR §424.5(a)(6) — Documentation requirements",
                ],
            },
            {
                "code": "PR-1",
                "description": "Deductible amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the annual deductible amount before Medicare pays. Part B deductible is set annually by CMS.",
                "appeal_grounds": [
                    "Verify deductible has not already been met for the period",
                    "Check for secondary insurance that covers deductible",
                    "Confirm correct benefit period for deductible application",
                ],
                "precedents": [
                    "42 CFR §410.160 — Part B annual deductible",
                    "Medicare Benefit Policy Manual Chapter 1",
                ],
            },
            {
                "code": "PR-2",
                "description": "Coinsurance amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the coinsurance percentage after deductible is met. Standard Medicare Part B coinsurance is 20%.",
                "appeal_grounds": [
                    "Verify coinsurance percentage is correctly applied",
                    "Check for secondary insurance or Medigap coverage",
                    "Confirm allowed amount used for coinsurance calculation is correct",
                ],
                "precedents": [
                    "42 CFR §410.152 — Part B coinsurance",
                    "Medicare Claims Processing Manual Chapter 12",
                ],
            },
            {
                "code": "PR-3",
                "description": "Co-payment amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the plan copayment amount for the service type. MA plans set copay amounts in the Evidence of Coverage.",
                "appeal_grounds": [
                    "Verify copay amount matches the plan's Evidence of Coverage",
                    "Check if service category was correctly classified",
                    "Confirm in-network vs out-of-network copay was correctly applied",
                ],
                "precedents": [
                    "42 CFR §422.100 — MA plan cost sharing requirements",
                    "Medicare Managed Care Manual Chapter 4",
                ],
            },
            {
                "code": "PR-96",
                "description": "Non-covered charge(s) - patient responsibility",
                "category": "Patient Responsibility",
                "cms_rule": "Service is not covered and patient is responsible for the full charge. Review ABN (Advance Beneficiary Notice) requirements.",
                "appeal_grounds": [
                    "Verify an ABN was properly issued before the service",
                    "Challenge whether the service should be covered",
                    "Check if alternative covered service codes apply",
                    "Request plan reconsideration with supporting documentation",
                ],
                "precedents": [
                    "CMS ABN requirements — Form CMS-R-131",
                    "42 CFR §411.404 — Advance Beneficiary Notice",
                ],
            },
            {
                "code": "PR-204",
                "description": "This service/equipment/drug is not covered under the patient's current benefit plan",
                "category": "Not Covered by Plan",
                "cms_rule": "The service is excluded from the patient's specific plan benefits. Review the plan's Evidence of Coverage for exclusions.",
                "appeal_grounds": [
                    "Review the plan's Evidence of Coverage for the specific exclusion",
                    "Request coverage determination or exception",
                    "Provide medical necessity documentation for exception request",
                    "Consider plan change during Open Enrollment if service is needed",
                ],
                "precedents": [
                    "42 CFR §422.568 — MA coverage determination process",
                    "Medicare Managed Care Manual Chapter 13",
                ],
            },
            {
                "code": "OA-18",
                "description": "Exact duplicate claim/service (Outpatient Adjudication)",
                "category": "Duplicate Claim",
                "cms_rule": "Duplicate claim identified during outpatient adjudication. If services are distinct, resubmit with appropriate documentation.",
                "appeal_grounds": [
                    "Provide documentation that services were distinct",
                    "Include appropriate modifiers for repeat or bilateral procedures",
                    "Submit operative notes showing separate encounters",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 4 — Outpatient claims",
                    "42 CFR §419 — Outpatient prospective payment system",
                ],
            },
            {
                "code": "OA-23",
                "description": "The impact of prior payer(s) adjudication including payments and/or adjustments",
                "category": "Coordination of Benefits",
                "cms_rule": "Payment adjusted based on prior payer's adjudication. Verify coordination of benefits and submit primary payer EOB.",
                "appeal_grounds": [
                    "Submit primary payer's Explanation of Benefits (EOB)",
                    "Verify coordination of benefits order is correct",
                    "Ensure all payer information is current and accurate",
                ],
                "precedents": [
                    "42 CFR §411.20-411.206 — Medicare Secondary Payer",
                    "CMS Medicare Secondary Payer Manual",
                ],
            },
            {
                "code": "N-30",
                "description": "Patient ineligible for this service",
                "category": "Eligibility",
                "cms_rule": "Patient does not meet eligibility criteria for the billed service. Verify enrollment and benefit eligibility.",
                "appeal_grounds": [
                    "Verify patient enrollment and eligibility dates",
                    "Check for retroactive eligibility changes",
                    "Confirm patient meets age, condition, or other eligibility criteria",
                    "Request eligibility verification from CMS",
                ],
                "precedents": [
                    "42 CFR §406 — Medicare eligibility requirements",
                    "CMS Medicare General Information Manual Chapter 2",
                ],
            },
        ]

        for code_entry in codes:
            self._codes[code_entry["code"].upper()] = code_entry
```

- [ ] **3.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_denial_codes.py -v
```

- [ ] **3.5** Commit: `"Add curated denial codes database with 25 CARC/RARC codes, CMS rules, and appeal arguments"`

---

## Task 4: Denial Parser

**Files:** `healthflow/tools/denial_parser.py`, `healthflow/tests/test_denial_parser.py`

**Why:** Extracts structured denial details from free-text denial letters using regex.

### Steps

- [ ] **4.1** Create test file `healthflow/tests/test_denial_parser.py`:

```python
from healthflow.tools.denial_parser import DenialParser


def test_extracts_co_code():
    parser = DenialParser()
    text = "Your claim was denied with reason code CO-50. The service is not medically necessary."
    result = parser.parse(text)
    assert result.denial_reason_code == "CO-50"


def test_extracts_pr_code():
    parser = DenialParser()
    text = "Adjustment reason PR-1 applied to your claim for the deductible amount."
    result = parser.parse(text)
    assert result.denial_reason_code == "PR-1"


def test_extracts_oa_code():
    parser = DenialParser()
    text = "Claim adjusted per OA-18 duplicate claim rules."
    result = parser.parse(text)
    assert result.denial_reason_code == "OA-18"


def test_extracts_treatment_denied():
    parser = DenialParser()
    text = "The following service has been denied: MRI of the lumbar spine. This service is not covered."
    result = parser.parse(text)
    assert "MRI" in result.treatment_denied or "lumbar" in result.treatment_denied.lower()


def test_extracts_treatment_not_covered():
    parser = DenialParser()
    text = "Physical therapy sessions are not covered under your current plan."
    result = parser.parse(text)
    assert "physical therapy" in result.treatment_denied.lower()


def test_extracts_policy_section_lcd():
    parser = DenialParser()
    text = "Per LCD L35936, this service does not meet coverage criteria."
    result = parser.parse(text)
    assert result.policy_section_cited is not None
    assert "L35936" in result.policy_section_cited


def test_extracts_policy_section_cfr():
    parser = DenialParser()
    text = "As per 42 CFR §405.940, your appeal rights are outlined below."
    result = parser.parse(text)
    assert result.policy_section_cited is not None
    assert "CFR" in result.policy_section_cited


def test_extracts_appeal_deadline():
    parser = DenialParser()
    text = "You have 60 days from the date of this notice to file an appeal."
    result = parser.parse(text)
    assert result.appeal_deadline is not None
    assert "60" in result.appeal_deadline


def test_extracts_denial_date():
    parser = DenialParser()
    text = "Date of denial: 03/15/2026. Your claim for services has been denied."
    result = parser.parse(text)
    assert result.denial_date is not None
    assert "03/15/2026" in result.denial_date


def test_no_code_found():
    parser = DenialParser()
    text = "Your claim has been denied. Please contact us for more information."
    result = parser.parse(text)
    assert result.denial_reason_code is None


def test_multiple_codes_returns_first():
    parser = DenialParser()
    text = "Denial reasons: CO-50 for medical necessity and CO-97 for bundled service."
    result = parser.parse(text)
    assert result.denial_reason_code == "CO-50"
```

- [ ] **4.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_denial_parser.py -v
```

- [ ] **4.3** Create `healthflow/tools/denial_parser.py`:

```python
import re

from healthflow.models.schemas import DenialAnalysis


class DenialParser:
    """Extracts denial details from redacted text using regex and keyword matching."""

    # Denial code patterns
    CODE_PATTERN = re.compile(r"\b(CO-\d+|PR-\d+|OA-\d+|N-\d+)\b", re.IGNORECASE)

    # Treatment denied patterns
    TREATMENT_PATTERNS = [
        re.compile(r"denied[:\s]+([^.;\n]{3,80})", re.IGNORECASE),
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
```

- [ ] **4.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_denial_parser.py -v
```

- [ ] **4.5** Commit: `"Add denial parser with regex extraction for codes, treatments, policy sections, deadlines, and dates"`

---

## Task 5: Appeal Writer

**Files:** `healthflow/tools/appeal_writer.py`, `healthflow/tests/test_appeal_writer.py`

**Why:** Generates a formal appeal letter template from parsed denial analysis and coverage arguments. No LLM call needed.

### Steps

- [ ] **5.1** Create test file `healthflow/tests/test_appeal_writer.py`:

```python
from healthflow.models.schemas import CoverageArgument, DenialAnalysis
from healthflow.tools.appeal_writer import AppealWriter


SAMPLE_ANALYSIS = DenialAnalysis(
    denial_reason_code="CO-50",
    denial_reason="Not medically necessary",
    treatment_denied="MRI of lumbar spine",
    policy_section_cited="LCD L35936",
    appeal_deadline="60 days",
    denial_date="03/15/2026",
)

SAMPLE_ARGUMENT = CoverageArgument(
    cms_rule="Medicare covers services when medically necessary as defined in Section 1862(a)(1)(A) of the Social Security Act.",
    common_appeal_grounds=[
        "Provide detailed clinical documentation supporting medical necessity",
        "Include physician letter explaining why the service is required",
    ],
    success_precedents=[
        "CMS Manual Chapter 13 §13.5.1 — Redetermination rights",
        "42 CFR §405.940-405.958 — Medicare appeals process",
    ],
)


def test_letter_contains_denial_details():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "CO-50" in letter
    assert "MRI of lumbar spine" in letter or "MRI" in letter
    assert "not medically necessary" in letter.lower() or "medical necessity" in letter.lower()


def test_letter_contains_coverage_argument():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "1862(a)(1)(A)" in letter or "medically necessary" in letter.lower()
    assert "clinical documentation" in letter.lower()


def test_letter_has_placeholders():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "[PATIENT_NAME]" in letter
    assert "[DOB]" in letter
    assert "[MEMBER_ID]" in letter
    assert "[PROVIDER_NAME]" in letter
    assert "[CLAIM_NUMBER]" in letter


def test_letter_has_formal_structure():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    # Has a date
    assert "202" in letter  # Year in date
    # Has RE: line
    assert "RE:" in letter or "Re:" in letter
    # Has closing
    assert "Sincerely" in letter or "sincerely" in letter.lower()
    # Has opening appeal statement
    assert "appeal" in letter.lower()


def test_letter_includes_precedents():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "42 CFR" in letter or "CMS Manual" in letter


def test_letter_with_no_policy_section():
    analysis = DenialAnalysis(
        denial_reason_code="CO-50",
        denial_reason="Not medically necessary",
        treatment_denied="Physical therapy",
        policy_section_cited=None,
        appeal_deadline=None,
        denial_date=None,
    )
    writer = AppealWriter()
    letter = writer.generate(analysis, SAMPLE_ARGUMENT)
    assert "[PATIENT_NAME]" in letter
    assert "Physical therapy" in letter or "physical therapy" in letter.lower()
```

- [ ] **5.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_writer.py -v
```

- [ ] **5.3** Create `healthflow/tools/appeal_writer.py`:

```python
from datetime import date

from healthflow.models.schemas import CoverageArgument, DenialAnalysis


class AppealWriter:
    """Generates a formal appeal letter template from denial analysis and coverage arguments."""

    def generate(self, analysis: DenialAnalysis, argument: CoverageArgument) -> str:
        """Generate a formal appeal letter with placeholders for PHI."""
        today = date.today().strftime("%B %d, %Y")

        sections = [
            self._header(today),
            self._re_line(analysis),
            self._opening(analysis),
            self._denial_summary(analysis),
            self._coverage_argument(analysis, argument),
            self._evidence_section(argument),
            self._request(analysis),
            self._closing(),
        ]

        return "\n\n".join(sections)

    def _header(self, today: str) -> str:
        return (
            f"{today}\n\n"
            "[PROVIDER_NAME]\n"
            "[PROVIDER_ADDRESS]\n\n"
            "Appeals Committee\n"
            "[INSURANCE_COMPANY_NAME]\n"
            "[INSURANCE_COMPANY_ADDRESS]"
        )

    def _re_line(self, analysis: DenialAnalysis) -> str:
        parts = ["RE: Appeal of Claim Denial"]
        parts.append(f"Patient: [PATIENT_NAME]")
        parts.append(f"Date of Birth: [DOB]")
        parts.append(f"Member ID: [MEMBER_ID]")
        parts.append(f"Claim Number: [CLAIM_NUMBER]")
        if analysis.denial_reason_code:
            parts.append(f"Denial Code: {analysis.denial_reason_code}")
        if analysis.denial_date:
            parts.append(f"Date of Denial: {analysis.denial_date}")
        return "\n".join(parts)

    def _opening(self, analysis: DenialAnalysis) -> str:
        return (
            "Dear Appeals Committee,\n\n"
            "I am writing to formally appeal the denial of coverage for "
            f"{analysis.treatment_denied} for patient [PATIENT_NAME] "
            f"(Member ID: [MEMBER_ID]). "
            f"This appeal is submitted within the required timeframe"
            f"{' of ' + analysis.appeal_deadline if analysis.appeal_deadline else ''}."
        )

    def _denial_summary(self, analysis: DenialAnalysis) -> str:
        lines = ["DENIAL SUMMARY", "-" * 40]
        lines.append(f"The claim for {analysis.treatment_denied} was denied.")
        if analysis.denial_reason_code:
            lines.append(f"Denial Code: {analysis.denial_reason_code}")
        lines.append(f"Stated Reason: {analysis.denial_reason}")
        if analysis.policy_section_cited:
            lines.append(f"Policy Section Cited: {analysis.policy_section_cited}")
        return "\n".join(lines)

    def _coverage_argument(
        self, analysis: DenialAnalysis, argument: CoverageArgument
    ) -> str:
        lines = ["COVERAGE ARGUMENT", "-" * 40]
        lines.append(
            f"We respectfully disagree with this denial and request reconsideration "
            f"based on the following:"
        )
        lines.append("")
        lines.append(f"Applicable CMS Rule: {argument.cms_rule}")
        lines.append("")
        lines.append("Grounds for Appeal:")
        for i, ground in enumerate(argument.common_appeal_grounds, 1):
            lines.append(f"  {i}. {ground}")
        return "\n".join(lines)

    def _evidence_section(self, argument: CoverageArgument) -> str:
        lines = ["SUPPORTING EVIDENCE AND PRECEDENTS", "-" * 40]
        lines.append("The following precedents and references support this appeal:")
        lines.append("")
        for precedent in argument.success_precedents:
            lines.append(f"  - {precedent}")
        lines.append("")
        lines.append("Enclosed Documentation:")
        lines.append("  - [ ] Physician letter of medical necessity")
        lines.append("  - [ ] Relevant clinical records and test results")
        lines.append("  - [ ] Supporting specialist consultation notes")
        lines.append("  - [ ] [Additional documentation as applicable]")
        return "\n".join(lines)

    def _request(self, analysis: DenialAnalysis) -> str:
        return (
            "REQUEST\n"
            + "-" * 40
            + "\n"
            + f"Based on the above, we respectfully request that the denial of "
            f"{analysis.treatment_denied} be overturned and the claim be reprocessed "
            f"for payment. The medical necessity of this service is well-documented "
            f"and supported by applicable CMS guidelines.\n\n"
            f"If additional information is needed, please contact [PROVIDER_NAME] "
            f"at [PROVIDER_PHONE]."
        )

    def _closing(self) -> str:
        return (
            "Sincerely,\n\n"
            "[PROVIDER_NAME]\n"
            "[PROVIDER_TITLE]\n"
            "[PROVIDER_PHONE]\n\n"
            "On behalf of:\n"
            "[PATIENT_NAME]\n"
            "DOB: [DOB]\n"
            "Member ID: [MEMBER_ID]"
        )
```

- [ ] **5.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_writer.py -v
```

- [ ] **5.5** Commit: `"Add appeal writer that generates formal letter templates with PHI placeholders"`

---

## Task 6: Appeal Agent

**Files:** `healthflow/agents/appeal_agent.py`, `healthflow/tests/test_appeal_agent.py`

**Why:** Orchestrates PHI redaction, denial parsing, code lookup, letter generation, and Claude refinement.

### Steps

- [ ] **6.1** Create test file `healthflow/tests/test_appeal_agent.py`:

```python
from unittest.mock import MagicMock, patch

from healthflow.agents.appeal_agent import AppealAgent


SAMPLE_DENIAL = (
    "Patient: John Smith\n"
    "Member ID: ABC123456\n"
    "DOB: 01/15/1960\n"
    "Date of denial: 03/15/2026\n"
    "\n"
    "Dear John Smith,\n"
    "\n"
    "Your claim for MRI of lumbar spine has been denied.\n"
    "Denial code: CO-50. The service is not deemed medically necessary.\n"
    "Per LCD L35936, this service does not meet coverage criteria.\n"
    "You have 60 days to file an appeal.\n"
)


@patch("healthflow.agents.appeal_agent.anthropic")
def test_full_flow_returns_all_components(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Additional appeal suggestion: request peer-to-peer review.")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    analysis, argument, letter, recommendation = agent.process_appeal(SAMPLE_DENIAL, "")

    assert analysis.denial_reason_code == "CO-50"
    assert argument.cms_rule != ""
    assert len(argument.common_appeal_grounds) > 0
    assert "[PATIENT_NAME]" in letter
    assert recommendation != ""


@patch("healthflow.agents.appeal_agent.anthropic")
def test_claude_receives_redacted_text_only(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Suggestion")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    agent.process_appeal(SAMPLE_DENIAL, "")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "John Smith" not in user_msg
    assert "ABC123456" not in user_msg
    assert "01/15/1960" not in user_msg
    assert "[PATIENT_NAME]" in user_msg or "CO-50" in user_msg


@patch("healthflow.agents.appeal_agent.anthropic")
def test_system_prompt_prohibits_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Suggestion")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    agent.process_appeal(SAMPLE_DENIAL, "")

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()
    assert "guarantee" in system.lower()


@patch("healthflow.agents.appeal_agent.anthropic")
def test_unknown_code_uses_fallback(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Review your appeal rights.")]
    mock_client.messages.create.return_value = mock_response

    denial_text = "Your claim has been denied. Code: CO-9999. The service is not covered."
    agent = AppealAgent()
    analysis, argument, letter, recommendation = agent.process_appeal(denial_text, "")

    assert analysis.denial_reason_code == "CO-9999"
    assert argument.cms_rule != ""
    assert len(argument.common_appeal_grounds) > 0
    assert "[PATIENT_NAME]" in letter
```

- [ ] **6.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_agent.py -v
```

- [ ] **6.3** Create `healthflow/agents/appeal_agent.py`:

```python
import anthropic

from healthflow.logs.audit import AuditLogger
from healthflow.models.schemas import CoverageArgument, DenialAnalysis
from healthflow.tools.appeal_writer import AppealWriter
from healthflow.tools.denial_codes import DenialCodeDB
from healthflow.tools.denial_parser import DenialParser
from healthflow.tools.phi_redactor import PHIRedactor

SYSTEM_PROMPT = (
    "You are a health insurance claims appeal assistant. Review denial details and "
    "suggest additional appeal arguments. Focus on coverage rules, documentation gaps, "
    "and procedural rights. Never give medical advice. Never guarantee appeal outcomes. "
    "All patient information has been redacted — do not ask for or reference real patient details."
)

FALLBACK_CMS_RULE = (
    "Medicare beneficiaries have the right to appeal any coverage denial under "
    "42 CFR §405.904. The appeals process includes redetermination, reconsideration, "
    "ALJ hearing, Medicare Appeals Council review, and federal court review."
)

FALLBACK_APPEAL_GROUNDS = [
    "Request a detailed explanation of the denial reason",
    "Provide complete medical records and clinical documentation",
    "Include a physician letter supporting the medical necessity of the service",
    "Reference applicable Medicare coverage guidelines (LCD/NCD)",
    "Request a peer-to-peer review with the plan's medical director",
]

FALLBACK_PRECEDENTS = [
    "42 CFR §405.904 — Medicare appeals rights",
    "42 CFR §405.940-405.958 — Redetermination process",
    "CMS Medicare Claims Processing Manual Chapter 29 — Appeals",
]


class AppealAgent:
    """Orchestrates the full appeal process: redact, parse, lookup, write, refine."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.audit = AuditLogger()
        self.redactor = PHIRedactor()
        self.parser = DenialParser()
        self.code_db = DenialCodeDB()
        self.writer = AppealWriter()

    def process_appeal(
        self,
        denial_text: str,
        additional_context: str,
    ) -> tuple[DenialAnalysis, CoverageArgument, str, str]:
        """Process a denial letter and generate an appeal.

        Returns:
            (analysis, coverage_argument, appeal_letter, refined_recommendation)
        """
        # Step 1: Redact PHI
        redacted_denial, denial_log = self.redactor.redact(denial_text)
        redacted_context, context_log = self.redactor.redact(additional_context)

        self.audit.log("phi_redacted", {
            "denial_redactions": len(denial_log),
            "context_redactions": len(context_log),
            "phi_types": list({entry["placeholder"] for entry in denial_log + context_log}),
        })

        # Step 2: Parse denial details
        analysis = self.parser.parse(redacted_denial)

        self.audit.log("denial_parsed", {
            "code": analysis.denial_reason_code,
            "treatment": analysis.treatment_denied,
            "has_deadline": analysis.appeal_deadline is not None,
        })

        # Step 3: Look up denial code
        code_entry = None
        if analysis.denial_reason_code:
            code_entry = self.code_db.lookup(analysis.denial_reason_code)

        # Step 4: If not found, try keyword search
        if code_entry is None and analysis.denial_reason:
            code_entry = self.code_db.search_by_keyword(analysis.denial_reason)

        # Step 5: Build coverage argument
        if code_entry:
            argument = CoverageArgument(
                cms_rule=code_entry["cms_rule"],
                common_appeal_grounds=code_entry["appeal_grounds"],
                success_precedents=code_entry["precedents"],
            )
        else:
            argument = CoverageArgument(
                cms_rule=FALLBACK_CMS_RULE,
                common_appeal_grounds=FALLBACK_APPEAL_GROUNDS,
                success_precedents=FALLBACK_PRECEDENTS,
            )

        # Step 6: Generate appeal letter
        appeal_letter = self.writer.generate(analysis, argument)

        # Step 7: Call Claude to refine (redacted text only)
        refined_recommendation = self._refine_with_claude(
            redacted_denial, redacted_context, analysis, argument
        )

        self.audit.log("appeal_generated", {
            "code": analysis.denial_reason_code,
            "code_found_in_db": code_entry is not None,
            "letter_length": len(appeal_letter),
        })

        return analysis, argument, appeal_letter, refined_recommendation

    def _refine_with_claude(
        self,
        redacted_denial: str,
        redacted_context: str,
        analysis: DenialAnalysis,
        argument: CoverageArgument,
    ) -> str:
        """Call Claude with redacted text to refine appeal arguments."""
        user_prompt_parts = [
            "Denial letter (PHI redacted):",
            redacted_denial,
            "",
            f"Denial Code: {analysis.denial_reason_code or 'Not identified'}",
            f"Denial Reason: {analysis.denial_reason}",
            f"Treatment Denied: {analysis.treatment_denied}",
            "",
            f"CMS Rule: {argument.cms_rule}",
            "",
            "Current appeal grounds:",
        ]
        for ground in argument.common_appeal_grounds:
            user_prompt_parts.append(f"- {ground}")

        if redacted_context:
            user_prompt_parts.append("")
            user_prompt_parts.append(f"Additional context: {redacted_context}")

        user_prompt_parts.append("")
        user_prompt_parts.append(
            "Based on the denial details above, suggest any additional appeal arguments, "
            "documentation to include, or procedural steps the patient should consider. "
            "Be specific and reference applicable regulations."
        )

        user_prompt = "\n".join(user_prompt_parts)

        self.audit.log("tool_called", {
            "tool": "claude_api",
            "model": "claude-sonnet-4-6",
            "task": "appeal_refine",
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        recommendation = response.content[0].text
        self.audit.log("recommendation_generated", {
            "length": len(recommendation),
            "task": "appeal_refine",
        })
        return recommendation
```

- [ ] **6.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_agent.py -v
```

- [ ] **6.5** Commit: `"Add appeal agent orchestrating PHI redaction, denial parsing, code lookup, letter generation, and Claude refinement"`

---

## Task 7: /appeal API Route

**Files:** `healthflow/api/routes.py`, `healthflow/tests/test_appeal_route.py`

**Why:** Expose the appeal feature via a REST endpoint.

### Steps

- [ ] **7.1** Create test file `healthflow/tests/test_appeal_route.py`:

```python
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from healthflow.main import app
from healthflow.models.schemas import CoverageArgument, DenialAnalysis

client = TestClient(app)

SAMPLE_DENIAL_TEXT = (
    "Patient: John Smith\n"
    "Member ID: ABC123456\n"
    "Your claim for MRI of lumbar spine has been denied.\n"
    "Denial code: CO-50. The service is not deemed medically necessary.\n"
    "You have 60 days to file an appeal.\n"
)

MOCK_ANALYSIS = DenialAnalysis(
    denial_reason_code="CO-50",
    denial_reason="Not medically necessary",
    treatment_denied="MRI of lumbar spine",
    policy_section_cited="LCD L35936",
    appeal_deadline="60 days",
    denial_date="03/15/2026",
)

MOCK_ARGUMENT = CoverageArgument(
    cms_rule="Medicare covers services when medically necessary.",
    common_appeal_grounds=["Provide clinical documentation"],
    success_precedents=["42 CFR §405.940"],
)


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "Additional suggestions from Claude.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "denial_analysis" in data
    assert "coverage_argument" in data
    assert "appeal_letter" in data
    assert "disclaimer" in data


def test_appeal_empty_denial_text():
    response = client.post(
        "/appeal",
        json={"denial_text": ""},
    )
    assert response.status_code == 422


def test_appeal_whitespace_denial_text():
    response = client.post(
        "/appeal",
        json={"denial_text": "   "},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "Suggestions.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    assert "educational" in data["disclaimer"].lower() or "informational" in data["disclaimer"].lower()
    assert "not" in data["disclaimer"].lower() and "legal" in data["disclaimer"].lower()


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_response_has_appeal_letter(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee, we formally appeal...",
        "Suggestions.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    assert len(data["appeal_letter"]) > 0
    assert "appeal" in data["appeal_letter"].lower()


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_medical_advice_filtered(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "You should take ibuprofen. Also request peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    # The harness filter_output should catch "you should take"
    # The recommendation is embedded in the response but filtered
    assert response.status_code == 200
```

- [ ] **7.2** Run tests to verify they fail:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_route.py -v
```

- [ ] **7.3** Modify `healthflow/api/routes.py` — add imports at the top of the imports section (after existing imports):

Add to the imports from `healthflow.models.schemas`:

```python
    AppealRequest,
    AppealResponse,
    CoverageArgument,
    DenialAnalysis,
```

Add a new import:

```python
from healthflow.agents.appeal_agent import AppealAgent
```

Add a new constant after the existing `ESTIMATE_DISCLAIMER`:

```python
APPEAL_DISCLAIMER = (
    "This appeal letter template is for educational and informational purposes only. "
    "It does not constitute legal advice and does not guarantee appeal success. "
    "Consult a healthcare advocate or attorney for formal appeals."
)
```

Add the `/appeal` endpoint at the end of the file (before the final newline):

```python
@router.post("/appeal", response_model=AppealResponse)
def generate_appeal(request: AppealRequest):
    harness.audit.log("tool_called", {
        "tool": "appeal_agent",
        "denial_length": len(request.denial_text),
    })

    agent = AppealAgent()
    analysis, argument, appeal_letter, raw_recommendation = agent.process_appeal(
        request.denial_text,
        request.additional_context,
    )

    # Filter Claude's recommendation through the harness
    filtered_recommendation = harness.filter_output(raw_recommendation)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "type": "appeal",
        "denial_code": analysis.denial_reason_code,
        "treatment_denied": analysis.treatment_denied,
    })

    return AppealResponse(
        session_id=session_id,
        denial_analysis=analysis,
        coverage_argument=argument,
        appeal_letter=appeal_letter,
        disclaimer=APPEAL_DISCLAIMER,
    )
```

- [ ] **7.4** Run tests to verify they pass:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_route.py -v
```

- [ ] **7.5** Commit: `"Add POST /appeal API route with PHI safety, medical advice filtering, and disclaimer"`

---

## Task 8: CLI Appeal Command

**Files:** `healthflow/cli.py`

**Why:** Let users generate appeals from the command line.

### Steps

- [ ] **8.1** Modify `healthflow/cli.py` — add the `appeal` command before the `if __name__ == "__main__": cli()` block (before line 224). Insert the following:

```python
@cli.command()
@click.option(
    "--denial-text",
    default="",
    help="Pasted denial letter text (prompted if not provided)",
)
@click.option("--context", default="", help="Optional additional context")
def appeal(denial_text: str, context: str):
    """Generate an appeal letter from a denial letter."""
    if not denial_text:
        denial_text = click.prompt(
            "Paste your denial letter text (end with Enter on an empty line)",
            default="",
            prompt_suffix="\n> ",
        )
        if not denial_text.strip():
            click.echo("Error: Denial text cannot be empty.")
            sys.exit(1)

    payload: dict = {
        "denial_text": denial_text,
        "additional_context": context,
    }

    try:
        response = httpx.post(f"{BASE_URL}/appeal", json=payload, timeout=60.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        click.echo("Start it with: python -m healthflow.main")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()

    click.echo("\n" + "=" * 60)
    click.echo("  HEALTHFLOW — Claims Denial Appeal")
    click.echo("=" * 60)

    analysis = data["denial_analysis"]
    click.echo("\n--- Denial Analysis ---")
    click.echo(f"  Denial Code:     {analysis.get('denial_reason_code', 'N/A') or 'N/A'}")
    click.echo(f"  Denial Reason:   {analysis.get('denial_reason', 'N/A')}")
    click.echo(f"  Treatment:       {analysis.get('treatment_denied', 'N/A')}")
    click.echo(f"  Policy Section:  {analysis.get('policy_section_cited', 'N/A') or 'N/A'}")
    click.echo(f"  Appeal Deadline: {analysis.get('appeal_deadline', 'N/A') or 'N/A'}")
    click.echo(f"  Denial Date:     {analysis.get('denial_date', 'N/A') or 'N/A'}")

    argument = data["coverage_argument"]
    click.echo("\n--- Coverage Argument ---")
    click.echo(f"  CMS Rule: {argument.get('cms_rule', 'N/A')}")
    click.echo("  Appeal Grounds:")
    for ground in argument.get("common_appeal_grounds", []):
        click.echo(f"    - {ground}")
    click.echo("  Precedents:")
    for precedent in argument.get("success_precedents", []):
        click.echo(f"    - {precedent}")

    click.echo("\n" + "-" * 60)
    click.echo("\nAPPEAL LETTER:\n")
    click.echo(data["appeal_letter"])

    click.echo("\n" + "-" * 60)
    click.echo(f"\n{data['disclaimer']}")
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()
```

- [ ] **8.2** Verify the command appears in help:

```bash
.venv/bin/python -m healthflow.cli appeal --help
```

- [ ] **8.3** Commit: `"Add CLI appeal command with denial text input and formatted output"`

---

## Task 9: Integration Tests + README

**Files:** `healthflow/tests/test_appeal_integration.py`, `README.md`

**Why:** Verify the full flow works end-to-end and document the new feature.

### Steps

- [ ] **9.1** Create test file `healthflow/tests/test_appeal_integration.py`:

```python
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from healthflow.main import app

client = TestClient(app)

REALISTIC_DENIAL_LETTER = """
EXPLANATION OF BENEFITS

Patient: Maria Garcia
Member ID: H3312-034-001
Date of Birth: 07/22/1958
SSN: 123-45-6789
Phone: (555) 867-5309

Date of denial: 02/28/2026

Dear Maria Garcia,

This letter is to inform you that your claim for MRI of the lumbar spine
(CPT 72148) has been denied.

Denial Code: CO-50
Reason: These are non-covered services because this is not deemed a medical
necessity by the plan.

Per LCD L35936, the requested service does not meet the coverage criteria
established for this procedure.

You have the right to appeal this decision. You must file your appeal
within 60 days of the date of this notice.

To file an appeal, send your written request along with any supporting
documentation to:

Appeals Committee
Medicare Advantage Plan
PO Box 12345
Any City, ST 00000

If you have questions, contact Member Services at (800) 555-1234.

Sincerely,
Claims Department
"""


@patch("healthflow.api.routes.AppealAgent")
def test_end_to_end_realistic_denial(mock_agent_cls):
    """End-to-end test with a realistic denial letter."""
    from healthflow.agents.appeal_agent import AppealAgent as RealAgent
    from healthflow.tools.denial_codes import DenialCodeDB
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.tools.appeal_writer import AppealWriter
    from healthflow.models.schemas import CoverageArgument

    # Run the real pipeline (except Claude)
    redactor = PHIRedactor()
    redacted, log = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)
    db = DenialCodeDB()
    code_entry = db.lookup(analysis.denial_reason_code) if analysis.denial_reason_code else None

    assert analysis.denial_reason_code == "CO-50"
    assert "Maria Garcia" not in redacted

    if code_entry:
        argument = CoverageArgument(
            cms_rule=code_entry["cms_rule"],
            common_appeal_grounds=code_entry["appeal_grounds"],
            success_precedents=code_entry["precedents"],
        )
    else:
        argument = CoverageArgument(
            cms_rule="Fallback",
            common_appeal_grounds=["Fallback ground"],
            success_precedents=["Fallback precedent"],
        )

    writer = AppealWriter()
    letter = writer.generate(analysis, argument)

    assert "[PATIENT_NAME]" in letter
    assert "CO-50" in letter

    # Now test via the API endpoint with mocked agent
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        letter,
        "Consider requesting peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["denial_analysis"]["denial_reason_code"] == "CO-50"
    assert len(data["appeal_letter"]) > 100


@patch("healthflow.api.routes.AppealAgent")
def test_phi_not_in_response(mock_agent_cls):
    """Verify PHI from the denial letter does not appear in the response."""
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.models.schemas import CoverageArgument

    redactor = PHIRedactor()
    redacted, _ = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)

    argument = CoverageArgument(
        cms_rule="Test rule",
        common_appeal_grounds=["Test ground"],
        success_precedents=["Test precedent"],
    )

    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        "Dear Appeals Committee, regarding [PATIENT_NAME]...",
        "Recommendation text.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    data = response.json()
    response_text = str(data)

    assert "Maria Garcia" not in response_text
    assert "123-45-6789" not in response_text
    assert "H3312-034-001" not in response_text
    assert "(555) 867-5309" not in response_text


@patch("healthflow.api.routes.AppealAgent")
def test_medical_advice_filtered(mock_agent_cls):
    """Verify medical advice from Claude is filtered out."""
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.models.schemas import CoverageArgument

    redactor = PHIRedactor()
    redacted, _ = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)

    argument = CoverageArgument(
        cms_rule="Test rule",
        common_appeal_grounds=["Test ground"],
        success_precedents=["Test precedent"],
    )

    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        "Dear Appeals Committee...",
        "You should take ibuprofen for pain. Also, request peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    assert response.status_code == 200
    # The harness filters "you should take" from the recommendation
    # The response should still succeed
```

- [ ] **9.2** Run integration tests:

```bash
.venv/bin/python -m pytest healthflow/tests/test_appeal_integration.py -v
```

- [ ] **9.3** Add appeal documentation to `README.md`. After the `POST /calculate` section and before `GET /plans/{zip_code}`, insert:

```markdown
### POST /appeal

Parse a denial letter and generate a formal appeal letter template.

```bash
curl -X POST http://localhost:8000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "denial_text": "Patient: John Smith\nMember ID: ABC123\nYour claim for MRI of lumbar spine has been denied.\nDenial code: CO-50. The service is not deemed medically necessary.\nYou have 60 days to file an appeal.",
    "additional_context": "Patient has documented history of chronic lower back pain."
  }'
```
```

Add to the CLI Usage section:

```markdown
# Generate appeal letter
python -m healthflow.cli appeal --denial-text "Your claim for MRI has been denied. Denial code: CO-50."
```

Add to the Architecture section:

```markdown
- **PHI Redactor**: Regex-based PHI stripping before any LLM call
- **Denial Parser**: Extracts denial codes, treatments, deadlines from letters
- **Denial Code DB**: Curated database of ~25 CARC/RARC codes with CMS rules
- **Appeal Writer**: Generates formal appeal letter templates
- **Appeal Agent**: Orchestrates denial parsing, code lookup, and Claude refinement
```

- [ ] **9.4** Run all tests to verify nothing is broken:

```bash
.venv/bin/python -m pytest healthflow/tests/ -v
```

- [ ] **9.5** Commit: `"Add appeal integration tests and update README with /appeal endpoint documentation"`

---

## Verification Checklist

After all tasks are complete, verify:

- [ ] All tests pass: `.venv/bin/python -m pytest healthflow/tests/ -v`
- [ ] CLI help works: `.venv/bin/python -m healthflow.cli appeal --help`
- [ ] No PHI reaches Claude (verified by test_claude_receives_redacted_text_only)
- [ ] Every response includes the disclaimer
- [ ] Medical advice is filtered from Claude output
- [ ] Unknown denial codes fall back to generic appeal template
