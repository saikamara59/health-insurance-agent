import pytest
from datetime import timedelta

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


@pytest.mark.anyio
async def test_create_and_decode_refresh_token(db_session):
    import uuid as _uuid
    broker_id = _uuid.uuid4()
    token = await create_refresh_token(db_session, broker_id)
    payload = decode_token(token)
    assert payload["sub"] == str(broker_id)
    assert payload["type"] == "refresh"
    assert payload["jti"] is not None
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
