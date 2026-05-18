"""Unit tests for the PHI encryption primitive (AES-256-GCM)."""
import base64
import importlib

import pytest

import healthflow.auth.phi_crypto as phi_crypto


def _b64key(byte_val: int = 0x42) -> str:
    return base64.b64encode(bytes([byte_val] * 32)).decode()


def test_load_phi_keys_raises_when_unset(monkeypatch):
    """Missing PHI_ENCRYPTION_KEY env var must raise at module reload."""
    monkeypatch.delenv("PHI_ENCRYPTION_KEY", raising=False)
    # Drop any optional v2+ vars too
    for var in list(__import__("os").environ):
        if var.startswith("PHI_ENCRYPTION_KEY"):
            monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="PHI_ENCRYPTION_KEY"):
        importlib.reload(phi_crypto)
    # Restore for the rest of the suite
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", _b64key())
    importlib.reload(phi_crypto)


def test_load_phi_keys_rejects_known_placeholder(monkeypatch):
    """The literal placeholder 'replace-me' must be rejected."""
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", "replace-me")
    with pytest.raises(RuntimeError, match="placeholder"):
        importlib.reload(phi_crypto)
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", _b64key())
    importlib.reload(phi_crypto)


def test_load_phi_keys_returns_v1_for_single_key(monkeypatch):
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", _b64key(0x11))
    for var in list(__import__("os").environ):
        if var.startswith("PHI_ENCRYPTION_KEY_V"):
            monkeypatch.delenv(var, raising=False)
    importlib.reload(phi_crypto)
    assert "v1" in phi_crypto._KEYS
    assert len(phi_crypto._KEYS) == 1
    assert phi_crypto._CURRENT_VERSION == "v1"


def test_current_version_advances_with_v2(monkeypatch):
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", _b64key(0x11))
    monkeypatch.setenv("PHI_ENCRYPTION_KEY_V2", _b64key(0x22))
    importlib.reload(phi_crypto)
    assert set(phi_crypto._KEYS) == {"v1", "v2"}
    assert phi_crypto._CURRENT_VERSION == "v2"
    # Restore single-key state
    monkeypatch.delenv("PHI_ENCRYPTION_KEY_V2", raising=False)
    importlib.reload(phi_crypto)


def test_encrypt_returns_versioned_three_part_token():
    token = phi_crypto.encrypt("hello")
    parts = token.split(":")
    assert len(parts) == 3
    assert parts[0] == phi_crypto._CURRENT_VERSION
    # Both nonce and ciphertext are non-empty base64 strings
    assert parts[1] and parts[2]


@pytest.mark.parametrize("plaintext", [
    "Eleanor Rigby",
    "Patient with 数字 and emoji 🩺",
    "x" * 4000,  # large
    "",
])
def test_encrypt_decrypt_roundtrip(plaintext):
    token = phi_crypto.encrypt(plaintext)
    assert phi_crypto.decrypt(token) == plaintext


def test_decrypt_raises_phi_decryption_error_on_garbage():
    with pytest.raises(phi_crypto.PhiDecryptionError):
        phi_crypto.decrypt("not-a-real-token")
    with pytest.raises(phi_crypto.PhiDecryptionError):
        phi_crypto.decrypt("v1:bad:bad")
    with pytest.raises(phi_crypto.PhiDecryptionError):
        # Valid base64 but tampered ciphertext
        phi_crypto.decrypt("v1:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAA")


def test_cross_version_roundtrip(monkeypatch):
    """A token encrypted under v1 still decrypts after v2 becomes current."""
    # Establish v1
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", _b64key(0x11))
    monkeypatch.delenv("PHI_ENCRYPTION_KEY_V2", raising=False)
    importlib.reload(phi_crypto)
    v1_token = phi_crypto.encrypt("under-v1")
    assert v1_token.startswith("v1:")

    # Add v2 — v2 is now current
    monkeypatch.setenv("PHI_ENCRYPTION_KEY_V2", _b64key(0x22))
    importlib.reload(phi_crypto)
    assert phi_crypto._CURRENT_VERSION == "v2"
    # The v1 token still decrypts because v1's key is still loaded
    assert phi_crypto.decrypt(v1_token) == "under-v1"
    # New encryptions use v2
    v2_token = phi_crypto.encrypt("under-v2")
    assert v2_token.startswith("v2:")
    assert phi_crypto.decrypt(v2_token) == "under-v2"

    # Restore single-key state
    monkeypatch.delenv("PHI_ENCRYPTION_KEY_V2", raising=False)
    importlib.reload(phi_crypto)
