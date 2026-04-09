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
