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
