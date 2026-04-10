# HealthFlow

AI-powered Medicare Advantage plan comparison service. Compares plans by premium, deductible, out-of-pocket max, star rating, and estimates costs for your specific medications and procedures. Powered by Claude for plain-English recommendations.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your-key-here

# Start the API server
python -m healthflow.main
```

The API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

### POST /compare

Compare Medicare Advantage plans with personalized cost estimates.

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "zip_code": "10001",
    "age": 65,
    "income_level": "low",
    "medications": ["Metformin", "Lisinopril"],
    "procedures": ["Annual physical", "Blood work"]
  }'
```

### POST /estimate

Get cost estimate for a specific medication or procedure under a plan.

```bash
curl -X POST http://localhost:8000/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "H3312-034",
    "item_name": "Metformin",
    "item_type": "medication"
  }'
```

### POST /translate

Answer a question about a pasted Summary of Benefits document in plain English.

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "INPATIENT HOSPITAL CARE\nYou pay $250 copay per day for days 1-5.\n\nEMERGENCY CARE\nEmergency room: $90 copay (waived if admitted)",
    "question": "How much does an ER visit cost?"
  }'
```

### POST /calculate

Calculate estimated annual out-of-pocket costs based on your expected healthcare usage.

```bash
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "zip_code": "10001",
    "income_level": "low",
    "usage": {
      "doctor_visits_per_year": 12,
      "prescriptions": [
        {"name": "Metformin", "fills_per_year": 12},
        {"name": "Ozempic", "fills_per_year": 12}
      ],
      "procedures": [
        {"name": "MRI", "count": 2},
        {"name": "Blood work", "count": 4}
      ]
    }
  }'
```

You can also pass a `session_id` from a prior `/compare` call to reuse the same plans:

```bash
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id-here",
    "usage": {"doctor_visits_per_year": 12}
  }'
```

### POST /appeal

Parse a denial letter and generate a formal appeal letter template.

```bash
curl -X POST http://localhost:8000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "denial_text": "Patient: John Smith\nMember ID: ABC123\nYour claim for MRI of lumbar spine has been denied.\nDenial code: CO-50. The service is not deemed medically necessary.\nYou have 60 days to file an appeal.",
    "additional_context": "Patient has documented history of chronic lower back pain."
  }'
```

### POST /verify

Check provider network status and drug formulary coverage per plan.

```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "zip_code": "10001",
    "income_level": "low",
    "providers": [
      {"name": "Dr. Sarah Chen", "npi": "1234567890"},
      {"name": "Dr. Emily Thompson"}
    ],
    "prescriptions": ["Metformin", "Lisinopril", "Humira"]
  }'
```

Or use a session from a prior `/compare` call:

```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "providers": [{"name": "Dr. Sarah Chen", "npi": "1234567890"}],
    "prescriptions": ["Metformin"]
  }'
```

### GET /plans/{zip_code}

List available plans for a zip code.

```bash
curl http://localhost:8000/plans/10001
```

### GET /health

Health check.

```bash
curl http://localhost:8000/health
```

## CLI Usage

Start the API server first, then use the CLI:

```bash
# Interactive comparison
python -m healthflow.cli compare

# With arguments
python -m healthflow.cli compare --zip-code 10001 --age 65 --income low --medications "Metformin,Lisinopril"

# Cost estimate
python -m healthflow.cli estimate --plan-id H3312-034 --item Metformin --type medication

# Annual cost calculation
python -m healthflow.cli calculate --zip-code 10001 --income low --doctor-visits 12 --prescriptions "Metformin:12,Ozempic:12" --procedures "MRI:2"

# Generate appeal letter
python -m healthflow.cli appeal --denial-text "Your claim for MRI has been denied. Denial code: CO-50."

# Verify provider network and formulary coverage
python -m healthflow.cli verify \
  --zip-code 10001 \
  --income low \
  --providers "Dr. Sarah Chen:1234567890,Dr. Emily Thompson" \
  --prescriptions "Metformin,Lisinopril,Humira"

# Verify with a session from a prior compare
python -m healthflow.cli verify \
  --session-id your-session-id \
  --providers "Dr. Sarah Chen:1234567890" \
  --prescriptions "Metformin"
```

## Supported Zip Codes

10001 (NYC), 90210 (LA), 60601 (Chicago), 33101 (Miami), 77001 (Houston), 85001 (Phoenix), 98101 (Seattle), 30301 (Atlanta), 02101 (Boston), 75201 (Dallas)

Other zip codes return a randomized selection of plans.

## Authentication

HealthFlow uses JWT-based authentication. All client endpoints require a valid access token.

Set the following environment variables before starting the server:

- `JWT_SECRET` — Secret key for signing JWT tokens (required in production)
- `DATABASE_URL` — PostgreSQL connection string (e.g. `postgresql+asyncpg://user:pass@localhost/healthflow`)

### Auth Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | /auth/register | Create a broker account | No |
| POST | /auth/login | Get access + refresh tokens | No |
| POST | /auth/refresh | Refresh an access token | Refresh token |

### Client Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | /clients | Create a client profile | Yes |
| GET | /clients | List broker's clients | Yes |
| GET | /clients/{id} | Get client details | Yes |
| PUT | /clients/{id} | Update client profile | Yes |
| DELETE | /clients/{id} | Delete client | Yes |

### Example Usage

```bash
# Register a broker account
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "broker@example.com", "password": "securepass123", "full_name": "Test Broker"}'

# Login — returns access_token and refresh_token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "broker@example.com", "password": "securepass123"}'

# Refresh an expired access token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# Create a client profile (use the access_token from login response)
curl -X POST http://localhost:8000/clients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"full_name": "Jane Doe", "zip_code": "10001", "age": 45, "income_level": "medium", "doctors": [], "prescriptions": [], "procedures": []}'

# List all clients for the authenticated broker
curl http://localhost:8000/clients \
  -H "Authorization: Bearer <access_token>"

# Get a specific client
curl http://localhost:8000/clients/<client_id> \
  -H "Authorization: Bearer <access_token>"

# Update a client
curl -X PUT http://localhost:8000/clients/<client_id> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"age": 46, "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin"]}'

# Delete a client
curl -X DELETE http://localhost:8000/clients/<client_id> \
  -H "Authorization: Bearer <access_token>"
```

## Frontend

A React single-page application for health insurance brokers to manage client portfolios and run plan analyses.

### How to run

```bash
cd frontend && npm install && npm run dev
```

The frontend is available at http://localhost:5173.

Requires the FastAPI backend running at http://localhost:8000.

### Pages

| Page | Path | Description |
|------|------|-------------|
| Login | /login | Broker authentication (register / sign in) |
| Client Portfolio | / | List all clients, add new clients |
| Client Profile | /clients/:id | View and edit client details, run plan analysis |

---

## Running Tests

```bash
pytest healthflow/tests/ -v
```

## Tech Stack

- **FastAPI** — REST API framework
- **Claude API** (claude-sonnet-4-6) — AI-powered plan recommendations
- **Pydantic** — Request/response validation
- **Redis** — Optional session persistence (in-memory default)
- **Click** — CLI interface

## Architecture

```
HTTP Request → FastAPI → Harness (validate/filter/log) → Tools (fetch/parse/estimate) → Agent (Claude) → Response
```

- **Harness**: Validates inputs, filters medical advice from outputs, logs all decisions
- **CMS Fetcher**: Curated dataset of ~20 realistic Medicare Advantage plans
- **Plan Parser**: Ranks and scores plans based on income-weighted criteria
- **Cost Estimator**: ~30 medications and ~20 procedures with realistic pricing
- **Comparison Agent**: Generates plain-English recommendations via Claude
- **PHI Redactor**: Regex-based PHI stripping before any LLM call
- **Denial Parser**: Extracts denial codes, treatments, deadlines from letters
- **Denial Code DB**: Curated database of ~25 CARC/RARC codes with CMS rules
- **Appeal Writer**: Generates formal appeal letter templates
- **Appeal Agent**: Orchestrates denial parsing, code lookup, and Claude refinement
