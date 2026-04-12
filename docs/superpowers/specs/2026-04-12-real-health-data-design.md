# HealthFlow Phase 8: Real Health Data Integration — Design Spec

## Overview

Replace mock/curated health data with real public data from CMS and FDA. A data refresh script downloads CMS Medicare Advantage plan files and FDA drug data, processes them into a pre-built SQLite database (`healthflow_data.db`). The app reads from this file at startup. Same interfaces — `CMSFetcher` protocol and `CostEstimator` — so zero breaking changes to existing code.

## Data Sources

### 1. CMS Medicare Advantage Plan Data
- **Source:** `data.cms.gov` — Landscape Source files (PBP Benefits, Plan Information)
- **Coverage:** ~4,000+ real Medicare Advantage plans nationwide
- **Fields:** plan_id (H-number), plan_name, organization, plan_type (HMO/PPO/PFFS), monthly_premium, annual_deductible, out_of_pocket_max, star_rating, drug_coverage, county/zip coverage areas
- **Update frequency:** Quarterly by CMS
- **No auth required** — public CSV downloads

### 2. FDA/RxNorm Drug Data
- **Source:** `api.fda.gov/drug/label` + `rxnav.nlm.nih.gov/REST` APIs
- **Coverage:** Top ~200 most prescribed Medicare drugs
- **Fields:** drug name (brand + generic), NDC code, dosage form, formulary tier, typical copays by plan type, prior auth flag, quantity limits
- **Tier assignment:** Based on CMS Part D formulary reference tiers (Tier 1 Generic through Tier 4 Specialty)
- **No auth required** — public APIs

## Data Pipeline

```
scripts/refresh_data.py:
  1. Download CMS plan landscape CSV from data.cms.gov
  2. Download CMS star ratings CSV
  3. Download CMS service area (county/zip) files
  4. Fetch top 200 drug labels from FDA OpenFDA API
  5. Fetch generic/brand name mappings from RxNorm API
  6. Parse, clean, normalize all data
  7. Build healthflow_data.db (SQLite) with plans, plan_counties, plan_zips, drugs tables
  8. Print summary: X plans, Y drugs, Z zip codes loaded
```

**Run manually:** `python scripts/refresh_data.py`
**Output:** `healthflow_data.db` in project root (gitignored — too large for repo)

## SQLite Database Schema (`healthflow_data.db`)

### `plans` table
| Column | Type | Notes |
|--------|------|-------|
| plan_id | TEXT | Primary key, e.g. "H3312-034" |
| plan_name | TEXT | Full plan name |
| organization | TEXT | Insurer name (Aetna, Humana, etc.) |
| plan_type | TEXT | HMO, PPO, PFFS, HMO-POS |
| monthly_premium | REAL | 0.00 - 300.00 |
| annual_deductible | REAL | |
| out_of_pocket_max | REAL | |
| star_rating | REAL | 1.0 - 5.0 |
| drug_coverage | INTEGER | 0 or 1 |
| state | TEXT | Two-letter state code |

### `plan_counties` table
| Column | Type | Notes |
|--------|------|-------|
| plan_id | TEXT | FK → plans.plan_id |
| state | TEXT | |
| county | TEXT | County name |
| fips_code | TEXT | 5-digit FIPS |

### `plan_zips` table
| Column | Type | Notes |
|--------|------|-------|
| plan_id | TEXT | FK → plans.plan_id |
| zip_code | TEXT | 5-digit zip |

### `drugs` table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key autoincrement |
| name | TEXT | Common name (used for matching) |
| generic_name | TEXT | Generic/chemical name |
| brand_name | TEXT | Brand name(s) |
| ndc | TEXT | National Drug Code |
| dosage_form | TEXT | Tablet, Capsule, Injection, etc. |
| tier_generic | TEXT | Tier 1, Tier 2, Tier 3, Tier 4 |
| copay_hmo | REAL | Typical HMO copay |
| copay_ppo | REAL | Typical PPO copay |
| prior_auth | INTEGER | 0 or 1 |
| quantity_limit | TEXT | e.g. "90-day supply" |

## New/Modified Files

### New: `scripts/refresh_data.py`

Standalone script. Downloads CMS + FDA data, processes into SQLite.

**CMS data fetching:**
- Downloads landscape CSV from data.cms.gov (Socrata API or direct CSV link)
- Parses plan info: name, premiums, deductibles, OOP max, star ratings
- Parses service area files: maps plan_id to counties and zip codes
- Handles missing/malformed data gracefully (skip rows, log warnings)

**FDA data fetching:**
- Queries OpenFDA drug label API for top 200 drugs by name
- Queries RxNorm for generic/brand name mappings
- Maps to formulary tiers based on drug type (generic → Tier 1, brand → Tier 2, specialty → Tier 4)
- Assigns typical copays per tier: Tier 1 $3-10, Tier 2 $20-45, Tier 3 $47-95, Tier 4 $100-300

**Output:** Creates/overwrites `healthflow_data.db` in project root.

### New: `healthflow/data/__init__.py`

Empty package marker.

### New: `healthflow/data/plan_database.py`

Reads from `healthflow_data.db`. Provides plan lookups.

**Interface:**
- `PlanDatabase(db_path: str = "healthflow_data.db")`
- `search_plans(zip_code: str) -> list[dict]` — queries plan_zips join plans, returns plan dicts matching the `CMSFetcher` output format
- `search_plans_by_state(state: str) -> list[dict]` — broader search
- `get_plan(plan_id: str) -> dict | None` — single plan lookup
- `is_available() -> bool` — checks if healthflow_data.db exists

### New: `healthflow/data/drug_database.py`

Reads from `healthflow_data.db`. Provides drug lookups.

**Interface:**
- `DrugDatabase(db_path: str = "healthflow_data.db")`
- `search_drug(name: str) -> dict | None` — exact match first, then fuzzy (LIKE %name%)
- `get_tier(drug_name: str) -> str | None` — returns tier string
- `get_copay(drug_name: str, plan_type: str) -> float | None` — returns copay for HMO or PPO
- `is_available() -> bool` — checks if healthflow_data.db exists

### Modified: `healthflow/tools/cms_fetcher.py`

Add `RealCMSFetcher` class implementing `CMSFetcher` protocol:
```python
class RealCMSFetcher:
    def __init__(self):
        self.db = PlanDatabase()
    
    def fetch_plans(self, zip_code: str) -> list[dict]:
        if self.db.is_available():
            plans = self.db.search_plans(zip_code)
            if plans:
                return plans
        # Fallback to mock data if DB not available or no results
        return MockCMSFetcher().fetch_plans(zip_code)
```

### Modified: `healthflow/tools/cost_estimator.py`

Update `CostEstimator` to check `DrugDatabase` first:
```python
def estimate(self, item_name, item_type, plan_type):
    if item_type == "medication":
        # Try real data first
        drug_db = DrugDatabase()
        if drug_db.is_available():
            result = drug_db.search_drug(item_name)
            if result:
                return format_drug_result(result, plan_type)
        # Fallback to hardcoded MEDICATIONS
        ...
```

### Modified: `healthflow/api/routes.py`

Update the module-level `fetcher` to use `RealCMSFetcher` instead of `MockCMSFetcher`:
```python
fetcher = RealCMSFetcher()  # Falls back to mock if data file missing
```

## Integration Strategy

**Zero breaking changes:**
- `CMSFetcher` protocol unchanged: `fetch_plans(zip_code) -> list[dict]`
- `CostEstimator` interface unchanged: `estimate(name, type, plan_type) -> dict|None`
- All existing tests continue to work (they don't depend on specific plan data)
- Mock data still available as fallback when `healthflow_data.db` doesn't exist
- New tests verify real data integration separately

## Testing

### `healthflow/tests/test_plan_database.py`
1. Search by zip returns plans (with test fixture SQLite)
2. Unknown zip returns empty list
3. Get plan by ID
4. is_available() returns False when file missing

### `healthflow/tests/test_drug_database.py`
1. Search known drug returns result
2. Fuzzy match works (partial name)
3. Unknown drug returns None
4. Copay lookup by plan type

### `healthflow/tests/test_real_fetcher.py`
1. RealCMSFetcher returns plans for known zip
2. Falls back to mock when DB missing
3. Matches CMSFetcher protocol output format

### `healthflow/tests/test_refresh_script.py`
1. Script creates SQLite file
2. Plans table populated
3. Drugs table populated
4. Zip mapping works

## What This Does NOT Do

- No real-time CMS API calls (uses pre-downloaded data)
- No automatic data refresh (manual script run)
- No provider-to-plan network mapping (not publicly available)
- No real formulary per plan (uses tier-based estimates)
- No drug interaction checking
