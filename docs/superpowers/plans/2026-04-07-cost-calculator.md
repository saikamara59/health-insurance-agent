# Cost Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/calculate` endpoint that estimates annual out-of-pocket costs per plan based on a user's expected healthcare usage (doctor visits, prescriptions, procedures), ranking plans by total cost.

**Architecture:** A CostModeler does pure math (copay accumulation, deductible tracking, OOP max cap) per plan. A CostCalculatorAgent orchestrates the modeler across plans and calls Claude for a recommendation. The endpoint integrates with existing session data from `/compare` or works standalone.

**Tech Stack:** Python, FastAPI, Anthropic SDK, Pydantic, pytest

---

### Task 1: Pydantic Models for Cost Calculator

**Files:**
- Modify: `healthflow/models/schemas.py`
- Create: `healthflow/tests/test_calculate_schemas.py`

- [ ] **Step 1: Write tests for the new models**

Create `healthflow/tests/test_calculate_schemas.py`:

```python
import pytest
from healthflow.models.schemas import (
    CalculateRequest,
    CalculateResponse,
    CostBreakdown,
    PlanCostResult,
    PrescriptionDetail,
    PrescriptionInput,
    ProcedureDetail,
    ProcedureInput,
    UsageInput,
)


def test_usage_input_valid():
    usage = UsageInput(
        doctor_visits_per_year=12,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
        procedures=[ProcedureInput(name="MRI", count=2)],
    )
    assert usage.doctor_visits_per_year == 12
    assert len(usage.prescriptions) == 1
    assert len(usage.procedures) == 1


def test_usage_input_zero_visits():
    usage = UsageInput(doctor_visits_per_year=0)
    assert usage.doctor_visits_per_year == 0


def test_usage_input_visits_too_high():
    with pytest.raises(ValueError):
        UsageInput(doctor_visits_per_year=366)


def test_prescription_input_fills_too_low():
    with pytest.raises(ValueError):
        PrescriptionInput(name="Metformin", fills_per_year=0)


def test_procedure_input_count_too_high():
    with pytest.raises(ValueError):
        ProcedureInput(name="MRI", count=366)


def test_calculate_request_with_session():
    req = CalculateRequest(
        session_id="abc-123",
        usage=UsageInput(doctor_visits_per_year=6),
    )
    assert req.session_id == "abc-123"
    assert req.zip_code is None


def test_calculate_request_with_zip():
    req = CalculateRequest(
        zip_code="10001",
        income_level="low",
        usage=UsageInput(doctor_visits_per_year=6),
    )
    assert req.zip_code == "10001"
    assert req.session_id is None


def test_calculate_request_missing_both():
    with pytest.raises(ValueError, match="session_id.*zip_code"):
        CalculateRequest(
            usage=UsageInput(doctor_visits_per_year=6),
        )


def test_calculate_request_zip_without_income():
    with pytest.raises(ValueError, match="income_level"):
        CalculateRequest(
            zip_code="10001",
            usage=UsageInput(doctor_visits_per_year=6),
        )


def test_cost_breakdown_model():
    breakdown = CostBreakdown(
        premium_total=0.0,
        deductible_spent=0.0,
        doctor_visit_costs=240.0,
        prescription_costs=60.0,
        procedure_costs=300.0,
        total_before_oop_cap=600.0,
        oop_cap_applied=False,
        final_care_cost=600.0,
    )
    assert breakdown.final_care_cost == 600.0
    assert breakdown.oop_cap_applied is False


def test_plan_cost_result_model():
    result = PlanCostResult(
        plan_name="Test Plan",
        plan_id="H0001-001",
        annual_premium=0.0,
        annual_care_cost=600.0,
        total_annual_cost=600.0,
        breakdown=CostBreakdown(
            premium_total=0.0,
            deductible_spent=0.0,
            doctor_visit_costs=240.0,
            prescription_costs=60.0,
            procedure_costs=300.0,
            total_before_oop_cap=600.0,
            oop_cap_applied=False,
            final_care_cost=600.0,
        ),
        prescription_details=[
            PrescriptionDetail(name="Metformin", cost_per_fill=5.0, annual_cost=60.0)
        ],
        procedure_details=[
            ProcedureDetail(name="MRI", cost_per_visit=150.0, annual_cost=300.0)
        ],
    )
    assert result.total_annual_cost == 600.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_calculate_schemas.py -v
```

Expected: FAIL — `ImportError: cannot import name 'CalculateRequest'`

- [ ] **Step 3: Add models to schemas.py**

Append the following to the end of `healthflow/models/schemas.py` (after the `TranslateResponse` class at line 116):

```python


class PrescriptionInput(BaseModel):
    name: str
    fills_per_year: int = Field(..., ge=1, le=365)


class ProcedureInput(BaseModel):
    name: str
    count: int = Field(..., ge=1, le=365)


class UsageInput(BaseModel):
    doctor_visits_per_year: int = Field(..., ge=0, le=365)
    prescriptions: list[PrescriptionInput] = Field(
        default_factory=list, max_length=20
    )
    procedures: list[ProcedureInput] = Field(
        default_factory=list, max_length=20
    )


class CalculateRequest(BaseModel):
    session_id: str | None = None
    zip_code: str | None = None
    income_level: str | None = None
    usage: UsageInput

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str | None) -> str | None:
        if v is not None and (len(v) != 5 or not v.isdigit()):
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str | None) -> str | None:
        if v is not None and v not in {"low", "medium", "high"}:
            raise ValueError("Income level must be one of: high, low, medium")
        return v

    def model_post_init(self, __context: object) -> None:
        if self.session_id is None and self.zip_code is None:
            raise ValueError(
                "Either session_id or zip_code must be provided"
            )
        if self.session_id is None and self.income_level is None:
            raise ValueError(
                "income_level is required when using zip_code instead of session_id"
            )


class PrescriptionDetail(BaseModel):
    name: str
    cost_per_fill: float
    annual_cost: float


class ProcedureDetail(BaseModel):
    name: str
    cost_per_visit: float
    annual_cost: float


class CostBreakdown(BaseModel):
    premium_total: float
    deductible_spent: float
    doctor_visit_costs: float
    prescription_costs: float
    procedure_costs: float
    total_before_oop_cap: float
    oop_cap_applied: bool
    final_care_cost: float


class PlanCostResult(BaseModel):
    plan_name: str
    plan_id: str
    annual_premium: float
    annual_care_cost: float
    total_annual_cost: float
    breakdown: CostBreakdown
    prescription_details: list[PrescriptionDetail]
    procedure_details: list[ProcedureDetail]


class CalculateResponse(BaseModel):
    session_id: str
    plans: list[PlanCostResult]
    recommendation: str
    disclaimer: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_calculate_schemas.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add healthflow/models/schemas.py healthflow/tests/test_calculate_schemas.py
git commit -m "feat: add Pydantic models for cost calculator endpoint"
```

---

### Task 2: Cost Modeler

**Files:**
- Create: `healthflow/tools/cost_modeler.py`
- Create: `healthflow/tests/test_cost_modeler.py`

- [ ] **Step 1: Write tests for cost modeler**

Create `healthflow/tests/test_cost_modeler.py`:

```python
from healthflow.models.schemas import (
    PlanSummary,
    PrescriptionInput,
    ProcedureInput,
    UsageInput,
)
from healthflow.tools.cost_modeler import CostModeler


def _make_plan(
    plan_type: str = "HMO",
    monthly_premium: float = 0.0,
    annual_deductible: float = 0.0,
    out_of_pocket_max: float = 5000.0,
) -> PlanSummary:
    return PlanSummary(
        plan_name="Test Plan",
        plan_id="H0001-001",
        monthly_premium=monthly_premium,
        annual_deductible=annual_deductible,
        out_of_pocket_max=out_of_pocket_max,
        star_rating=4.0,
        plan_type=plan_type,
        drug_coverage=True,
    )


def test_zero_usage_only_premium():
    modeler = CostModeler()
    plan = _make_plan(monthly_premium=50.0)
    usage = UsageInput(doctor_visits_per_year=0)
    result = modeler.calculate(plan, usage)
    assert result.annual_premium == 600.0
    assert result.annual_care_cost == 0.0
    assert result.total_annual_cost == 600.0


def test_doctor_visits_hmo_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(doctor_visits_per_year=12)
    result = modeler.calculate(plan, usage)
    # HMO doctor visit copay is $20
    assert result.breakdown.doctor_visit_costs == 240.0


def test_doctor_visits_ppo_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="PPO")
    usage = UsageInput(doctor_visits_per_year=12)
    result = modeler.calculate(plan, usage)
    # PPO doctor visit copay is $40
    assert result.breakdown.doctor_visit_costs == 480.0


def test_prescription_costs():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    # Metformin HMO copay is $5
    assert result.breakdown.prescription_costs == 60.0
    assert len(result.prescription_details) == 1
    assert result.prescription_details[0].cost_per_fill == 5.0
    assert result.prescription_details[0].annual_cost == 60.0


def test_procedure_costs():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        procedures=[ProcedureInput(name="MRI", count=2)],
    )
    result = modeler.calculate(plan, usage)
    # MRI HMO cost is $150
    assert result.breakdown.procedure_costs == 300.0
    assert len(result.procedure_details) == 1
    assert result.procedure_details[0].cost_per_visit == 150.0
    assert result.procedure_details[0].annual_cost == 300.0


def test_oop_max_cap_applied():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO", out_of_pocket_max=200.0)
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="Humira", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    # Humira HMO is $150/fill * 12 = $1800, but OOP max is $200
    assert result.breakdown.oop_cap_applied is True
    assert result.annual_care_cost == 200.0
    assert result.breakdown.final_care_cost == 200.0


def test_unknown_drug_default_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="UnknownDrug999", fills_per_year=4)],
    )
    result = modeler.calculate(plan, usage)
    # Default copay for unknown drugs is $25
    assert result.breakdown.prescription_costs == 100.0
    assert result.prescription_details[0].cost_per_fill == 25.0


def test_unknown_procedure_default_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        procedures=[ProcedureInput(name="Brain Transplant", count=1)],
    )
    result = modeler.calculate(plan, usage)
    # Default copay for unknown procedures is $100
    assert result.breakdown.procedure_costs == 100.0
    assert result.procedure_details[0].cost_per_visit == 100.0


def test_total_cost_includes_premium_and_care():
    modeler = CostModeler()
    plan = _make_plan(monthly_premium=25.0, plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=6,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    # Premium: $25 * 12 = $300
    # Doctor visits: $20 * 6 = $120
    # Rx: $5 * 12 = $60
    # Total care: $180
    # Total: $300 + $180 = $480
    assert result.annual_premium == 300.0
    assert result.annual_care_cost == 180.0
    assert result.total_annual_cost == 480.0


def test_deductible_tracking():
    modeler = CostModeler()
    plan = _make_plan(annual_deductible=250.0, plan_type="HMO")
    usage = UsageInput(doctor_visits_per_year=6)
    result = modeler.calculate(plan, usage)
    # Doctor visits: $20 * 6 = $120, deductible is $250 but care is only $120
    assert result.breakdown.deductible_spent == 120.0
    assert result.breakdown.doctor_visit_costs == 120.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_cost_modeler.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement cost modeler**

Create `healthflow/tools/cost_modeler.py`:

```python
from healthflow.models.schemas import (
    CostBreakdown,
    PlanCostResult,
    PlanSummary,
    PrescriptionDetail,
    ProcedureDetail,
    UsageInput,
)
from healthflow.tools.cost_estimator import CostEstimator

DOCTOR_VISIT_COPAY = {"HMO": 20.0, "PPO": 40.0}
DEFAULT_DRUG_COPAY = 25.0
DEFAULT_PROCEDURE_COPAY = 100.0


class CostModeler:
    def __init__(self) -> None:
        self.estimator = CostEstimator()

    def calculate(self, plan: PlanSummary, usage: UsageInput) -> PlanCostResult:
        annual_premium = plan.monthly_premium * 12

        # Doctor visit costs
        visit_copay = DOCTOR_VISIT_COPAY.get(plan.plan_type, 40.0)
        doctor_visit_costs = visit_copay * usage.doctor_visits_per_year

        # Prescription costs
        prescription_details: list[PrescriptionDetail] = []
        prescription_costs = 0.0
        for rx in usage.prescriptions:
            estimate = self.estimator.estimate(rx.name, "medication", plan.plan_type)
            if estimate is not None:
                cost_per_fill = estimate["estimated_cost"]
            else:
                cost_per_fill = DEFAULT_DRUG_COPAY
            annual_cost = cost_per_fill * rx.fills_per_year
            prescription_costs += annual_cost
            prescription_details.append(
                PrescriptionDetail(
                    name=rx.name,
                    cost_per_fill=cost_per_fill,
                    annual_cost=annual_cost,
                )
            )

        # Procedure costs
        procedure_details: list[ProcedureDetail] = []
        procedure_costs = 0.0
        for proc in usage.procedures:
            estimate = self.estimator.estimate(proc.name, "procedure", plan.plan_type)
            if estimate is not None:
                cost_per_visit = estimate["estimated_cost"]
            else:
                cost_per_visit = DEFAULT_PROCEDURE_COPAY
            annual_cost = cost_per_visit * proc.count
            procedure_costs += annual_cost
            procedure_details.append(
                ProcedureDetail(
                    name=proc.name,
                    cost_per_visit=cost_per_visit,
                    annual_cost=annual_cost,
                )
            )

        # Total care costs before caps
        total_care = doctor_visit_costs + prescription_costs + procedure_costs

        # Deductible tracking
        deductible_spent = min(plan.annual_deductible, total_care)

        # OOP max cap
        oop_cap_applied = total_care > plan.out_of_pocket_max
        final_care_cost = min(total_care, plan.out_of_pocket_max)

        return PlanCostResult(
            plan_name=plan.plan_name,
            plan_id=plan.plan_id,
            annual_premium=annual_premium,
            annual_care_cost=final_care_cost,
            total_annual_cost=annual_premium + final_care_cost,
            breakdown=CostBreakdown(
                premium_total=annual_premium,
                deductible_spent=deductible_spent,
                doctor_visit_costs=doctor_visit_costs,
                prescription_costs=prescription_costs,
                procedure_costs=procedure_costs,
                total_before_oop_cap=total_care,
                oop_cap_applied=oop_cap_applied,
                final_care_cost=final_care_cost,
            ),
            prescription_details=prescription_details,
            procedure_details=procedure_details,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_cost_modeler.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tools/cost_modeler.py healthflow/tests/test_cost_modeler.py
git commit -m "feat: add cost modeler with copay accumulation and OOP cap"
```

---

### Task 3: Cost Calculator Agent

**Files:**
- Create: `healthflow/agents/cost_calculator_agent.py`
- Create: `healthflow/tests/test_cost_calculator_agent.py`

- [ ] **Step 1: Write tests for cost calculator agent**

Create `healthflow/tests/test_cost_calculator_agent.py`:

```python
from unittest.mock import MagicMock, patch
from healthflow.agents.cost_calculator_agent import CostCalculatorAgent
from healthflow.models.schemas import (
    PlanSummary,
    PrescriptionInput,
    UsageInput,
)


SAMPLE_PLANS = [
    PlanSummary(
        plan_name="Expensive Plan",
        plan_id="H0001-001",
        monthly_premium=100.0,
        annual_deductible=500.0,
        out_of_pocket_max=8000.0,
        star_rating=3.0,
        plan_type="PPO",
        drug_coverage=True,
    ),
    PlanSummary(
        plan_name="Cheap Plan",
        plan_id="H0001-002",
        monthly_premium=0.0,
        annual_deductible=0.0,
        out_of_pocket_max=4000.0,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
    ),
]

SAMPLE_USAGE = UsageInput(
    doctor_visits_per_year=12,
    prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
)


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_returns_sorted_results(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Cheap Plan saves you money.")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    results, recommendation = agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    # Cheap Plan (HMO, $0 premium) should be cheaper than Expensive Plan (PPO, $100/mo)
    assert results[0].plan_id == "H0001-002"
    assert results[0].total_annual_cost < results[1].total_annual_cost


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_calls_claude(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation text.")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    _, recommendation = agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    mock_client.messages.create.assert_called_once()
    assert recommendation == "Recommendation text."


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_system_prompt_no_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Text")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_prompt_includes_cost_data(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Text")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Cheap Plan" in user_msg
    assert "Expensive Plan" in user_msg
    assert "Metformin" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_cost_calculator_agent.py -v
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement cost calculator agent**

Create `healthflow/agents/cost_calculator_agent.py`:

```python
import anthropic

from healthflow.logs.audit import AuditLogger
from healthflow.models.schemas import PlanCostResult, PlanSummary, UsageInput
from healthflow.tools.cost_modeler import CostModeler

SYSTEM_PROMPT = (
    "You are a health insurance cost comparison assistant. Compare plans based on "
    "estimated annual out-of-pocket costs. Focus on total cost (premium + care costs), "
    "not just premium. Highlight which plan saves the most money for the user's specific "
    "usage pattern. Break down where the savings come from. Never give medical advice."
)


class CostCalculatorAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.audit = AuditLogger()
        self.modeler = CostModeler()

    def calculate(
        self,
        plans: list[PlanSummary],
        usage: UsageInput,
    ) -> tuple[list[PlanCostResult], str]:
        # Calculate costs for each plan
        results = [self.modeler.calculate(plan, usage) for plan in plans]

        # Sort by total annual cost (cheapest first)
        results.sort(key=lambda r: r.total_annual_cost)

        # Get Claude recommendation
        user_prompt = self._build_prompt(results, usage)

        self.audit.log(
            "tool_called",
            {"tool": "claude_api", "model": "claude-sonnet-4-6", "task": "calculate"},
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        recommendation = response.content[0].text
        self.audit.log(
            "recommendation_generated",
            {"length": len(recommendation), "task": "calculate"},
        )

        return results, recommendation

    def _build_prompt(
        self,
        results: list[PlanCostResult],
        usage: UsageInput,
    ) -> str:
        lines = [
            "Compare these Medicare Advantage plans by estimated annual out-of-pocket cost.",
            "",
            f"User's expected usage: {usage.doctor_visits_per_year} doctor visits/year",
        ]

        if usage.prescriptions:
            rx_list = ", ".join(
                f"{rx.name} ({rx.fills_per_year}x/year)" for rx in usage.prescriptions
            )
            lines.append(f"Prescriptions: {rx_list}")

        if usage.procedures:
            proc_list = ", ".join(
                f"{p.name} ({p.count}x/year)" for p in usage.procedures
            )
            lines.append(f"Procedures: {proc_list}")

        lines.append("")
        lines.append("## Plans (ranked by total cost, cheapest first)")
        lines.append("")

        for i, r in enumerate(results, 1):
            lines.append(f"### #{i}: {r.plan_name} ({r.plan_id})")
            lines.append(f"- Annual Premium: ${r.annual_premium:.2f}")
            lines.append(f"- Annual Care Cost: ${r.annual_care_cost:.2f}")
            lines.append(f"- **Total Annual Cost: ${r.total_annual_cost:.2f}**")
            lines.append(f"- Doctor Visits: ${r.breakdown.doctor_visit_costs:.2f}")
            lines.append(f"- Prescriptions: ${r.breakdown.prescription_costs:.2f}")
            lines.append(f"- Procedures: ${r.breakdown.procedure_costs:.2f}")
            if r.breakdown.oop_cap_applied:
                lines.append(f"- OOP Max Cap Applied (saved ${r.breakdown.total_before_oop_cap - r.breakdown.final_care_cost:.2f})")

            if r.prescription_details:
                for rx in r.prescription_details:
                    lines.append(f"  - {rx.name}: ${rx.cost_per_fill:.2f}/fill x {int(rx.annual_cost / rx.cost_per_fill)} = ${rx.annual_cost:.2f}/year")

            lines.append("")

        lines.append(
            "Recommend the best plan for this user's usage. Focus on total annual cost "
            "and where the savings come from. Do NOT give medical advice."
        )

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_cost_calculator_agent.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/agents/cost_calculator_agent.py healthflow/tests/test_cost_calculator_agent.py
git commit -m "feat: add cost calculator agent with Claude recommendation"
```

---

### Task 4: Add /calculate API Route

**Files:**
- Modify: `healthflow/api/routes.py`
- Create: `healthflow/tests/test_calculate_route.py`

- [ ] **Step 1: Write tests for the calculate route**

Create `healthflow/tests/test_calculate_route.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_with_zip_code(mock_agent_cls):
    mock_agent = MagicMock()
    mock_results = [MagicMock()]
    mock_results[0].model_dump.return_value = {
        "plan_name": "Test Plan",
        "plan_id": "H0001-001",
        "annual_premium": 0.0,
        "annual_care_cost": 240.0,
        "total_annual_cost": 240.0,
        "breakdown": {
            "premium_total": 0.0,
            "deductible_spent": 0.0,
            "doctor_visit_costs": 240.0,
            "prescription_costs": 0.0,
            "procedure_costs": 0.0,
            "total_before_oop_cap": 240.0,
            "oop_cap_applied": False,
            "final_care_cost": 240.0,
        },
        "prescription_details": [],
        "procedure_details": [],
    }
    mock_agent.calculate.return_value = (mock_results, "Test Plan is cheapest.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "usage": {
                "doctor_visits_per_year": 12,
                "prescriptions": [{"name": "Metformin", "fills_per_year": 12}],
                "procedures": [],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "recommendation" in data
    assert "disclaimer" in data
    assert "session_id" in data


def test_calculate_missing_both_session_and_zip():
    response = client.post(
        "/calculate",
        json={
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 422


def test_calculate_zip_without_income():
    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_with_session_id(mock_agent_cls):
    # First, create a session via /compare
    with patch("healthflow.api.routes.ComparisonAgent") as mock_compare_cls:
        mock_compare = MagicMock()
        mock_compare.recommend.return_value = "Plan A is best."
        mock_compare_cls.return_value = mock_compare

        compare_resp = client.post(
            "/compare",
            json={"zip_code": "10001", "age": 65, "income_level": "low"},
        )
        session_id = compare_resp.json()["session_id"]

    # Now use that session_id for /calculate
    mock_agent = MagicMock()
    mock_agent.calculate.return_value = ([], "No plans.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "session_id": session_id,
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 200


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_invalid_session_id(mock_agent_cls):
    response = client.post(
        "/calculate",
        json={
            "session_id": "nonexistent-session",
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 404


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.calculate.return_value = ([], "Recommendation.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "usage": {"doctor_visits_per_year": 0},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "estimate" in data["disclaimer"].lower() or "not medical advice" in data["disclaimer"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/test_calculate_route.py -v
```

Expected: FAIL — route not found (404)

- [ ] **Step 3: Add the /calculate route to routes.py**

Add the following import to the top of `healthflow/api/routes.py`, with the existing imports:

```python
from healthflow.agents.cost_calculator_agent import CostCalculatorAgent
```

Add `CalculateRequest`, `CalculateResponse` to the existing import from `healthflow.models.schemas`:

```python
from healthflow.models.schemas import (
    CalculateRequest,
    CalculateResponse,
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

Add a second disclaimer constant after the existing `DISCLAIMER`:

```python
ESTIMATE_DISCLAIMER = (
    "These are estimates based on typical plan costs and your expected usage. "
    "Actual costs may vary based on provider network, specific services, and plan terms. "
    "This is not medical advice."
)
```

Add the route at the end of the file:

```python


@router.post("/calculate", response_model=CalculateResponse)
def calculate_costs(request: CalculateRequest):
    # Load plans from session or fetch fresh
    if request.session_id:
        session_data = session_store.load(request.session_id)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        plan_ids = session_data.get("plan_ids", [])
        zip_code = session_data.get("zip_code", "10001")
        raw_plans = fetcher.fetch_plans(zip_code)
        raw_plans = [p for p in raw_plans if p["plan_id"] in plan_ids] or raw_plans
        income_level = session_data.get("income_level", "medium")
    else:
        raw_plans = fetcher.fetch_plans(request.zip_code)
        income_level = request.income_level

    ranked_plans = parser.parse_and_rank(raw_plans, income_level)

    harness.audit.log("tool_called", {"tool": "cost_calculator", "plans": len(ranked_plans)})

    agent = CostCalculatorAgent()
    results, raw_recommendation = agent.calculate(ranked_plans, request.usage)

    recommendation = harness.filter_output(raw_recommendation)

    session_id = request.session_id or str(uuid.uuid4())
    session_store.save(session_id, {
        "zip_code": request.zip_code or session_data.get("zip_code"),
        "income_level": income_level,
        "plan_ids": [r.plan_id for r in results],
        "calculation": True,
    })

    return CalculateResponse(
        session_id=session_id,
        plans=results,
        recommendation=recommendation,
        disclaimer=ESTIMATE_DISCLAIMER,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/test_calculate_route.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add healthflow/api/routes.py healthflow/tests/test_calculate_route.py
git commit -m "feat: add /calculate endpoint for annual cost estimation"
```

---

### Task 5: CLI Calculate Command

**Files:**
- Modify: `healthflow/cli.py`

- [ ] **Step 1: Add calculate command to cli.py**

Add the following command after the `estimate` command (before the `if __name__` block):

```python


@cli.command()
@click.option("--session-id", default="", help="Session ID from a prior /compare call")
@click.option("--zip-code", default="", help="5-digit US zip code")
@click.option(
    "--income",
    default="",
    type=click.Choice(["low", "medium", "high", ""], case_sensitive=False),
    help="Income level",
)
@click.option("--doctor-visits", prompt="Doctor visits per year", type=int, help="Expected doctor visits per year")
@click.option("--prescriptions", default="", help="Comma-separated name:fills pairs (e.g., Metformin:12,Ozempic:12)")
@click.option("--procedures", default="", help="Comma-separated name:count pairs (e.g., MRI:2,Blood work:4)")
def calculate(session_id: str, zip_code: str, income: str, doctor_visits: int, prescriptions: str, procedures: str):
    """Calculate estimated annual out-of-pocket costs."""
    payload: dict = {
        "usage": {
            "doctor_visits_per_year": doctor_visits,
            "prescriptions": [],
            "procedures": [],
        }
    }

    if session_id:
        payload["session_id"] = session_id
    elif zip_code:
        payload["zip_code"] = zip_code
        payload["income_level"] = income or "medium"
    else:
        click.echo("Error: Provide --session-id or --zip-code")
        sys.exit(1)

    for item in prescriptions.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.rsplit(":", 1)
        if len(parts) == 2:
            payload["usage"]["prescriptions"].append(
                {"name": parts[0].strip(), "fills_per_year": int(parts[1])}
            )
        else:
            payload["usage"]["prescriptions"].append(
                {"name": parts[0].strip(), "fills_per_year": 12}
            )

    for item in procedures.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.rsplit(":", 1)
        if len(parts) == 2:
            payload["usage"]["procedures"].append(
                {"name": parts[0].strip(), "count": int(parts[1])}
            )
        else:
            payload["usage"]["procedures"].append(
                {"name": parts[0].strip(), "count": 1}
            )

    try:
        response = httpx.post(f"{BASE_URL}/calculate", json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()

    click.echo("\n" + "=" * 60)
    click.echo("  HEALTHFLOW — Annual Cost Calculator")
    click.echo("=" * 60)

    for i, plan in enumerate(data["plans"], 1):
        b = plan["breakdown"]
        click.echo(f"\n--- #{i}: {plan['plan_name']} ---")
        click.echo(f"  Annual Premium:    ${plan['annual_premium']:>10,.2f}")
        click.echo(f"  Annual Care Cost:  ${plan['annual_care_cost']:>10,.2f}")
        click.echo(f"  TOTAL ANNUAL COST: ${plan['total_annual_cost']:>10,.2f}")
        click.echo(f"  ---")
        click.echo(f"  Doctor Visits:     ${b['doctor_visit_costs']:>10,.2f}")
        click.echo(f"  Prescriptions:     ${b['prescription_costs']:>10,.2f}")
        click.echo(f"  Procedures:        ${b['procedure_costs']:>10,.2f}")
        if b["oop_cap_applied"]:
            click.echo(f"  ** OOP Max cap applied — saved ${b['total_before_oop_cap'] - b['final_care_cost']:,.2f}")

        if plan["prescription_details"]:
            click.echo("  Rx Breakdown:")
            for rx in plan["prescription_details"]:
                click.echo(f"    - {rx['name']}: ${rx['cost_per_fill']:.2f}/fill x {int(rx['annual_cost'] / rx['cost_per_fill'])} = ${rx['annual_cost']:.2f}/yr")

        if plan["procedure_details"]:
            click.echo("  Procedure Breakdown:")
            for proc in plan["procedure_details"]:
                click.echo(f"    - {proc['name']}: ${proc['cost_per_visit']:.2f} x {int(proc['annual_cost'] / proc['cost_per_visit'])} = ${proc['annual_cost']:.2f}/yr")

    click.echo("\n" + "-" * 60)
    click.echo("\nRECOMMENDATION:\n")
    click.echo(data["recommendation"])
    click.echo(f"\n{data['disclaimer']}")
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()
```

- [ ] **Step 2: Verify CLI help**

```bash
.venv/bin/python -m healthflow.cli calculate --help
```

Expected: Shows help with all options

- [ ] **Step 3: Commit**

```bash
git add healthflow/cli.py
git commit -m "feat: add CLI calculate command for annual cost estimation"
```

---

### Task 6: Integration Tests + README Update

**Files:**
- Create: `healthflow/tests/test_calculate_integration.py`
- Modify: `README.md`

- [ ] **Step 1: Write integration tests**

Create `healthflow/tests/test_calculate_integration.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


@patch("healthflow.api.routes.CostCalculatorAgent")
@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_then_calculate_flow(mock_compare_cls, mock_calc_cls):
    """End-to-end: /compare → get session_id → /calculate with session_id"""
    # Step 1: Compare
    mock_compare = MagicMock()
    mock_compare.recommend.return_value = "Plan A is best."
    mock_compare_cls.return_value = mock_compare

    compare_resp = client.post(
        "/compare",
        json={"zip_code": "10001", "age": 65, "income_level": "low"},
    )
    assert compare_resp.status_code == 200
    session_id = compare_resp.json()["session_id"]

    # Step 2: Calculate using session
    mock_calc = MagicMock()
    mock_calc.calculate.return_value = ([], "Cheapest plan saves $500.")
    mock_calc_cls.return_value = mock_calc

    calc_resp = client.post(
        "/calculate",
        json={
            "session_id": session_id,
            "usage": {
                "doctor_visits_per_year": 12,
                "prescriptions": [{"name": "Metformin", "fills_per_year": 12}],
                "procedures": [{"name": "Blood work", "count": 4}],
            },
        },
    )
    assert calc_resp.status_code == 200
    data = calc_resp.json()
    assert data["session_id"] == session_id
    assert "recommendation" in data


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_standalone_with_full_usage(mock_agent_cls):
    """Standalone /calculate with prescriptions and procedures."""
    mock_agent = MagicMock()
    mock_agent.calculate.return_value = ([], "Recommendation text.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "90210",
            "income_level": "high",
            "usage": {
                "doctor_visits_per_year": 24,
                "prescriptions": [
                    {"name": "Metformin", "fills_per_year": 12},
                    {"name": "Ozempic", "fills_per_year": 12},
                ],
                "procedures": [
                    {"name": "MRI", "count": 2},
                    {"name": "Blood work", "count": 4},
                ],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "recommendation" in data
    assert "disclaimer" in data


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_output_filtered(mock_agent_cls):
    """Verify medical advice is filtered from calculator output."""
    mock_agent = MagicMock()
    mock_agent.calculate.return_value = (
        [],
        "Plan A is cheapest. You should take Metformin twice daily.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "you should take" not in data["recommendation"].lower()
```

- [ ] **Step 2: Run integration tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_calculate_integration.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Add /calculate endpoint to README.md**

After the `### POST /translate` section in README.md, add:

```markdown
### POST /calculate

Calculate estimated annual out-of-pocket costs based on your expected healthcare usage.

```bash
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "zip_code": "10001",
    "income_level": "low",
    "usage": {
      "doctor_visits_per_year": 12,
      "prescriptions": [
        {"name": "Metformin", "fills_per_year": 12},
        {"name": "Ozempic", "fills_per_year": 12}
      ],
      "procedures": [
        {"name": "MRI", "count": 2},
        {"name": "Blood work", "count": 4}
      ]
    }
  }'
```

You can also pass a `session_id` from a prior `/compare` call to reuse the same plans:

```bash
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id-here",
    "usage": {"doctor_visits_per_year": 12}
  }'
```
```

Also add under the CLI Usage section:

```markdown
# Annual cost calculation
python -m healthflow.cli calculate --zip-code 10001 --income low --doctor-visits 12 --prescriptions "Metformin:12,Ozempic:12" --procedures "MRI:2"
```

- [ ] **Step 4: Run full test suite**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/test_calculate_integration.py README.md
git commit -m "feat: add integration tests and docs for cost calculator"
```
