import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import JWTError, jwt
from passlib.context import CryptContext

_LEGACY_DEFAULT = "healthflow-dev-secret-change-in-production"


def _load_jwt_secret() -> str:
    value = os.getenv("JWT_SECRET")
    if not value:
        raise RuntimeError(
            "JWT_SECRET environment variable is required. "
            "Generate a long random string and set it in .env or your deploy environment."
        )
    if value == _LEGACY_DEFAULT:
        raise RuntimeError(
            "JWT_SECRET is set to the legacy default. "
            "Replace it with a real secret — the legacy value is in source control."
        )
    return value


JWT_SECRET = _load_jwt_secret()
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


_COMMON_PASSWORDS: frozenset[str] = frozenset(
    line.strip().lower()
    for line in (Path(__file__).parent / "common_passwords.txt").read_text().splitlines()
    if line.strip()
)


def validate_password(password: str) -> None:
    """Raise ValueError if the password fails policy: ≥12 chars, has letter +
    digit + non-alphanumeric, and is not in the common-passwords block-list.
    """
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not any(c.isalpha() for c in password):
        raise ValueError("Password must contain a letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain a digit")
    if all(c.isalnum() for c in password):
        raise ValueError("Password must contain a non-alphanumeric character")
    if password.lower() in _COMMON_PASSWORDS:
        raise ValueError("Password is too common — choose something less guessable")
