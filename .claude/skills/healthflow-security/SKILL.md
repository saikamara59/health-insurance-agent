---
name: healthflow-security
description: Use when touching healthflow/auth/, healthflow/agents/ (LLM calls), client/PHI fields in healthflow/database/models.py, env/config, the seed script, or anything that logs request bodies. Project-specific PHI and secret-handling rules for HealthFlow.
---

# HealthFlow Security Notes

Project-specific traps. Generic OWASP advice (parameterize SQL, sanitize HTML, etc.) is not repeated here — assume those.

## PHI on the wire to Anthropic

Five agents in `healthflow/agents/` send data to Claude: `comparison_agent`, `cost_calculator_agent`, `network_agent`, `translation_agent`, `appeal_agent`. Client records contain medications, conditions, doctors, NPIs — all PHI.

**Rule:** Pass only the fields the prompt actually needs. Never pass a whole `Client` ORM object or `client.dict()` into a prompt template.

**Rule:** Don't log prompt payloads at INFO. If you must log for debugging, redact medication names, NPIs, and free-text symptom fields before logging — and gate it behind DEBUG.

**Rule:** When adding a new agent, the prompt-building function should take a typed minimal struct (e.g. `ComparisonInput`), not the full client.

## JWT_SECRET default is unsafe

`healthflow/auth/security.py:7` falls back to `"healthflow-dev-secret-change-in-production"` if `JWT_SECRET` is unset. Fine for local; catastrophic in prod.

**Rule:** Any deploy/Docker change must verify `JWT_SECRET` is set from the environment with no string default. If you touch this file, consider raising on missing env var instead of defaulting.

## Two databases — don't cross them

- `healthflow.db` → brokers, clients, prescriptions (PHI/PII)
- `healthflow_data.db` → CMS plans, ZIPs (public reference data)

**Rule:** Don't add foreign keys, joins, or backups that mix them. Keeping them separate is the only data-classification boundary this project has.

## Secrets and rotating keys

`.env.example` lists: `ANTHROPIC_API_KEY`, `JWT_SECRET`, `HUD_API_TOKEN`, and (in flight) `MARKETPLACE_API_KEY`.

**Rule:** Healthcare.gov Marketplace keys rotate every ~60 days. When implementing the ACA fetcher, treat HTTP 401 from `marketplace.api.healthcare.gov` as "key expired" with a clear actionable error (not a generic auth failure). Don't retry on 401.

**Rule:** Never commit `.env`, `~/.cache/healthflow/*`, or either `.db` file. The cache holds 39k HUD ZIPs but is rebuildable; the DBs hold PHI.

## Demo credentials in seed.py

`seed.py` creates `demo@healthflow.com / healthflow123`. This is intentional for local demos.

**Rule:** Never reuse this credential pattern for staging/prod. If you add a new "demo" account, it must be gated behind an explicit `SEED_DEMO=1` env var, not run on every startup.

## Logs

`healthflow.log` at repo root and `logs/` are not in `.gitignore`-equivalent containers — verify before any logging change. PHI in logs is the easiest accidental leak in this codebase.

## Quick checklist when reviewing a security-sensitive change

- [ ] No full `Client` objects passed into agent prompts or logs
- [ ] No new env var with an unsafe string default (look at `os.getenv("X", "...")`)
- [ ] No query/migration that joins `healthflow.db` and `healthflow_data.db`
- [ ] 401 from external APIs handled distinctly from other auth errors
- [ ] No new file path that could end up checked in containing PHI (`.db`, `.log`, cache dumps)
