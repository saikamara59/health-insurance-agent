# Test Folder Reorganization

**Date:** 2026-05-12
**Status:** Approved (design)
**Prerequisite for:** [2026-05-12-multi-tenancy-design.md](./2026-05-12-multi-tenancy-design.md)

## Problem

`healthflow/tests/` contains 66 flat `test_*.py` files (plus `__init__.py` and `conftest.py`). Finding the test for a given module requires `ls | grep`, and adding new tests (e.g. the upcoming `tests/tenancy/` suite) keeps making the problem worse. The flat layout reads as accidental rather than intentional and obscures the modular structure that already exists in the production code (`healthflow/auth/`, `healthflow/agents/`, `healthflow/api/`, etc.).

## Goal

Reorganize `healthflow/tests/` into domain subfolders that **mirror the production code layout**, so a developer who knows where a feature lives in `healthflow/` immediately knows where its tests live in `tests/`.

The reorg is purely structural: no test logic changes, no fixture changes, no production code changes. CI and `pytest` discovery continue to work without configuration changes (or with minimal ones).

## Non-Goals

- **No production code reorganization.** `healthflow/` layout stays exactly as it is.
- **No test logic changes.** Pure `git mv` + `__init__.py`. If a test breaks because of import or discovery issues, fix the move; do not edit assertions.
- **No fixture refactoring.** `tests/conftest.py` remains at the top level; subfolders inherit fixtures via pytest's normal lookup. No per-subfolder conftests unless a fixture is genuinely folder-specific (none anticipated).
- **No deletions or merges of existing tests.** Even tests that look redundant stay until a separate spec evaluates them.
- **Not a microservice split.** This is the modular-monolith path. Folder boundaries are organizational, not deployment boundaries.

## Design

### Subfolder layout

Eight subfolders, mirroring production code domains:

```
healthflow/tests/
  __init__.py                  # already exists
  conftest.py                  # stays at top level — shared fixtures
  auth/                        # auth, security, sessions, audit logger
  agents/                      # the 5 LLM agents + harness
  api/                         # FastAPI routes, schemas, integration tests, app wiring
  database/                    # ORM models, DB config, plan/drug DB
  data/                        # data fetchers (CMS, FDA, HUD, NPPES), parsers, seed
  tools/                       # domain helpers (cost estimator, formulary, denial parser)
  feedback/                    # RLHF feedback loop, reward model, prompt updater
  observability/               # server log middleware, audit logger
  tenancy/                     # cross-broker isolation (the existing one) — set up empty
                               # for the multi-tenancy spec to fill in
```

Each subfolder contains an `__init__.py` (matching the existing `tests/__init__.py` package style — pytest discovers tests in a package layout this way).

### File-to-folder mapping

| Subfolder | Files |
|---|---|
| `auth/` | `test_auth.py`, `test_auth_dependencies.py`, `test_auth_integration.py`, `test_auth_schemas.py`, `test_security.py`, `test_session.py` |
| `agents/` | `test_appeal_agent.py`, `test_comparison_agent.py`, `test_cost_calculator_agent.py`, `test_network_agent.py`, `test_translation_agent.py`, `test_harness.py` |
| `api/` | `test_app_wiring.py`, `test_appeal_integration.py`, `test_appeal_route.py`, `test_appeal_schemas.py`, `test_calculate_integration.py`, `test_calculate_route.py`, `test_calculate_schemas.py`, `test_clients.py`, `test_comparison.py`, `test_feedback_integration.py`, `test_feedback_routes.py`, `test_feedback_schemas.py`, `test_routes.py`, `test_schemas.py`, `test_test_router.py`, `test_translate_integration.py`, `test_translate_route.py`, `test_translate_schemas.py`, `test_verify_integration.py`, `test_verify_route.py`, `test_verify_schemas.py` |
| `database/` | `test_database_config.py`, `test_database_models.py`, `test_drug_database.py`, `test_plan_database.py` |
| `data/` | `test_cms_fetcher.py`, `test_document_parser.py`, `test_npi_client.py`, `test_plan_parser.py`, `test_provider_cache.py`, `test_real_data_integration.py`, `test_real_fetcher.py`, `test_refresh_downloaders.py`, `test_seed_data.py`, `test_zip_mappings.py` |
| `tools/` | `test_appeal_writer.py`, `test_cost_estimator.py`, `test_cost_estimator_real.py`, `test_cost_modeler.py`, `test_denial_codes.py`, `test_denial_parser.py`, `test_formulary_checker.py`, `test_phi_redactor.py`, `test_provider_checker.py`, `test_provider_network.py`, `test_verify_cli.py` |
| `feedback/` | `test_feedback_collector.py`, `test_feedback_models.py`, `test_prompt_updater.py`, `test_reward_model.py` |
| `observability/` | `test_audit.py`, `test_server_log.py`, `test_server_log_middleware.py` |
| `tenancy/` | `test_cross_broker_isolation.py` |

Total: 66 files moved into 9 subfolders. (`conftest.py` and `__init__.py` stay at the top level.)

### Borderline cases — decisions made now to avoid bikeshed

- **`test_phi_redactor.py` → `tools/`** — the redactor lives in `healthflow/tools/phi_redactor.py` per import. Mirror.
- **`test_audit.py` → `observability/`** — tests `healthflow.logs.audit.AuditLogger`, not authentication.
- **`test_schemas.py` → `api/`** — tests `healthflow.models.schemas` request/response shapes. Even though source lives in `models/`, the tests are about API contracts.
- **`test_routes.py` → `api/`** — general route tests against `healthflow.main:app`.
- **`test_clients.py` → `api/`** — integration tests for `/clients` endpoints (registers + logs in + CRUDs).

If during the move a file's intent doesn't match its mapped folder, document the surprise and move it; don't go back and edit this spec.

### Mechanics

1. Create the 9 subfolders, each with an empty `__init__.py`.
2. `git mv` each file per the table above. One commit per subfolder is acceptable; one commit total is also acceptable. Single PR either way.
3. Run the full test suite. `pytest` should discover all 462 tests without configuration changes — `tests/__init__.py` already establishes package layout, and the `pyproject.toml`/`pytest.ini` test path (if any) points at `healthflow/tests/`.
4. If any test fails to import or collect: fix the import path (likely a sibling import like `from .helpers import X` that needs to become absolute), do **not** revert the move. If the fix exceeds 10 lines for a single file, stop and surface — that's a sign of unanticipated coupling.

### Verification

CI must be green after the reorg. Locally:

```
pytest healthflow/tests/ -q --collect-only | tail -20    # confirm count ≈ 462
pytest healthflow/tests/                                 # full run, all green
make all                                                 # if there's a Makefile target, run it
```

The `tests/tenancy/__init__.py` is created with the existing `test_cross_broker_isolation.py` already inside it. The multi-tenancy spec then adds the 3 new files into `tests/tenancy/` directly, no further reorg needed.

### Risks

| Risk | Mitigation |
|---|---|
| Hidden imports between test files (e.g. one test imports a helper from another) break after the move. | Fix imports to use absolute paths. Likely only a handful of files. If many files share helpers, that's a signal to extract to `tests/conftest.py` or `tests/helpers/` — but defer that judgment until evidence appears. |
| Existing CI config has a hardcoded path like `pytest healthflow/tests/test_*.py`. | Audit CI config (`.github/workflows/`, `Makefile`) before starting. If present, update to `pytest healthflow/tests/` (recursive). |
| Test collection count drops (some tests no longer discovered). | The verification step above catches this. The pre-move count is the baseline. |
| `pytest` rootdir / conftest discovery confusion. | `tests/conftest.py` stays put; its fixtures remain visible to subfolder tests via pytest's bottom-up conftest lookup. No additional `conftest.py` files are needed. |

## Out of Scope

- Reorganizing `healthflow/` (production code) into different modules — separate concern.
- Reviewing or merging redundant tests — separate concern.
- Splitting into actual microservices — explicitly rejected; this is a modular-monolith improvement.
- Adding a docstring or README to each subfolder — nice-to-have, not blocking. May land in a follow-up if reviewers ask.

## Acceptance

The reorg is done when:

1. All 9 subfolders exist with `__init__.py`.
2. All 66 files are moved per the mapping table; `tests/` no longer contains any `test_*.py` files at the top level.
3. `pytest healthflow/tests/` collects and passes the full 462-test suite (or whatever the current count is).
4. CI is green on the merge.
5. The multi-tenancy spec's references to `tests/tenancy/` are now satisfied by the new layout — that spec can proceed without modification.
