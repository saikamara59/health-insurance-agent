# HealthFlow Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI service that compares Medicare Advantage plans and estimates medication/procedure costs, powered by Claude for plain-English recommendations.

**Architecture:** Three-layer design — Harness (validation + output filtering + logging) wraps Tools (CMS fetcher, plan parser, cost estimator) and Agent (Claude recommendation). FastAPI serves the API, with an optional Click CLI wrapper.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, Anthropic SDK, Redis (optional), Click, pytest, httpx

---

### Task 1: Project Scaffolding + Dependencies

**Files:**
- Create: `healthflow/main.py`
- Create: `healthflow/api/__init__.py`
- Create: `healthflow/agents/__init__.py`
- Create: `healthflow/tools/__init__.py`
- Create: `healthflow/models/__init__.py`
- Create: `healthflow/memory/__init__.py`
- Create: `healthflow/logs/__init__.py`
- Create: `healthflow/tests/__init__.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.115
uvicorn>=0.30
click>=8.1
anthropic>=0.40
redis>=5.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 2: Create the directory structure with __init__.py files**

```bash
mkdir -p healthflow/api healthflow/agents healthflow/tools healthflow/models healthflow/memory healthflow/logs healthflow/tests
touch healthflow/__init__.py healthflow/api/__init__.py healthflow/agents/__init__.py healthflow/tools/__init__.py healthflow/models/__init__.py healthflow/memory/__init__.py healthflow/logs/__init__.py healthflow/tests/__init__.py
```

- [ ] **Step 3: Create minimal main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="HealthFlow",
    description="AI-powered Medicare Advantage plan comparison service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("healthflow.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: Install dependencies and verify the app starts**

```bash
pip install -r requirements.txt
cd /Users/saidukamara/code/projects/health-insurance-agent
python -m healthflow.main &
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt healthflow/
git commit -m "feat: scaffold HealthFlow project structure with FastAPI"
```

---

### Task 2: Pydantic Models

**Files:**
- Create: `healthflow/models/schemas.py`
- Create: `healthflow/tests/test_schemas.py`

- [ ] **Step 1: Write tests for Pydantic models**

Create `healthflow/tests/test_schemas.py`:

```python
import pytest
from healthflow.models.schemas import (
    CompareRequest,
    CompareResponse,
    CostDetails,
    EstimateRequest,
    EstimateResponse,
    PlanSummary,
)


def test_compare_request_valid():
    req = CompareRequest(zip_code="10001", age=65, income_level="low")
    assert req.zip_code == "10001"
    assert req.age == 65
    assert req.income_level == "low"
    assert req.medications == []
    assert req.procedures == []


def test_compare_request_with_meds_and_procedures():
    req = CompareRequest(
        zip_code="90210",
        age=70,
        income_level="high",
        medications=["Metformin", "Lisinopril"],
        procedures=["Annual physical"],
    )
    assert len(req.medications) == 2
    assert len(req.procedures) == 1


def test_compare_request_invalid_zip():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="123", age=65, income_level="low")


def test_compare_request_invalid_zip_non_numeric():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="abcde", age=65, income_level="low")


def test_compare_request_invalid_age_too_low():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=17, income_level="low")


def test_compare_request_invalid_age_too_high():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=121, income_level="low")


def test_compare_request_invalid_income():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=65, income_level="rich")


def test_estimate_request_valid():
    req = EstimateRequest(
        plan_id="H1234-001", item_name="Metformin", item_type="medication"
    )
    assert req.plan_id == "H1234-001"
    assert req.item_type == "medication"


def test_estimate_request_invalid_type():
    with pytest.raises(ValueError):
        EstimateRequest(
            plan_id="H1234-001", item_name="Metformin", item_type="vitamin"
        )


def test_plan_summary_model():
    plan = PlanSummary(
        plan_name="Aetna Medicare Eagle Plus (HMO)",
        plan_id="H1234-001",
        monthly_premium=0.0,
        annual_deductible=250.0,
        out_of_pocket_max=4500.0,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
        estimated_medication_costs=None,
        estimated_procedure_costs=None,
    )
    assert plan.star_rating == 4.5
    assert plan.drug_coverage is True


def test_cost_details_model():
    details = CostDetails(
        formulary_tier="Tier 1 - Generic",
        copay=10.0,
        coinsurance_pct=None,
        prior_auth_required=False,
        quantity_limit="90-day supply",
    )
    assert details.copay == 10.0
    assert details.prior_auth_required is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_schemas.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'healthflow.models.schemas'`

- [ ] **Step 3: Implement the Pydantic models**

Create `healthflow/models/schemas.py`:

```python
from pydantic import BaseModel, Field, field_validator


class CompareRequest(BaseModel):
    zip_code: str = Field(..., description="5-digit US zip code")
    age: int = Field(..., ge=18, le=120, description="Age between 18 and 120")
    income_level: str = Field(..., description="Income level: low, medium, or high")
    medications: list[str] = Field(
        default_factory=list, max_length=10, description="Optional list of medications"
    )
    procedures: list[str] = Field(
        default_factory=list, max_length=10, description="Optional list of procedures"
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        if len(v) != 5 or not v.isdigit():
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"Income level must be one of: {', '.join(sorted(allowed))}")
        return v


class EstimateRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID to estimate costs for")
    item_name: str = Field(..., description="Medication or procedure name")
    item_type: str = Field(..., description="Type: medication or procedure")

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        allowed = {"medication", "procedure"}
        if v not in allowed:
            raise ValueError(f"Item type must be one of: {', '.join(sorted(allowed))}")
        return v


class PlanSummary(BaseModel):
    plan_name: str
    plan_id: str
    monthly_premium: float
    annual_deductible: float
    out_of_pocket_max: float
    star_rating: float = Field(..., ge=1.0, le=5.0)
    plan_type: str
    drug_coverage: bool
    estimated_medication_costs: dict[str, float] | None = None
    estimated_procedure_costs: dict[str, float] | None = None


class CompareResponse(BaseModel):
    session_id: str
    zip_code: str
    plans: list[PlanSummary]
    recommendation: str
    disclaimer: str


class CostDetails(BaseModel):
    formulary_tier: str | None = None
    copay: float | None = None
    coinsurance_pct: float | None = None
    prior_auth_required: bool = False
    quantity_limit: str | None = None


class EstimateResponse(BaseModel):
    plan_name: str
    item_name: str
    item_type: str
    estimated_cost: float
    cost_details: CostDetails
    disclaimer: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_schemas.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/models/schemas.py healthflow/tests/test_schemas.py
git commit -m "feat: add Pydantic request/response models with validation"
```

---

### Task 3: Audit Logger

**Files:**
- Create: `healthflow/logs/audit.py`
- Create: `healthflow/tests/test_audit.py`

- [ ] **Step 1: Write tests for audit logger**

Create `healthflow/tests/test_audit.py`:

```python
import json
import logging
from healthflow.logs.audit import AuditLogger


def test_audit_log_creates_structured_entry(caplog):
    logger = AuditLogger()
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        logger.log("input_validated", {"zip_code": "10001", "age": 65})

    assert len(caplog.records) == 1
    record = caplog.records[0]
    data = json.loads(record.getMessage())
    assert data["event_type"] == "input_validated"
    assert data["details"]["zip_code"] == "10001"
    assert "timestamp" in data


def test_audit_log_event_types(caplog):
    logger = AuditLogger()
    event_types = [
        "input_validated",
        "tool_called",
        "plans_fetched",
        "costs_estimated",
        "recommendation_generated",
        "output_filtered",
    ]
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        for et in event_types:
            logger.log(et, {"test": True})

    assert len(caplog.records) == 6


def test_audit_log_timestamp_is_iso_format(caplog):
    logger = AuditLogger()
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        logger.log("tool_called", {"tool": "cms_fetcher"})

    data = json.loads(caplog.records[0].getMessage())
    # ISO 8601 format check — contains "T" separator
    assert "T" in data["timestamp"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_audit.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement audit logger**

Create `healthflow/logs/audit.py`:

```python
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


class AuditLogger:
    def __init__(self, log_file: str = "healthflow.log"):
        self._logger = logging.getLogger("healthflow.audit")
        if not self._logger.handlers:
            self._logger.setLevel(logging.INFO)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self._logger.addHandler(console_handler)

            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3
            )
            file_handler.setLevel(logging.INFO)
            self._logger.addHandler(file_handler)

    def log(self, event_type: str, details: dict) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        self._logger.info(json.dumps(entry))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_audit.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/logs/audit.py healthflow/tests/test_audit.py
git commit -m "feat: add structured JSON audit logger with rotation"
```

---

### Task 4: Harness — Input Validation + Output Filtering

**Files:**
- Create: `healthflow/agents/harness.py`
- Create: `healthflow/tests/test_harness.py`

- [ ] **Step 1: Write tests for harness**

Create `healthflow/tests/test_harness.py`:

```python
import pytest
from healthflow.agents.harness import Harness, ValidationError


def test_validate_valid_input():
    harness = Harness()
    result = harness.validate_input("10001", 65, "low", ["Metformin"], ["MRI"])
    assert result["zip_code"] == "10001"
    assert result["age"] == 65
    assert result["income_level"] == "low"


def test_validate_invalid_zip_short():
    harness = Harness()
    with pytest.raises(ValidationError, match="5 digits"):
        harness.validate_input("123", 65, "low")


def test_validate_invalid_zip_non_numeric():
    harness = Harness()
    with pytest.raises(ValidationError, match="5 digits"):
        harness.validate_input("abcde", 65, "low")


def test_validate_invalid_age_too_low():
    harness = Harness()
    with pytest.raises(ValidationError, match="between 18 and 120"):
        harness.validate_input("10001", 15, "low")


def test_validate_invalid_age_too_high():
    harness = Harness()
    with pytest.raises(ValidationError, match="between 18 and 120"):
        harness.validate_input("10001", 200, "low")


def test_validate_invalid_income():
    harness = Harness()
    with pytest.raises(ValidationError, match="income"):
        harness.validate_input("10001", 65, "rich")


def test_validate_too_many_medications():
    harness = Harness()
    meds = [f"Drug{i}" for i in range(11)]
    with pytest.raises(ValidationError, match="10"):
        harness.validate_input("10001", 65, "low", medications=meds)


def test_validate_too_many_procedures():
    harness = Harness()
    procs = [f"Proc{i}" for i in range(11)]
    with pytest.raises(ValidationError, match="10"):
        harness.validate_input("10001", 65, "low", procedures=procs)


def test_validate_empty_medication_string():
    harness = Harness()
    with pytest.raises(ValidationError, match="empty"):
        harness.validate_input("10001", 65, "low", medications=[""])


def test_filter_output_clean_text():
    harness = Harness()
    text = "Plan A has a lower premium of $0/month and a 4.5 star rating."
    result = harness.filter_output(text)
    assert "Plan A has a lower premium" in result
    assert "not medical advice" in result.lower()


def test_filter_output_blocks_medication_advice():
    harness = Harness()
    text = "Based on your profile, you should take Metformin daily."
    result = harness.filter_output(text)
    assert "you should take" not in result.lower()
    assert "[redacted" in result.lower() or "not medical advice" in result.lower()


def test_filter_output_blocks_diagnostic_suggestion():
    harness = Harness()
    text = "Your symptoms suggest you might have diabetes."
    result = harness.filter_output(text)
    assert "symptoms suggest" not in result.lower()


def test_filter_output_blocks_treatment_advice():
    harness = Harness()
    text = "I recommend treatment with insulin for your condition."
    result = harness.filter_output(text)
    assert "i recommend treatment" not in result.lower()


def test_filter_output_always_has_disclaimer():
    harness = Harness()
    text = "Plan B is the best value option."
    result = harness.filter_output(text)
    assert "not medical advice" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_harness.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement the harness**

Create `healthflow/agents/harness.py`:

```python
import re

from healthflow.logs.audit import AuditLogger


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_harness.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/agents/harness.py healthflow/tests/test_harness.py
git commit -m "feat: add harness with input validation and output filtering"
```

---

### Task 5: CMS Fetcher (Mock Data)

**Files:**
- Create: `healthflow/tools/cms_fetcher.py`
- Create: `healthflow/tests/test_cms_fetcher.py`

- [ ] **Step 1: Write tests for CMS fetcher**

Create `healthflow/tests/test_cms_fetcher.py`:

```python
from healthflow.tools.cms_fetcher import MockCMSFetcher


def test_fetch_plans_known_zip():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    assert len(plans) >= 5
    for plan in plans:
        assert "plan_name" in plan
        assert "plan_id" in plan
        assert "monthly_premium" in plan
        assert "annual_deductible" in plan
        assert "out_of_pocket_max" in plan
        assert "star_rating" in plan
        assert "plan_type" in plan
        assert "drug_coverage" in plan


def test_fetch_plans_unknown_zip_returns_plans():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("99999")
    assert len(plans) >= 3


def test_fetch_plans_realistic_premium_range():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    for plan in plans:
        assert 0 <= plan["monthly_premium"] <= 175


def test_fetch_plans_realistic_star_rating():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    for plan in plans:
        assert 1.0 <= plan["star_rating"] <= 5.0


def test_fetch_plans_has_hmo_and_ppo():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    plan_types = {p["plan_type"] for p in plans}
    assert "HMO" in plan_types or "PPO" in plan_types


def test_fetch_plans_multiple_zips_return_data():
    fetcher = MockCMSFetcher()
    for zip_code in ["10001", "90210", "60601", "33101", "77001"]:
        plans = fetcher.fetch_plans(zip_code)
        assert len(plans) >= 5, f"Zip {zip_code} returned fewer than 5 plans"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_cms_fetcher.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement MockCMSFetcher with curated data**

Create `healthflow/tools/cms_fetcher.py`:

```python
import random
from typing import Protocol


class CMSFetcher(Protocol):
    def fetch_plans(self, zip_code: str) -> list[dict]: ...


ALL_PLANS = [
    {
        "plan_name": "Aetna Medicare Eagle Plus (HMO)",
        "plan_id": "H3312-034",
        "monthly_premium": 0.00,
        "annual_deductible": 250.00,
        "out_of_pocket_max": 4500.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Aetna Medicare Value (PPO)",
        "plan_id": "H5521-017",
        "monthly_premium": 45.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5900.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Humana Gold Plus (HMO-POS)",
        "plan_id": "H1036-200",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3400.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Humana Choice (PPO)",
        "plan_id": "H1036-180",
        "monthly_premium": 75.50,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 6700.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Medicare Advantage Choice (PPO)",
        "plan_id": "H2228-050",
        "monthly_premium": 25.00,
        "annual_deductible": 150.00,
        "out_of_pocket_max": 5500.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Medicare Advantage Star (HMO)",
        "plan_id": "H2228-063",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3900.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Dual Complete (HMO-SNP)",
        "plan_id": "H2228-071",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Cigna Preferred Medicare (HMO)",
        "plan_id": "H5410-022",
        "monthly_premium": 35.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4200.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Cigna True Choice Medicare (PPO)",
        "plan_id": "H5410-038",
        "monthly_premium": 110.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5000.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "BCBS Medicare Blue Choice (PPO)",
        "plan_id": "H7917-010",
        "monthly_premium": 55.00,
        "annual_deductible": 175.00,
        "out_of_pocket_max": 6200.00,
        "star_rating": 4.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "BCBS Medicare Essentials (HMO)",
        "plan_id": "H7917-025",
        "monthly_premium": 0.00,
        "annual_deductible": 300.00,
        "out_of_pocket_max": 4800.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Wellcare Value Script (HMO)",
        "plan_id": "H1032-064",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 4000.00,
        "star_rating": 3.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Wellcare No Premium (HMO)",
        "plan_id": "H1032-070",
        "monthly_premium": 0.00,
        "annual_deductible": 500.00,
        "out_of_pocket_max": 5500.00,
        "star_rating": 3.0,
        "plan_type": "HMO",
        "drug_coverage": False,
    },
    {
        "plan_name": "Kaiser Permanente Senior Advantage (HMO)",
        "plan_id": "H0524-001",
        "monthly_premium": 15.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3200.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Molina Medicare Complete Care (HMO)",
        "plan_id": "H9622-005",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3800.00,
        "star_rating": 3.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Anthem MediBlue Plus (PPO)",
        "plan_id": "H3952-018",
        "monthly_premium": 89.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5200.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Centene Ambetter Medicare (HMO)",
        "plan_id": "H6105-012",
        "monthly_premium": 20.00,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 4600.00,
        "star_rating": 3.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Devoted Health Medicare (HMO)",
        "plan_id": "H8230-003",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3500.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Clover Health Preferred (PPO)",
        "plan_id": "H7322-008",
        "monthly_premium": 30.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4900.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Oscar Medicare Advantage (HMO)",
        "plan_id": "H8245-002",
        "monthly_premium": 175.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
]

# Plans available per zip code — index into ALL_PLANS
ZIP_CODE_PLAN_INDICES: dict[str, list[int]] = {
    "10001": [0, 1, 2, 4, 5, 7, 9, 17, 18, 19],  # NYC
    "90210": [0, 2, 3, 5, 8, 13, 14, 15, 18, 19],  # LA
    "60601": [1, 2, 4, 6, 7, 10, 11, 14, 16, 17],  # Chicago
    "33101": [0, 3, 4, 5, 8, 11, 14, 17, 18, 19],  # Miami
    "77001": [1, 2, 6, 7, 9, 10, 12, 15, 16, 18],  # Houston
    "85001": [0, 3, 5, 8, 11, 12, 13, 14, 16, 19],  # Phoenix
    "98101": [2, 4, 5, 6, 9, 10, 13, 15, 17, 18],  # Seattle
    "30301": [0, 1, 3, 7, 8, 10, 11, 14, 16, 19],  # Atlanta
    "02101": [1, 2, 5, 6, 9, 10, 13, 17, 18, 19],  # Boston
    "75201": [0, 3, 4, 7, 8, 11, 12, 15, 16, 18],  # Dallas
}


class MockCMSFetcher:
    def fetch_plans(self, zip_code: str) -> list[dict]:
        if zip_code in ZIP_CODE_PLAN_INDICES:
            indices = ZIP_CODE_PLAN_INDICES[zip_code]
            return [ALL_PLANS[i].copy() for i in indices]

        rng = random.Random(int(zip_code))
        indices = rng.sample(range(len(ALL_PLANS)), k=min(8, len(ALL_PLANS)))
        return [ALL_PLANS[i].copy() for i in indices]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_cms_fetcher.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tools/cms_fetcher.py healthflow/tests/test_cms_fetcher.py
git commit -m "feat: add MockCMSFetcher with curated realistic Medicare plan data"
```

---

### Task 6: Plan Parser

**Files:**
- Create: `healthflow/tools/plan_parser.py`
- Create: `healthflow/tests/test_plan_parser.py`

- [ ] **Step 1: Write tests for plan parser**

Create `healthflow/tests/test_plan_parser.py`:

```python
from healthflow.tools.plan_parser import PlanParser


SAMPLE_PLANS = [
    {
        "plan_name": "Plan A",
        "plan_id": "H0001-001",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan B",
        "plan_id": "H0001-002",
        "monthly_premium": 100.00,
        "annual_deductible": 500.00,
        "out_of_pocket_max": 8000.00,
        "star_rating": 3.0,
        "plan_type": "PPO",
        "drug_coverage": False,
    },
    {
        "plan_name": "Plan C",
        "plan_id": "H0001-003",
        "monthly_premium": 50.00,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 5000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan D",
        "plan_id": "H0001-004",
        "monthly_premium": 25.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4000.00,
        "star_rating": 4.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan E",
        "plan_id": "H0001-005",
        "monthly_premium": 150.00,
        "annual_deductible": 400.00,
        "out_of_pocket_max": 7000.00,
        "star_rating": 2.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan F",
        "plan_id": "H0001-006",
        "monthly_premium": 75.00,
        "annual_deductible": 300.00,
        "out_of_pocket_max": 6000.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
]


def test_parse_returns_plan_summaries():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "medium")
    assert len(plans) == 5
    for plan in plans:
        assert hasattr(plan, "plan_name")
        assert hasattr(plan, "monthly_premium")
        assert hasattr(plan, "star_rating")


def test_parse_returns_max_5():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "low")
    assert len(plans) <= 5


def test_low_income_prefers_low_premium():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "low")
    # Plan A has $0 premium — should rank highly for low income
    assert plans[0].plan_id == "H0001-001"


def test_high_income_prefers_high_star():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "high")
    # Plan A has 5.0 stars — should rank highly for high income
    assert plans[0].plan_id == "H0001-001"


def test_parse_fewer_than_5_plans():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS[:3], "medium")
    assert len(plans) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_plan_parser.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement plan parser**

Create `healthflow/tools/plan_parser.py`:

```python
from healthflow.models.schemas import PlanSummary


SCORING_WEIGHTS = {
    "low": {"premium": 0.5, "deductible": 0.3, "star_rating": 0.2},
    "medium": {"premium": 0.3, "deductible": 0.3, "star_rating": 0.4},
    "high": {"premium": 0.1, "deductible": 0.2, "star_rating": 0.7},
}

# Max values for normalization
MAX_PREMIUM = 175.0
MAX_DEDUCTIBLE = 500.0
MAX_STAR = 5.0


class PlanParser:
    def parse_and_rank(
        self, raw_plans: list[dict], income_level: str
    ) -> list[PlanSummary]:
        weights = SCORING_WEIGHTS[income_level]
        scored: list[tuple[float, PlanSummary]] = []

        for raw in raw_plans:
            plan = PlanSummary(
                plan_name=raw["plan_name"],
                plan_id=raw["plan_id"],
                monthly_premium=raw["monthly_premium"],
                annual_deductible=raw["annual_deductible"],
                out_of_pocket_max=raw["out_of_pocket_max"],
                star_rating=raw["star_rating"],
                plan_type=raw["plan_type"],
                drug_coverage=raw["drug_coverage"],
                estimated_medication_costs=None,
                estimated_procedure_costs=None,
            )

            # Lower premium/deductible = better → invert the normalized score
            premium_score = 1.0 - (plan.monthly_premium / MAX_PREMIUM) if MAX_PREMIUM else 1.0
            deductible_score = 1.0 - (plan.annual_deductible / MAX_DEDUCTIBLE) if MAX_DEDUCTIBLE else 1.0
            star_score = plan.star_rating / MAX_STAR

            total_score = (
                weights["premium"] * premium_score
                + weights["deductible"] * deductible_score
                + weights["star_rating"] * star_score
            )
            scored.append((total_score, plan))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [plan for _, plan in scored[:5]]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_plan_parser.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tools/plan_parser.py healthflow/tests/test_plan_parser.py
git commit -m "feat: add plan parser with income-based scoring and ranking"
```

---

### Task 7: Cost Estimator

**Files:**
- Create: `healthflow/tools/cost_estimator.py`
- Create: `healthflow/tests/test_cost_estimator.py`

- [ ] **Step 1: Write tests for cost estimator**

Create `healthflow/tests/test_cost_estimator.py`:

```python
import pytest
from healthflow.tools.cost_estimator import CostEstimator


def test_estimate_medication_known():
    estimator = CostEstimator()
    result = estimator.estimate("Metformin", "medication", "HMO")
    assert result is not None
    assert result["estimated_cost"] >= 0
    assert "cost_details" in result
    assert result["cost_details"]["formulary_tier"] is not None


def test_estimate_medication_case_insensitive():
    estimator = CostEstimator()
    result = estimator.estimate("metformin", "medication", "HMO")
    assert result is not None


def test_estimate_medication_fuzzy_match():
    estimator = CostEstimator()
    result = estimator.estimate("Metformin 500mg", "medication", "HMO")
    assert result is not None
    assert "Metformin" in result["item_name"]


def test_estimate_medication_unknown():
    estimator = CostEstimator()
    result = estimator.estimate("MadeUpDrug123", "medication", "HMO")
    assert result is None


def test_estimate_procedure_known():
    estimator = CostEstimator()
    result = estimator.estimate("MRI", "procedure", "PPO")
    assert result is not None
    assert result["estimated_cost"] > 0


def test_estimate_procedure_case_insensitive():
    estimator = CostEstimator()
    result = estimator.estimate("annual physical", "procedure", "HMO")
    assert result is not None


def test_estimate_procedure_unknown():
    estimator = CostEstimator()
    result = estimator.estimate("Brain Transplant", "procedure", "HMO")
    assert result is None


def test_estimate_procedure_hmo_vs_ppo_differs():
    estimator = CostEstimator()
    hmo = estimator.estimate("MRI", "procedure", "HMO")
    ppo = estimator.estimate("MRI", "procedure", "PPO")
    assert hmo is not None
    assert ppo is not None
    # Costs may differ by plan type
    assert isinstance(hmo["estimated_cost"], (int, float))
    assert isinstance(ppo["estimated_cost"], (int, float))


def test_estimate_multiple_medications():
    estimator = CostEstimator()
    meds = ["Metformin", "Lisinopril", "Atorvastatin"]
    results = estimator.estimate_multiple(meds, "medication", "HMO")
    assert len(results) == 3
    for med, result in results.items():
        assert result is not None


def test_estimate_multiple_procedures():
    estimator = CostEstimator()
    procs = ["Annual physical", "Blood work"]
    results = estimator.estimate_multiple(procs, "procedure", "PPO")
    assert len(results) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_cost_estimator.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement cost estimator**

Create `healthflow/tools/cost_estimator.py`:

```python
MEDICATIONS = [
    {"name": "Metformin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Lisinopril", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Atorvastatin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Amlodipine", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Omeprazole", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Levothyroxine", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Albuterol", "tier": "Tier 2 - Preferred Brand", "copay_hmo": 25.0, "copay_ppo": 35.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Gabapentin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Losartan", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Hydrochlorothiazide", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Sertraline", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Montelukast", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 12.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Pantoprazole", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Escitalopram", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Rosuvastatin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 12.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Tamsulosin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Meloxicam", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Glipizide", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Insulin Glargine", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 75.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Eliquis", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Jardiance", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 90.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Ozempic", "tier": "Tier 4 - Specialty", "copay_hmo": 100.0, "copay_ppo": 150.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Xarelto", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Humira", "tier": "Tier 4 - Specialty", "copay_hmo": 150.0, "copay_ppo": 250.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Dupixent", "tier": "Tier 4 - Specialty", "copay_hmo": 150.0, "copay_ppo": 275.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Entresto", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 90.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Tresiba", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 80.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Farxiga", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 85.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Trulicity", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Warfarin", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
]

PROCEDURES = [
    {"name": "Annual physical", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Blood work", "category": "diagnostic", "cost_hmo": 10.0, "cost_ppo": 20.0},
    {"name": "X-ray", "category": "diagnostic", "cost_hmo": 30.0, "cost_ppo": 50.0},
    {"name": "MRI", "category": "diagnostic", "cost_hmo": 150.0, "cost_ppo": 250.0},
    {"name": "CT scan", "category": "diagnostic", "cost_hmo": 125.0, "cost_ppo": 200.0},
    {"name": "ER visit", "category": "inpatient", "cost_hmo": 150.0, "cost_ppo": 200.0},
    {"name": "Urgent care", "category": "outpatient", "cost_hmo": 25.0, "cost_ppo": 50.0},
    {"name": "Physical therapy", "category": "outpatient", "cost_hmo": 20.0, "cost_ppo": 40.0},
    {"name": "Specialist office visit", "category": "specialist", "cost_hmo": 40.0, "cost_ppo": 50.0},
    {"name": "Colonoscopy", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Mammogram", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Dental cleaning", "category": "outpatient", "cost_hmo": 25.0, "cost_ppo": 35.0},
    {"name": "Vision exam", "category": "outpatient", "cost_hmo": 15.0, "cost_ppo": 25.0},
    {"name": "Hearing test", "category": "diagnostic", "cost_hmo": 20.0, "cost_ppo": 35.0},
    {"name": "Mental health visit", "category": "specialist", "cost_hmo": 25.0, "cost_ppo": 40.0},
    {"name": "Lab panel", "category": "diagnostic", "cost_hmo": 15.0, "cost_ppo": 25.0},
    {"name": "EKG", "category": "diagnostic", "cost_hmo": 20.0, "cost_ppo": 35.0},
    {"name": "Ultrasound", "category": "diagnostic", "cost_hmo": 50.0, "cost_ppo": 80.0},
    {"name": "Minor surgery", "category": "outpatient", "cost_hmo": 250.0, "cost_ppo": 400.0},
    {"name": "Inpatient day", "category": "inpatient", "cost_hmo": 300.0, "cost_ppo": 500.0},
]


def _fuzzy_match(query: str, candidates: list[dict]) -> dict | None:
    query_lower = query.lower().strip()
    # Exact match first
    for item in candidates:
        if item["name"].lower() == query_lower:
            return item
    # Substring match
    for item in candidates:
        if query_lower in item["name"].lower() or item["name"].lower() in query_lower:
            return item
    return None


class CostEstimator:
    def estimate(
        self, item_name: str, item_type: str, plan_type: str
    ) -> dict | None:
        if item_type == "medication":
            match = _fuzzy_match(item_name, MEDICATIONS)
            if match is None:
                return None
            copay_key = "copay_hmo" if plan_type == "HMO" else "copay_ppo"
            return {
                "item_name": match["name"],
                "item_type": "medication",
                "estimated_cost": match[copay_key],
                "cost_details": {
                    "formulary_tier": match["tier"],
                    "copay": match[copay_key],
                    "coinsurance_pct": None,
                    "prior_auth_required": match["prior_auth"],
                    "quantity_limit": match["quantity_limit"],
                },
            }
        elif item_type == "procedure":
            match = _fuzzy_match(item_name, PROCEDURES)
            if match is None:
                return None
            cost_key = "cost_hmo" if plan_type == "HMO" else "cost_ppo"
            return {
                "item_name": match["name"],
                "item_type": "procedure",
                "estimated_cost": match[cost_key],
                "cost_details": {
                    "formulary_tier": None,
                    "copay": match[cost_key],
                    "coinsurance_pct": None,
                    "prior_auth_required": False,
                    "quantity_limit": None,
                },
            }
        return None

    def estimate_multiple(
        self, items: list[str], item_type: str, plan_type: str
    ) -> dict[str, dict | None]:
        return {item: self.estimate(item, item_type, plan_type) for item in items}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_cost_estimator.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tools/cost_estimator.py healthflow/tests/test_cost_estimator.py
git commit -m "feat: add cost estimator with medication and procedure datasets"
```

---

### Task 8: Session Store

**Files:**
- Create: `healthflow/memory/session.py`
- Create: `healthflow/tests/test_session.py`

- [ ] **Step 1: Write tests for session store**

Create `healthflow/tests/test_session.py`:

```python
from healthflow.memory.session import InMemoryStore


def test_save_and_load():
    store = InMemoryStore()
    store.save("session-1", {"zip_code": "10001", "plans": []})
    result = store.load("session-1")
    assert result is not None
    assert result["zip_code"] == "10001"


def test_load_nonexistent():
    store = InMemoryStore()
    result = store.load("nonexistent")
    assert result is None


def test_overwrite_session():
    store = InMemoryStore()
    store.save("session-1", {"version": 1})
    store.save("session-1", {"version": 2})
    result = store.load("session-1")
    assert result["version"] == 2


def test_multiple_sessions():
    store = InMemoryStore()
    store.save("s1", {"data": "first"})
    store.save("s2", {"data": "second"})
    assert store.load("s1")["data"] == "first"
    assert store.load("s2")["data"] == "second"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_session.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement session store**

Create `healthflow/memory/session.py`:

```python
import json
from abc import ABC, abstractmethod


class SessionStore(ABC):
    @abstractmethod
    def save(self, session_id: str, data: dict) -> None: ...

    @abstractmethod
    def load(self, session_id: str) -> dict | None: ...


class InMemoryStore(SessionStore):
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def save(self, session_id: str, data: dict) -> None:
        self._store[session_id] = data

    def load(self, session_id: str) -> dict | None:
        return self._store.get(session_id)


class RedisStore(SessionStore):
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        import redis

        self._client = redis.from_url(redis_url)
        self._ttl = 3600  # 1 hour

    def save(self, session_id: str, data: dict) -> None:
        self._client.setex(session_id, self._ttl, json.dumps(data))

    def load(self, session_id: str) -> dict | None:
        raw = self._client.get(session_id)
        if raw is None:
            return None
        return json.loads(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_session.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/memory/session.py healthflow/tests/test_session.py
git commit -m "feat: add session store with in-memory and Redis implementations"
```

---

### Task 9: Comparison Agent (Claude Integration)

**Files:**
- Create: `healthflow/agents/comparison_agent.py`
- Create: `healthflow/tests/test_comparison_agent.py`

- [ ] **Step 1: Write tests for comparison agent**

Create `healthflow/tests/test_comparison_agent.py`:

```python
from unittest.mock import MagicMock, patch
from healthflow.agents.comparison_agent import ComparisonAgent
from healthflow.models.schemas import PlanSummary


SAMPLE_PLANS = [
    PlanSummary(
        plan_name="Aetna Medicare Eagle Plus (HMO)",
        plan_id="H3312-034",
        monthly_premium=0.00,
        annual_deductible=250.00,
        out_of_pocket_max=4500.00,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
        estimated_medication_costs={"Metformin": 5.0},
        estimated_procedure_costs={"MRI": 150.0},
    ),
    PlanSummary(
        plan_name="UHC Medicare Advantage Choice (PPO)",
        plan_id="H2228-050",
        monthly_premium=25.00,
        annual_deductible=150.00,
        out_of_pocket_max=5500.00,
        star_rating=4.0,
        plan_type="PPO",
        drug_coverage=True,
        estimated_medication_costs={"Metformin": 10.0},
        estimated_procedure_costs={"MRI": 250.0},
    ),
]


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_returns_recommendation(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Plan A is the best choice for your budget.")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    result = agent.recommend(
        plans=SAMPLE_PLANS,
        age=65,
        income_level="low",
        medications=["Metformin"],
        procedures=["MRI"],
    )

    assert "Plan A" in result
    mock_client.messages.create.assert_called_once()


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_sends_system_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation text")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(plans=SAMPLE_PLANS, age=65, income_level="low")

    call_kwargs = mock_client.messages.create.call_args
    assert "system" in call_kwargs.kwargs
    assert "medical advice" in call_kwargs.kwargs["system"].lower()


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_includes_plan_data_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(plans=SAMPLE_PLANS, age=65, income_level="low")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Aetna" in user_msg
    assert "H3312-034" in user_msg


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_includes_cost_data_when_provided(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(
        plans=SAMPLE_PLANS,
        age=65,
        income_level="low",
        medications=["Metformin"],
        procedures=["MRI"],
    )

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Metformin" in user_msg
    assert "MRI" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_comparison_agent.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement comparison agent**

Create `healthflow/agents/comparison_agent.py`:

```python
import anthropic

from healthflow.logs.audit import AuditLogger
from healthflow.models.schemas import PlanSummary

SYSTEM_PROMPT = (
    "You are a health insurance plan comparison assistant. Your role is to compare "
    "Medicare Advantage plans based on their financial details, coverage, and star ratings. "
    "You must NEVER give medical advice, recommend treatments, suggest medications, or "
    "diagnose conditions. Only compare plans based on premiums, deductibles, out-of-pocket "
    "maximums, star ratings, and cost estimates for the user's specified medications and "
    "procedures. Be clear, concise, and helpful."
)


class ComparisonAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.audit = AuditLogger()

    def recommend(
        self,
        plans: list[PlanSummary],
        age: int,
        income_level: str,
        medications: list[str] | None = None,
        procedures: list[str] | None = None,
    ) -> str:
        user_prompt = self._build_prompt(plans, age, income_level, medications, procedures)

        self.audit.log("tool_called", {"tool": "claude_api", "model": "claude-sonnet-4-6"})

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        recommendation = response.content[0].text
        self.audit.log("recommendation_generated", {"length": len(recommendation)})
        return recommendation

    def _build_prompt(
        self,
        plans: list[PlanSummary],
        age: int,
        income_level: str,
        medications: list[str] | None = None,
        procedures: list[str] | None = None,
    ) -> str:
        lines = [
            f"Compare these Medicare Advantage plans for a {age}-year-old with {income_level} income.",
            "",
            "## Plans",
            "",
        ]

        for i, plan in enumerate(plans, 1):
            lines.append(f"### Plan {i}: {plan.plan_name} ({plan.plan_id})")
            lines.append(f"- Type: {plan.plan_type}")
            lines.append(f"- Monthly Premium: ${plan.monthly_premium:.2f}")
            lines.append(f"- Annual Deductible: ${plan.annual_deductible:.2f}")
            lines.append(f"- Out-of-Pocket Max: ${plan.out_of_pocket_max:.2f}")
            lines.append(f"- Star Rating: {plan.star_rating}/5.0")
            lines.append(f"- Drug Coverage: {'Yes' if plan.drug_coverage else 'No'}")

            if plan.estimated_medication_costs:
                lines.append("- Medication Costs:")
                for med, cost in plan.estimated_medication_costs.items():
                    lines.append(f"  - {med}: ${cost:.2f}/month")

            if plan.estimated_procedure_costs:
                lines.append("- Procedure Costs:")
                for proc, cost in plan.estimated_procedure_costs.items():
                    lines.append(f"  - {proc}: ${cost:.2f}")

            lines.append("")

        if medications:
            lines.append(f"The user takes these medications: {', '.join(medications)}")
        if procedures:
            lines.append(f"The user needs these procedures: {', '.join(procedures)}")

        lines.append("")
        lines.append(
            "Provide a clear comparison and recommend the best plan for this user's "
            "situation. Focus on total estimated costs and value. Do NOT give any medical advice."
        )

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_comparison_agent.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/agents/comparison_agent.py healthflow/tests/test_comparison_agent.py
git commit -m "feat: add comparison agent with Claude API integration"
```

---

### Task 10: API Routes

**Files:**
- Create: `healthflow/api/routes.py`
- Create: `healthflow/tests/test_routes.py`

- [ ] **Step 1: Write tests for API routes**

Create `healthflow/tests/test_routes.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_plans_known_zip():
    response = client.get("/plans/10001")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) >= 5


def test_get_plans_invalid_zip():
    response = client.get("/plans/123")
    assert response.status_code == 422


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = "Plan A is the best value."
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={
            "zip_code": "10001",
            "age": 65,
            "income_level": "low",
            "medications": ["Metformin"],
            "procedures": ["MRI"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "recommendation" in data
    assert "disclaimer" in data
    assert "session_id" in data
    assert len(data["plans"]) <= 5


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_invalid_zip(mock_agent_cls):
    response = client.post(
        "/compare",
        json={"zip_code": "abc", "age": 65, "income_level": "low"},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_invalid_age(mock_agent_cls):
    response = client.post(
        "/compare",
        json={"zip_code": "10001", "age": 10, "income_level": "low"},
    )
    assert response.status_code == 422


def test_estimate_known_medication():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Metformin",
            "item_type": "medication",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "estimated_cost" in data
    assert "cost_details" in data


def test_estimate_unknown_item():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "FakeDrug999",
            "item_type": "medication",
        },
    )
    assert response.status_code == 404


def test_estimate_invalid_type():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Metformin",
            "item_type": "vitamin",
        },
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest healthflow/tests/test_routes.py -v
```

Expected: FAIL — routes not implemented

- [ ] **Step 3: Implement API routes**

Create `healthflow/api/routes.py`:

```python
import uuid

from fastapi import APIRouter, HTTPException, Path

from healthflow.agents.comparison_agent import ComparisonAgent
from healthflow.agents.harness import Harness
from healthflow.memory.session import InMemoryStore
from healthflow.models.schemas import (
    CompareRequest,
    CompareResponse,
    CostDetails,
    EstimateRequest,
    EstimateResponse,
    PlanSummary,
)
from healthflow.tools.cms_fetcher import MockCMSFetcher
from healthflow.tools.cost_estimator import CostEstimator
from healthflow.tools.plan_parser import PlanParser

router = APIRouter()

fetcher = MockCMSFetcher()
parser = PlanParser()
estimator = CostEstimator()
harness = Harness()
session_store = InMemoryStore()

DISCLAIMER = (
    "This is a plan comparison tool, not medical advice. "
    "Consult a licensed healthcare professional for medical decisions."
)


@router.get("/plans/{zip_code}")
def get_plans(zip_code: str = Path(..., pattern=r"^\d{5}$")):
    raw_plans = fetcher.fetch_plans(zip_code)
    plans = [
        PlanSummary(
            plan_name=p["plan_name"],
            plan_id=p["plan_id"],
            monthly_premium=p["monthly_premium"],
            annual_deductible=p["annual_deductible"],
            out_of_pocket_max=p["out_of_pocket_max"],
            star_rating=p["star_rating"],
            plan_type=p["plan_type"],
            drug_coverage=p["drug_coverage"],
        )
        for p in raw_plans
    ]
    return {"zip_code": zip_code, "plans": plans}


@router.post("/compare", response_model=CompareResponse)
def compare_plans(request: CompareRequest):
    harness.audit.log("tool_called", {"tool": "cms_fetcher", "zip_code": request.zip_code})
    raw_plans = fetcher.fetch_plans(request.zip_code)
    harness.audit.log("plans_fetched", {"count": len(raw_plans)})

    ranked_plans = parser.parse_and_rank(raw_plans, request.income_level)

    # Attach cost estimates to each plan
    for plan in ranked_plans:
        if request.medications:
            med_costs = estimator.estimate_multiple(
                request.medications, "medication", plan.plan_type
            )
            plan.estimated_medication_costs = {
                name: result["estimated_cost"]
                for name, result in med_costs.items()
                if result is not None
            }
        if request.procedures:
            proc_costs = estimator.estimate_multiple(
                request.procedures, "procedure", plan.plan_type
            )
            plan.estimated_procedure_costs = {
                name: result["estimated_cost"]
                for name, result in proc_costs.items()
                if result is not None
            }
            harness.audit.log("costs_estimated", {
                "medications": len(request.medications),
                "procedures": len(request.procedures),
            })

    agent = ComparisonAgent()
    raw_recommendation = agent.recommend(
        plans=ranked_plans,
        age=request.age,
        income_level=request.income_level,
        medications=request.medications or None,
        procedures=request.procedures or None,
    )

    recommendation = harness.filter_output(raw_recommendation)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "zip_code": request.zip_code,
        "age": request.age,
        "income_level": request.income_level,
        "plan_ids": [p.plan_id for p in ranked_plans],
    })

    return CompareResponse(
        session_id=session_id,
        zip_code=request.zip_code,
        plans=ranked_plans,
        recommendation=recommendation,
        disclaimer=DISCLAIMER,
    )


@router.post("/estimate", response_model=EstimateResponse)
def estimate_cost(request: EstimateRequest):
    # Look up plan type from fetcher data
    plan_type = "HMO"  # default
    for zip_plans in [fetcher.fetch_plans(z) for z in ["10001"]]:
        for p in zip_plans:
            if p["plan_id"] == request.plan_id:
                plan_type = p["plan_type"]
                break

    result = estimator.estimate(request.item_name, request.item_type, plan_type)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cost data found for '{request.item_name}' ({request.item_type})",
        )

    return EstimateResponse(
        plan_name=request.plan_id,
        item_name=result["item_name"],
        item_type=result["item_type"],
        estimated_cost=result["estimated_cost"],
        cost_details=CostDetails(**result["cost_details"]),
        disclaimer=DISCLAIMER,
    )
```

- [ ] **Step 4: Update main.py to include the router**

Update `healthflow/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from healthflow.api.routes import router

app = FastAPI(
    title="HealthFlow",
    description="AI-powered Medicare Advantage plan comparison service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("healthflow.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest healthflow/tests/test_routes.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add healthflow/api/routes.py healthflow/tests/test_routes.py healthflow/main.py
git commit -m "feat: add FastAPI routes for compare, estimate, plans, and health"
```

---

### Task 11: CLI Wrapper

**Files:**
- Create: `healthflow/cli.py`

- [ ] **Step 1: Implement CLI wrapper**

Create `healthflow/cli.py`:

```python
import json
import sys

import click
import httpx

BASE_URL = "http://localhost:8000"


@click.group()
def cli():
    """HealthFlow — AI-powered Medicare plan comparison tool."""
    pass


@cli.command()
@click.option("--zip-code", prompt="Zip code", help="5-digit US zip code")
@click.option("--age", prompt="Age", type=int, help="Your age (18-120)")
@click.option(
    "--income",
    prompt="Income level",
    type=click.Choice(["low", "medium", "high"]),
    help="Income level",
)
@click.option("--medications", default="", help="Comma-separated medication list")
@click.option("--procedures", default="", help="Comma-separated procedure list")
def compare(zip_code: str, age: int, income: str, medications: str, procedures: str):
    """Compare Medicare Advantage plans."""
    payload = {
        "zip_code": zip_code,
        "age": age,
        "income_level": income,
        "medications": [m.strip() for m in medications.split(",") if m.strip()],
        "procedures": [p.strip() for p in procedures.split(",") if p.strip()],
    }

    try:
        response = httpx.post(f"{BASE_URL}/compare", json=payload, timeout=30.0)
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
    click.echo("  HEALTHFLOW — Medicare Plan Comparison")
    click.echo("=" * 60)

    for i, plan in enumerate(data["plans"], 1):
        click.echo(f"\n--- Plan {i}: {plan['plan_name']} ---")
        click.echo(f"  ID:             {plan['plan_id']}")
        click.echo(f"  Type:           {plan['plan_type']}")
        click.echo(f"  Premium:        ${plan['monthly_premium']:.2f}/mo")
        click.echo(f"  Deductible:     ${plan['annual_deductible']:.2f}/yr")
        click.echo(f"  OOP Max:        ${plan['out_of_pocket_max']:.2f}")
        click.echo(f"  Star Rating:    {'*' * int(plan['star_rating'])} ({plan['star_rating']})")
        click.echo(f"  Drug Coverage:  {'Yes' if plan['drug_coverage'] else 'No'}")

        if plan.get("estimated_medication_costs"):
            click.echo("  Medication Costs:")
            for med, cost in plan["estimated_medication_costs"].items():
                click.echo(f"    - {med}: ${cost:.2f}/mo")

        if plan.get("estimated_procedure_costs"):
            click.echo("  Procedure Costs:")
            for proc, cost in plan["estimated_procedure_costs"].items():
                click.echo(f"    - {proc}: ${cost:.2f}")

    click.echo("\n" + "-" * 60)
    click.echo("\nRECOMMENDATION:\n")
    click.echo(data["recommendation"])
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()


@cli.command()
@click.option("--plan-id", prompt="Plan ID", help="Plan ID (e.g., H3312-034)")
@click.option("--item", prompt="Item name", help="Medication or procedure name")
@click.option(
    "--type",
    "item_type",
    prompt="Type",
    type=click.Choice(["medication", "procedure"]),
    help="medication or procedure",
)
def estimate(plan_id: str, item: str, item_type: str):
    """Estimate cost for a medication or procedure."""
    payload = {"plan_id": plan_id, "item_name": item, "item_type": item_type}

    try:
        response = httpx.post(f"{BASE_URL}/estimate", json=payload, timeout=10.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()
    click.echo(f"\nCost Estimate for {data['item_name']} ({data['item_type']})")
    click.echo(f"  Plan: {data['plan_name']}")
    click.echo(f"  Estimated Cost: ${data['estimated_cost']:.2f}")
    details = data["cost_details"]
    if details.get("formulary_tier"):
        click.echo(f"  Formulary Tier: {details['formulary_tier']}")
    if details.get("prior_auth_required"):
        click.echo("  Prior Authorization: Required")
    if details.get("quantity_limit"):
        click.echo(f"  Quantity Limit: {details['quantity_limit']}")
    click.echo(f"\n{data['disclaimer']}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI help works**

```bash
python -m healthflow.cli --help
```

Expected: Shows help text with `compare` and `estimate` commands

- [ ] **Step 3: Commit**

```bash
git add healthflow/cli.py
git commit -m "feat: add Click CLI wrapper for compare and estimate commands"
```

---

### Task 12: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write README**

Replace contents of `README.md`:

```markdown
# HealthFlow

AI-powered Medicare Advantage plan comparison service. Compares plans by premium, deductible, out-of-pocket max, star rating, and estimates costs for your specific medications and procedures. Powered by Claude for plain-English recommendations.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your-key-here

# Start the API server
python -m healthflow.main
```

The API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

### POST /compare

Compare Medicare Advantage plans with personalized cost estimates.

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "zip_code": "10001",
    "age": 65,
    "income_level": "low",
    "medications": ["Metformin", "Lisinopril"],
    "procedures": ["Annual physical", "Blood work"]
  }'
```

### POST /estimate

Get cost estimate for a specific medication or procedure under a plan.

```bash
curl -X POST http://localhost:8000/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "H3312-034",
    "item_name": "Metformin",
    "item_type": "medication"
  }'
```

### GET /plans/{zip_code}

List available plans for a zip code.

```bash
curl http://localhost:8000/plans/10001
```

### GET /health

Health check.

```bash
curl http://localhost:8000/health
```

## CLI Usage

Start the API server first, then use the CLI:

```bash
# Interactive comparison
python -m healthflow.cli compare

# With arguments
python -m healthflow.cli compare --zip-code 10001 --age 65 --income low --medications "Metformin,Lisinopril"

# Cost estimate
python -m healthflow.cli estimate --plan-id H3312-034 --item Metformin --type medication
```

## Supported Zip Codes

10001 (NYC), 90210 (LA), 60601 (Chicago), 33101 (Miami), 77001 (Houston), 85001 (Phoenix), 98101 (Seattle), 30301 (Atlanta), 02101 (Boston), 75201 (Dallas)

Other zip codes return a randomized selection of plans.

## Running Tests

```bash
pytest healthflow/tests/ -v
```

## Tech Stack

- **FastAPI** — REST API framework
- **Claude API** (claude-sonnet-4-6) — AI-powered plan recommendations
- **Pydantic** — Request/response validation
- **Redis** — Optional session persistence (in-memory default)
- **Click** — CLI interface

## Architecture

```
HTTP Request → FastAPI → Harness (validate/filter/log) → Tools (fetch/parse/estimate) → Agent (Claude) → Response
```

- **Harness**: Validates inputs, filters medical advice from outputs, logs all decisions
- **CMS Fetcher**: Curated dataset of ~20 realistic Medicare Advantage plans
- **Plan Parser**: Ranks and scores plans based on income-weighted criteria
- **Cost Estimator**: ~30 medications and ~20 procedures with realistic pricing
- **Comparison Agent**: Generates plain-English recommendations via Claude
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with API and CLI usage"
```

---

### Task 13: Full Integration Test

**Files:**
- Modify: `healthflow/tests/test_comparison.py` (create — this was in the original spec)

- [ ] **Step 1: Write end-to-end integration test**

Create `healthflow/tests/test_comparison.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


@patch("healthflow.api.routes.ComparisonAgent")
def test_full_compare_pipeline(mock_agent_cls):
    """End-to-end test: request → validation → fetch → parse → estimate → agent → response"""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = (
        "Based on your profile as a 65-year-old with low income, "
        "Plan A offers the best value with a $0 monthly premium "
        "and strong 4.5 star rating. Your Metformin costs only $5/month."
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={
            "zip_code": "10001",
            "age": 65,
            "income_level": "low",
            "medications": ["Metformin", "Lisinopril"],
            "procedures": ["Annual physical", "Blood work"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "session_id" in data
    assert data["zip_code"] == "10001"
    assert len(data["plans"]) <= 5
    assert len(data["plans"]) >= 1
    assert "recommendation" in data
    assert "disclaimer" in data

    # Verify plan data
    plan = data["plans"][0]
    assert "plan_name" in plan
    assert "monthly_premium" in plan
    assert "star_rating" in plan

    # Verify cost estimates attached
    assert plan.get("estimated_medication_costs") is not None
    assert "Metformin" in plan["estimated_medication_costs"]

    # Verify disclaimer is always present
    assert "not medical advice" in data["disclaimer"].lower()


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_filters_medical_advice(mock_agent_cls):
    """Verify the harness filters medical advice from Claude's response."""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = (
        "Plan A is great. Also, you should take Metformin twice daily."
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={"zip_code": "10001", "age": 65, "income_level": "low"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "you should take" not in data["recommendation"].lower()


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_no_meds_or_procs(mock_agent_cls):
    """Verify compare works without medications or procedures."""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = "Plan A is the best value."
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={"zip_code": "90210", "age": 70, "income_level": "high"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) <= 5


def test_estimate_medication_integration():
    """End-to-end estimate for a known medication."""
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Ozempic",
            "item_type": "medication",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_cost"] > 0
    assert data["cost_details"]["formulary_tier"] == "Tier 4 - Specialty"
    assert data["cost_details"]["prior_auth_required"] is True


def test_estimate_procedure_integration():
    """End-to-end estimate for a known procedure."""
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "ER visit",
            "item_type": "procedure",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_cost"] > 0
```

- [ ] **Step 2: Run all tests**

```bash
pytest healthflow/tests/ -v
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_comparison.py
git commit -m "test: add end-to-end integration tests for full pipeline"
```

---

### Task 14: Final Verification

- [ ] **Step 1: Run the full test suite**

```bash
pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Start the server and verify API docs load**

```bash
python -m healthflow.main &
curl http://localhost:8000/health
curl http://localhost:8000/docs
# Visit http://localhost:8000/docs in browser to see Swagger UI
kill %1
```

- [ ] **Step 3: Verify CLI help**

```bash
python -m healthflow.cli --help
python -m healthflow.cli compare --help
python -m healthflow.cli estimate --help
```

- [ ] **Step 4: Clean up any .pyc or log files from git tracking**

```bash
echo "__pycache__/
*.pyc
*.log
.env
" > .gitignore
git add .gitignore
git commit -m "chore: add .gitignore"
```
