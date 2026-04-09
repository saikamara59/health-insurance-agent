# HealthFlow Phase 6A: Database Layer + Auth Backend — Design Spec

## Overview

Add PostgreSQL persistence and JWT authentication to HealthFlow. Brokers create accounts, log in, and manage clients with full profiles (zip, age, income, doctors, prescriptions, procedures). All API calls are tied to a broker ID and logged as action history. This is the foundation for the multi-user broker dashboard.

## Database Models (PostgreSQL + SQLAlchemy 2.0)

### `brokers` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key, server-generated |
| email | VARCHAR(255) | Unique, indexed |
| hashed_password | VARCHAR(255) | bcrypt via passlib |
| full_name | VARCHAR(255) | |
| role | VARCHAR(20) | "broker" or "admin", default "broker" |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMP | Server default now() |

### `clients` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key, server-generated |
| broker_id | UUID | FK → brokers.id, indexed |
| full_name | VARCHAR(255) | |
| zip_code | VARCHAR(5) | |
| age | INTEGER | |
| income_level | VARCHAR(10) | low/medium/high |
| doctors | JSONB | `[{"name": "Dr. Chen", "npi": "1234567890"}]` |
| prescriptions | JSONB | `["Metformin", "Lisinopril"]` |
| procedures | JSONB | `["MRI", "Blood work"]` |
| created_at | TIMESTAMP | Server default now() |
| updated_at | TIMESTAMP | Auto-updated on change |

### `action_history` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key, server-generated |
| broker_id | UUID | FK → brokers.id, indexed |
| client_id | UUID | FK → clients.id, indexed |
| action_type | VARCHAR(50) | compare/calculate/translate/appeal/verify |
| request_data | JSONB | Input parameters (no PHI) |
| response_summary | JSONB | Key results summary |
| created_at | TIMESTAMP | Server default now() |

## Auth System (JWT)

### Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | /auth/register | Create broker account | No |
| POST | /auth/login | Returns access + refresh tokens | No |
| POST | /auth/refresh | Refresh access token | Refresh token |

### Token Strategy

- Access token: JWT, HS256, 1 hour expiry, contains `{"sub": broker_id, "role": role}`
- Refresh token: JWT, HS256, 7 days expiry, contains `{"sub": broker_id, "type": "refresh"}`
- Secret key: from `JWT_SECRET` env var (falls back to a dev default for local dev)

### Password Security

- Hashing: bcrypt via `passlib[bcrypt]`
- Minimum password length: 8 characters
- Login returns 401 on bad credentials (no enumeration of which field is wrong)

### Protected Endpoints

All existing Phase 1-5 endpoints become protected:
- Require `Authorization: Bearer <token>` header
- `get_current_broker` dependency extracts broker from token
- 401 if missing/invalid/expired token

### Role-Based Access

- `broker`: sees only their own clients and action history
- `admin`: sees all brokers, clients, and history (future use)
- Client CRUD endpoints filter by `broker_id` from token

## Client CRUD Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /clients | Create a client profile |
| GET | /clients | List broker's clients |
| GET | /clients/{id} | Get client details |
| PUT | /clients/{id} | Update client profile |
| DELETE | /clients/{id} | Delete client |

### Client Request/Response

```python
class ClientCreate(BaseModel):
    full_name: str
    zip_code: str          # 5-digit
    age: int               # 18-120
    income_level: str      # low/medium/high
    doctors: list[dict]    # [{"name": "...", "npi": "..."}]
    prescriptions: list[str]
    procedures: list[str]

class ClientResponse(BaseModel):
    id: str
    broker_id: str
    full_name: str
    zip_code: str
    age: int
    income_level: str
    doctors: list[dict]
    prescriptions: list[str]
    procedures: list[str]
    created_at: str
    updated_at: str
```

## New Project Structure

```
healthflow/
├── ...existing files...
├── database/
│   ├── __init__.py
│   ├── config.py         # SQLAlchemy async engine + session factory
│   ├── models.py         # Broker, Client, ActionHistory ORM models
│   └── migrations/       # Alembic directory (init + initial migration)
│       ├── env.py
│       ├── alembic.ini
│       └── versions/
├── auth/
│   ├── __init__.py
│   ├── router.py         # /auth/* endpoints
│   ├── security.py       # JWT create/verify, password hash/verify
│   └── dependencies.py   # get_current_broker FastAPI dependency
├── frontend/             # React app (placeholder for Phase 6D)
│   └── .gitkeep
```

## Database Configuration

- Connection string: `DATABASE_URL` env var, default `postgresql+asyncpg://postgres:postgres@localhost:5432/healthflow`
- For tests: SQLite in-memory via `sqlite+aiosqlite:///` (no PostgreSQL dependency for testing)
- Session: async SQLAlchemy sessions via `async_sessionmaker`
- Engine: `create_async_engine` with connection pooling

## New Dependencies

```
sqlalchemy>=2.0
asyncpg>=0.29
aiosqlite>=0.20
alembic>=1.13
python-jose>=3.3
passlib[bcrypt]>=1.7
python-multipart>=0.0.9
```

## Modified Files

### `healthflow/main.py`
- Import and include auth router and client router
- Add startup event to initialize database
- Existing endpoint routers unchanged (auth protection added in Phase 6C)

### `healthflow/models/schemas.py`
- Add: `BrokerCreate`, `BrokerResponse`, `LoginRequest`, `TokenResponse`, `ClientCreate`, `ClientResponse`, `ClientUpdate`

## Testing

### `healthflow/tests/test_database_models.py`
- Create broker, verify fields
- Create client linked to broker
- Create action history entry
- Client cascade on broker reference
- JSONB fields store/retrieve correctly

### `healthflow/tests/test_auth.py`
- Register new broker — 201
- Register duplicate email — 409
- Login with correct credentials — returns tokens
- Login with wrong password — 401
- Access protected endpoint without token — 401
- Access protected endpoint with valid token — 200
- Expired token — 401
- Refresh token flow — new access token returned

### `healthflow/tests/test_clients.py`
- Create client — 201
- List clients — returns only broker's clients
- Get client by ID — 200
- Get another broker's client — 403
- Update client — 200
- Delete client — 204

## What This Does NOT Do

- No frontend (Phase 6D)
- No Docker setup (Phase 6E)
- No refactoring of existing Phase 1-5 endpoints for multi-tenancy (Phase 6C)
- No rate limiting (future)
- No email verification (future)
- No password reset flow (future)
