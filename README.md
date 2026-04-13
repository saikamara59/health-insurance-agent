# HealthFlow

AI-powered health insurance brokerage platform. Brokers manage client portfolios, compare Medicare Advantage plans, estimate costs, verify provider networks, translate coverage documents, generate claims appeal letters, and learn from feedback — all powered by Claude.

Built with real CMS Medicare plan data, real FDA drug data, and real NPPES provider lookups.

---

## Quick Start

### Option 1: Full Setup (recommended)

```bash
cp .env.example .env          # Add your ANTHROPIC_API_KEY
make all                       # Install deps, load data, run 407 tests
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

# Seed demo users
python seed.py                                # Login: demo@healthflow.com / healthflow123
```

### Option 3: Docker

```bash
cp .env.example .env          # Add your ANTHROPIC_API_KEY
make docker-up                 # Backend + Frontend + Redis
```

App at http://localhost (frontend) and http://localhost:8000/docs (API docs).

---

## Features

### AI-Powered Agents

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Plan Comparison | `POST /compare` | Compare up to 5 Medicare plans with AI recommendation |
| Coverage Translation | `POST /translate` | Paste a Summary of Benefits, ask questions in plain English |
| Cost Calculator | `POST /calculate` | Estimate annual out-of-pocket based on healthcare usage |
| Claims Appeal | `POST /appeal` | Parse denial letters, generate formal appeal templates |
| Network Verification | `POST /verify` | Check if doctors are in-network and drugs on formulary |
| Cost Estimation | `POST /estimate` | Get copay/tier for a specific medication or procedure |
| Plan Lookup | `GET /plans/{zip}` | List available plans for a zip code |

### Client Management

| Endpoint | Description |
|----------|-------------|
| `POST /clients` | Create client profile |
| `GET /clients` | List broker's clients |
| `GET /clients/{id}` | Get client details |
| `PUT /clients/{id}` | Update client |
| `DELETE /clients/{id}` | Delete client |

### Authentication

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create broker account |
| `POST /auth/login` | Get access + refresh tokens |
| `POST /auth/refresh` | Refresh expired access token |
| `GET /auth/profile` | Get broker profile |
| `PUT /auth/profile` | Update broker profile |

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
| `GET /history` | List action history (filterable) |
| `POST /history` | Record an action |

---

## Real Health Data

HealthFlow uses real public health data from CMS and FDA.

```bash
# Load curated seed data (51 plans, 90 drugs, 26 zip codes)
python scripts/refresh_data.py --seed-only

# Or download latest from CMS and FDA APIs
python scripts/refresh_data.py
```

Data stored in `healthflow_data.db` (gitignored). Falls back to mock data if the file doesn't exist.

**Data sources:**
- **CMS Medicare Advantage** — Real plan names, premiums, deductibles, star ratings from data.cms.gov
- **FDA OpenFDA** — Real drug names, NDC codes, formulary tiers from api.fda.gov
- **NPPES NPI Registry** — Real provider lookups from npiregistry.cms.hhs.gov (live API)

---

## Frontend Dashboard

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | Broker sign-in and registration |
| Dashboard | `/` | Overview with metrics, activity feed, system status |
| Client Portfolios | `/clients` | Client table with filters, pagination, CRUD |
| Add Client | `/clients/new` | 4-step intake wizard (Personal → Financial → Healthcare → Review) |
| Onboarding Success | `/clients/success` | Post-creation confirmation with quick actions |
| Client Profile | `/clients/:id` | Analysis workflow, profile editing, prescriptions, doctors |
| Plan Comparison | `/compare` | Side-by-side plan comparison with AI recommendation |
| Network Verification | `/network` | Provider and formulary checker per plan |
| Coverage Translator | `/translator` | Document Q&A with conversational follow-up |
| Cost Calculator | `/calculator` | Annual cost projections with utilization sliders |
| Claims Appeal | `/appeals` | Denial letter parser + appeal letter generator |
| Comparison History | `/history` | Timeline of all analyses and actions |
| Leads Pipeline | `/leads` | Prospect pipeline with intent badges |
| Analytics | `/analytics` | KPIs, charts, cohort analysis, reports |
| Activity Feed | `/activity` | Full audit trail of client interactions |
| Settings | `/settings` | Profile, security, API integrations, notifications |
| Support | `/support` | Knowledge library, ticket submission, contact |

---

## Makefile Commands

```bash
make help           # Show all commands
make install        # Install backend + frontend deps
make test           # Run all 407 tests
make test-quick     # Tests with compact output
make test-cov       # Tests with coverage report
make lint           # Run ruff linter
make lint-fix       # Auto-fix unused imports
make dev            # Start backend server
make frontend       # Start frontend dev server
make data           # Load real health data (seed)
make seed           # Seed demo broker + clients
make build          # Build frontend for production
make check          # CI gate: lint + tests + build
make all            # Full setup from scratch
make docker-up      # Start Docker stack
make docker-down    # Stop Docker stack
make clean          # Remove all generated files
```

---

## Architecture

```
React Frontend → Nginx → FastAPI Backend → Harness → Tools + Agents → Claude API
                                              ↓
                                     SQLite / PostgreSQL
```

### Backend Layers

- **Harness** — Input validation, medical advice output filtering, PHI redaction, audit logging
- **Tools** — Real CMS plan database, FDA drug database, plan parser, cost estimator, cost modeler, document parser, denial parser, denial codes DB (25 CARC/RARC codes), appeal writer, PHI redactor, NPI client (real NPPES API), provider network (40 providers), formulary checker, provider cache (24h TTL)
- **Agents** — Comparison, translation, cost calculator, appeal, network verification — all powered by Claude (claude-sonnet-4-6)
- **Feedback** — RLHF system: feedback collector, reward model, prompt updater, A/B testing
- **Database** — SQLAlchemy 2.0 async ORM, SQLite default (PostgreSQL via `DATABASE_URL`)
- **Auth** — JWT access/refresh tokens, bcrypt passwords, role-based access

### Frontend

- React 18 + Vite + Tailwind CSS
- Fonts: Saira Stencil One (logo), Merriweather (display), Manrope (headlines), Inter (body)
- Material Symbols Outlined icons
- Responsive sidebar with mobile hamburger menu
- Notification slide-out panel

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key for AI recommendations |
| `DATABASE_URL` | `sqlite+aiosqlite:///healthflow.db` | Database connection string |
| `JWT_SECRET` | dev default | JWT signing secret (change in production) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (optional) |

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

**Services:**
- `backend` — Python 3.12, FastAPI, uvicorn (port 8000)
- `frontend` — Node 20 build → Nginx (port 80)
- `redis` — Redis 7 Alpine (port 6379)

---

## Testing

```bash
make test           # 407 tests, ~22 seconds
make test-cov       # With coverage report
make lint           # Ruff linter
```

**Test coverage:** Auth, client CRUD, all 5 AI agents, feedback system, reward model, prompt updater, plan/drug databases, PHI redaction, denial parsing, API routes, integration flows.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Frontend | React 18, Vite, Tailwind CSS, React Router v6 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Cache | Redis (optional) |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Data | CMS data.cms.gov, FDA OpenFDA, NPPES NPI Registry |
| Infrastructure | Docker, Nginx, docker-compose |
| Testing | pytest, pytest-asyncio, httpx |

---

## Project Structure

```
healthflow/
├── main.py                    # FastAPI app entry point
├── api/                       # REST API routes
│   ├── routes.py              # Phase 1-5 agent endpoints
│   ├── client_router.py       # Client CRUD
│   ├── history_router.py      # Action history
│   └── v1/                    # Public API (future)
├── agents/                    # AI agents (Claude-powered)
│   ├── comparison_agent.py    # Plan comparison
│   ├── translation_agent.py   # Coverage Q&A
│   ├── cost_calculator_agent.py # Cost projections
│   ├── appeal_agent.py        # Claims appeal
│   ├── network_agent.py       # Network verification
│   └── harness.py             # Input/output guardrails
├── tools/                     # Data processing (no AI)
│   ├── cms_fetcher.py         # Real + mock plan data
│   ├── cost_estimator.py      # Drug/procedure pricing
│   ├── plan_parser.py         # Plan scoring/ranking
│   ├── cost_modeler.py        # Annual cost math
│   ├── document_parser.py     # SoB section splitting
│   ├── denial_parser.py       # Denial letter extraction
│   ├── denial_codes.py        # 25 CARC/RARC codes
│   ├── appeal_writer.py       # Appeal letter templates
│   ├── phi_redactor.py        # PHI stripping (regex)
│   ├── npi_client.py          # Real NPPES API
│   ├── provider_network.py    # 40 curated providers
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
│   ├── config.py              # SQLAlchemy engine
│   └── models.py              # ORM models
├── auth/                      # Authentication
│   ├── router.py              # Auth endpoints
│   ├── security.py            # JWT + bcrypt
│   └── dependencies.py        # FastAPI auth deps
├── models/
│   └── schemas.py             # Pydantic models
├── memory/
│   └── session.py             # Session store
├── logs/
│   └── audit.py               # Structured logging
└── tests/                     # 407 tests
frontend/                      # React SPA (17 pages)
scripts/
└── refresh_data.py            # CMS + FDA data loader
```
