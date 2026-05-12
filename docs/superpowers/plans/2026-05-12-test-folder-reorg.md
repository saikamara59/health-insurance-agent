# Test Folder Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the 66 flat `test_*.py` files in `healthflow/tests/` into 9 domain subfolders mirroring the production code structure, with no test logic changes and no production code changes.

**Architecture:** Pure structural reorg via `git mv` + per-subfolder `__init__.py`. Pytest's default discovery finds tests recursively via the existing `tests/__init__.py` package layout. No CI config or `pyproject.toml` changes required (`make test` already uses `healthflow/tests/` recursively; CI runs only frontend e2e). Per-subfolder commits give bisectability.

**Tech Stack:** Python, pytest, git. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-05-12-test-folder-reorg-design.md](../specs/2026-05-12-test-folder-reorg-design.md)

---

## File Structure

After this plan, `healthflow/tests/` looks like:

```
healthflow/tests/
  __init__.py                       (existing, untouched)
  conftest.py                       (existing, untouched — fixtures inherited via pytest lookup)
  auth/__init__.py                  (new) + 6 test files
  agents/__init__.py                (new) + 6 test files
  api/__init__.py                   (new) + 21 test files
  database/__init__.py              (new) + 4 test files
  data/__init__.py                  (new) + 10 test files
  tools/__init__.py                 (new) + 11 test files
  feedback/__init__.py              (new) + 4 test files
  observability/__init__.py         (new) + 3 test files
  tenancy/__init__.py               (new) + 1 test file (existing test_cross_broker_isolation.py)
```

Total: 9 new `__init__.py` files, 66 file moves.

---

## Task 1: Capture baseline

**Files:**
- Read-only: `healthflow/tests/`, `Makefile`

- [ ] **Step 1: Confirm working tree is clean and on main**

```bash
git status
git branch --show-current
```

Expected: `nothing to commit, working tree clean` and `main`. If not clean, stop and resolve before proceeding.

- [ ] **Step 2: Capture pre-reorg test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -5
```

Expected: a final line like `462 tests collected in X.XXs` (count may differ; record whatever it is). Note this number — every later verification step must match it.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick
```

Expected: all tests pass. If anything is failing on `main` before we start, stop and surface — don't reorg on top of broken tests.

- [ ] **Step 4: Record the baseline count and the head SHA**

In your scratchpad / commit log message later, write down:

```
Pre-reorg baseline:
  test count: <NUMBER FROM STEP 2>
  HEAD: <output of: git rev-parse HEAD>
```

No commit for this task — it's audit only.

---

## Task 2: Create the 9 subfolders with `__init__.py`

**Files:**
- Create: `healthflow/tests/auth/__init__.py`
- Create: `healthflow/tests/agents/__init__.py`
- Create: `healthflow/tests/api/__init__.py`
- Create: `healthflow/tests/database/__init__.py`
- Create: `healthflow/tests/data/__init__.py`
- Create: `healthflow/tests/tools/__init__.py`
- Create: `healthflow/tests/feedback/__init__.py`
- Create: `healthflow/tests/observability/__init__.py`
- Create: `healthflow/tests/tenancy/__init__.py`

- [ ] **Step 1: Create the 9 directories and empty `__init__.py` files in each**

```bash
for d in auth agents api database data tools feedback observability tenancy; do
  mkdir -p "healthflow/tests/$d"
  : > "healthflow/tests/$d/__init__.py"
done
```

- [ ] **Step 2: Verify the scaffold**

```bash
ls healthflow/tests/*/__init__.py
```

Expected: 9 lines, one per subfolder.

- [ ] **Step 3: Confirm test count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. Empty `__init__.py` files do not add or remove tests.

- [ ] **Step 4: Commit the scaffold**

```bash
git add healthflow/tests/auth/__init__.py healthflow/tests/agents/__init__.py healthflow/tests/api/__init__.py healthflow/tests/database/__init__.py healthflow/tests/data/__init__.py healthflow/tests/tools/__init__.py healthflow/tests/feedback/__init__.py healthflow/tests/observability/__init__.py healthflow/tests/tenancy/__init__.py
git commit -m "Scaffold tests/ subfolders for domain reorg"
```

---

## Task 3: Move auth tests (6 files)

**Files:**
- Move: `healthflow/tests/test_auth.py` → `healthflow/tests/auth/test_auth.py`
- Move: `healthflow/tests/test_auth_dependencies.py` → `healthflow/tests/auth/test_auth_dependencies.py`
- Move: `healthflow/tests/test_auth_integration.py` → `healthflow/tests/auth/test_auth_integration.py`
- Move: `healthflow/tests/test_auth_schemas.py` → `healthflow/tests/auth/test_auth_schemas.py`
- Move: `healthflow/tests/test_security.py` → `healthflow/tests/auth/test_security.py`
- Move: `healthflow/tests/test_session.py` → `healthflow/tests/auth/test_session.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_auth.py healthflow/tests/auth/test_auth.py
git mv healthflow/tests/test_auth_dependencies.py healthflow/tests/auth/test_auth_dependencies.py
git mv healthflow/tests/test_auth_integration.py healthflow/tests/auth/test_auth_integration.py
git mv healthflow/tests/test_auth_schemas.py healthflow/tests/auth/test_auth_schemas.py
git mv healthflow/tests/test_security.py healthflow/tests/auth/test_security.py
git mv healthflow/tests/test_session.py healthflow/tests/auth/test_session.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully (no `ERROR` lines).

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. If lower: a sibling import inside one of the moved files broke. Read the error from Step 2, fix the import to use absolute paths (e.g. `from healthflow.tests.helpers import X` rather than `from .helpers import X`), then re-verify. **Do not revert the move.** If the fix exceeds 10 lines for one file, stop and surface — that's unanticipated coupling.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move auth tests into healthflow/tests/auth/"
```

---

## Task 4: Move agent tests (6 files)

**Files:**
- Move: `healthflow/tests/test_appeal_agent.py` → `healthflow/tests/agents/test_appeal_agent.py`
- Move: `healthflow/tests/test_comparison_agent.py` → `healthflow/tests/agents/test_comparison_agent.py`
- Move: `healthflow/tests/test_cost_calculator_agent.py` → `healthflow/tests/agents/test_cost_calculator_agent.py`
- Move: `healthflow/tests/test_network_agent.py` → `healthflow/tests/agents/test_network_agent.py`
- Move: `healthflow/tests/test_translation_agent.py` → `healthflow/tests/agents/test_translation_agent.py`
- Move: `healthflow/tests/test_harness.py` → `healthflow/tests/agents/test_harness.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_appeal_agent.py healthflow/tests/agents/test_appeal_agent.py
git mv healthflow/tests/test_comparison_agent.py healthflow/tests/agents/test_comparison_agent.py
git mv healthflow/tests/test_cost_calculator_agent.py healthflow/tests/agents/test_cost_calculator_agent.py
git mv healthflow/tests/test_network_agent.py healthflow/tests/agents/test_network_agent.py
git mv healthflow/tests/test_translation_agent.py healthflow/tests/agents/test_translation_agent.py
git mv healthflow/tests/test_harness.py healthflow/tests/agents/test_harness.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/agents/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the same import-fix procedure as Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move agent tests into healthflow/tests/agents/"
```

---

## Task 5: Move API tests (21 files)

**Files:**
- Move: `healthflow/tests/test_app_wiring.py` → `healthflow/tests/api/test_app_wiring.py`
- Move: `healthflow/tests/test_appeal_integration.py` → `healthflow/tests/api/test_appeal_integration.py`
- Move: `healthflow/tests/test_appeal_route.py` → `healthflow/tests/api/test_appeal_route.py`
- Move: `healthflow/tests/test_appeal_schemas.py` → `healthflow/tests/api/test_appeal_schemas.py`
- Move: `healthflow/tests/test_calculate_integration.py` → `healthflow/tests/api/test_calculate_integration.py`
- Move: `healthflow/tests/test_calculate_route.py` → `healthflow/tests/api/test_calculate_route.py`
- Move: `healthflow/tests/test_calculate_schemas.py` → `healthflow/tests/api/test_calculate_schemas.py`
- Move: `healthflow/tests/test_clients.py` → `healthflow/tests/api/test_clients.py`
- Move: `healthflow/tests/test_comparison.py` → `healthflow/tests/api/test_comparison.py`
- Move: `healthflow/tests/test_feedback_integration.py` → `healthflow/tests/api/test_feedback_integration.py`
- Move: `healthflow/tests/test_feedback_routes.py` → `healthflow/tests/api/test_feedback_routes.py`
- Move: `healthflow/tests/test_feedback_schemas.py` → `healthflow/tests/api/test_feedback_schemas.py`
- Move: `healthflow/tests/test_routes.py` → `healthflow/tests/api/test_routes.py`
- Move: `healthflow/tests/test_schemas.py` → `healthflow/tests/api/test_schemas.py`
- Move: `healthflow/tests/test_test_router.py` → `healthflow/tests/api/test_test_router.py`
- Move: `healthflow/tests/test_translate_integration.py` → `healthflow/tests/api/test_translate_integration.py`
- Move: `healthflow/tests/test_translate_route.py` → `healthflow/tests/api/test_translate_route.py`
- Move: `healthflow/tests/test_translate_schemas.py` → `healthflow/tests/api/test_translate_schemas.py`
- Move: `healthflow/tests/test_verify_integration.py` → `healthflow/tests/api/test_verify_integration.py`
- Move: `healthflow/tests/test_verify_route.py` → `healthflow/tests/api/test_verify_route.py`
- Move: `healthflow/tests/test_verify_schemas.py` → `healthflow/tests/api/test_verify_schemas.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_app_wiring.py healthflow/tests/api/test_app_wiring.py
git mv healthflow/tests/test_appeal_integration.py healthflow/tests/api/test_appeal_integration.py
git mv healthflow/tests/test_appeal_route.py healthflow/tests/api/test_appeal_route.py
git mv healthflow/tests/test_appeal_schemas.py healthflow/tests/api/test_appeal_schemas.py
git mv healthflow/tests/test_calculate_integration.py healthflow/tests/api/test_calculate_integration.py
git mv healthflow/tests/test_calculate_route.py healthflow/tests/api/test_calculate_route.py
git mv healthflow/tests/test_calculate_schemas.py healthflow/tests/api/test_calculate_schemas.py
git mv healthflow/tests/test_clients.py healthflow/tests/api/test_clients.py
git mv healthflow/tests/test_comparison.py healthflow/tests/api/test_comparison.py
git mv healthflow/tests/test_feedback_integration.py healthflow/tests/api/test_feedback_integration.py
git mv healthflow/tests/test_feedback_routes.py healthflow/tests/api/test_feedback_routes.py
git mv healthflow/tests/test_feedback_schemas.py healthflow/tests/api/test_feedback_schemas.py
git mv healthflow/tests/test_routes.py healthflow/tests/api/test_routes.py
git mv healthflow/tests/test_schemas.py healthflow/tests/api/test_schemas.py
git mv healthflow/tests/test_test_router.py healthflow/tests/api/test_test_router.py
git mv healthflow/tests/test_translate_integration.py healthflow/tests/api/test_translate_integration.py
git mv healthflow/tests/test_translate_route.py healthflow/tests/api/test_translate_route.py
git mv healthflow/tests/test_translate_schemas.py healthflow/tests/api/test_translate_schemas.py
git mv healthflow/tests/test_verify_integration.py healthflow/tests/api/test_verify_integration.py
git mv healthflow/tests/test_verify_route.py healthflow/tests/api/test_verify_route.py
git mv healthflow/tests/test_verify_schemas.py healthflow/tests/api/test_verify_schemas.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/api/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move API tests into healthflow/tests/api/"
```

---

## Task 6: Move database tests (4 files)

**Files:**
- Move: `healthflow/tests/test_database_config.py` → `healthflow/tests/database/test_database_config.py`
- Move: `healthflow/tests/test_database_models.py` → `healthflow/tests/database/test_database_models.py`
- Move: `healthflow/tests/test_drug_database.py` → `healthflow/tests/database/test_drug_database.py`
- Move: `healthflow/tests/test_plan_database.py` → `healthflow/tests/database/test_plan_database.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_database_config.py healthflow/tests/database/test_database_config.py
git mv healthflow/tests/test_database_models.py healthflow/tests/database/test_database_models.py
git mv healthflow/tests/test_drug_database.py healthflow/tests/database/test_drug_database.py
git mv healthflow/tests/test_plan_database.py healthflow/tests/database/test_plan_database.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/database/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move database tests into healthflow/tests/database/"
```

---

## Task 7: Move data-pipeline tests (10 files)

**Files:**
- Move: `healthflow/tests/test_cms_fetcher.py` → `healthflow/tests/data/test_cms_fetcher.py`
- Move: `healthflow/tests/test_document_parser.py` → `healthflow/tests/data/test_document_parser.py`
- Move: `healthflow/tests/test_npi_client.py` → `healthflow/tests/data/test_npi_client.py`
- Move: `healthflow/tests/test_plan_parser.py` → `healthflow/tests/data/test_plan_parser.py`
- Move: `healthflow/tests/test_provider_cache.py` → `healthflow/tests/data/test_provider_cache.py`
- Move: `healthflow/tests/test_real_data_integration.py` → `healthflow/tests/data/test_real_data_integration.py`
- Move: `healthflow/tests/test_real_fetcher.py` → `healthflow/tests/data/test_real_fetcher.py`
- Move: `healthflow/tests/test_refresh_downloaders.py` → `healthflow/tests/data/test_refresh_downloaders.py`
- Move: `healthflow/tests/test_seed_data.py` → `healthflow/tests/data/test_seed_data.py`
- Move: `healthflow/tests/test_zip_mappings.py` → `healthflow/tests/data/test_zip_mappings.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_cms_fetcher.py healthflow/tests/data/test_cms_fetcher.py
git mv healthflow/tests/test_document_parser.py healthflow/tests/data/test_document_parser.py
git mv healthflow/tests/test_npi_client.py healthflow/tests/data/test_npi_client.py
git mv healthflow/tests/test_plan_parser.py healthflow/tests/data/test_plan_parser.py
git mv healthflow/tests/test_provider_cache.py healthflow/tests/data/test_provider_cache.py
git mv healthflow/tests/test_real_data_integration.py healthflow/tests/data/test_real_data_integration.py
git mv healthflow/tests/test_real_fetcher.py healthflow/tests/data/test_real_fetcher.py
git mv healthflow/tests/test_refresh_downloaders.py healthflow/tests/data/test_refresh_downloaders.py
git mv healthflow/tests/test_seed_data.py healthflow/tests/data/test_seed_data.py
git mv healthflow/tests/test_zip_mappings.py healthflow/tests/data/test_zip_mappings.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/data/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move data-pipeline tests into healthflow/tests/data/"
```

---

## Task 8: Move tools tests (11 files)

**Files:**
- Move: `healthflow/tests/test_appeal_writer.py` → `healthflow/tests/tools/test_appeal_writer.py`
- Move: `healthflow/tests/test_cost_estimator.py` → `healthflow/tests/tools/test_cost_estimator.py`
- Move: `healthflow/tests/test_cost_estimator_real.py` → `healthflow/tests/tools/test_cost_estimator_real.py`
- Move: `healthflow/tests/test_cost_modeler.py` → `healthflow/tests/tools/test_cost_modeler.py`
- Move: `healthflow/tests/test_denial_codes.py` → `healthflow/tests/tools/test_denial_codes.py`
- Move: `healthflow/tests/test_denial_parser.py` → `healthflow/tests/tools/test_denial_parser.py`
- Move: `healthflow/tests/test_formulary_checker.py` → `healthflow/tests/tools/test_formulary_checker.py`
- Move: `healthflow/tests/test_phi_redactor.py` → `healthflow/tests/tools/test_phi_redactor.py`
- Move: `healthflow/tests/test_provider_checker.py` → `healthflow/tests/tools/test_provider_checker.py`
- Move: `healthflow/tests/test_provider_network.py` → `healthflow/tests/tools/test_provider_network.py`
- Move: `healthflow/tests/test_verify_cli.py` → `healthflow/tests/tools/test_verify_cli.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_appeal_writer.py healthflow/tests/tools/test_appeal_writer.py
git mv healthflow/tests/test_cost_estimator.py healthflow/tests/tools/test_cost_estimator.py
git mv healthflow/tests/test_cost_estimator_real.py healthflow/tests/tools/test_cost_estimator_real.py
git mv healthflow/tests/test_cost_modeler.py healthflow/tests/tools/test_cost_modeler.py
git mv healthflow/tests/test_denial_codes.py healthflow/tests/tools/test_denial_codes.py
git mv healthflow/tests/test_denial_parser.py healthflow/tests/tools/test_denial_parser.py
git mv healthflow/tests/test_formulary_checker.py healthflow/tests/tools/test_formulary_checker.py
git mv healthflow/tests/test_phi_redactor.py healthflow/tests/tools/test_phi_redactor.py
git mv healthflow/tests/test_provider_checker.py healthflow/tests/tools/test_provider_checker.py
git mv healthflow/tests/test_provider_network.py healthflow/tests/tools/test_provider_network.py
git mv healthflow/tests/test_verify_cli.py healthflow/tests/tools/test_verify_cli.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/tools/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move tools tests into healthflow/tests/tools/"
```

---

## Task 9: Move feedback tests (4 files)

**Files:**
- Move: `healthflow/tests/test_feedback_collector.py` → `healthflow/tests/feedback/test_feedback_collector.py`
- Move: `healthflow/tests/test_feedback_models.py` → `healthflow/tests/feedback/test_feedback_models.py`
- Move: `healthflow/tests/test_prompt_updater.py` → `healthflow/tests/feedback/test_prompt_updater.py`
- Move: `healthflow/tests/test_reward_model.py` → `healthflow/tests/feedback/test_reward_model.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_feedback_collector.py healthflow/tests/feedback/test_feedback_collector.py
git mv healthflow/tests/test_feedback_models.py healthflow/tests/feedback/test_feedback_models.py
git mv healthflow/tests/test_prompt_updater.py healthflow/tests/feedback/test_prompt_updater.py
git mv healthflow/tests/test_reward_model.py healthflow/tests/feedback/test_reward_model.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/feedback/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move feedback-loop tests into healthflow/tests/feedback/"
```

---

## Task 10: Move observability tests (3 files)

**Files:**
- Move: `healthflow/tests/test_audit.py` → `healthflow/tests/observability/test_audit.py`
- Move: `healthflow/tests/test_server_log.py` → `healthflow/tests/observability/test_server_log.py`
- Move: `healthflow/tests/test_server_log_middleware.py` → `healthflow/tests/observability/test_server_log_middleware.py`

- [ ] **Step 1: Move the files with `git mv`**

```bash
git mv healthflow/tests/test_audit.py healthflow/tests/observability/test_audit.py
git mv healthflow/tests/test_server_log.py healthflow/tests/observability/test_server_log.py
git mv healthflow/tests/test_server_log_middleware.py healthflow/tests/observability/test_server_log_middleware.py
```

- [ ] **Step 2: Verify discovery for the moved files**

```bash
.venv/bin/python -m pytest healthflow/tests/observability/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move observability tests into healthflow/tests/observability/"
```

---

## Task 11: Move tenancy test (1 file)

**Files:**
- Move: `healthflow/tests/test_cross_broker_isolation.py` → `healthflow/tests/tenancy/test_cross_broker_isolation.py`

- [ ] **Step 1: Move the file with `git mv`**

```bash
git mv healthflow/tests/test_cross_broker_isolation.py healthflow/tests/tenancy/test_cross_broker_isolation.py
```

- [ ] **Step 2: Verify discovery for the moved file**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/ --collect-only -q 2>&1 | tail -3
```

Expected: tests collected successfully.

- [ ] **Step 3: Verify total count is unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: same count as Task 1 Step 2. On mismatch, follow the import-fix procedure from Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move cross-broker isolation test into healthflow/tests/tenancy/"
```

---

## Task 12: Final verification

**Files:** None (verification only).

- [ ] **Step 1: Confirm `healthflow/tests/` has no remaining top-level `test_*.py` files**

```bash
ls healthflow/tests/test_*.py 2>/dev/null
```

Expected: no output (the glob matches nothing). If any files remain, they were missed in Tasks 3–11; move them into the appropriate subfolder per the spec mapping table, commit, then re-run this step.

- [ ] **Step 2: Confirm the new layout**

```bash
ls -d healthflow/tests/*/
```

Expected: 9 directories — `agents/`, `api/`, `auth/`, `data/`, `database/`, `feedback/`, `observability/`, `tenancy/`, `tools/`. (Plus `__pycache__/` which is fine.)

- [ ] **Step 3: Run the full test suite**

```bash
make test-quick
```

Expected: all tests pass. The count must match the baseline from Task 1 Step 2.

- [ ] **Step 4: Run `make check` to confirm lint + tests + frontend build still pass**

```bash
make check
```

Expected: green across lint, tests, and frontend build.

- [ ] **Step 5: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 10 commits (1 scaffold + 9 per-subfolder moves), each with a clear message. If reviewing the PR, this is what reviewers will bisect.

No new commit for this task — verification only. Push when satisfied:

```bash
git push origin main
```

(Or: open a PR if the team workflow uses PRs. There's no remote rule against direct push to `main` recorded in the repo.)
