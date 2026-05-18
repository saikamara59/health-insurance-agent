"""SQLAlchemy TypeDecorators that transparently encrypt/decrypt PHI columns.

EncryptedString wraps a String column; reads/writes plain Python strings.
EncryptedJSON wraps a String column (NOT JSON — ciphertext is opaque text);
reads/writes plain Python list/dict, serialised through json.dumps/loads
internally.

In strict mode (default), a stored plaintext value (no vN: prefix) raises
PhiDecryptionError on read — surfaces a migration gap loudly. The
PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 toggle opens a migration window where
plaintext is returned with a WARN log.

See healthflow/auth/phi_crypto.py for the wire format and key loading.
"""
import json
import logging
import os

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from healthflow.auth.phi_crypto import PhiDecryptionError, decrypt, encrypt

logger = logging.getLogger(__name__)


def _looks_like_ciphertext(value: str) -> bool:
    """Heuristic: real ciphertext starts with `vN:` where N is digits.

    Acceptable false-positive: a plaintext value like 'v1: yes' would be
    misclassified and fail to decrypt — surfaces as PhiDecryptionError
    (loud), not silent data corruption. Real PHI doesn't have this shape.
    """
    if not value.startswith("v") or ":" not in value[:6]:
        return False
    version_part = value.split(":", 1)[0]
    # version_part is e.g. "v1", "v12"; the rest must be digits
    return len(version_part) >= 2 and version_part[1:].isdigit()


def _decrypt_or_passthrough(value: str) -> str:
    """Decrypt a stored value; in strict mode, raise on plaintext."""
    if _looks_like_ciphertext(value):
        return decrypt(value)
    if os.getenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ") == "1":
        logger.warning(
            "encrypted_types: returning plaintext value during migration window — "
            "this should not happen in production. Run scripts/encrypt_existing_phi.py."
        )
        return value
    raise PhiDecryptionError(
        "Encrypted column contains plaintext. Run scripts/encrypt_existing_phi.py "
        "or set PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 during a migration window."
    )


class EncryptedString(TypeDecorator):
    """A SQLAlchemy column type that encrypts/decrypts string values transparently."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _decrypt_or_passthrough(value)


class EncryptedJSON(TypeDecorator):
    """A SQLAlchemy column type that encrypts/decrypts JSON-serialisable values transparently.

    Underlying storage is String (NOT JSON) because ciphertext is opaque text —
    SQLite stores both as TEXT so the on-disk shape is unchanged from a JSON
    column, but the declared type is String for honesty.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(json.dumps(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(_decrypt_or_passthrough(value))
