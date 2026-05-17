from datetime import datetime, timedelta, timezone

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
from healthflow.auth.dependencies import get_current_broker
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerProfileUpdate,
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
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    result = await db.execute(
        select(Broker).where(Broker.email == login_data.email)
    )
    broker = result.scalar_one_or_none()

    if broker is None:
        raise generic_error

    now = datetime.now(timezone.utc)

    # Lock check — generic 401, never leak lock state to the client.
    # SQLite returns naive datetimes; treat them as UTC for comparison.
    if broker.locked_until is not None:
        locked_until = broker.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise generic_error

    if not verify_password(login_data.password, broker.hashed_password):
        broker.failed_login_count += 1
        if broker.failed_login_count >= 5:
            broker.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise generic_error

    if not broker.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Success — reset lockout state.
    broker.failed_login_count = 0
    broker.locked_until = None

    access_token = create_access_token(
        {"sub": str(broker.id), "role": broker.role}
    )
    refresh_token = await create_refresh_token(db, broker.id)

    await db.commit()

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
    """Exchange a valid refresh token for a new access + refresh token pair.

    Rotation + theft signal: every refresh revokes the presented token and
    issues a new one. Replaying a revoked token revokes ALL of that broker's
    active refresh tokens (force re-login).
    """
    from healthflow.database.models import RefreshToken
    from healthflow.logs.audit import AuditLogger
    from sqlalchemy import update as sa_update
    import uuid as _uuid

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    try:
        payload = decode_token(refresh_data.refresh_token)
    except ValueError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    broker_id_str = payload.get("sub")
    jti = payload.get("jti")
    if broker_id_str is None or jti is None:
        raise credentials_exception

    try:
        broker_id = _uuid.UUID(broker_id_str)
        jti_uuid = _uuid.UUID(jti)
    except ValueError:
        raise credentials_exception

    # Look up the refresh-token row by jti.
    row_result = await db.execute(
        select(RefreshToken).where(RefreshToken.id == jti_uuid)
    )
    row = row_result.scalar_one_or_none()
    if row is None:
        raise credentials_exception

    if row.revoked_at is not None:
        # THEFT SIGNAL — revoked token replayed.
        now = datetime.now(timezone.utc)
        await db.execute(
            sa_update(RefreshToken)
            .where(
                RefreshToken.broker_id == row.broker_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        AuditLogger().log(
            "refresh_token_replay_revoke_all",
            {"broker_id": str(row.broker_id), "presented_jti": str(jti_uuid)},
        )
        raise credentials_exception

    # Load the broker.
    broker_result = await db.execute(
        select(Broker).where(Broker.id == broker_id)
    )
    broker = broker_result.scalar_one_or_none()
    if broker is None or not broker.is_active:
        raise credentials_exception

    # Revoke the presented token, then issue a new pair.
    row.revoked_at = datetime.now(timezone.utc)
    new_access_token = create_access_token(
        {"sub": str(broker.id), "role": broker.role}
    )
    new_refresh_token = await create_refresh_token(db, broker.id)
    await db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@auth_router.post("/logout", status_code=204)
async def logout(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the presented refresh token. Access token expires naturally.

    Idempotent: revoking an already-revoked token is a no-op. Invalid tokens
    are silently accepted to avoid the endpoint becoming a probe for valid
    token shapes.
    """
    from healthflow.database.models import RefreshToken
    import uuid as _uuid

    try:
        payload = decode_token(refresh_data.refresh_token)
    except ValueError:
        return  # silently accept — no info leak

    jti = payload.get("jti")
    if jti is None:
        return

    try:
        jti_uuid = _uuid.UUID(jti)
    except ValueError:
        return

    row_result = await db.execute(
        select(RefreshToken).where(RefreshToken.id == jti_uuid)
    )
    row = row_result.scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@auth_router.get("/profile", response_model=BrokerResponse)
async def get_profile(
    broker: Broker = Depends(get_current_broker),
) -> BrokerResponse:
    """Get the current broker's profile."""
    return BrokerResponse(
        id=str(broker.id),
        email=broker.email,
        full_name=broker.full_name,
        role=broker.role,
        is_active=broker.is_active,
        created_at=broker.created_at.isoformat(),
    )


@auth_router.put("/profile", response_model=BrokerResponse)
async def update_profile(
    update: BrokerProfileUpdate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> BrokerResponse:
    """Update the current broker's profile."""
    if update.full_name is not None:
        broker.full_name = update.full_name
    if update.email is not None:
        broker.email = update.email
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
