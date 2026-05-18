"""AES-256-GCM field encryption for PHI columns.

Key loading is fail-loud at module import (same pattern as JWT_SECRET in
healthflow/auth/security.py). Wire format is `vN:<base64-nonce>:<base64-ct>`
where `vN` is the key version; new writes use _CURRENT_VERSION (the highest
configured), reads dispatch on the prefix. This makes rotation additive —
add PHI_ENCRYPTION_KEY_V2, restart the app, new writes use v2, old v1 rows
still decrypt with the v1 key.

Never delete a key version while any row exists encrypted under it.
"""
import base64
import os
import re
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KNOWN_PLACEHOLDERS: frozenset[str] = frozenset({
    "replace-me",
    "change-me",
    "<set-in-prod>",
})

# Match PHI_ENCRYPTION_KEY (treated as v1) and PHI_ENCRYPTION_KEY_V2, _V3, ...
_KEY_ENV_PATTERN = re.compile(r"^PHI_ENCRYPTION_KEY(?:_V(\d+))?$")


class PhiDecryptionError(Exception):
    """Raised when a stored value cannot be decrypted.

    Causes: missing/unknown key version, malformed token, tampered ciphertext,
    or a plaintext value when PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ is unset.
    """


def _load_phi_keys() -> dict[str, bytes]:
    """Read PHI_ENCRYPTION_KEY (= v1) and any PHI_ENCRYPTION_KEY_V2, V3, ...

    Each value is a base64-encoded 32-byte key. Returns {"v1": bytes, "v2": bytes, ...}.
    Raises RuntimeError if PHI_ENCRYPTION_KEY is unset or set to a known placeholder.
    """
    keys: dict[str, bytes] = {}
    for env_name, raw in os.environ.items():
        match = _KEY_ENV_PATTERN.match(env_name)
        if not match:
            continue
        if raw in _KNOWN_PLACEHOLDERS:
            raise RuntimeError(
                f"{env_name} is set to a known placeholder value. "
                f"Replace it with a real base64-encoded 32-byte key."
            )
        try:
            key_bytes = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise RuntimeError(f"{env_name} is not valid base64: {exc}") from exc
        if len(key_bytes) != 32:
            raise RuntimeError(
                f"{env_name} must be a 32-byte key (base64-encoded), "
                f"got {len(key_bytes)} bytes after decode."
            )
        version = f"v{match.group(1) or '1'}"
        keys[version] = key_bytes

    if "v1" not in keys:
        raise RuntimeError(
            "PHI_ENCRYPTION_KEY environment variable is required. "
            "Generate one with: "
            "python -c \"import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )

    return keys


_KEYS: dict[str, bytes] = _load_phi_keys()
_CURRENT_VERSION: str = max(_KEYS, key=lambda v: int(v[1:]))


def encrypt(plaintext: str) -> str:
    """Encrypt a string under _CURRENT_VERSION. Returns `vN:nonce:ciphertext`."""
    key = _KEYS[_CURRENT_VERSION]
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return f"{_CURRENT_VERSION}:{base64.b64encode(nonce).decode()}:{base64.b64encode(ct).decode()}"


def decrypt(token: str) -> str:
    """Decrypt a `vN:nonce:ciphertext` token. Raises PhiDecryptionError on any failure."""
    parts = token.split(":")
    if len(parts) != 3:
        raise PhiDecryptionError("Malformed token: expected three colon-separated parts")
    version, nonce_b64, ct_b64 = parts
    key = _KEYS.get(version)
    if key is None:
        raise PhiDecryptionError(f"Unknown key version: {version}")
    try:
        nonce = base64.b64decode(nonce_b64)
        ct = base64.b64decode(ct_b64)
    except Exception as exc:
        raise PhiDecryptionError(f"Invalid base64 in token: {exc}") from exc
    aesgcm = AESGCM(key)
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ct, associated_data=None)
    except InvalidTag as exc:
        raise PhiDecryptionError("Decryption failed: ciphertext tampered or wrong key") from exc
    return plaintext_bytes.decode("utf-8")
