import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import (
    create_access_token,
    create_password_reset_token,
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
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
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

    # New accounts land inactive — an admin has to approve them from the
    # Administration page before the user can log in. Pre-seeded accounts
    # (demo + admin) are activated by the seed scripts; existing accounts
    # in the live DB are untouched (their is_active was True at insert).
    broker = Broker(
        email=broker_data.email,
        hashed_password=hash_password(broker_data.password),
        full_name=broker_data.full_name,
        is_active=False,
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
        # Same message whether the account is brand-new pending approval or
        # was previously approved and then deactivated — both flows resolve
        # the same way (admin re-activates from the Administration page).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
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


@auth_router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Authenticated broker rotates their own password.

    Revokes all of the broker's active refresh tokens on success — a password
    change is a security event; other devices must re-login.
    """
    from healthflow.database.models import RefreshToken

    if not verify_password(payload.current_password, broker.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password",
        )

    broker.hashed_password = hash_password(payload.new_password)

    now = datetime.now(timezone.utc)
    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.broker_id == broker.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    await db.commit()


_FORGOT_PASSWORD_GENERIC_MESSAGE = (
    "If an account exists for that email, a reset link has been sent."
)
_FORGOT_PASSWORD_COOLDOWN_SECONDS = 60


def _frontend_base_url() -> str:
    value = os.getenv("FRONTEND_BASE_URL")
    if not value:
        raise RuntimeError(
            "FRONTEND_BASE_URL is required to build password-reset links"
        )
    return value.rstrip("/")


@auth_router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Send a password-reset email. Always returns the same generic 200 message
    regardless of whether the email exists, the cooldown is active, or the
    mailer fails. No enumeration; no error oracle.
    """
    from healthflow.database.models import PasswordResetToken
    from healthflow.email.mailer import get_mailer
    from healthflow.email.templates import render_password_reset
    from healthflow.logs.audit import AuditLogger
    import uuid as _uuid

    generic = ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)

    result = await db.execute(select(Broker).where(Broker.email == payload.email))
    broker = result.scalar_one_or_none()
    if broker is None:
        return generic

    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(seconds=_FORGOT_PASSWORD_COOLDOWN_SECONDS)
    cooldown_q = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == broker.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.created_at > cooldown_cutoff,
        ).limit(1)
    )
    if cooldown_q.scalar_one_or_none() is not None:
        return generic

    jti = _uuid.uuid4()
    expires_at = now + timedelta(minutes=60)
    row = PasswordResetToken(
        id=jti,
        broker_id=broker.id,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    # Commit the row BEFORE sending so the cooldown survives a mailer failure
    # and the audit log entry has a corresponding DB row to reference.
    await db.commit()

    token = create_password_reset_token(broker.id, jti)
    reset_url = f"{_frontend_base_url()}/reset-password?token={token}"
    subject, text_body, html_body = render_password_reset(broker.email, reset_url)

    try:
        get_mailer().send(broker.email, subject, text_body, html_body)
    except Exception as e:
        AuditLogger().log(
            "password_reset_send_failed",
            {"broker_id": str(broker.id), "error": repr(e)},
        )

    return generic


@auth_router.post("/reset-password", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a single-use reset token and rotate the password.

    Returns the same generic 401 for: invalid JWT, wrong type claim, unknown jti,
    used token, expired token, missing/inactive broker. Differentiating helps
    attackers more than legit users.
    """
    from healthflow.database.models import PasswordResetToken, RefreshToken
    import uuid as _uuid

    generic_401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired reset token",
    )

    try:
        claims = decode_token(payload.token)
    except ValueError:
        raise generic_401

    if claims.get("type") != "reset":
        raise generic_401

    broker_id_str = claims.get("sub")
    jti_str = claims.get("jti")
    if broker_id_str is None or jti_str is None:
        raise generic_401

    try:
        broker_id = _uuid.UUID(broker_id_str)
        jti = _uuid.UUID(jti_str)
    except ValueError:
        raise generic_401

    now = datetime.now(timezone.utc)

    row_result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.id == jti)
    )
    row = row_result.scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise generic_401
    # SQLite returns naive datetimes; treat them as UTC for comparison.
    row_expires_at = row.expires_at
    if row_expires_at.tzinfo is None:
        row_expires_at = row_expires_at.replace(tzinfo=timezone.utc)
    if row_expires_at < now:
        raise generic_401

    broker_result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = broker_result.scalar_one_or_none()
    if broker is None or not broker.is_active:
        raise generic_401

    broker.hashed_password = hash_password(payload.new_password)
    row.used_at = now
    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.broker_id == broker.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()
