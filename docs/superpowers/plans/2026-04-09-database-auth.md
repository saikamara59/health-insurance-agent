# Database Layer + Auth Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PostgreSQL persistence with SQLAlchemy 2.0, JWT authentication, broker accounts, client CRUD, and action history — the foundation for the multi-user broker dashboard.

**Architecture:** SQLAlchemy async ORM models for brokers, clients, and action history. JWT auth with access/refresh tokens. FastAPI dependency injection for current-broker extraction. SQLite in-memory for tests to avoid PostgreSQL dependency.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2.0, asyncpg, aiosqlite, Alembic, python-jose, passlib[bcrypt], pytest

---

### Task 1: Dependencies + Project Structure

**Files:**
- Modify: `requirements.txt`
- Create: `healthflow/database/__init__.py`
- Create: `healthflow/auth/__init__.py`
- Create: `frontend/.gitkeep`

- [ ] **Step 1: Update requirements.txt**

Replace the contents of `requirements.txt` with:

```python
fastapi>=0.115
uvicorn>=0.30
click>=8.1
anthropic>=0.40
redis>=5.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27
sqlalchemy>=2.0
asyncpg>=0.29
aiosqlite>=0.20
alembic>=1.13
python-jose>=3.3
passlib[bcrypt]>=1.7
python-multipart>=0.0.9
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create directory structure**

Create the following empty `__init__.py` files and the frontend placeholder:

`healthflow/database/__init__.py`:
```python
```

`healthflow/auth/__init__.py`:
```python
```

`frontend/.gitkeep`:
```
```

- [ ] **Step 3: Install dependencies**

```bash
.venv/bin/pip install -r requirements.txt
```

- [ ] **Step 4: Verify**

Run `.venv/bin/python -c "import sqlalchemy; import jose; import passlib; import aiosqlite; print('OK')"` and confirm it prints `OK`.

---

### Task 2: Database Config

**Files:**
- Create: `healthflow/database/config.py`
- Create: `healthflow/tests/test_database_config.py`

- [ ] **Step 1: Write tests for database config**

Create `healthflow/tests/test_database_config.py`:

```python
import pytest
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """get_db should yield an AsyncSession and close it after."""
    from healthflow.database.config import get_test_session_factory, get_db_with_factory

    factory = await get_test_session_factory()
    session = None
    async for s in get_db_with_factory(factory):
        session = s
        assert isinstance(s, AsyncSession)
    # Session should have been closed after the generator exits
    assert session is not None


@pytest.mark.asyncio
async def test_database_url_default():
    """Default DATABASE_URL should point to local PostgreSQL."""
    with patch.dict("os.environ", {}, clear=True):
        from importlib import reload
        import healthflow.database.config as cfg
        reload(cfg)
        assert "postgresql+asyncpg" in cfg.DATABASE_URL


@pytest.mark.asyncio
async def test_database_url_from_env():
    """DATABASE_URL should be read from environment."""
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite+aiosqlite:///"}):
        from importlib import reload
        import healthflow.database.config as cfg
        reload(cfg)
        assert cfg.DATABASE_URL == "sqlite+aiosqlite:///"
```

- [ ] **Step 2: Implement database config**

Create `healthflow/database/config.py`:

```python
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/healthflow",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_with_factory(
    factory: async_sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    """Variant of get_db that accepts a custom session factory (used in tests)."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_test_session_factory() -> async_sessionmaker:
    """Create an in-memory SQLite engine + session factory for testing."""
    from healthflow.database.models import Base

    test_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    return factory
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_database_config.py -v
```

---

### Task 3: ORM Models

**Files:**
- Create: `healthflow/database/models.py`
- Create: `healthflow/tests/test_database_models.py`

- [ ] **Step 1: Write tests for ORM models**

Create `healthflow/tests/test_database_models.py`:

```python
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.models import Base, Broker, Client, ActionHistory


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_broker(db_session):
    broker = Broker(
        email="test@example.com",
        hashed_password="fakehash",
        full_name="Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()

    result = await db_session.execute(select(Broker).where(Broker.email == "test@example.com"))
    saved = result.scalar_one()
    assert saved.email == "test@example.com"
    assert saved.full_name == "Test Broker"
    assert saved.role == "broker"
    assert saved.is_active is True
    assert saved.id is not None
    assert isinstance(saved.created_at, datetime)


@pytest.mark.asyncio
async def test_create_client_linked_to_broker(db_session):
    broker = Broker(
        email="broker@example.com",
        hashed_password="fakehash",
        full_name="Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    client = Client(
        broker_id=broker.id,
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin", "Lisinopril"],
        procedures=["MRI"],
    )
    db_session.add(client)
    await db_session.commit()

    result = await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    saved = result.scalar_one()
    assert saved.full_name == "Jane Doe"
    assert saved.zip_code == "10001"
    assert saved.age == 45
    assert saved.income_level == "medium"
    assert saved.doctors == [{"name": "Dr. Chen", "npi": "1234567890"}]
    assert saved.prescriptions == ["Metformin", "Lisinopril"]
    assert saved.procedures == ["MRI"]
    assert saved.broker_id == broker.id


@pytest.mark.asyncio
async def test_create_action_history(db_session):
    broker = Broker(
        email="broker2@example.com",
        hashed_password="fakehash",
        full_name="Broker Two",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    client = Client(
        broker_id=broker.id,
        full_name="John Smith",
        zip_code="90210",
        age=30,
        income_level="high",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    action = ActionHistory(
        broker_id=broker.id,
        client_id=client.id,
        action_type="compare",
        request_data={"zip_code": "90210", "age": 30},
        response_summary={"plans_found": 3},
    )
    db_session.add(action)
    await db_session.commit()

    result = await db_session.execute(
        select(ActionHistory).where(ActionHistory.broker_id == broker.id)
    )
    saved = result.scalar_one()
    assert saved.action_type == "compare"
    assert saved.request_data == {"zip_code": "90210", "age": 30}
    assert saved.response_summary == {"plans_found": 3}
    assert saved.client_id == client.id


@pytest.mark.asyncio
async def test_jsonb_stores_complex_data(db_session):
    broker = Broker(
        email="broker3@example.com",
        hashed_password="fakehash",
        full_name="Broker Three",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    complex_doctors = [
        {"name": "Dr. Chen", "npi": "1234567890"},
        {"name": "Dr. Patel", "npi": "0987654321"},
    ]
    complex_prescriptions = ["Metformin", "Lisinopril", "Atorvastatin"]

    client = Client(
        broker_id=broker.id,
        full_name="Complex Client",
        zip_code="60601",
        age=55,
        income_level="low",
        doctors=complex_doctors,
        prescriptions=complex_prescriptions,
        procedures=["MRI", "Blood work", "CT Scan"],
    )
    db_session.add(client)
    await db_session.commit()

    result = await db_session.execute(select(Client).where(Client.full_name == "Complex Client"))
    saved = result.scalar_one()
    assert len(saved.doctors) == 2
    assert saved.doctors[0]["npi"] == "1234567890"
    assert len(saved.prescriptions) == 3
    assert "Atorvastatin" in saved.prescriptions
    assert len(saved.procedures) == 3


@pytest.mark.asyncio
async def test_broker_unique_email(db_session):
    broker1 = Broker(
        email="unique@example.com",
        hashed_password="fakehash",
        full_name="Broker One",
    )
    db_session.add(broker1)
    await db_session.commit()

    broker2 = Broker(
        email="unique@example.com",
        hashed_password="fakehash2",
        full_name="Broker Two",
    )
    db_session.add(broker2)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Implement ORM models**

Create `healthflow/database/models.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    pass


class GUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as String(36).
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(uuid.UUID(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="broker", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    clients: Mapped[list["Client"]] = relationship(back_populates="broker", cascade="all, delete-orphan")
    actions: Mapped[list["ActionHistory"]] = relationship(back_populates="broker", cascade="all, delete-orphan")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("brokers.id"), index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(5), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    income_level: Mapped[str] = mapped_column(String(10), nullable=False)
    doctors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    prescriptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    procedures: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    broker: Mapped["Broker"] = relationship(back_populates="clients")
    actions: Mapped[list["ActionHistory"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class ActionHistory(Base):
    __tablename__ = "action_history"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("brokers.id"), index=True, nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("clients.id"), index=True, nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    request_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    broker: Mapped["Broker"] = relationship(back_populates="actions")
    client: Mapped["Client"] = relationship(back_populates="actions")
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_database_models.py -v
```

---

### Task 4: Pydantic Auth/Client Schemas

**Files:**
- Modify: `healthflow/models/schemas.py` (append after line 323)
- Create: `healthflow/tests/test_auth_schemas.py`

- [ ] **Step 1: Write tests for the new Pydantic schemas**

Create `healthflow/tests/test_auth_schemas.py`:

```python
import pytest
from datetime import datetime
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerResponse,
    LoginRequest,
    TokenResponse,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
)


def test_broker_create_valid():
    b = BrokerCreate(
        email="broker@example.com",
        password="securepass123",
        full_name="Test Broker",
    )
    assert b.email == "broker@example.com"
    assert b.password == "securepass123"
    assert b.full_name == "Test Broker"


def test_broker_create_short_password():
    with pytest.raises(ValueError, match="8"):
        BrokerCreate(
            email="broker@example.com",
            password="short",
            full_name="Test Broker",
        )


def test_broker_create_invalid_email():
    with pytest.raises(ValueError):
        BrokerCreate(
            email="not-an-email",
            password="securepass123",
            full_name="Test Broker",
        )


def test_broker_response():
    b = BrokerResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        email="broker@example.com",
        full_name="Test Broker",
        role="broker",
        is_active=True,
        created_at="2026-04-09T12:00:00Z",
    )
    assert b.id == "550e8400-e29b-41d4-a716-446655440000"
    assert b.role == "broker"


def test_login_request():
    l = LoginRequest(email="broker@example.com", password="securepass123")
    assert l.email == "broker@example.com"
    assert l.password == "securepass123"


def test_token_response():
    t = TokenResponse(
        access_token="abc.def.ghi",
        refresh_token="jkl.mno.pqr",
        token_type="bearer",
    )
    assert t.token_type == "bearer"
    assert t.access_token == "abc.def.ghi"


def test_client_create_valid():
    c = ClientCreate(
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin"],
        procedures=["MRI"],
    )
    assert c.full_name == "Jane Doe"
    assert c.age == 45


def test_client_create_invalid_zip():
    with pytest.raises(ValueError, match="5 digits"):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="123",
            age=45,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_age_too_young():
    with pytest.raises(ValueError):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=5,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_age_too_old():
    with pytest.raises(ValueError):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=200,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_invalid_income():
    with pytest.raises(ValueError, match="Income level"):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=45,
            income_level="mega-rich",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_response():
    c = ClientResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        broker_id="660e8400-e29b-41d4-a716-446655440000",
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin"],
        procedures=["MRI"],
        created_at="2026-04-09T12:00:00Z",
        updated_at="2026-04-09T12:00:00Z",
    )
    assert c.id == "550e8400-e29b-41d4-a716-446655440000"
    assert c.broker_id == "660e8400-e29b-41d4-a716-446655440000"


def test_client_update_partial():
    u = ClientUpdate(age=50, zip_code="90210")
    assert u.age == 50
    assert u.zip_code == "90210"
    assert u.full_name is None
    assert u.income_level is None
    assert u.doctors is None


def test_client_update_empty():
    u = ClientUpdate()
    assert u.full_name is None
    assert u.age is None
```

- [ ] **Step 2: Append new schemas to schemas.py**

Append the following to the end of `healthflow/models/schemas.py` (after the `VerifyResponse` class at line 323):

```python


# ── Phase 6A: Auth & Client Schemas ──────────────────────────────────────────


class BrokerCreate(BaseModel):
    email: str = Field(..., description="Broker email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: str = Field(..., description="Broker full name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v


class BrokerResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str = Field(..., description="Broker email")
    password: str = Field(..., description="Broker password")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ClientCreate(BaseModel):
    full_name: str = Field(..., description="Client full name")
    zip_code: str = Field(..., description="5-digit US zip code")
    age: int = Field(..., ge=18, le=120, description="Age between 18 and 120")
    income_level: str = Field(..., description="Income level: low, medium, or high")
    doctors: list[dict] = Field(
        default_factory=list, description="List of doctor objects with name and npi"
    )
    prescriptions: list[str] = Field(
        default_factory=list, description="List of prescription names"
    )
    procedures: list[str] = Field(
        default_factory=list, description="List of procedure names"
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        if len(v) != 5 or not v.isdigit():
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"Income level must be one of: {', '.join(sorted(allowed))}")
        return v


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

    model_config = {"from_attributes": True}


class ClientUpdate(BaseModel):
    full_name: str | None = None
    zip_code: str | None = None
    age: int | None = Field(default=None, ge=18, le=120)
    income_level: str | None = None
    doctors: list[dict] | None = None
    prescriptions: list[str] | None = None
    procedures: list[str] | None = None

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str | None) -> str | None:
        if v is not None and (len(v) != 5 or not v.isdigit()):
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str | None) -> str | None:
        if v is not None and v not in {"low", "medium", "high"}:
            raise ValueError(f"Income level must be one of: high, low, medium")
        return v
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_auth_schemas.py -v
```

---

### Task 5: Security Module

**Files:**
- Create: `healthflow/auth/security.py`
- Create: `healthflow/tests/test_security.py`

- [ ] **Step 1: Write tests for the security module**

Create `healthflow/tests/test_security.py`:

```python
import pytest
from datetime import timedelta
from unittest.mock import patch

from healthflow.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_hash_password_returns_hash():
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = hash_password("mysecretpassword")
    assert verify_password("mysecretpassword", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mysecretpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token({"sub": "broker-123", "role": "broker"})
    payload = decode_token(token)
    assert payload["sub"] == "broker-123"
    assert payload["role"] == "broker"
    assert "exp" in payload


def test_create_access_token_custom_expiry():
    token = create_access_token(
        {"sub": "broker-123", "role": "broker"},
        expires_delta=timedelta(minutes=5),
    )
    payload = decode_token(token)
    assert payload["sub"] == "broker-123"


def test_create_and_decode_refresh_token():
    token = create_refresh_token({"sub": "broker-123"})
    payload = decode_token(token)
    assert payload["sub"] == "broker-123"
    assert payload["type"] == "refresh"
    assert "exp" in payload


def test_expired_token_raises():
    token = create_access_token(
        {"sub": "broker-123", "role": "broker"},
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(Exception):
        decode_token(token)


def test_invalid_token_raises():
    with pytest.raises(Exception):
        decode_token("this.is.not.a.valid.token")


def test_tampered_token_raises():
    token = create_access_token({"sub": "broker-123", "role": "broker"})
    # Tamper with the token by changing a character
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(Exception):
        decode_token(tampered)
```

- [ ] **Step 2: Implement the security module**

Create `healthflow/auth/security.py`:

```python
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token with the given data payload."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with a longer expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_security.py -v
```

---

### Task 6: Auth Dependencies

**Files:**
- Create: `healthflow/auth/dependencies.py`
- Create: `healthflow/tests/test_auth_dependencies.py`
- Create: `healthflow/tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures in conftest.py**

Create `healthflow/tests/conftest.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.models import Base
from healthflow.database.config import get_db
from healthflow.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    return factory


@pytest_asyncio.fixture
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session_factory):
    """FastAPI TestClient with the database dependency overridden to use SQLite."""

    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write tests for auth dependencies**

Create `healthflow/tests/test_auth_dependencies.py`:

```python
import pytest
import uuid
from healthflow.auth.security import create_access_token, hash_password
from healthflow.database.models import Broker


@pytest.mark.asyncio
async def test_valid_token_returns_broker(client, db_session):
    """A valid access token should authenticate and return the broker."""
    broker = Broker(
        email="dep-test@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Dep Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    token = create_access_token({"sub": str(broker.id), "role": "broker"})
    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should not be 401 — token is valid
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_missing_token_returns_401(client):
    """A request without a token should return 401."""
    response = await client.get("/clients")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    """A request with an invalid token should return 401."""
    response = await client.get(
        "/clients",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_broker_returns_401(client):
    """A valid token for a non-existent broker should return 401."""
    fake_id = str(uuid.uuid4())
    token = create_access_token({"sub": fake_id, "role": "broker"})
    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
```

- [ ] **Step 3: Implement auth dependencies**

Create `healthflow/auth/dependencies.py`:

```python
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import decode_token
from healthflow.database.config import get_db
from healthflow.database.models import Broker

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


async def get_current_broker(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Broker:
    """Extract and validate the current broker from a JWT access token.

    Raises:
        HTTPException 401: If the token is invalid, expired, or the broker
            is not found or inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except (ValueError, Exception):
        raise credentials_exception

    broker_id_str: str | None = payload.get("sub")
    if broker_id_str is None:
        raise credentials_exception

    token_type = payload.get("type")
    if token_type != "access":
        raise credentials_exception

    try:
        broker_id = uuid.UUID(broker_id_str)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = result.scalar_one_or_none()

    if broker is None or not broker.is_active:
        raise credentials_exception

    return broker
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_auth_dependencies.py -v
```

Note: These tests depend on the client router being wired up (Task 8 / Task 9). If running before those tasks, the `/clients` endpoint won't exist yet. In that case, defer running these tests until after Task 9 is complete.

---

### Task 7: Auth Router

**Files:**
- Create: `healthflow/auth/router.py`
- Create: `healthflow/tests/test_auth.py`

- [ ] **Step 1: Write tests for the auth router**

Create `healthflow/tests/test_auth.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "newbroker@example.com",
            "password": "securepass123",
            "full_name": "New Broker",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newbroker@example.com"
    assert data["full_name"] == "New Broker"
    assert data["role"] == "broker"
    assert data["is_active"] is True
    assert "id" in data
    # Password should not be in response
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/auth/register",
        json={
            "email": "dup@example.com",
            "password": "securepass123",
            "full_name": "First Broker",
        },
    )
    response = await client.post(
        "/auth/register",
        json={
            "email": "dup@example.com",
            "password": "anotherpass123",
            "full_name": "Second Broker",
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "full_name": "Short Pass",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    # Register first
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "securepass123",
            "full_name": "Login Broker",
        },
    )
    # Login
    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "securepass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register",
        json={
            "email": "wrongpw@example.com",
            "password": "securepass123",
            "full_name": "Wrong PW Broker",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepass123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client):
    # Register and login
    await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "securepass123",
            "full_name": "Refresh Broker",
        },
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "refresh@example.com", "password": "securepass123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client):
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token.value"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client):
    """Using an access token as a refresh token should fail."""
    await client.post(
        "/auth/register",
        json={
            "email": "noaccess@example.com",
            "password": "securepass123",
            "full_name": "No Access Broker",
        },
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "noaccess@example.com", "password": "securepass123"},
    )
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Implement the auth router**

Create `healthflow/auth/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from healthflow.database.config import get_db
from healthflow.database.models import Broker
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerResponse,
    LoginRequest,
    TokenResponse,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token")


@auth_router.post("/register", response_model=BrokerResponse, status_code=201)
async def register(
    broker_data: BrokerCreate,
    db: AsyncSession = Depends(get_db),
) -> BrokerResponse:
    """Register a new broker account."""
    # Check if email already exists
    result = await db.execute(
        select(Broker).where(Broker.email == broker_data.email)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    broker = Broker(
        email=broker_data.email,
        hashed_password=hash_password(broker_data.password),
        full_name=broker_data.full_name,
    )
    db.add(broker)
    await db.flush()
    await db.refresh(broker)

    return BrokerResponse(
        id=str(broker.id),
        email=broker.email,
        full_name=broker.full_name,
        role=broker.role,
        is_active=broker.is_active,
        created_at=broker.created_at.isoformat(),
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a broker and return access + refresh tokens."""
    result = await db.execute(
        select(Broker).where(Broker.email == login_data.email)
    )
    broker = result.scalar_one_or_none()

    if broker is None or not verify_password(login_data.password, broker.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not broker.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    access_token = create_access_token(
        {"sub": str(broker.id), "role": broker.role}
    )
    refresh_token = create_refresh_token({"sub": str(broker.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@auth_router.post("/refresh")
async def refresh(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Exchange a valid refresh token for a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    try:
        payload = decode_token(refresh_data.refresh_token)
    except (ValueError, Exception):
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    broker_id = payload.get("sub")
    if broker_id is None:
        raise credentials_exception

    result = await db.execute(
        select(Broker).where(Broker.id == broker_id)
    )
    broker = result.scalar_one_or_none()
    if broker is None or not broker.is_active:
        raise credentials_exception

    new_access_token = create_access_token(
        {"sub": str(broker.id), "role": broker.role}
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_auth.py -v
```

Note: These tests depend on the auth router being wired into the main app (Task 9). If running before Task 9, defer until after Task 9 is complete.

---

### Task 8: Client CRUD Router

**Files:**
- Create: `healthflow/api/client_router.py`
- Create: `healthflow/tests/test_clients.py`

- [ ] **Step 1: Write tests for client CRUD**

Create `healthflow/tests/test_clients.py`:

```python
import pytest
from healthflow.auth.security import create_access_token, hash_password
from healthflow.database.models import Broker


async def _register_and_login(client, email="crud@example.com"):
    """Helper to register a broker and get an auth token."""
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "CRUD Broker",
        },
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "securepass123"},
    )
    return login_resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_client(client):
    token = await _register_and_login(client, "create-client@example.com")
    response = await client.post(
        "/clients",
        json={
            "full_name": "Jane Doe",
            "zip_code": "10001",
            "age": 45,
            "income_level": "medium",
            "doctors": [{"name": "Dr. Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin"],
            "procedures": ["MRI"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Jane Doe"
    assert data["zip_code"] == "10001"
    assert data["age"] == 45
    assert "id" in data
    assert "broker_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_clients(client):
    token = await _register_and_login(client, "list-clients@example.com")
    # Create two clients
    await client.post(
        "/clients",
        json={
            "full_name": "Client One",
            "zip_code": "10001",
            "age": 30,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/clients",
        json={
            "full_name": "Client Two",
            "zip_code": "90210",
            "age": 50,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {c["full_name"] for c in data}
    assert "Client One" in names
    assert "Client Two" in names


@pytest.mark.asyncio
async def test_get_client_by_id(client):
    token = await _register_and_login(client, "get-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Get Me",
            "zip_code": "60601",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_nonexistent_client(client):
    token = await _register_and_login(client, "noexist@example.com")
    import uuid
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/clients/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_client(client):
    token = await _register_and_login(client, "update-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Before Update",
            "zip_code": "10001",
            "age": 35,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.put(
        f"/clients/{client_id}",
        json={"full_name": "After Update", "age": 36},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "After Update"
    assert data["age"] == 36
    # Unchanged fields should stay the same
    assert data["zip_code"] == "10001"
    assert data["income_level"] == "low"


@pytest.mark.asyncio
async def test_delete_client(client):
    token = await _register_and_login(client, "delete-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Delete Me",
            "zip_code": "10001",
            "age": 25,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.delete(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_ownership_check_get(client):
    """Broker A cannot view Broker B's client."""
    token_a = await _register_and_login(client, "broker-a@example.com")
    token_b = await _register_and_login(client, "broker-b@example.com")

    # Broker A creates a client
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "A's Client",
            "zip_code": "10001",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    # Broker B tries to access it
    response = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ownership_check_update(client):
    """Broker A cannot update Broker B's client."""
    token_a = await _register_and_login(client, "owner-a@example.com")
    token_b = await _register_and_login(client, "owner-b@example.com")

    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "A's Client",
            "zip_code": "10001",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.put(
        f"/clients/{client_id}",
        json={"full_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ownership_check_delete(client):
    """Broker A cannot delete Broker B's client."""
    token_a = await _register_and_login(client, "del-a@example.com")
    token_b = await _register_and_login(client, "del-b@example.com")

    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "A's Client",
            "zip_code": "10001",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.delete(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_client_without_auth(client):
    response = await client.post(
        "/clients",
        json={
            "full_name": "No Auth",
            "zip_code": "10001",
            "age": 30,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Implement the client CRUD router**

Create `healthflow/api/client_router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.config import get_db
from healthflow.database.models import Broker, Client
from healthflow.models.schemas import ClientCreate, ClientResponse, ClientUpdate

client_router = APIRouter(prefix="/clients", tags=["clients"])


def _client_to_response(client: Client) -> ClientResponse:
    """Convert a Client ORM model to a ClientResponse Pydantic model."""
    return ClientResponse(
        id=str(client.id),
        broker_id=str(client.broker_id),
        full_name=client.full_name,
        zip_code=client.zip_code,
        age=client.age,
        income_level=client.income_level,
        doctors=client.doctors,
        prescriptions=client.prescriptions,
        procedures=client.procedures,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat(),
    )


@client_router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Create a new client profile for the current broker."""
    client = Client(
        broker_id=broker.id,
        full_name=client_data.full_name,
        zip_code=client_data.zip_code,
        age=client_data.age,
        income_level=client_data.income_level,
        doctors=client_data.doctors,
        prescriptions=client_data.prescriptions,
        procedures=client_data.procedures,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return _client_to_response(client)


@client_router.get("", response_model=list[ClientResponse])
async def list_clients(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> list[ClientResponse]:
    """List all clients belonging to the current broker."""
    result = await db.execute(
        select(Client).where(Client.broker_id == broker.id)
    )
    clients = result.scalars().all()
    return [_client_to_response(c) for c in clients]


@client_router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Get a specific client by ID. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _client_to_response(client)


@client_router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    update_data: ClientUpdate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Update a client's profile. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Apply only the fields that were explicitly set
    update_fields = update_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return _client_to_response(client)


@client_router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a client. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(client)
    await db.flush()
    return Response(status_code=204)
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_clients.py -v
```

Note: These tests depend on the routers being wired into the main app (Task 9). Run after Task 9 is complete.

---

### Task 9: Wire into Main App

**Files:**
- Modify: `healthflow/main.py`
- Create: `healthflow/tests/test_app_wiring.py`

- [ ] **Step 1: Write tests for app wiring**

Create `healthflow/tests/test_app_wiring.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_health_check_still_works(client):
    """The existing health check or root endpoint should still work."""
    response = await client.get("/health")
    # Accept 200 or 404 — just make sure the app boots
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_auth_register_route_exists(client):
    """The /auth/register route should be registered."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "wiring@example.com",
            "password": "securepass123",
            "full_name": "Wiring Test",
        },
    )
    # Should not be 404 (route not found)
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_auth_login_route_exists(client):
    """The /auth/login route should be registered."""
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepass123"},
    )
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_clients_route_exists(client):
    """The /clients route should be registered (requires auth)."""
    response = await client.get("/clients")
    # Should be 401 (not authenticated), not 404 (not found)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_existing_compare_route_still_exists(client):
    """Existing Phase 1-5 routes should still be accessible."""
    response = await client.post("/compare", json={})
    # Should be 422 (validation error), not 404
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_openapi_schema_includes_new_routes(client):
    """The OpenAPI schema should include auth and client routes."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/refresh" in paths
    assert "/clients" in paths
```

- [ ] **Step 2: Modify healthflow/main.py**

Replace the entire contents of `healthflow/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from healthflow.api.routes import router
from healthflow.auth.router import auth_router
from healthflow.api.client_router import client_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup (for development/testing)."""
    from healthflow.database.config import engine
    from healthflow.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="HealthFlow",
    description="AI-powered Medicare Advantage plan comparison service",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(client_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("healthflow.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest healthflow/tests/test_app_wiring.py -v
```

- [ ] **Step 4: Run ALL tests from Tasks 6-9**

Now that everything is wired up, run the full suite of new tests:

```bash
.venv/bin/python -m pytest healthflow/tests/test_auth_dependencies.py healthflow/tests/test_auth.py healthflow/tests/test_clients.py healthflow/tests/test_app_wiring.py -v
```

---

### Task 10: Integration Tests + README

**Files:**
- Create: `healthflow/tests/test_integration_auth_clients.py`
- Modify: `README.md`

- [ ] **Step 1: Write end-to-end integration tests**

Create `healthflow/tests/test_integration_auth_clients.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_full_auth_and_client_flow(client):
    """End-to-end: register -> login -> create client -> list -> verify ownership."""

    # Step 1: Register a broker
    register_resp = await client.post(
        "/auth/register",
        json={
            "email": "e2e@example.com",
            "password": "securepass123",
            "full_name": "E2E Broker",
        },
    )
    assert register_resp.status_code == 201
    broker_id = register_resp.json()["id"]

    # Step 2: Login
    login_resp = await client.post(
        "/auth/login",
        json={"email": "e2e@example.com", "password": "securepass123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 3: Create a client
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Jane Doe",
            "zip_code": "10001",
            "age": 45,
            "income_level": "medium",
            "doctors": [{"name": "Dr. Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin", "Lisinopril"],
            "procedures": ["MRI"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    client_data = create_resp.json()
    client_id = client_data["id"]
    assert client_data["broker_id"] == broker_id
    assert client_data["full_name"] == "Jane Doe"
    assert len(client_data["doctors"]) == 1
    assert len(client_data["prescriptions"]) == 2

    # Step 4: Create a second client
    create_resp2 = await client.post(
        "/clients",
        json={
            "full_name": "John Smith",
            "zip_code": "90210",
            "age": 30,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers,
    )
    assert create_resp2.status_code == 201

    # Step 5: List clients — should see both
    list_resp = await client.get("/clients", headers=headers)
    assert list_resp.status_code == 200
    clients_list = list_resp.json()
    assert len(clients_list) == 2

    # Step 6: Get a specific client
    get_resp = await client.get(f"/clients/{client_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["full_name"] == "Jane Doe"

    # Step 7: Update the client
    update_resp = await client.put(
        f"/clients/{client_id}",
        json={"age": 46, "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin"]},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["age"] == 46
    assert len(update_resp.json()["prescriptions"]) == 3

    # Step 8: Delete the second client
    second_id = create_resp2.json()["id"]
    delete_resp = await client.delete(f"/clients/{second_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Verify only one client remains
    list_resp2 = await client.get("/clients", headers=headers)
    assert len(list_resp2.json()) == 1

    # Step 9: Refresh the token
    refresh_resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]
    assert new_access_token != access_token

    # Step 10: Use the new token to access clients
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    list_resp3 = await client.get("/clients", headers=new_headers)
    assert list_resp3.status_code == 200
    assert len(list_resp3.json()) == 1


@pytest.mark.asyncio
async def test_multi_broker_isolation(client):
    """Two brokers should not see each other's clients."""

    # Register Broker A
    await client.post(
        "/auth/register",
        json={
            "email": "isolation-a@example.com",
            "password": "securepass123",
            "full_name": "Broker A",
        },
    )
    login_a = await client.post(
        "/auth/login",
        json={"email": "isolation-a@example.com", "password": "securepass123"},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Broker B
    await client.post(
        "/auth/register",
        json={
            "email": "isolation-b@example.com",
            "password": "securepass123",
            "full_name": "Broker B",
        },
    )
    login_b = await client.post(
        "/auth/login",
        json={"email": "isolation-b@example.com", "password": "securepass123"},
    )
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Broker A creates a client
    resp_a = await client.post(
        "/clients",
        json={
            "full_name": "A's Client",
            "zip_code": "10001",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers_a,
    )
    assert resp_a.status_code == 201
    a_client_id = resp_a.json()["id"]

    # Broker B creates a client
    resp_b = await client.post(
        "/clients",
        json={
            "full_name": "B's Client",
            "zip_code": "90210",
            "age": 35,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers_b,
    )
    assert resp_b.status_code == 201

    # Broker A lists clients — should see only their own
    list_a = await client.get("/clients", headers=headers_a)
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["full_name"] == "A's Client"

    # Broker B lists clients — should see only their own
    list_b = await client.get("/clients", headers=headers_b)
    assert len(list_b.json()) == 1
    assert list_b.json()[0]["full_name"] == "B's Client"

    # Broker B cannot access Broker A's client
    cross_resp = await client.get(f"/clients/{a_client_id}", headers=headers_b)
    assert cross_resp.status_code == 403

    # Broker B cannot update Broker A's client
    cross_update = await client.put(
        f"/clients/{a_client_id}",
        json={"full_name": "Hacked"},
        headers=headers_b,
    )
    assert cross_update.status_code == 403

    # Broker B cannot delete Broker A's client
    cross_delete = await client.delete(f"/clients/{a_client_id}", headers=headers_b)
    assert cross_delete.status_code == 403
```

- [ ] **Step 2: Update README.md**

Add the following section to `README.md` (append before any existing "Development" or "Testing" section, or at the end if none exists):

```markdown
## Authentication

HealthFlow uses JWT-based authentication. All client endpoints require a valid access token.

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
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "broker@example.com", "password": "securepass123", "full_name": "Test Broker"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "broker@example.com", "password": "securepass123"}'

# Create a client (use the access_token from login response)
curl -X POST http://localhost:8000/clients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"full_name": "Jane Doe", "zip_code": "10001", "age": 45, "income_level": "medium", "doctors": [], "prescriptions": [], "procedures": []}'
```

### Dependencies

```
sqlalchemy>=2.0
asyncpg>=0.29
aiosqlite>=0.20
alembic>=1.13
python-jose>=3.3
passlib[bcrypt]>=1.7
python-multipart>=0.0.9
```
```

- [ ] **Step 3: Run ALL tests**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v
```

- [ ] **Step 4: Verify the full test suite passes**

```bash
.venv/bin/python -m pytest healthflow/tests/ -v --tb=short
```

Confirm all tests pass with zero failures. If any tests fail from earlier phases, investigate whether the new changes broke them (they should not, since existing routes are unchanged).
