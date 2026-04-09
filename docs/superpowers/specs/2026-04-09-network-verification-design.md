# HealthFlow Phase 5: Network Verification Agent — Design Spec

## Overview

Add a network verification feature that checks whether a user's doctors are in-network and prescriptions are on formulary for each plan. Uses the real NPPES NPI Registry API for provider verification combined with curated network/formulary mapping data. Integrates with Phase 1 session data or works standalone. Results are cached for 24 hours in a dedicated cache to avoid redundant API calls.

## New Endpoint

| Method | Path | Description |
|--------|------|-------------|
| POST | /verify | Check provider network status and drug formulary coverage per plan |

## Data Sources

### Real: NPPES NPI Registry API
- Endpoint: `https://npiregistry.cms.hhs.gov/api/?version=2.1`
- No auth required, public, free
- Query by NPI number (`number` param) or name (`first_name`/`last_name` params) + state (`state` param)
- Returns JSON with `result_count` and `results` array
- Each result has: `basic` (name, credential, enumeration_date), `taxonomies` (specialty), `addresses`
- Used to VERIFY a provider exists and get their details (name, specialty, credential)

### Curated: Provider Network Mapping
~40 providers mapped to plans and zip codes. Each provider entry:
```python
{
    "npi": "1234567890",
    "name": "Dr. Sarah Chen",
    "specialty": "Internal Medicine",
    "zip_codes": ["10001", "10002"],
    "in_network_plans": ["H3312-034", "H1036-200", "H2228-050"],
}
```
Covers specialties: Internal Medicine, Family Medicine, Cardiology, Orthopedics, Dermatology, Psychiatry, Neurology, Oncology, Endocrinology, Pulmonology.
Mapped to same 10 zip codes as Phase 1.

### Curated: Drug Formulary
Reuses existing medication data from `cost_estimator.py` (30 drugs with tier/copay). Extends with per-plan formulary status. Most drugs are on formulary for all plans; some specialty drugs (Humira, Dupixent, Ozempic) are restricted to certain plans.

## Request/Response Models

**Request:**

```python
class ProviderInput(BaseModel):
    name: str
    npi: str | None = None

class VerifyRequest(BaseModel):
    session_id: str | None = None
    zip_code: str | None = None
    income_level: str | None = None
    providers: list[ProviderInput] = Field(default_factory=list, max_length=10)
    prescriptions: list[str] = Field(default_factory=list, max_length=20)
```

Validation: either `session_id` or both `zip_code` + `income_level` required (same pattern as CalculateRequest).

**Response:**

```python
class ProviderResult(BaseModel):
    name: str
    npi: str | None
    npi_verified: bool
    specialty: str | None
    in_network: bool
    warning: str | None

class FormularyResult(BaseModel):
    drug_name: str
    on_formulary: bool
    tier: str | None
    copay: float | None
    prior_auth_required: bool
    warning: str | None

class PlanNetworkResult(BaseModel):
    plan_name: str
    plan_id: str
    provider_results: list[ProviderResult]
    formulary_results: list[FormularyResult]

class VerifyResponse(BaseModel):
    session_id: str
    plans: list[PlanNetworkResult]
    recommendation: str
    disclaimer: str
```

## New/Modified Files

### New: `healthflow/tools/npi_client.py`

Calls the real NPPES NPI Registry API.

**Interface:**
- `NPIClient.lookup_by_npi(npi: str) -> dict | None` — Query by NPI number. Returns `{"npi": str, "name": str, "specialty": str, "credential": str, "state": str}` or None.
- `NPIClient.search_by_name(first_name: str, last_name: str, state: str | None = None) -> list[dict]` — Search by name. Returns list of provider dicts (may be empty).

Uses `httpx` for HTTP calls. Parses NPPES response format (results[0].basic.first_name, etc.).

### New: `healthflow/tools/provider_checker.py`

Combines NPI verification with curated network data.

**Interface:**
- `ProviderChecker.check(provider_name: str, npi: str | None, plan_id: str) -> ProviderResult`

**Logic:**
1. If NPI provided: look up via NPIClient.lookup_by_npi(). If found, npi_verified=True and extract specialty.
2. If no NPI: try NPIClient.search_by_name() with parsed first/last name. If found, use first result.
3. Check curated network mapping for plan_id. If NPI is in plan's network, in_network=True.
4. If provider not found in NPI registry: npi_verified=False, warning="Provider not found in NPI registry. Verify name and credentials."
5. If provider found but not in plan's network: in_network=False, no warning (legitimate out-of-network).

**Curated data:** `PROVIDER_NETWORK` list of ~40 provider dicts embedded in the module, each with npi, name, specialty, zip_codes, in_network_plans.

### New: `healthflow/tools/formulary_checker.py`

Checks drugs against per-plan formulary data.

**Interface:**
- `FormularyChecker.check(drug_name: str, plan_id: str, plan_type: str) -> FormularyResult`

**Logic:**
1. Look up drug via existing `CostEstimator.estimate()` for tier and copay info.
2. Check `PLAN_FORMULARY_EXCLUSIONS` — a dict mapping plan_ids to lists of excluded drug names.
3. If drug found and not excluded: on_formulary=True, return tier/copay.
4. If drug not found in CostEstimator: on_formulary=False, warning="Drug not found in formulary database."
5. If drug excluded from plan: on_formulary=False, warning="This drug is not on this plan's formulary."

### New: `healthflow/tools/provider_cache.py`

Dedicated cache with 24-hour TTL. Separate from SessionStore.

**Interface:**
- `ProviderCache.get(key: str) -> dict | None` — Returns cached data if not expired, else None.
- `ProviderCache.set(key: str, data: dict) -> None` — Stores data with expiry timestamp.

**Implementations:**
- `InMemoryProviderCache` — Dict with `{key: {"data": dict, "expires_at": float}}`. Default.
- `RedisProviderCache` — Uses `redis.setex()` with 86400 TTL. Optional.

Key format: `npi:{npi_number}` or `name:{first}:{last}`

### New: `healthflow/agents/network_agent.py`

Orchestrates provider and formulary verification across plans.

**Interface:**
- `NetworkAgent.verify(plans: list[PlanSummary], providers: list[ProviderInput], prescriptions: list[str]) -> tuple[list[PlanNetworkResult], str]`

**Flow:**
1. For each plan, for each provider: call ProviderChecker.check() (with caching)
2. For each plan, for each prescription: call FormularyChecker.check()
3. Build PlanNetworkResult per plan
4. Sort plans by: number of in-network providers (desc), then number of on-formulary drugs (desc)
5. Call Claude for a recommendation summarizing network compatibility
6. Return (results, recommendation)

**System prompt:** "You are a health insurance network verification assistant. Summarize which plans have the best network coverage for the user's doctors and prescriptions. Highlight any providers that are out-of-network or drugs not on formulary. Never give medical advice."

### Modified: `healthflow/models/schemas.py`

Add: `ProviderInput`, `VerifyRequest`, `ProviderResult`, `FormularyResult`, `PlanNetworkResult`, `VerifyResponse`

`VerifyRequest` has same session_id/zip_code/income_level validation as `CalculateRequest`.

### Modified: `healthflow/api/routes.py`

Add `POST /verify` endpoint:
- Same session/standalone pattern as `/calculate`
- Calls NetworkAgent.verify()
- Filters recommendation through harness
- Returns VerifyResponse with disclaimer

### Modified: `healthflow/cli.py`

Add `verify` command:
- Options: `--session-id`, `--zip-code`, `--income`, `--providers` (comma-separated "name:npi" pairs), `--prescriptions` (comma-separated drug names)
- POSTs to `/verify`
- Displays per-plan provider and formulary status

## Guardrails

- Every response includes disclaimer: "Network status and formulary coverage are based on publicly available data and may not reflect current plan contracts. Provider networks and drug formularies can change. Verify directly with your plan before making decisions. This is not medical advice."
- Harness output filter blocks medical advice (reused)
- Audit log: provider lookups, formulary checks, verification results

## Testing

### `healthflow/tests/test_npi_client.py`
1. Lookup by NPI returns provider details (mock httpx)
2. Lookup by NPI not found returns None (mock httpx)
3. Search by name returns results (mock httpx)
4. Search by name no results returns empty list (mock httpx)
5. API error handled gracefully (returns None)

### `healthflow/tests/test_provider_checker.py`
1. NPI verified and in-network
2. NPI verified but out-of-network
3. NPI not found — warning generated
4. No NPI provided — name search used
5. Provider in curated data matches plan

### `healthflow/tests/test_formulary_checker.py`
1. Known drug on formulary — returns tier/copay
2. Known drug excluded from specific plan
3. Unknown drug — warning generated
4. Drug copay differs by plan type (HMO vs PPO)

### `healthflow/tests/test_provider_cache.py`
1. Set and get within TTL
2. Expired entry returns None
3. Nonexistent key returns None
4. Multiple entries independent

### `healthflow/tests/test_network_agent.py`
1. Agent returns sorted results (most in-network first)
2. Agent calls Claude with provider/formulary data
3. System prompt prohibits medical advice
4. Plans ranked by network coverage

### `healthflow/tests/test_verify_route.py`
1. POST /verify with zip_code — valid response
2. POST /verify with session_id — valid response
3. POST /verify missing both — 422
4. Response has disclaimer
5. Response has provider and formulary results

### `healthflow/tests/test_verify_integration.py`
1. End-to-end with mocked NPPES API
2. Cache prevents duplicate API calls
3. Medical advice filtered from output

## What This Does NOT Do

- No real provider-to-plan network mapping (curated data)
- No real formulary API (extends existing curated drug data)
- No provider appointment scheduling
- No insurance enrollment
- No medical advice
- No PII/PHI stored
