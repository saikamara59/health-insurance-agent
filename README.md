# HealthFlow

**An AI-powered health insurance brokerage platform** designed and built by [Saidu Kamara](https://github.com/saikamara59) to solve a real industry problem: health insurance is confusing, comparisons are manual, and brokers waste hours on paperwork that should be automated.

HealthFlow gives insurance brokers a single platform to manage client portfolios, compare Medicare Advantage plans side-by-side, estimate annual costs, verify provider networks against real NPPES data, translate dense policy documents into plain English, and auto-generate claims appeal letters — all backed by AI that learns from broker feedback to get smarter over time.

### Why This Exists

Health insurance brokers today juggle spreadsheets, PDFs, and phone calls to compare plans for their clients. Denial appeals are manually drafted from scratch. Brokers can't quickly answer "Is my doctor in-network?" or "What will my prescriptions cost under this plan?" without hours of research.

**HealthFlow automates all of this.** It pulls real plan data from CMS, real drug pricing from FDA, real provider verification from NPPES, and uses AI to generate the analysis and recommendations that brokers need — in seconds, not hours.

### Built With Real Data

This isn't a demo with fake data. HealthFlow integrates with real public health data sources:

- **51 Medicare Advantage plans** sourced from CMS with actual premiums, deductibles, and star ratings (currently a curated snapshot — CMS retired the Socrata API at `data.cms.gov/resource/` in 2026-05; live refresh is paused pending migration to the CMS quarterly file downloads or a successor API)
- **90 real medications** from FDA (OpenFDA) with accurate formulary tiers and copays
- **45 real doctors** with verified NPIs from the NPPES National Provider Registry (live API)
- **27 zip codes** across 11 major metro areas

---

## Security & Multi-Tenancy

HealthFlow enforces **per-broker tenant isolation at the SQLAlchemy layer**: every query against a PHI table (`clients`, `action_history`, `feedback`) is auto-filtered to the current broker via a `do_orm_execute` event listener. Forgetting a `WHERE broker_id = ...` clause in a route is structurally impossible — the filter is a property of the database session, not of every developer remembering to add it.

- **Foundation:** `healthflow/auth/tenant_context.py` (request-scoped `ContextVar`), `healthflow/database/tenant_filter.py` (the filter + raw-SQL guard).
- **Enforcement:** `healthflow/auth/dependencies.py:get_current_broker` sets the `ContextVar` for the duration of an authenticated request; the filter consumes it.
- **Composite writes** (e.g. `ActionHistory.client_id` referencing a Client) load the related row through the filter first; cross-broker references return 404 instead of writing.
- **Cross-broker reads** (RLHF analytics, e2e reset) are gated behind `system_context(reason="...")` with WARN-level audit logging. Each call site documents *why* it bypasses isolation.
- **Test coverage:** `healthflow/tests/tenancy/` proves cross-broker access is impossible across every PHI route, including a concurrent `asyncio.gather` test for ContextVar isolation.

Tenant isolation is the first piece of a six-part HIPAA-readiness foundation, all shipped: multi-tenancy, PHI redaction, PHI access audit log, auth hardening (lockout + refresh-token rotation + fail-loud `JWT_SECRET`), encryption at rest (AES-256-GCM on 8 PHI columns), and account management (admin RBAC + change/forgot/reset-password). See `docs/superpowers/specs/` for the per-project design rationale and `.claude/skills/healthflow-security/SKILL.md` for the per-rule guidance.

---

## Quick Start

### Option 1: Full Setup (recommended)

```bash
cp .env.example .env          # Add your ANTHROPIC_API_KEY
make all                       # Install deps, load data, run 610 tests
```

### Option 2: Step by Step

```bash
# Backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
python scripts/refresh_data.py --seed-only   # Load real health data
python -m healthflow.main                     # API at http://localhost:8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev     # Dashboard at http://localhost:5173

# Seed demo data (18 clients with real doctors)
python seed.py                                # Login: demo@healthflow.com / Healthflow123!
```

### Option 3: Docker

```bash
cp .env.example .env          # Add your ANTHROPIC_API_KEY
make docker-up                 # Backend + Frontend + Redis
```

App at http://localhost (frontend) and http://localhost:8000/docs (API docs).

---

## Demo Data

The seed script creates **18 clients across 11 cities** with real NPPES-verified doctors:

| City | Clients | Real Doctors (with NPIs) |
|------|---------|--------------------------|
| New York | Eleanor Rigby, Julian Miller, Marcus Chen | Dr. Nivedita Aanur, Dr. Justin Aaron |
| Staten Island | Anthony Russo, Maria DeLuca, Kevin O'Sullivan | Dr. Deborah Aanonsen, Dr. Fuad Abaleka |
| Los Angeles | Sofia Rodriguez, David Park | Dr. Omer Aba-Omer, Dr. Allan Abbott |
| Chicago | Sarah Hudson, Benjamin Thorne | Dr. Alexandra Aaronson, Dr. Jeff Abbott |
| Miami | Isabella Fernandez, Carlos Gutierrez | Dr. Yasmin Akhunji, Dr. Angel Alejandro |
| Houston | James Washington | Dr. Rodeo Abrencillo, Dr. Roberto Adachi |
| Seattle | Emily Nakamura | Dr. Nandini Abburi, Dr. Ali Abu-Alya |
| Atlanta | Robert Johnson | Dr. Amber Albaugh, Dr. Juliana Amankwah |
| Boston | Patricia O'Brien | Dr. Yuliya Afinogenova, Dr. Syed Ahmed |
| Dallas | Miguel Torres | Dr. Cherian Abraham, Dr. Sindhu Abraham |
| Phoenix | Linda Yamamoto | Dr. Sohail Abdul Salim, Dr. Naief Abudaff |

Each client has realistic prescriptions (Metformin, Ozempic, Eliquis, Humira, etc.) and age-appropriate procedures.

```bash
# Seed is idempotent — safe to run multiple times
python seed.py

# Refresh real doctor data from NPPES
python scripts/fetch_real_doctors.py
```

---

## Real Health Data

HealthFlow uses real public health data — no mock data in production.

| Source | Data | Count |
|--------|------|-------|
| **CMS** (curated snapshot¹) | Medicare Advantage plans (names, premiums, deductibles, star ratings) | 51 plans |
| **FDA OpenFDA** | Drug names, NDC codes, formulary tiers, copays | 90 drugs |
| **NPPES Registry** | Real doctor NPIs, specialties, locations (live API) | 45 doctors |
| **NLM RxNorm / RxNav** | Canonical US drug terminology — RxCUI, brand/generic mapping, ingredients (live REST API, no auth) | ~150k drug concepts |
| **Zip Mapping** | Plan availability by zip code | 27 zip codes |

```bash
python scripts/refresh_data.py --seed-only   # Load curated seed data
python scripts/refresh_data.py               # Download latest from FDA + NPPES (CMS path currently degraded — see Data refresh below)
```

Data stored in `healthflow_data.db` (gitignored). Falls back to curated mock data if the file doesn't exist.

¹ CMS Socrata API (`data.cms.gov/resource/`) was retired 2026-05; migration to the [quarterly Plan Landscape downloads](https://www.cms.gov/medicare/health-drug-plans/medicare-advantage-prescription-drug-coverage/plan-information) or a successor REST API is on the roadmap. FDA OpenFDA and NPPES are live.

---

## Data refresh

`make refresh-data` rebuilds `healthflow_data.db` from real public sources:

- **CMS Medicare Advantage Plan Landscape** (no auth) — every active MA plan
  in the country, ~3,000 plans across all carriers and states.
- **HUD USPS ZIP↔county crosswalk** (free token; sign up at
  https://www.huduser.gov/portal/dataset/uspszip-api.html) — joins CMS county
  service areas to ~33,000 US ZIPs.
- **FDA NDC directory** — drug catalog used by cost calculations.

Set `HUD_API_TOKEN=<token>` in `.env` to enable nationwide ZIP coverage.
Without it, the refresh still works but falls back to ~25 hand-curated demo
ZIPs.

> **Note (2026-05):** CMS retired the legacy Socrata SODA API at
> `data.cms.gov/resource/`; the `jfhb-kvhx` Plan Landscape endpoint now
> returns HTTP 410 Gone permanently. The full pagination + county-join
> wiring is in place and well-tested, but `download_cms_data` falls back
> to the curated `SEED_PLANS` until we migrate to the new API or to CMS's
> quarterly file downloads at
> https://www.cms.gov/medicare/health-drug-plans/medicare-advantage-prescription-drug-coverage/plan-information.
> HUD ZIP↔county still works and populates `plan_zips`; `plan_counties`
> stays empty in this degraded mode because we have no CMS county data to
> join against.

CLI flags:

```sh
python scripts/refresh_data.py                  # default — try real data, fall back to seed
python scripts/refresh_data.py --force-refresh  # ignore the local cache
python scripts/refresh_data.py --seed-only      # skip network entirely
python scripts/refresh_data.py --verbose        # debug logging
```

Cache lives in `~/.cache/healthflow/`. CMS and FDA TTL is 7/30 days; HUD is
30 days (HUD updates quarterly).

### Manual smoke check after a refresh

```sh
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plans;"           # ~3,000 with HUD token
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_counties;"   # ~30,000
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_zips;"       # ~400,000
```

```sql
SELECT p.plan_name, p.organization
FROM plans p JOIN plan_zips z ON p.plan_id = z.plan_id
WHERE z.zip_code = '10001'
LIMIT 20;
```

---

## Features

### AI-Powered Agents (Claude)

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Plan Comparison | `POST /compare` | Compare up to 5 Medicare plans with AI recommendation |
| Coverage Translation | `POST /translate` | Paste a Summary of Benefits, ask questions in plain English |
| Cost Calculator | `POST /calculate` | Estimate annual out-of-pocket based on healthcare usage |
| Claims Appeal | `POST /appeal` | Parse denial letters, generate formal appeal templates with PHI redaction |
| Network Verification | `POST /verify` | Check if doctors are in-network and drugs on formulary |
| Cost Estimation | `POST /estimate` | Get copay/tier for a specific medication or procedure |
| Plan Lookup | `GET /plans/{zip}` | List available plans for a zip code |

### Client Management (JWT Auth)

| Endpoint | Description |
|----------|-------------|
| `POST /clients` | Create client profile (name, zip, age, income, doctors, prescriptions, procedures) |
| `GET /clients` | List broker's clients |
| `GET /clients/{id}` | Get client details |
| `PUT /clients/{id}` | Update client |
| `DELETE /clients/{id}` | Delete client |

### Authentication

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create broker account (enforces password policy: ≥12 chars, letter+digit+symbol, not on common-passwords block-list) |
| `POST /auth/login` | Get access + refresh tokens (5 failed attempts → 15-minute account lockout) |
| `POST /auth/refresh` | Rotate refresh token; replaying a revoked token revokes all of the broker's active tokens (theft signal) |
| `POST /auth/logout` | Revoke the presented refresh token |
| `GET /auth/profile` | Get broker profile |
| `PUT /auth/profile` | Update broker profile |
| `POST /auth/change-password` | Authenticated broker rotates their own password; revokes all of the broker's refresh tokens |
| `POST /auth/forgot-password` | Request a password-reset email; always returns 200 (no enumeration); 60-second per-email cooldown |
| `POST /auth/reset-password` | Consume a single-use reset token + set a new password; revokes all of the broker's refresh tokens |

### Admin (RBAC-gated)

| Endpoint | Description |
|----------|-------------|
| `POST /admin/brokers/{broker_id}/unlock` | Force-unlock a locked broker (clears `failed_login_count` + `locked_until`); audit-logged |

Admins are created via `python scripts/promote_admin.py --email <broker-email>` — no API path flips role.

### Drug Search (RxNav)

| Endpoint | Description |
|----------|-------------|
| `GET /drugs/search?q=...&limit=...` | Authenticated drug autocomplete backed by NLM's RxNav REST API. Returns up to 50 matches with RxCUI, name, RxNorm Term Type, and a brand/generic flag. Silent-fail: a RxNav outage returns an empty list, not a 500. |

### RLHF Feedback System

| Endpoint | Description |
|----------|-------------|
| `POST /feedback` | Rate an AI output (accuracy, clarity, helpfulness 1-5) |
| `GET /feedback` | List feedback (filterable by agent type) |
| `GET /feedback/analytics` | Aggregated feedback stats per agent |
| `POST /feedback/reward-score` | Trigger reward model scoring |
| `GET /feedback/weekly-report` | Weekly performance summary |

### Action History

| Endpoint | Description |
|----------|-------------|
| `GET /history` | List action history (filterable by action_type, client_id) |
| `POST /history` | Record an action |

---

## Frontend Dashboard (18 Pages)

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | Broker sign-in and registration |
| Dashboard | `/` | Overview with metrics, activity feed, system status |
| Client Portfolios | `/clients` | Client table with filters, pagination, stats |
| Add Client | `/clients/new` | Single-form intake with Basics, Medical, and Providers sections |
| Onboarding Success | `/clients/success` | Post-creation confirmation with quick actions |
| Client Profile | `/clients/:id` | Analysis workflow, profile editing, prescriptions, doctors |
| Plan Comparison | `/compare` | Side-by-side plan cards with AI recommendation |
| Network Verification | `/network` | Provider and formulary checker with compatibility scores |
| Coverage Translator | `/translator` | Document Q&A with conversational follow-up |
| Cost Calculator | `/calculator` | Annual cost projections with utilization sliders |
| Claims Appeal | `/appeals` | Denial letter parser + appeal letter generator |
| Feedback Dashboard | `/feedback` | RLHF ratings, agent performance, weekly report |
| Comparison History | `/history` | Timeline of all analyses and actions |
| Leads Pipeline | `/leads` | Prospect pipeline with intent badges |
| Analytics | `/analytics` | KPIs, charts, cohort analysis, reports |
| Activity Feed | `/activity` | Full audit trail of client interactions |
| Settings | `/settings?tab=` | Profile, security, API integrations, notifications |
| Support | `/support` | Knowledge library, ticket submission, contact |

---

## Makefile Commands

```bash
make help           # Show all commands
make install        # Install backend + frontend deps
make test           # Run all 610 tests (verbose)
make test-quick     # Tests with compact output
make test-cov       # Tests with coverage report
make lint           # Run ruff linter
make lint-fix       # Auto-fix unused imports
make dead-code      # Find dead code with vulture
make dev            # Start backend server
make frontend       # Start frontend dev server
make data           # Load real CMS/FDA health data
make seed           # Seed 18 demo clients with real doctors
make build          # Build frontend for production
make check          # CI gate: lint + tests + build
make all            # Full setup from scratch
make docker-up      # Start Docker stack (backend + frontend + Redis)
make docker-down    # Stop Docker stack
make docker-logs    # Tail all service logs
make docker-reset   # Full rebuild from scratch
make clean          # Remove all generated files
```

---

## Architecture & Engineering Decisions

```
React Frontend → Nginx → FastAPI Backend → Harness → Tools + Agents → Claude API
                                              ↓
                              SQLite / PostgreSQL + healthflow_data.db
```

### Key Design Decisions

- **Guardrails-first approach** — Every AI output passes through a harness layer that blocks medical advice, redacts PHI (names, DOB, SSN, member IDs) via regex before any text reaches the LLM, and appends disclaimers. The AI never sees patient identifiable information.
- **Real data, graceful fallback** — The system uses real CMS/FDA data when available but falls back to curated mock data seamlessly. This means the app works out of the box without any external dependencies.
- **RLHF feedback loop** — Brokers rate every AI output (accuracy, clarity, helpfulness). A reward model scores outputs weekly, identifies the best examples, and a prompt updater generates improved few-shot prompts. A/B testing routes 20% of traffic to updated prompts to measure improvement before rolling out.
- **Income-weighted plan scoring** — Plans aren't ranked by premium alone. Low-income users see premium-weighted rankings, high-income users see quality-weighted rankings. The scoring model adapts to the client's financial situation.
- **PHI redaction before LLM** — In the claims appeal workflow, patient names, dates of birth, member IDs, SSNs, and phone numbers are regex-stripped before any text reaches Claude. The appeal letter template uses placeholders that the user fills in after download.

### Backend Layers

- **Harness** — Input validation, medical advice output filtering, PHI regex redaction, structured audit logging
- **Tools** — Real CMS plan database (51 plans), real FDA drug database (90 drugs), plan parser with income-weighted scoring, cost modeler with OOP max cap and deductible tracking, document parser with section matching, denial parser with CARC/RARC extraction, 25 denial codes with CMS rules and appeal arguments, appeal letter template generator, NPI client (live NPPES API), 45 NPPES-verified providers, formulary checker with per-plan drug exclusions, 24h TTL provider cache
- **Agents** — 5 Claude-powered agents: comparison, translation, cost calculator, appeal, network verification. Each agent builds a structured prompt from data, calls Claude for plain-English analysis, and filters the output through the harness.
- **Feedback** — RLHF loop: feedback collector (1-5 ratings), reward model (weekly scoring, flags low-quality patterns), prompt updater (few-shot generation from top-rated outputs), A/B testing (traffic-weighted variant routing)
- **Database** — SQLAlchemy 2.0 async ORM with 8 tables: Broker, Client, ActionHistory, Feedback, PromptVariant, PhiAccessLog (audit trail), RefreshToken (rotation + revocation), PasswordResetToken (single-use, cooldown-gated), plus the real health data in a separate SQLite file. PHI columns on Client/ActionHistory/Feedback are AES-256-GCM-encrypted via a TypeDecorator (`healthflow/database/encrypted_types.py`).
- **Auth** — JWT access/refresh tokens (1h/7d), bcrypt passwords, role-based access (broker/admin)

### Frontend

- React 18 + Vite + Tailwind CSS
- Design system: Saira Stencil One (logo), Merriweather (display), Manrope (headlines), Inter (body)
- Material Symbols Outlined icons
- Responsive sidebar with mobile hamburger menu + slide-in animation
- Notification slide-out panel with dismiss/clear functionality
- SessionStorage auth persistence (survives refresh)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key for AI recommendations |
| `DATABASE_URL` | `sqlite+aiosqlite:///healthflow.db` | Database connection string |
| `JWT_SECRET` | **(required, fail-loud)** | JWT signing secret. Module-import raises if unset or set to the legacy default. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `PHI_ENCRYPTION_KEY` | **(required, fail-loud)** | AES-256 key (base64-encoded 32 bytes) for column-level PHI encryption. Generate with `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`. Rotate by adding `PHI_ENCRYPTION_KEY_V2` alongside (new writes use the highest version). |
| `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` | unset | Migration-window escape hatch — lets the app read legacy plaintext rows during the encrypt-existing-phi sweep. **MUST be unset in production.** |
| `EMAIL_PROVIDER` | `console` | Transactional email backend. `console` logs the body (dev/test, no network). `ses` sends via AWS SES (BAA-eligible under the standard AWS BAA). |
| `EMAIL_FROM_ADDRESS` | (required when `EMAIL_PROVIDER=ses`) | Verified SES sender address. |
| `FRONTEND_BASE_URL` | (required for password reset) | Public origin used to build reset links: `${FRONTEND_BASE_URL}/reset-password?token=...`. |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (optional) |
| `HEALTHFLOW_TEST_MODE` | unset | **Test-only.** When `1`, registers `/__test/reset` and short-circuits Anthropic calls to deterministic stubs. Never set this in production. |

---

## CLI

```bash
python -m healthflow.cli compare --zip-code 10001 --age 65 --income low
python -m healthflow.cli estimate --plan-id H3312-034 --item Metformin --type medication
python -m healthflow.cli calculate --zip-code 10001 --income low --doctor-visits 12
python -m healthflow.cli appeal --denial-text "Claim denied. Code: CO-50."
python -m healthflow.cli verify --zip-code 10001 --income low --providers "Dr. Chen:1234567890"
```

---

## Docker

```bash
cp .env.example .env              # Add your ANTHROPIC_API_KEY
docker compose build               # Build images
docker compose up -d                # Start backend + frontend + Redis
docker compose logs -f              # Tail logs
docker compose down                 # Stop everything
```

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `backend` | Python 3.12 | 8000 | FastAPI + uvicorn |
| `frontend` | Node 20 → Nginx | 80 | React SPA + API proxy |
| `redis` | Redis 7 Alpine | 6379 | Session cache (optional) |

---

## Testing

```bash
make test           # ~610 backend tests, ~40 seconds
make test-cov       # With coverage report
make lint           # Ruff linter
make check          # Full CI gate: lint + tests + frontend build
```

Backend pytest covers: auth, client CRUD, all 5 AI agents, RLHF feedback system, reward model, prompt updater, A/B testing, real plan/drug databases, PHI redaction, denial parsing, cost modeling, provider caching, API routes, integration flows.

### Frontend E2E Tests (Playwright)

End-to-end tests run the real backend (Dockerized) against Chrome, Firefox, and Safari via Playwright. The test stack gates a `POST /__test/reset` endpoint behind `HEALTHFLOW_TEST_MODE=1` and seeds a deterministic broker + clients before each test. AI agents return deterministic stub responses in test mode so tests don't depend on a live Anthropic API key.

```bash
cd frontend
npm install
npx playwright install                 # one-time: download browsers
npm run test:e2e                       # runs docker stack + tests + teardown
npm run test:e2e:ui                    # interactive debugger UI
```

`global-setup.js` brings up `docker-compose.yml + docker-compose.test.yml` and `global-teardown.js` tears it down (including volumes). Auth is seeded per-test via an API login helper that writes `hf_token`/`hf_refresh` into `sessionStorage` before page load — see `frontend/tests/fixtures/index.js`.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Frontend | React 18, Vite, Tailwind CSS, React Router v6 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Cache | Redis 7 (optional) |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Data | CMS (curated; Socrata API retired 2026-05), FDA OpenFDA, NPPES NPI Registry |
| Infrastructure | Docker, Nginx, docker-compose |
| Testing | pytest, pytest-asyncio, httpx |
| Code Quality | ruff, vulture |

---

## Project Structure

```
healthflow/
├── main.py                    # FastAPI app entry point
├── api/                       # REST API routes
│   ├── routes.py              # Phase 1-5 agent endpoints
│   ├── client_router.py       # Client CRUD
│   └── history_router.py      # Action history
├── agents/                    # AI agents (Claude-powered)
│   ├── comparison_agent.py    # Plan comparison
│   ├── translation_agent.py   # Coverage Q&A
│   ├── cost_calculator_agent.py # Cost projections
│   ├── appeal_agent.py        # Claims appeal
│   ├── network_agent.py       # Network verification
│   └── harness.py             # Input/output guardrails
├── tools/                     # Data processing (no AI)
│   ├── cms_fetcher.py         # Real CMS + mock fallback
│   ├── cost_estimator.py      # Drug/procedure pricing (real + fallback)
│   ├── plan_parser.py         # Plan scoring/ranking
│   ├── cost_modeler.py        # Annual cost math
│   ├── document_parser.py     # SoB section splitting
│   ├── denial_parser.py       # Denial letter extraction
│   ├── denial_codes.py        # 25 CARC/RARC codes
│   ├── appeal_writer.py       # Appeal letter templates
│   ├── phi_redactor.py        # PHI stripping (regex)
│   ├── npi_client.py          # Real NPPES API
│   ├── provider_network.py    # 45 NPPES-verified providers
│   ├── provider_checker.py    # NPI + network check
│   ├── formulary_checker.py   # Drug formulary lookup
│   └── provider_cache.py      # 24h TTL cache
├── data/                      # Real health data layer
│   ├── plan_database.py       # SQLite CMS plan reader
│   └── drug_database.py       # SQLite FDA drug reader
├── feedback/                  # RLHF learning system
│   ├── collector.py           # Feedback CRUD
│   ├── reward_model.py        # Weekly scoring
│   ├── prompt_updater.py      # Few-shot + A/B testing
│   └── router.py              # Feedback API endpoints
├── database/                  # Persistence layer
│   ├── config.py              # SQLAlchemy async engine
│   └── models.py              # ORM models (8 tables)
├── auth/                      # Authentication
│   ├── router.py              # Auth endpoints
│   ├── security.py            # JWT + bcrypt
│   └── dependencies.py        # FastAPI auth deps
├── models/
│   └── schemas.py             # Pydantic models (~500 lines)
├── memory/
│   └── session.py             # Session store (in-memory + Redis)
├── logs/
│   └── audit.py               # Structured JSON logging
└── tests/                     # 610 tests

frontend/                      # React SPA (18 pages)
├── src/
│   ├── pages/                 # 18 page components
│   ├── components/            # Sidebar, TopBar, Layout, Notifications
│   ├── contexts/              # AuthContext (JWT)
│   └── api/                   # API client (fetch + auth)

scripts/
├── refresh_data.py            # CMS + FDA data loader
├── fetch_real_doctors.py      # NPPES doctor fetcher
└── real_doctors.json          # 45 real doctors with NPIs
```
