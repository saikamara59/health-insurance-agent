# HealthFlow Phase 8A: Public API v1 + API Key Auth + Rate Limiting — Design Spec

## Overview

Productize HealthFlow as an embeddable API. External developers authenticate with API keys (`hf_live_` prefixed), hit versioned `/api/v1/` endpoints for all Phase 1-5 features, and get structured JSON responses with usage metadata. In-memory rate limiting enforces 100 requests/day for free tier, unlimited for paid. API key management via broker dashboard (JWT auth).

## Database Model

### `api_keys` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| broker_id | UUID | FK → brokers.id, indexed |
| key_hash | VARCHAR(255) | SHA-256 hash of the full API key |
| key_prefix | VARCHAR(20) | `hf_live_` + first 8 chars (for display) |
| name | VARCHAR(100) | Human label e.g. "Production Key" |
| tier | VARCHAR(20) | "free" or "paid", default "free" |
| daily_limit | INTEGER | 100 for free, 0 for unlimited |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMP | |
| last_used_at | TIMESTAMP | Nullable |

## API Key Format

Format: `hf_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
- Prefix: `hf_live_`
- Body: 32 random hex characters via `secrets.token_hex(16)`
- Full key shown only once at creation
- Stored as SHA-256 hash in database
- `key_prefix` stored for identification in list views

## API Endpoints

### Key Management (JWT auth — broker dashboard)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api-keys | JWT | Create a new API key (returns full key once) |
| GET | /api-keys | JWT | List broker's keys (prefix + metadata, no full key) |
| DELETE | /api-keys/{id} | JWT | Revoke (soft delete) an API key |

### Public API v1 (API key auth via X-API-Key header)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/compare | API Key | Plan comparison |
| POST | /api/v1/translate | API Key | Coverage translation |
| POST | /api/v1/calculate | API Key | Cost calculation |
| POST | /api/v1/appeal | API Key | Claims appeal |
| POST | /api/v1/verify | API Key | Network verification |
| GET | /api/v1/usage | API Key | Request count and remaining quota |

## Auth Flow

```
Developer sends: X-API-Key: hf_live_xxxxx
  → Server hashes key with SHA-256
  → Looks up hash in api_keys table
  → Checks is_active == True
  → Checks rate limit (in-memory counter)
  → If all pass: execute agent, return response
  → If rate limited: 429 with error envelope
  → If invalid/revoked: 401 with error envelope
```

## Rate Limiting (In-Memory)

Global Python dict keyed by `api_key_id`, resets daily:

```python
_usage: dict[str, dict] = {}
# Each entry: {"count": int, "date": "YYYY-MM-DD"}
```

**Logic:**
- On each request: check if entry exists and date matches today
- If no entry or different date: reset to count=1, allow
- If count >= daily_limit and daily_limit > 0: return 429
- If daily_limit == 0: unlimited (paid tier), always allow
- Increment count on success

**Limitations:** Resets on server restart. Acceptable for Phase 8A — Redis upgrade in future.

## Response Envelope

All public API v1 endpoints return consistent JSON:

**Success:**
```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "usage": { "requests_today": 42, "daily_limit": 100, "remaining": 58 }
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error": { "code": "RATE_LIMIT_EXCEEDED", "message": "Daily request limit of 100 exceeded. Upgrade to paid tier for unlimited access." },
  "meta": { "request_id": "uuid", "api_version": "v1" }
}
```

**Error codes:** `INVALID_API_KEY`, `REVOKED_API_KEY`, `RATE_LIMIT_EXCEEDED`, `VALIDATION_ERROR`, `INTERNAL_ERROR`

## New/Modified Files

### New: `healthflow/api_keys/__init__.py`
Empty package marker.

### New: `healthflow/api_keys/service.py`
API key generation and CRUD.

**Interface:**
- `generate_key() -> tuple[str, str]` — returns `(full_key, key_hash)`. Uses `secrets.token_hex(16)` for the body, prepends `hf_live_`.
- `create_api_key(db, broker_id, name, tier="free") -> tuple[ApiKey, str]` — creates DB record, returns `(model, full_key)`. Full key only available at creation.
- `list_api_keys(db, broker_id) -> list[ApiKey]` — returns all active keys for broker.
- `revoke_api_key(db, broker_id, key_id) -> bool` — sets `is_active=False`. Returns False if not found or not owned by broker.
- `validate_key(db, raw_key) -> ApiKey | None` — hashes the key, looks up in DB, returns ApiKey if active, updates `last_used_at`.

### New: `healthflow/api_keys/rate_limiter.py`
In-memory rate limit checker.

**Interface:**
- `check_rate_limit(key_id: str, daily_limit: int) -> tuple[bool, int, int]` — returns `(allowed, count, remaining)`. Manages the global `_usage` dict.
- `get_usage(key_id: str) -> dict` — returns `{"requests_today": int, "daily_limit": int, "remaining": int}`.
- `reset_usage()` — test helper to clear the dict.

### New: `healthflow/api_keys/dependencies.py`
FastAPI dependency for API key auth.

**Interface:**
- `get_api_key_holder(x_api_key: str = Header(...), db = Depends(get_db)) -> ApiKey` — validates key, checks rate limit, raises HTTPException on failure. Returns the `ApiKey` ORM model.

### New: `healthflow/api_keys/router.py`
Key management endpoints (JWT auth, prefix `/api-keys`).

### New: `healthflow/api/v1/__init__.py`
Empty package marker.

### New: `healthflow/api/v1/router.py`
Public API v1 endpoints (API key auth, prefix `/api/v1`). Each endpoint:
1. Receives JSON matching existing Phase 1-5 request schemas
2. Calls the same agent logic (ComparisonAgent, TranslationAgent, etc.)
3. Wraps response in the envelope format
4. Includes usage metadata in `meta`

### Modified: `healthflow/database/models.py`
Append `ApiKey` ORM model after `PromptVariant`.

### Modified: `healthflow/models/schemas.py`
Append: `ApiKeyCreate`, `ApiKeyResponse`, `ApiKeyFullResponse`, `ApiEnvelope`, `UsageResponse`.

### Modified: `healthflow/main.py`
Include `api_keys_router` and `v1_router`.

## Pydantic Schemas

```python
class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=100)
    tier: str = Field(default="free")  # "free" or "paid"

class ApiKeyResponse(BaseModel):
    id: str
    key_prefix: str
    name: str
    tier: str
    daily_limit: int
    is_active: bool
    created_at: str
    last_used_at: str | None

class ApiKeyFullResponse(ApiKeyResponse):
    """Only returned at creation — includes the full key."""
    full_key: str

class UsageResponse(BaseModel):
    requests_today: int
    daily_limit: int
    remaining: int

class ApiEnvelope(BaseModel):
    status: str  # "success" or "error"
    data: dict | None = None
    error: dict | None = None
    meta: dict
```

## OpenAPI Documentation

FastAPI auto-generates at `/docs`. Public v1 endpoints tagged as "Public API v1" with descriptions and example bodies. Key management tagged as "API Key Management".

## Testing

### `healthflow/tests/test_api_key_service.py`
1. Generate key — has `hf_live_` prefix, 40 chars total
2. Create key — stored in DB, hash matches
3. Validate key — valid key returns ApiKey, invalid returns None
4. Revoke key — revoked key validation returns None
5. List keys — only active keys for broker

### `healthflow/tests/test_rate_limiter.py`
1. First request allowed, count=1
2. 100 requests allowed (free tier)
3. 101st request blocked (returns False)
4. Unlimited tier (daily_limit=0) always allowed
5. Day rollover resets count

### `healthflow/tests/test_api_keys_routes.py`
1. POST /api-keys — 201, returns full key
2. GET /api-keys — lists keys (no full key)
3. DELETE /api-keys/{id} — 204
4. Requires JWT auth

### `healthflow/tests/test_public_api.py`
1. POST /api/v1/compare — valid key → success envelope
2. POST /api/v1/compare — invalid key → 401
3. POST /api/v1/compare — revoked key → 401
4. POST /api/v1/compare — rate limited → 429
5. GET /api/v1/usage — returns correct counts
6. All endpoints return envelope format

## What This Does NOT Do

- No Stripe billing (Phase 8E)
- No webhook callbacks (Phase 8D)
- No white label config (Phase 8D)
- No Python/JS SDKs (Phase 8B/8C)
- No usage dashboard frontend (Phase 8F)
- No Redis rate limiting (future upgrade)
