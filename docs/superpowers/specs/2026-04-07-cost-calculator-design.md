# HealthFlow Phase 3: Out-of-Pocket Cost Calculator — Design Spec

## Overview

Add a cost calculator that estimates annual out-of-pocket costs per plan based on a user's expected healthcare usage. Users provide doctor visit frequency, prescriptions (name + fills/year), and expected procedures. The calculator runs the math against each plan's cost structure and ranks plans by total annual cost (premium + care), not just premium. Integrates with Phase 1 session data or works standalone.

## New Endpoint

| Method | Path | Description |
|--------|------|-------------|
| POST | /calculate | Calculate estimated annual out-of-pocket costs per plan |

## Request/Response Models

**Request:**

```python
class PrescriptionInput(BaseModel):
    name: str
    fills_per_year: int = Field(..., ge=1, le=365)

class ProcedureInput(BaseModel):
    name: str
    count: int = Field(..., ge=1, le=365)

class UsageInput(BaseModel):
    doctor_visits_per_year: int = Field(..., ge=0, le=365)
    prescriptions: list[PrescriptionInput] = Field(default_factory=list, max_length=20)
    procedures: list[ProcedureInput] = Field(default_factory=list, max_length=20)

class CalculateRequest(BaseModel):
    session_id: str | None = None         # reuse plans from prior /compare call
    zip_code: str | None = None           # required if no session_id
    income_level: str | None = None       # required if no session_id
    usage: UsageInput
```

Validation: either `session_id` OR both `zip_code` + `income_level` must be provided. If `session_id` is given, zip/income are ignored.

**Response:**

```python
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

## New/Modified Files

### New: `healthflow/tools/cost_modeler.py`

Pure math — no AI calls. Takes a plan's cost structure + usage inputs and calculates annual out-of-pocket cost.

**Interface:**
- `CostModeler.calculate(plan: PlanSummary, usage: UsageInput, plan_type_copays: dict) -> PlanCostResult`

**Calculation logic:**
1. **Premium**: `monthly_premium * 12`
2. **Doctor visits**: copay per visit * visits_per_year. Copay by plan type: HMO = $20, PPO = $40
3. **Prescriptions**: For each prescription, look up cost via CostEstimator using plan_type, multiply by fills_per_year. Unknown drugs use a default $25 copay.
4. **Procedures**: For each procedure, look up cost via CostEstimator using plan_type, multiply by count. Unknown procedures use a default $100 copay.
5. **Deductible**: If plan has annual_deductible > 0, the first $X of care costs are paid at full price (deductible spending). Care costs above the deductible use the copay rates. Simplified model: deductible is subtracted from total care costs (care_costs = max(0, raw_care_costs - deductible_benefit)), where deductible_benefit represents the savings from copay rates vs full cost. For simplicity, we model it as: total care cost = sum of all copays (doctor + rx + procedures), and deductible_spent = min(annual_deductible, total_care_cost). The deductible doesn't reduce costs further in this simplified model — it's already factored into copay rates.
6. **OOP Max cap**: If total care costs exceed `out_of_pocket_max`, cap at OOP max. `oop_cap_applied = True` if capped.
7. **Total annual cost**: `annual_premium + final_care_cost`

**Dependencies:** Uses `CostEstimator` from Phase 1 for medication/procedure cost lookups.

### New: `healthflow/agents/cost_calculator_agent.py`

Orchestrates the calculation flow and generates a Claude recommendation.

**Interface:**
- `CostCalculatorAgent.calculate(plans: list[PlanSummary], usage: UsageInput) -> tuple[list[PlanCostResult], str]`

**Flow:**
1. Run `CostModeler.calculate()` for each plan
2. Sort results by `total_annual_cost` ascending (cheapest first)
3. Build a prompt with the cost breakdowns + usage context
4. Call Claude (claude-sonnet-4-6) for a plain-English recommendation comparing total costs
5. Return `(sorted_results, recommendation)`

**System prompt:** "You are a health insurance cost comparison assistant. Compare plans based on estimated annual out-of-pocket costs. Focus on total cost (premium + care), not just premium. Highlight which plan saves the most money for the user's specific usage pattern. Never give medical advice."

### Modified: `healthflow/models/schemas.py`

Add: `PrescriptionInput`, `ProcedureInput`, `UsageInput`, `CalculateRequest`, `PrescriptionDetail`, `ProcedureDetail`, `CostBreakdown`, `PlanCostResult`, `CalculateResponse`

`CalculateRequest` has a model-level validator: either `session_id` or both `zip_code` and `income_level` must be provided.

### Modified: `healthflow/api/routes.py`

Add `POST /calculate` endpoint:
- If `session_id` provided: load plan_ids from session, fetch those plans from fetcher
- If no session: validate zip_code + income_level present, fetch and rank plans
- Run CostCalculatorAgent.calculate()
- Filter recommendation through harness
- Save results to session
- Return CalculateResponse

### Modified: `healthflow/cli.py`

Add `calculate` command:
- Options: `--session-id`, `--zip-code`, `--income`, `--doctor-visits`, `--prescriptions` (comma-separated "name:fills" pairs), `--procedures` (comma-separated "name:count" pairs)
- POSTs to `/calculate`
- Displays ranked plan table with cost breakdowns

## Testing

### `healthflow/tests/test_cost_modeler.py`

1. Calculate with zero usage — only premium costs
2. Calculate with doctor visits only — correct copay math
3. Calculate with prescriptions — correct per-fill * fills_per_year
4. Calculate with procedures — correct per-visit * count
5. Calculate hits OOP max cap — costs capped correctly
6. Calculate with unknown drug — uses default $25 copay
7. Calculate with unknown procedure — uses default $100 copay
8. HMO vs PPO copay differences — HMO cheaper for doctor visits

### `healthflow/tests/test_cost_calculator_agent.py`

1. Agent returns sorted results (cheapest first)
2. Agent calls Claude with cost data in prompt
3. Agent system prompt prohibits medical advice

### `healthflow/tests/test_calculate_route.py`

1. POST /calculate with session_id — valid response
2. POST /calculate with zip_code — valid response
3. POST /calculate missing both session_id and zip_code — 422
4. POST /calculate with session_id and zip_code — session_id takes precedence
5. Response has disclaimer

### `healthflow/tests/test_calculate_integration.py`

1. End-to-end: compare → calculate with session_id
2. Cost breakdown math verification

## Guardrails

- Reuse existing harness `filter_output()` for Claude recommendation
- Every response includes disclaimer: "These are estimates based on typical plan costs and your expected usage. Actual costs may vary based on provider network, specific services, and plan terms."
- Usage validation via Pydantic: doctor visits 0-365, prescriptions max 20 items, procedures max 20 items, fills/count 1-365

## What This Does NOT Do

- No real insurance cost modeling (simplified copay-based estimates)
- No network provider lookups
- No coinsurance calculations (uses copay-only model for Phase 3)
- No medical advice
- No PII storage
