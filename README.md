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
```

## Supported Zip Codes

10001 (NYC), 90210 (LA), 60601 (Chicago), 33101 (Miami), 77001 (Houston), 85001 (Phoenix), 98101 (Seattle), 30301 (Atlanta), 02101 (Boston), 75201 (Dallas)

Other zip codes return a randomized selection of plans.

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
