# HealthFlow — Phase 1 Design Spec

## Overview

HealthFlow is an AI-powered FastAPI service that compares Medicare Advantage health insurance plans and estimates medication/procedure costs. Users provide their zip code, age, income level, and optionally their medications and procedures. The agent returns a side-by-side comparison of up to 5 plans with personalized cost estimates and a plain-English recommendation powered by Claude.

**Phase 1 scope**: REST API (primary) + optional CLI wrapper, curated realistic mock data, no PII, no payments, no submissions.

## Architecture

Three-layer architecture with strict unidirectional data flow:

```
HTTP Request → FastAPI Router → Harness (validate/filter/log) → Tools (fetch/parse/estimate) → Agent (Claude) → Harness (output filter) → Response
```

## API Endpoints

| Method | Path          | Description                                                        |
|--------|---------------|--------------------------------------------------------------------|
| POST   | /compare      | Full comparison with optional cost estimates + recommendation      |
| POST   | /estimate     | Cost estimate for a medication or procedure under a specific plan  |
| GET    | /plans/{zip}  | Returns available plans for a zip code (no agent call)             |
| GET    | /health       | Health check                                                       |

## Project Structure

```
healthflow/
├── main.py                  # FastAPI app + uvicorn entry point
├── cli.py                   # Optional Click wrapper that calls the API
├── api/
│   └── routes.py            # FastAPI route definitions
├── agents/
│   ├── comparison_agent.py  # Core plan comparison + Claude recommendation
│   └── harness.py           # Input validation, output filtering, logging
├── tools/
│   ├── cms_fetcher.py       # Mock CMS data (curated realistic dataset)
│   ├── plan_parser.py       # Normalize and score plans
│   └── cost_estimator.py    # Medication and procedure cost estimation
├── models/
│   └── schemas.py           # Pydantic request/response models
├── memory/
│   └── session.py           # Session store (in-memory default, Redis optional)
├── logs/
│   └── audit.py             # Structured JSON audit logging
├── tests/
│   └── test_comparison.py   # Unit + integration tests
├── requirements.txt
└── README.md
```

## Component Details

### FastAPI App (`main.py`)

- Creates FastAPI application with metadata (title, description, version)
- Includes router from `api/routes.py`
- Runs via uvicorn
- Configures CORS middleware for future frontend integration

### API Routes (`api/routes.py`)

- `POST /compare`: accepts `CompareRequest`, orchestrates harness → fetcher → parser → cost estimator → agent → output filter, returns `CompareResponse`
- `POST /estimate`: accepts `EstimateRequest`, looks up cost for a single item under a specific plan, returns `EstimateResponse`
- `GET /plans/{zip_code}`: returns raw plan list for a zip code (no Claude call)
- `GET /health`: returns `{"status": "healthy"}`

### Pydantic Models (`models/schemas.py`)

**Request models:**

```python
class CompareRequest:
    zip_code: str           # 5-digit US zip
    age: int                # 18-120
    income_level: str       # "low" | "medium" | "high"
    medications: list[str]  # optional, e.g. ["Metformin", "Lisinopril"]
    procedures: list[str]   # optional, e.g. ["Annual physical", "Blood work"]

class EstimateRequest:
    plan_id: str
    item_name: str
    item_type: str          # "medication" | "procedure"
```

**Response models:**

```python
class PlanSummary:
    plan_name: str
    plan_id: str
    monthly_premium: float
    annual_deductible: float
    out_of_pocket_max: float
    star_rating: float      # 1.0-5.0
    plan_type: str          # "HMO" | "PPO"
    drug_coverage: bool
    estimated_medication_costs: dict[str, float] | None
    estimated_procedure_costs: dict[str, float] | None

class CompareResponse:
    session_id: str
    zip_code: str
    plans: list[PlanSummary]
    recommendation: str
    disclaimer: str

class CostDetails:
    formulary_tier: str | None
    copay: float | None
    coinsurance_pct: float | None
    prior_auth_required: bool
    quantity_limit: str | None

class EstimateResponse:
    plan_name: str
    item_name: str
    item_type: str
    estimated_cost: float
    cost_details: CostDetails
    disclaimer: str
```

### Harness (`agents/harness.py`)

**Input validation:**
- Zip code: exactly 5 digits, all numeric
- Age: integer 18-120
- Income level: one of "low", "medium", "high"
- Medications/procedures: list of non-empty strings, max 10 items each
- Raises `ValidationError` with human-readable messages

**Output filtering:**
- Regex + keyword scanning for medical advice patterns:
  - Medication recommendations: "you should take", "stop taking", "switch to", "increase dosage"
  - Diagnostic suggestions: "you might have", "symptoms suggest", "this could indicate"
  - Treatment advice: "I recommend treatment", "you need surgery", "seek emergency"
- If detected: replaces offending text with generic redaction notice
- Always appends disclaimer
- Logs every filter action with the matched pattern

### CMS Fetcher (`tools/cms_fetcher.py`)

Protocol: `CMSFetcher` with method `fetch_plans(zip_code: str) -> list[dict]`

**Phase 1: `MockCMSFetcher`** with ~20 curated plans from Aetna, Humana, UnitedHealthcare, Cigna, BCBS. Realistic financials mapped to 10 real zip codes (10001, 90210, 60601, 33101, 77001, 85001, 98101, 30301, 02101, 75201). Unknown zips get a randomized subset.

### Plan Parser (`tools/plan_parser.py`)

- Normalizes raw dicts into `PlanSummary` objects
- Scores and ranks plans, returns top 5
- Scoring weights by income: low (premium-heavy), medium (balanced), high (quality-heavy)

### Cost Estimator (`tools/cost_estimator.py`)

- ~30 common medications with formulary tiers and copays
- ~20 common procedures with costs by plan type
- Fuzzy string matching for item lookup

### Comparison Agent (`agents/comparison_agent.py`)

- Builds prompt for Claude (claude-sonnet-4-6) with plan data + cost estimates + user context
- System prompt constrains to insurance comparison only
- Returns recommendation string filtered by harness

### Session Store (`memory/session.py`)

- `SessionStore` ABC with `InMemoryStore` (default) and `RedisStore` (optional)

### Audit Logger (`logs/audit.py`)

- Structured JSON logging to stdout + rotating file
- Event types: `input_validated`, `tool_called`, `plans_fetched`, `costs_estimated`, `recommendation_generated`, `output_filtered`

## Testing

1. Input validation (valid/invalid inputs)
2. Plan parser (normalization, scoring, filtering)
3. Cost estimator (medication/procedure lookup, fuzzy matching)
4. Output filter (medical advice detection, disclaimer)
5. API endpoints (FastAPI TestClient)
6. End-to-end (mocked Claude API)

## Dependencies

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

## What This Project Does NOT Do

- No real CMS API calls (curated mock data)
- No PII storage or collection
- No payment processing
- No medical advice — actively blocked by harness
- No authentication (Phase 1)
- No frontend (API only)
