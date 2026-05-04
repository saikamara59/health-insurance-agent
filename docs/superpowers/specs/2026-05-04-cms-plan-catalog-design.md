# Real CMS Plan Catalog with Nationwide ZIP Coverage

**Date:** 2026-05-04
**Status:** Approved (design)
**Follow-up to:** Existing seed catalog in `scripts/refresh_data.py`

## Problem

The plan catalog is hand-seeded: ~50 Medicare Advantage plans across ~25 carriers, with hardcoded ZIP→plan mappings for ~25 demo ZIPs. A `download_cms_data()` function exists but has two flaws:

1. It caps at 5,000 rows in a single Socrata call with no pagination, and doesn't request the `county_code` field. Even when it succeeds, the downloaded plans land in the `plans` table with no service-area information.
2. The orchestrator (`main()` in `refresh_data.py:467`) ignores the downloaded plans for ZIP mapping purposes — it only inserts `plan_zips` rows from the hardcoded `SEED_ZIP_MAPPINGS` dict. Result: the 4,950 newly-downloaded plans are unreachable from any ZIP search and exist only as orphans visible to the state-level search path.

So even with a "real CMS" path enabled, the broker comparing plans for ZIP 10001 still sees only the seed catalog. We want nationwide ZIP coverage backed by real, current CMS data.

## Goal

`make refresh-data` produces a SQLite database where:

- The `plans` table contains every active Medicare Advantage plan published in the CMS Plan Landscape (~3,000 plans).
- The `plan_zips` table maps every US ZIP (~33,000) to the set of plans available there, by joining CMS county service areas to a HUD ZIP↔county crosswalk.
- A broker entering any US ZIP on the compare page sees real, current plan options for that location.

The script remains a single command with no required flags. It still works offline by falling back to the existing seed.

## Non-Goals

- ACA marketplace plans, Medigap supplements, employer plans, or PDP-only Part D plans. Still Medicare Advantage only — that's what the CMS `jfhb-kvhx` Socrata dataset publishes.
- Any UI changes. The compare page consumes the same `/compare` API shape.
- Any FastAPI surface changes. `PlanDatabase.search_plans(zip)` keeps the same signature and contract.
- A scheduled / cron-driven refresh. `make refresh-data` stays manual.
- Residential-ratio weighting in the ZIP↔county join. We keep the full set of counties per ZIP so a ZIP that straddles county lines exposes plans from every overlapping county.

## Approach

Three external data sources, joined in the script, written to SQLite atomically:

1. **CMS Medicare Advantage Plan Landscape** via Socrata API at `https://data.cms.gov/resource/jfhb-kvhx.json`. Public, no auth. The dataset has one row per `(plan, county)` combination. Paged via `$limit=5000` + `$offset` until a short page terminates the loop.

2. **HUD USPS ZIP↔county crosswalk** via the HUD User API at `https://www.huduser.gov/hudapi/public/usps?type=2&query=All`. Free, requires `HUD_API_TOKEN` (free signup at huduser.gov). One call returns all ~33K national ZIP records.

3. **Pure in-memory join** that produces `dict[zip_code, list[plan_id]]` from the two crosswalks.

The script always produces a working DB. The fallback ladder degrades gracefully: missing token → seed ZIPs only; CMS network failure → seed plans + seed ZIPs.

## Architecture

All work lives in `scripts/refresh_data.py`. No new files in the runtime path; no schema changes; no FastAPI changes.

### Functions

| Function | Status | Purpose |
|---|---|---|
| `download_cms_data()` | refactored | Paged Socrata pull. Now also requests `county_code`. Returns `(plans: list[tuple], plan_county_map: dict[plan_id, set[county_fips]])`. |
| `download_hud_zip_county()` | new | Reads `HUD_API_TOKEN` from env, calls HUD USPS Crosswalk API, returns `dict[zip_code, set[county_fips]]` or `None` on failure / missing token. |
| `build_zip_mappings(plan_county_map, zip_county_map)` | new | Pure function. Inverts `plan_county_map` to a county→plans index, then expands every ZIP through its counties. Returns `dict[zip_code, list[plan_id]]`. |
| `_load_or_fetch(cache_key, ttl_days, fetch_fn)` | new | Cache wrapper. Reads `~/.cache/healthflow/<key>.json` if present and within TTL; otherwise calls `fetch_fn()` and writes through. Bypassed by `--force-refresh`. |
| `main()` | refactored | Orchestrates the calls and assembles the final ZIP mapping. |

### Orchestration

```text
1. load_dotenv()                           # read HUD_API_TOKEN from .env
2. plans, plan_county_map = _load_or_fetch("cms_landscape", 7, download_cms_data)
   → on failure: plans = SEED_PLANS, plan_county_map = None
3. zip_county_map = _load_or_fetch("hud_zip_county", 30, download_hud_zip_county)
   → on failure or no token: zip_county_map = None
4. if plan_county_map and zip_county_map:
       zip_to_plans = build_zip_mappings(plan_county_map, zip_county_map)
   else:
       zip_to_plans = SEED_ZIP_MAPPINGS
5. write_sqlite(temp_path, plans, plan_county_map, zip_to_plans, drugs)
6. atomic rename temp_path → healthflow_data.db
```

### Tables

No schema changes. Same DDL as today:

- `plans` — one row per plan. Same columns. Just more rows (~50 → ~3,000).
- `plan_counties` — currently defined but never populated. After this change, populated from `plan_county_map` and becomes the canonical service-area record. ~30,000 rows.
- `plan_zips` — derived index for fast ZIP search. Grows from ~150 rows to ~400,000.
- `drugs` — unchanged.

## Data flow

### CMS Socrata pagination

Selected fields:

```
contract_id, plan_id, plan_name, organization_name, plan_type,
monthly_consolidated_premium, annual_drug_deductible, out_of_pocket_maximum,
overall_star_rating, drug_coverage, state, county_code
```

Pagination: `$limit=5000`, `$offset` advances by 5000 each iteration. Stop when a page returns fewer than `$limit` rows. Expected ~30K rows total, ~6 pages.

While iterating, accumulate two structures:

- `plans: dict[plan_id, tuple]` — first occurrence of each `plan_id` wins for plan-level fields.
- `plan_county_map: dict[plan_id, set[county_fips]]` — every `(plan_id, county_code)` pair is recorded.

At the end, `plans` is converted to the `list[tuple]` shape the existing SQLite writer expects.

### HUD USPS Crosswalk

Single GET request:

```
GET https://www.huduser.gov/hudapi/public/usps?type=2&query=All
Authorization: Bearer <HUD_API_TOKEN>
```

`type=2` is the ZIP-to-county relationship file; `query=All` returns the full national dataset. Response is a JSON object with a `data.results` array of records, each with `zip` and `geoid` (county FIPS) fields.

We collect `zip_county_map: dict[zip_code, set[county_fips]]` — every county that appears for a ZIP is kept. We deliberately do not use HUD's `res_ratio` weighting; for plan-availability purposes we want the full set, not the dominant county.

### Join

```python
def build_zip_mappings(plan_county_map, zip_county_map):
    county_to_plans = defaultdict(list)
    for plan_id, counties in plan_county_map.items():
        for county in counties:
            county_to_plans[county].append(plan_id)

    zip_to_plans = {}
    for zip_code, counties in zip_county_map.items():
        plan_ids = set()
        for county in counties:
            plan_ids.update(county_to_plans.get(county, ()))
        if plan_ids:
            zip_to_plans[zip_code] = sorted(plan_ids)
    return zip_to_plans
```

Pure, in-memory, no I/O. Tested in isolation.

### Atomic write

The script writes the full DB to `healthflow_data.db.tmp`, then `os.replace()` to `healthflow_data.db`. A mid-run crash leaves the previous DB intact rather than a half-built file. (Today's script writes directly to the target path, which is the bug we're fixing in passing.)

## Caching

Local cache directory: `~/.cache/healthflow/` (created on demand, follows XDG-style convention).

| Key | TTL | Why |
|---|---|---|
| `cms_landscape.json` | 7 days | CMS publishes monthly, sometimes more. A week is fresh enough for a demo and respects their API. |
| `hud_zip_county.json` | 30 days | HUD updates quarterly, so a month is comfortable. The dataset is large (~3 MB JSON). |

Cache files store the post-processed return value of the fetch function as JSON. `set` values are converted to sorted `list`s for serialization; `_load_or_fetch` rehydrates them back to `set`s on read. Caching the parsed result rather than the raw HTTP response keeps the wrapper simple — `_load_or_fetch(key, ttl, fetch_fn) → fetch_fn()` is a single-call interface with one cache I/O.

`--force-refresh` bypasses both caches. Corrupt cache (JSON parse error) is treated as a miss — file is deleted and refetched.

## Error handling

Every external call returns `None` on failure rather than raising. The orchestrator decides what to degrade to:

| What failed | What happens |
|---|---|
| `HUD_API_TOKEN` not set | `download_hud_zip_county()` returns `None` immediately, no network call. Log: "HUD_API_TOKEN not set; using seed ZIP mappings (~25 ZIPs covered). Set the token to enable nationwide ZIPs." |
| HUD HTTP error / timeout | Same as above; status code logged. |
| CMS fails on page 1 | `download_cms_data()` returns `None`. Fall back to `SEED_PLANS` and `SEED_ZIP_MAPPINGS`. Skip HUD download (no point mapping ZIPs to plans we don't have). |
| CMS fails on page N>1 | Return what we have so far, log how many plans we got. Partial nationwide coverage. |
| Cache file corrupt | Delete file, treat as cache miss. |
| `build_zip_mappings` produces empty result | Surface as error, fall back to `SEED_ZIP_MAPPINGS`. Defensive — should never happen if both inputs are non-None. |
| Atomic rename fails | Crash with a clear message. The previous DB is intact. |

The DB is never half-written; the script never raises out of the orchestrator without a fallback.

## CLI

```
python scripts/refresh_data.py [--force-refresh] [--use-seed] [--verbose]
```

| Flag | Default | Purpose |
|---|---|---|
| `--force-refresh` | off | Bypass the local cache for both CMS and HUD. |
| `--use-seed` | off | Skip the network entirely. Use `SEED_PLANS` + `SEED_ZIP_MAPPINGS`. Useful for offline debugging. |
| `--verbose` | off | DEBUG-level logging — pagination progress, cache hits/misses, per-table row counts. |

`make refresh-data` continues to invoke the script with no flags.

## Configuration

`.env` gains one optional variable:

```
# Optional — enables nationwide ZIP coverage in `make refresh-data`
# Free signup: https://www.huduser.gov/portal/dataset/uspszip-api.html
HUD_API_TOKEN=
```

`scripts/refresh_data.py` calls `load_dotenv(override=False)` at the top, mirroring `healthflow/main.py`. `.env.example` is updated to document the variable.

## Testing

Three layers.

### Unit tests (always run in CI)

New file: `healthflow/tests/test_zip_mappings.py`

- `test_build_zip_mappings_basic` — given a small `plan_county_map` and `zip_county_map`, assert the joined output.
- `test_build_zip_mappings_empty_inputs` — both empty → returns `{}`.
- `test_build_zip_mappings_zip_with_no_plans` — ZIP that maps to a county no plan covers is omitted from the output (rather than mapping to an empty list).
- `test_build_zip_mappings_multi_county_zip` — ZIP that touches two counties gets the deduped union of plans from both.

### Mock-based downloader tests (CI)

New file: `healthflow/tests/test_refresh_downloaders.py`

- `test_download_cms_data_paginates` — `httpx.Client.get` patched to return mock paged responses; asserts dedupe and county accumulation.
- `test_download_cms_data_skips_malformed_rows` — a row with a bad star rating is skipped, others land.
- `test_download_cms_data_handles_network_error` — `httpx` raises → returns `None`.
- `test_download_hud_zip_county_no_token` — `HUD_API_TOKEN` unset → returns `None` immediately, no HTTP call.
- `test_download_hud_zip_county_parses_response` — mock HUD response → expected dict.
- `test_cache_hit` — fresh cache file → `fetch_fn` not called.
- `test_cache_miss` — missing cache → `fetch_fn` called, result written to cache.

The HUD and CMS clients are HTTP-call boundaries where mocking is the right tool. The "integration tests must hit a real database" rule (auto-memory) applies to the app's data layer, not to these external API clients.

### Manual smoke check

Documented in the README under the data refresh section:

```sh
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plans;"           # ~3,000
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_counties;"   # ~30,000
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_zips;"       # ~400,000
sqlite3 healthflow_data.db "SELECT plan_name FROM plans p JOIN plan_zips z ON p.plan_id=z.plan_id WHERE z.zip_code='10001' LIMIT 20;"
```

Run after the first nationwide refresh.

### Existing tests

`test_plan_database.py`, `test_real_data_integration.py`, and the rest construct fixture DBs locally and don't depend on a live `healthflow_data.db`. They're unaffected by changes to `refresh_data.py` and must continue to pass after the refactor.

## Documentation

- `README.md` — new "Data refresh" subsection: what the script does, how to set `HUD_API_TOKEN`, the manual smoke check.
- `.env.example` — adds `HUD_API_TOKEN=` with the signup URL.
- No updates to `CLAUDE.md` — the data layer description stays accurate at the level the file describes it.

## Open Questions

None. All design decisions resolved during brainstorming:

- Geographic scope: nationwide (~33K ZIPs).
- Crosswalk source: HUD (authentic over zero-friction).
- Token UX: silent fallback with a warning log.
- TTLs: 7 days CMS, 30 days HUD.
- E2E test against live APIs: skipped in favor of the manual smoke check.

## Out of Scope (explicit)

- ACA / Medigap / employer / PDP plan types.
- UI changes on the compare page.
- FastAPI surface changes.
- Cron / scheduled refresh.
- HUD residential-ratio weighting.
- Backwards-compat shim for the old single-call CMS query.
