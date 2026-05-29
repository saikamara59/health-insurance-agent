import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import decode_token
from healthflow.auth.tenant_context import current_broker_id
from healthflow.database.config import get_db
from healthflow.database.models import Broker

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


async def get_current_broker(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[Broker, None]:
    """Extract and validate the current broker from a JWT access token.

    Sets `current_broker_id` for the duration of the request so that
    SQLAlchemy queries against tenant-scoped tables auto-filter to this
    broker. Resets on teardown so per-request isolation is clean under
    asyncio concurrency.

    Raises:
        HTTPException 401: If the token is invalid, expired, or the broker
            is not found or inactive.

    Teardown ordering (FastAPI LIFO): the ContextVar reset here runs BEFORE
    `get_db`'s teardown (commit + close). With `expire_on_commit=False`
    (the project default in `database/config.py`), commit does not fire
    SELECTs, so this is fine. If `expire_on_commit` is ever flipped to
    True or any cleanup path emits a query against a tenant-scoped table,
    queries during teardown will raise `TenantContextMissing`. In that
    case, restructure: have `get_db` enter `system_context()` for its
    cleanup phase (and add a comment justifying the new system_context
    call site).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is invalid or expired — please sign in again.",
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

    # Set the ContextVar BEFORE the broker SELECT so the SELECT itself runs
    # under the right context (Broker is not tenant-scoped, so this isn't
    # strictly required for correctness — but it keeps the order intuitive).
    context_token = current_broker_id.set(broker_id)
    try:
        result = await db.execute(select(Broker).where(Broker.id == broker_id))
        broker = result.scalar_one_or_none()

        if broker is None or not broker.is_active:
            raise credentials_exception

        yield broker
    finally:
        current_broker_id.reset(context_token)


async def require_admin(broker: Broker = Depends(get_current_broker)) -> Broker:
    """Yield the current broker if they are an admin, else raise HTTP 403.

    Returns the broker so the route can use the admin's id for audit logging.
    No bearer → 401 propagates from get_current_broker. Wrong role → 403.
    """
    if broker.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You need an admin account to view this page.",
        )
    return broker
