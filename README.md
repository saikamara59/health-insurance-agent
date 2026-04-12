# HealthFlow

AI-powered health insurance brokerage platform. Brokers manage client portfolios, compare Medicare Advantage plans, estimate costs, verify provider networks, translate coverage documents, and generate claims appeal letters — all powered by Claude.

## Quick Start

### 1. Backend

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
python -m healthflow.main
```

API runs at http://localhost:8000 with interactive docs at http://localhost:8000/docs.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at http://localhost:5173.

### 3. Seed Demo Data

```bash
python seed.py
```

Login: `demo@healthflow.com` / `healthflow123`

Creates a broker account with 4 sample clients pre-loaded with doctors, prescriptions, and procedures.

## Real Health Data

HealthFlow can use real CMS Medicare Advantage plan data and FDA drug data.

### Load seed data (recommended for development)
```bash
python scripts/refresh_data.py --seed-only
```

### Download latest data from CMS and FDA
```bash
python scripts/refresh_data.py
```

The data is stored in `healthflow_data.db` (gitignored). If the file doesn't exist, the app falls back to curated mock data.

## Features

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Plan Comparison | `POST /compare` | Compare up to 5 Medicare plans by premium, deductible, OOP max, star rating |
| Cost Estimation | `POST /estimate` | Get copay/tier for a specific medication or procedure |
| Coverage Translation | `POST /translate` | Paste a Summary of Benefits, ask a question in plain English |
| Annual Cost Calculator | `POST /calculate` | Estimate total annual out-of-pocket based on your healthcare usage |
| Claims Appeal | `POST /appeal` | Parse denial letters, generate formal appeal letter templates |
| Network Verification | `POST /verify` | Check if your doctors are in-network and drugs on formulary (real NPPES API) |
| Plan Lookup | `GET /plans/{zip}` | List available plans for a zip code |

## Authentication

JWT-based auth with role-based access control. Brokers see only their own clients.

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create broker account |
| `POST /auth/login` | Get access + refresh tokens |
| `POST /auth/refresh` | Refresh expired access token |

## Client Management

All client endpoints require a valid JWT token (`Authorization: Bearer <token>`).

| Endpoint | Description |
|----------|-------------|
| `POST /clients` | Create client profile |
| `GET /clients` | List broker's clients |
| `GET /clients/{id}` | Get client details |
| `PUT /clients/{id}` | Update client |
| `DELETE /clients/{id}` | Delete client |

Client profiles store: name, zip code, age, income level, doctors (with NPIs), prescriptions, and procedures.

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | Broker sign-in and registration |
| Client Portfolio | `/` | Client list with filters, pagination, summary stats |
| Client Profile | `/clients/:id` | Client detail with analysis workflow (all 5 AI features), profile editing |

## CLI

```bash
# Plan comparison
python -m healthflow.cli compare --zip-code 10001 --age 65 --income low

# Cost estimate
python -m healthflow.cli estimate --plan-id H3312-034 --item Metformin --type medication

# Annual cost calculator
python -m healthflow.cli calculate --zip-code 10001 --income low --doctor-visits 12 --prescriptions "Metformin:12"

# Claims appeal
python -m healthflow.cli appeal --denial-text "Your claim for MRI denied. Code: CO-50."

# Network verification
python -m healthflow.cli verify --zip-code 10001 --income low --providers "Dr. Chen:1234567890" --prescriptions "Metformin"
```

## Supported Zip Codes

10001 (NYC), 90210 (LA), 60601 (Chicago), 33101 (Miami), 77001 (Houston), 85001 (Phoenix), 98101 (Seattle), 30301 (Atlanta), 02101 (Boston), 75201 (Dallas)

Other zip codes return a randomized selection of plans.

## Architecture

```
Client (React) → FastAPI → Harness (validate/filter/log) → Tools + Agents → Claude → Response
```

### Backend Layers

- **Harness** — Input validation, medical advice output filtering, PHI redaction, audit logging
- **Tools** — CMS fetcher (20 curated plans), plan parser, cost estimator (30 drugs, 20 procedures), cost modeler, document parser, denial parser, denial codes DB (25 CARC/RARC codes), appeal writer, PHI redactor, NPI client (real NPPES API), provider network (40 providers), formulary checker, provider cache (24h TTL)
- **Agents** — Comparison, translation, cost calculator, appeal, network verification — all powered by Claude
- **Database** — SQLAlchemy 2.0 async ORM, SQLite default (PostgreSQL via `DATABASE_URL` env var)
- **Auth** — JWT access/refresh tokens, bcrypt passwords, role-based access

### Frontend

- React 18 + Vite + Tailwind CSS
- Material Design 3 color system (from Stitch designs)
- JWT auth with protected routes

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `DATABASE_URL` | `sqlite+aiosqlite:///healthflow.db` | Database connection string |
| `JWT_SECRET` | dev default | JWT signing secret (change in production) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (optional) |

## Running Tests

```bash
pytest healthflow/tests/ -v
```

329 tests covering all backend features, auth, and client CRUD.

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy 2.0, Pydantic, Anthropic SDK, Click, pytest

**Frontend:** React 18, Vite, Tailwind CSS, React Router v6

**Infrastructure:** SQLite/PostgreSQL, Redis (optional), NPPES API (real)
