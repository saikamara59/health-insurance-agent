# Encryption at Rest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encrypt 8 PHI columns across `Client`, `ActionHistory`, and `Feedback` at rest using AES-256-GCM via SQLAlchemy `TypeDecorator`s, with a versioned wire format that supports additive key rotation and a one-time migration script for existing plaintext rows.

**Architecture:** New `healthflow/auth/phi_crypto.py` owns the AES-GCM math + fail-loud key loading. New `healthflow/database/encrypted_types.py` provides `EncryptedString` and `EncryptedJSON` `TypeDecorator`s that wrap the math; the rest of the app never sees ciphertext. `models.py` swaps the column types on the 8 encrypted fields. A `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1` toggle gates a migration window during which `scripts/encrypt_existing_phi.py` re-encrypts legacy rows. Same fail-loud pattern as `JWT_SECRET` from sub-project #4; same `TypeDecorator` mechanism as `GUID` already in the codebase.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async (`TypeDecorator`), `cryptography>=42` (AES-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`), pytest. Adds `cryptography>=42` to `requirements.txt`.

**Spec:** [docs/superpowers/specs/2026-05-17-encryption-at-rest-design.md](../specs/2026-05-17-encryption-at-rest-design.md)

---

## Background: two patterns this plan reuses

**`TypeDecorator` for transparent column-level transformation.** The codebase already does this with `GUID` (`healthflow/database/models.py:19-36`), which converts `uuid.UUID` ↔ `str(36)` so columns declared `GUID()` round-trip cleanly. `EncryptedString` and `EncryptedJSON` use the exact same mechanism: `process_bind_param` runs on write, `process_result_value` runs on read. The ORM calls these automatically — application code never sees the encryption.

**Versioned wire format for rotation-safe encryption.** Every encrypted value is `vN:<base64-nonce>:<base64-ciphertext+tag>` where `vN` is the key version. `decrypt` parses the prefix and picks the right key from `_KEYS`. This means rotation is *additive*: add `PHI_ENCRYPTION_KEY_V2` to env, set `_CURRENT_VERSION = "v2"`, new writes go through v2, old `v1:` rows still decrypt with the v1 key. **No re-encryption sweep required for rotation.** The migration script in this plan re-encrypts existing *plaintext* rows (one-time), not for rotation.

---

## File Structure

```
healthflow/
  auth/
    phi_crypto.py            (NEW — _load_phi_keys, encrypt, decrypt, PhiDecryptionError)
  database/
    encrypted_types.py       (NEW — EncryptedString, EncryptedJSON TypeDecorators)
    models.py                (MODIFIED — 8 column type swaps)
  tests/
    conftest.py              (MODIFIED — set PHI_ENCRYPTION_KEY at import time)
    auth/
      test_phi_crypto.py     (NEW — 8 crypto unit tests)
    database/
      test_encrypted_types.py (NEW — 3 TypeDecorator tests + 4 cross-sub-project integration tests + 3 toggle tests)
scripts/
  encrypt_existing_phi.py    (NEW — one-time migration script)
  tests/
    test_encrypt_existing_phi.py (NEW — 1 migration test — placed in healthflow/tests/database/)
requirements.txt             (MODIFIED — add cryptography>=42)
.env.example                 (MODIFIED — PHI_ENCRYPTION_KEY note)
.claude/skills/
  healthflow-security/
    SKILL.md                 (MODIFIED — encryption rules + deploy checklist + never-delete-key-version)
```

Note: the migration script test goes in `healthflow/tests/database/test_encrypt_existing_phi.py` (per the project's test-folder reorg — there's no `scripts/tests/` directory).

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b encryption-at-rest/foundation
git branch --show-current
```

Expected: `encryption-at-rest/foundation`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `545 tests collected in X.XXs`. Record the actual number.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: all 545 tests pass. There is a known-flaky `test_tampered_token_raises`; if exactly that one fails on first run, re-run once before declaring failure.

No commit for this task.

---

## Task 2: Add `cryptography` dependency + conftest sets `PHI_ENCRYPTION_KEY`

**Files:**
- Modify: `requirements.txt`
- Modify: `healthflow/tests/conftest.py`

Both prep steps land before any encryption code so the suite stays green through subsequent tasks. Like Task 2 of the auth hardening plan, the conftest `setdefault` MUST land before Task 3's fail-loud module is imported.

- [ ] **Step 1: Add `cryptography>=42` to `requirements.txt`**

Edit `requirements.txt`. Add the line `cryptography>=42` alphabetically (between `click>=8.1` and `fastapi>=0.115`):

```
fastapi>=0.115
uvicorn>=0.30
click>=8.1
cryptography>=42
anthropic>=0.40
redis>=5.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27
sqlalchemy>=2.0
aiosqlite>=0.20
python-jose>=3.3
passlib[bcrypt]>=1.7
bcrypt<4.1
pytest-asyncio>=0.23
python-dotenv>=1.0
```

- [ ] **Step 2: Install the new dependency**

```bash
.venv/bin/pip install -r requirements.txt 2>&1 | tail -5
```

Expected: `cryptography` installed. Confirm:

```bash
.venv/bin/python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print('AESGCM OK')"
```

Expected: `AESGCM OK`.

- [ ] **Step 3: Add `PHI_ENCRYPTION_KEY` setdefault to conftest**

Edit `healthflow/tests/conftest.py`. The file currently starts with:

```python
import os

# Set JWT_SECRET before any healthflow.* module imports it. Required because
# healthflow.auth.security raises at import time if JWT_SECRET is unset or set
# to the known-bad legacy value — see docs/superpowers/specs/2026-05-16-auth-hardening-design.md.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
```

Add immediately after the `os.environ.setdefault` for `JWT_SECRET`:

```python
import base64 as _base64

# Set PHI_ENCRYPTION_KEY before any healthflow.* module imports it. Required because
# healthflow.auth.phi_crypto raises at import time if PHI_ENCRYPTION_KEY is unset.
# A deterministic test key — safe to commit because it's only used in tests.
os.environ.setdefault(
    "PHI_ENCRYPTION_KEY",
    _base64.b64encode(b"\x00" * 32).decode(),
)
```

The all-zeros 32-byte key is deterministic, base64-encoded, and obviously a test value (real keys are random). This loads before any healthflow import so Task 3's fail-loud module can be imported without raising.

- [ ] **Step 4: Run the full suite to confirm no regression**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 545 passed. The conftest change is a no-op today (no module reads `PHI_ENCRYPTION_KEY` yet); it primes for Task 3.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt healthflow/tests/conftest.py
git commit -m "deps + tests: add cryptography>=42 and PHI_ENCRYPTION_KEY conftest fixture"
```

No `Co-Authored-By` trailer.

---

## Task 3: `phi_crypto.py` module — keys, encrypt, decrypt

**Files:**
- Create: `healthflow/auth/phi_crypto.py`
- Create: `healthflow/tests/auth/test_phi_crypto.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/auth/test_phi_crypto.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_phi_crypto.py -v
```

Expected: ImportError — `healthflow.auth.phi_crypto` does not exist.

- [ ] **Step 3: Create `phi_crypto.py`**

Create `healthflow/auth/phi_crypto.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_phi_crypto.py -v
```

Expected: 11 passed (1 raise-on-unset + 1 placeholder + 1 single-key + 1 v2-becomes-current + 1 wire-format + 4 parametrized roundtrips + 1 garbage + 1 cross-version). The parametrize counts as 4 separate test invocations.

- [ ] **Step 5: Verify total count is now 545 + 11 = 556**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `556 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/phi_crypto.py healthflow/tests/auth/test_phi_crypto.py
git commit -m "phi_crypto: AES-256-GCM with versioned key envelope + fail-loud key loading"
```

---

## Task 4: `encrypted_types.py` — `EncryptedString` and `EncryptedJSON`

**Files:**
- Create: `healthflow/database/encrypted_types.py`
- Create: `healthflow/tests/database/test_encrypted_types.py`

This task adds the TypeDecorators in **strict mode only** — `_decrypt_or_passthrough` rejects plaintext. The `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` toggle is added in Task 9, after the per-column migrations are in.

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/database/test_encrypted_types.py`:

```python
"""Unit tests for EncryptedString and EncryptedJSON TypeDecorators.

Uses a throwaway in-memory SQLite session with a real key — no mocking,
real encrypt + real decrypt round-trip.
"""
import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, MetaData, Table, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.encrypted_types import EncryptedJSON, EncryptedString


@pytest_asyncio.fixture
async def encrypted_session():
    """Throwaway engine + a one-off table with encrypted columns. No app DB."""
    metadata = MetaData()
    test_table = Table(
        "enc_test",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("secret_str", EncryptedString(2000)),
        Column("secret_json", EncryptedJSON()),
    )
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session, test_table
    await engine.dispose()


@pytest.mark.anyio
async def test_encrypted_string_roundtrips(encrypted_session):
    session, test_table = encrypted_session
    await session.execute(
        test_table.insert().values(id=1, secret_str="Eleanor Rigby", secret_json=None)
    )
    await session.commit()

    result = await session.execute(select(test_table).where(test_table.c.id == 1))
    row = result.first()
    assert row.secret_str == "Eleanor Rigby"


@pytest.mark.anyio
async def test_encrypted_json_roundtrips_list_of_dicts(encrypted_session):
    session, test_table = encrypted_session
    value = [{"name": "Dr. Aanur", "npi": "1234567890"}, {"name": "Dr. Aaron"}]
    await session.execute(
        test_table.insert().values(id=2, secret_str=None, secret_json=value)
    )
    await session.commit()

    result = await session.execute(select(test_table).where(test_table.c.id == 2))
    row = result.first()
    assert row.secret_json == value


@pytest.mark.anyio
async def test_encrypted_columns_store_ciphertext_on_disk(encrypted_session):
    """Raw SQL bypasses the TypeDecorator — proves the value is ciphertext at rest."""
    session, test_table = encrypted_session
    await session.execute(
        test_table.insert().values(id=3, secret_str="Walt Whitman", secret_json=["dx"])
    )
    await session.commit()

    raw = await session.execute(text("SELECT secret_str, secret_json FROM enc_test WHERE id = 3"))
    secret_str, secret_json = raw.first()
    # Both should be ciphertext-shaped: starts with vN: and has the three-part form
    assert secret_str.startswith("v1:") and secret_str.count(":") == 2
    assert "Walt Whitman" not in secret_str
    assert secret_json.startswith("v1:")
    assert "dx" not in secret_json
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypted_types.py -v
```

Expected: ImportError — `healthflow.database.encrypted_types` does not exist.

- [ ] **Step 3: Create `encrypted_types.py`**

Create `healthflow/database/encrypted_types.py`:

```python
"""SQLAlchemy TypeDecorators that transparently encrypt/decrypt PHI columns.

EncryptedString wraps a String column; reads/writes plain Python strings.
EncryptedJSON wraps a String column (NOT JSON — ciphertext is opaque text);
reads/writes plain Python list/dict, serialised through json.dumps/loads
internally.

In strict mode (default), a stored plaintext value (no vN: prefix) raises
PhiDecryptionError on read — surfaces a migration gap loudly. The
PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 toggle (added in Task 9) opens a
migration window where plaintext is returned with a WARN log.

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypted_types.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Verify total count is now 556 + 3 = 559**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `559 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/encrypted_types.py healthflow/tests/database/test_encrypted_types.py
git commit -m "encrypted_types: EncryptedString + EncryptedJSON TypeDecorators (strict mode)"
```

---

## Task 5: Migrate `Client.full_name` (single column, smallest blast radius first)

**Files:**
- Modify: `healthflow/database/models.py`
- Test: existing `Client` tests + 1 new integration test

This task migrates ONE column to verify the end-to-end path through the real `Client` model, the tenant filter, the audit log, and existing client tests before piling on the JSON columns.

- [ ] **Step 1: Modify `models.py`**

Edit `healthflow/database/models.py`. Add this import near the top with the other `from healthflow.database.*` imports (currently there are none in models.py; add a new import after the existing `from sqlalchemy.types import JSON, TypeDecorator`):

```python
from healthflow.database.encrypted_types import EncryptedString
```

Find `Client.full_name` (line 78 in current file):

```python
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
```

Change to:

```python
    full_name: Mapped[str] = mapped_column(EncryptedString(2000), nullable=False)
```

The `Mapped[str]` annotation stays — TypeDecorator round-trips strings.

- [ ] **Step 2: Add a cross-sub-project integration test**

Append to `healthflow/tests/database/test_encrypted_types.py`:

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import current_broker_id, current_endpoint, system_context
from healthflow.database.models import Base, Broker, Client, PhiAccessLog
from healthflow.database.phi_audit import install_phi_audit
from healthflow.database.tenant_filter import install_tenant_filter


@pytest_asyncio.fixture
async def app_db():
    """The real app's Base.metadata + tenant filter + audit listener installed.
    Mirrors the production session factory."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    install_phi_audit(factory)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.anyio
async def test_client_full_name_encrypted_at_rest_with_tenant_filter_and_audit_log(app_db):
    """Cross-sub-project sanity: encryption + tenant filter + PHI audit all work together."""
    session = app_db

    # Seed a broker + client under system_context
    with system_context("test setup"):
        broker = Broker(
            email="enc1@t.test", hashed_password=hash_password("xPass-1234!"), full_name="EncBroker",
        )
        session.add(broker)
        await session.flush()
        client_a = Client(
            broker_id=broker.id, full_name="Eleanor Rigby", zip_code="10001",
            age=67, income_level="low",
            doctors=[], prescriptions=[], procedures=[],
        )
        session.add(client_a)
        await session.commit()
        client_id = client_a.id

    # Read via the ORM under broker's context — full_name decrypts transparently
    token = current_broker_id.set(broker.id)
    ep = current_endpoint.set("GET /clients/{id}")
    try:
        result = await session.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one()
        assert client.full_name == "Eleanor Rigby"
        # Tenant filter still applied; zip_code (plaintext column) still readable
        assert client.zip_code == "10001"
    finally:
        current_endpoint.reset(ep)
        current_broker_id.reset(token)

    # Raw SELECT bypasses the TypeDecorator — confirms ciphertext on disk
    with system_context("test verify"):
        raw = await session.execute(text("SELECT full_name FROM clients WHERE id = :id"),
                                     {"id": str(client_id)})
        on_disk = raw.scalar_one()
    assert on_disk.startswith("v1:")
    assert "Eleanor Rigby" not in on_disk

    # Audit log row_ids capture still works (UUIDs are plaintext)
    with system_context("test verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients/{id}")
        )).scalars().all()
    assert len(log) == 1
    assert str(client_id) in log[0].row_ids
```

- [ ] **Step 3: Run the new test + the existing client tests**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypted_types.py healthflow/tests/api/test_clients.py healthflow/tests/api/test_app_wiring.py -v 2>&1 | tail -20
```

Expected: all pass. The existing client tests (which create/read/update clients with `full_name = "Test User"` etc.) should round-trip cleanly through the new EncryptedString.

- [ ] **Step 4: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 560 passed (559 + 1 new integration test). If any test fails because it asserts on the on-disk representation of `full_name`, surface — that's a real test rewrite, not a 2-line fix.

- [ ] **Step 5: Commit**

```bash
git add healthflow/database/models.py healthflow/tests/database/test_encrypted_types.py
git commit -m "models: encrypt Client.full_name (first column migration)"
```

---

## Task 6: Migrate the three `EncryptedJSON` columns on `Client`

**Files:**
- Modify: `healthflow/database/models.py`

- [ ] **Step 1: Modify `models.py`**

Edit `healthflow/database/models.py`. Update the import line from Task 5:

```python
from healthflow.database.encrypted_types import EncryptedJSON, EncryptedString
```

Find these three lines on `Client` (currently lines 82-84):

```python
    doctors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    prescriptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    procedures: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
```

Change all three to use `EncryptedJSON`:

```python
    doctors: Mapped[list] = mapped_column(EncryptedJSON(), default=list, nullable=False)
    prescriptions: Mapped[list] = mapped_column(EncryptedJSON(), default=list, nullable=False)
    procedures: Mapped[list] = mapped_column(EncryptedJSON(), default=list, nullable=False)
```

`default=list` still works — TypeDecorator runs on bind, so an empty list becomes `encrypt('[]')` on write and round-trips as `[]` on read.

- [ ] **Step 2: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 560 passed (no new tests; existing client tests round-trip through the new columns).

If any existing test asserts something like `client.doctors == [{"name": "Dr. Aanur"}]` and that fails, the encryption round-trip isn't preserving the list — surface for investigation. JSON `dumps`/`loads` should be exact for serialisable types.

- [ ] **Step 3: Commit**

```bash
git add healthflow/database/models.py
git commit -m "models: encrypt Client.doctors, prescriptions, procedures (EncryptedJSON)"
```

---

## Task 7: Migrate `ActionHistory.request_data` and `response_summary`

**Files:**
- Modify: `healthflow/database/models.py`

- [ ] **Step 1: Modify `models.py`**

Edit `healthflow/database/models.py`. Find these two lines on `ActionHistory` (currently lines 109-110):

```python
    request_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
```

Change to:

```python
    request_data: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict, nullable=False)
```

`default=dict` (not `list`) — same pattern, just a different default factory.

- [ ] **Step 2: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 560 passed. The history router + feedback tests exercise these columns; they should round-trip cleanly.

- [ ] **Step 3: Commit**

```bash
git add healthflow/database/models.py
git commit -m "models: encrypt ActionHistory.request_data, response_summary"
```

---

## Task 8: Migrate `Feedback.comment` (last column)

**Files:**
- Modify: `healthflow/database/models.py`

- [ ] **Step 1: Modify `models.py`**

Edit `healthflow/database/models.py`. Find on `Feedback` (currently line 133):

```python
    comment: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
```

Change to:

```python
    comment: Mapped[str] = mapped_column(EncryptedString(4000), default="", nullable=False)
```

`default=""` still works — empty string encrypts to a small ciphertext, decrypts to `""`.

- [ ] **Step 2: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 560 passed. All 8 columns now encrypted.

- [ ] **Step 3: Commit**

```bash
git add healthflow/database/models.py
git commit -m "models: encrypt Feedback.comment (all 8 PHI columns now encrypted)"
```

---

## Task 9: Add `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` toggle tests + `.env.example`

**Files:**
- Modify: `healthflow/tests/database/test_encrypted_types.py`
- Modify: `.env.example`

The toggle logic already lives in `_decrypt_or_passthrough` (Task 4). This task adds tests that prove it works, and updates `.env.example` to document the variables.

- [ ] **Step 1: Write the toggle tests**

Append to `healthflow/tests/database/test_encrypted_types.py`:

```python
from sqlalchemy import text


@pytest.mark.anyio
async def test_plaintext_read_raises_in_strict_mode(encrypted_session, monkeypatch):
    """Strict mode (default): a stored plaintext value raises on read."""
    monkeypatch.delenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", raising=False)
    session, test_table = encrypted_session
    # Insert a plaintext value via raw SQL, bypassing the TypeDecorator
    await session.execute(
        text("INSERT INTO enc_test (id, secret_str, secret_json) VALUES (4, 'plaintext-value', NULL)")
    )
    await session.commit()

    from healthflow.auth.phi_crypto import PhiDecryptionError
    with pytest.raises(PhiDecryptionError):
        result = await session.execute(select(test_table).where(test_table.c.id == 4))
        # Force result materialisation (the decrypt happens when the value is consumed)
        _ = result.first().secret_str


@pytest.mark.anyio
async def test_plaintext_read_allowed_with_toggle(encrypted_session, monkeypatch):
    """Migration mode (toggle=1): a stored plaintext value reads back as plaintext."""
    monkeypatch.setenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", "1")
    session, test_table = encrypted_session
    await session.execute(
        text("INSERT INTO enc_test (id, secret_str, secret_json) VALUES (5, 'legacy-plaintext', NULL)")
    )
    await session.commit()

    result = await session.execute(select(test_table).where(test_table.c.id == 5))
    assert result.first().secret_str == "legacy-plaintext"


@pytest.mark.anyio
async def test_ciphertext_reads_regardless_of_toggle(encrypted_session, monkeypatch):
    """Round-tripped values work whether the toggle is on or off."""
    session, test_table = encrypted_session
    # Write via the ORM (encrypts)
    await session.execute(test_table.insert().values(id=6, secret_str="ciphered", secret_json=None))
    await session.commit()

    # Read with toggle off
    monkeypatch.delenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", raising=False)
    result = await session.execute(select(test_table).where(test_table.c.id == 6))
    assert result.first().secret_str == "ciphered"

    # Read with toggle on
    monkeypatch.setenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", "1")
    result = await session.execute(select(test_table).where(test_table.c.id == 6))
    assert result.first().secret_str == "ciphered"
```

- [ ] **Step 2: Run the toggle tests**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypted_types.py -v -k "plaintext or toggle"
```

Expected: 3 passed.

- [ ] **Step 3: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 563 passed (560 + 3 new).

- [ ] **Step 4: Update `.env.example`**

Edit `.env.example`. Add these lines (find a logical place near the `JWT_SECRET` block):

```
# Required. AES-256 key for PHI column encryption (Client/ActionHistory/Feedback).
# Generate one with:
#   python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# To rotate: add PHI_ENCRYPTION_KEY_V2 alongside; new writes use v2 automatically.
# Never delete PHI_ENCRYPTION_KEY while any row exists encrypted under v1.
PHI_ENCRYPTION_KEY=

# Migration-window-only escape hatch. Lets the app read legacy plaintext rows
# during the encrypt-existing-phi sweep. MUST be unset (or != "1") in production.
# PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1
```

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/database/test_encrypted_types.py .env.example
git commit -m "encrypted_types: plaintext-passthrough toggle for migration window"
```

---

## Task 10: `scripts/encrypt_existing_phi.py` + its test

**Files:**
- Create: `scripts/encrypt_existing_phi.py`
- Create: `healthflow/tests/database/test_encrypt_existing_phi.py`

- [ ] **Step 1: Write the failing test**

Create `healthflow/tests/database/test_encrypt_existing_phi.py`:

```python
"""Test the encrypt_existing_phi.py one-time migration script."""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Base, Broker, Client


@pytest_asyncio.fixture
async def db_with_plaintext_rows(monkeypatch):
    """Build a DB with rows whose encrypted columns contain plaintext (legacy state).

    Done by inserting via raw SQL, bypassing the TypeDecorator.
    """
    monkeypatch.setenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", "1")
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        with system_context("test setup"):
            broker = Broker(
                email="mig@t.test", hashed_password=hash_password("xPass-1234!"), full_name="Mig",
            )
            session.add(broker)
            await session.flush()
            # Insert client with PLAINTEXT in encrypted columns via raw SQL
            await session.execute(
                text("""
                    INSERT INTO clients (id, broker_id, full_name, zip_code, age, income_level,
                                         doctors, prescriptions, procedures, created_at, updated_at)
                    VALUES (:id, :bid, :name, :zip, :age, :inc, :docs, :rx, :proc,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "bid": str(broker.id),
                    "name": "Plain Patient",
                    "zip": "10001", "age": 50, "inc": "low",
                    "docs": json.dumps([{"name": "Dr. Plain"}]),
                    "rx": json.dumps(["Metformin"]),
                    "proc": json.dumps([]),
                },
            )
            await session.commit()
    yield engine, factory
    await engine.dispose()


@pytest.mark.anyio
async def test_encrypt_existing_phi_encrypts_plaintext_rows(db_with_plaintext_rows, monkeypatch):
    engine, factory = db_with_plaintext_rows

    from scripts.encrypt_existing_phi import encrypt_all
    await encrypt_all(factory)

    # After the script: rows should be ciphertext on disk
    async with factory() as session:
        with system_context("verify"):
            raw = await session.execute(text("SELECT full_name, doctors FROM clients"))
            row = raw.first()
            assert row.full_name.startswith("v1:")
            assert "Plain Patient" not in row.full_name
            assert row.doctors.startswith("v1:")

    # Reads via ORM should still return plaintext (with toggle off — strict mode)
    monkeypatch.delenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", raising=False)
    async with factory() as session:
        with system_context("verify"):
            client = (await session.execute(select(Client))).scalar_one()
            assert client.full_name == "Plain Patient"
            assert client.doctors == [{"name": "Dr. Plain"}]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypt_existing_phi.py -v
```

Expected: ImportError — `scripts.encrypt_existing_phi` does not exist.

- [ ] **Step 3: Create the migration script**

Create `scripts/encrypt_existing_phi.py`:

```python
#!/usr/bin/env python3
"""One-time migration: encrypt plaintext rows in the PHI columns.

After deploying the encryption change, existing rows in Client / ActionHistory /
Feedback contain plaintext in columns that are now declared `EncryptedString`
or `EncryptedJSON`. This script reads each row through the ORM (the TypeDecorator
returns plaintext IF PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1) and re-saves it —
the next flush triggers process_bind_param, which encrypts.

Run once at deploy time:
    PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 python scripts/encrypt_existing_phi.py
Then unset the env var and restart the app (strict mode resumes).

Idempotent: re-running on already-encrypted rows round-trips cleanly.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path for `python scripts/...` invocation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.tenant_context import system_context
from healthflow.database.models import ActionHistory, Client, Feedback

_BATCH_SIZE = 100

# Per-model: which fields to re-save. Only the encrypted columns need to be
# re-saved (their TypeDecorator triggers on the next flush).
_ENCRYPTED_FIELDS: dict[type, tuple[str, ...]] = {
    Client: ("full_name", "doctors", "prescriptions", "procedures"),
    ActionHistory: ("request_data", "response_summary"),
    Feedback: ("comment",),
}


async def encrypt_all(factory: async_sessionmaker) -> None:
    """Walk all PHI tables, re-save each row to trigger encryption."""
    for model, fields in _ENCRYPTED_FIELDS.items():
        await _encrypt_model(factory, model, fields)


async def _encrypt_model(factory: async_sessionmaker, model: type, fields: tuple[str, ...]) -> None:
    offset = 0
    while True:
        async with factory() as session:
            with system_context(f"encrypt-existing-phi migration: {model.__tablename__}"):
                result = await session.execute(
                    select(model).order_by(model.id).offset(offset).limit(_BATCH_SIZE)
                )
                rows = list(result.scalars().all())
                if not rows:
                    return
                for row in rows:
                    # Setting each encrypted field to its current value marks it
                    # dirty; the next flush triggers process_bind_param → encrypt.
                    for field in fields:
                        setattr(row, field, getattr(row, field))
                await session.commit()
                print(f"  {model.__tablename__}: encrypted {len(rows)} rows (offset {offset})")
        offset += _BATCH_SIZE


async def _main() -> int:
    from healthflow.database.config import async_session_factory
    print("Encrypting existing PHI rows. This may take a while for large databases.")
    await encrypt_all(async_session_factory)
    print("Done. Unset PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ and restart the app.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
```

- [ ] **Step 4: Run the test**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_encrypt_existing_phi.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 564 passed (563 + 1 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/encrypt_existing_phi.py healthflow/tests/database/test_encrypt_existing_phi.py
git commit -m "scripts: encrypt_existing_phi one-time migration + test"
```

---

## Task 11: Update the `healthflow-security` skill

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Read the current skill**

```bash
cat .claude/skills/healthflow-security/SKILL.md
```

It has YAML frontmatter, then sections. Don't touch the frontmatter. The closest related section is the "Auth hardening rules (enforced)" section (added in sub-project #4). Add the new encryption section after it for thematic cohesion (both are about defense in depth at the persistence + auth layer).

- [ ] **Step 2: Add the encryption section**

Edit `.claude/skills/healthflow-security/SKILL.md`. Add this section AFTER the existing "Auth hardening rules (enforced)" section:

```markdown
## Encryption at rest (enforced)

PHI columns on `Client`, `ActionHistory`, and `Feedback` are stored as
AES-256-GCM ciphertext at rest. Eight columns total:
`Client.full_name`, `doctors`, `prescriptions`, `procedures`;
`ActionHistory.request_data`, `response_summary`; `Feedback.comment`.
Encryption is enforced via SQLAlchemy `TypeDecorator`s (`EncryptedString`,
`EncryptedJSON` in `healthflow/database/encrypted_types.py`) — application
code never sees ciphertext. The math lives in `healthflow/auth/phi_crypto.py`.

**Rule:** `PHI_ENCRYPTION_KEY` is read fail-loud at module import (same pattern
as `JWT_SECRET`). A missing env var OR a known placeholder value raises
`RuntimeError`. Generate a real key with:
`python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`

**Rule:** Wire format is `vN:<base64-nonce>:<base64-ciphertext+tag>` where
`vN` is the key version (`v1`, `v2`, …). New writes use `_CURRENT_VERSION`
(the highest configured key). Reads dispatch on the prefix. This makes
rotation additive: add `PHI_ENCRYPTION_KEY_V2`, restart the app, new writes
go through v2, old `v1:` rows still decrypt with the v1 key.

**Rule:** **Never delete a key version while any row exists encrypted under
it.** Practical rotation sequence: add `v2`, run a (future) v1→v2 sweep
script, *then* drop the `v1` env var.

**Rule:** `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1` opens a migration window —
`EncryptedString`/`EncryptedJSON` columns may contain plaintext, which reads
back unchanged (with a WARN log). MUST be unset in production. Used only
during a one-time `scripts/encrypt_existing_phi.py` run at deploy time.
Strict mode (the default) raises `PhiDecryptionError` on plaintext in an
encrypted column — surfaces an incomplete migration loudly, not silently.

**Rule:** Searchable queries (`WHERE full_name = 'X'`) do NOT work on
encrypted columns — AES-GCM uses a random nonce per encryption, so the same
plaintext produces different ciphertext each time. If a search-by-PHI flow
becomes necessary, add a blind index (HMAC of the value) in a sibling
column. Today no such queries exist on encrypted columns; the quasi-
identifiers that ARE queried (`zip_code`, `age`, `income_level`) stay plain
text by design.

**Rule:** When adding a new PHI column, decide explicitly:
encrypted (use `EncryptedString` or `EncryptedJSON`), or plaintext quasi-
identifier (queried by value). Add it to `_ENCRYPTED_FIELDS` in
`scripts/encrypt_existing_phi.py` if encrypted, so any future re-encryption
sweep covers it.
```

- [ ] **Step 3: Verify the frontmatter is intact**

```bash
head -10 .claude/skills/healthflow-security/SKILL.md
```

The `---` frontmatter block must be unchanged.

- [ ] **Step 4: Run the full suite (no behavior change)**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 564 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "skill: healthflow-security — document encryption at rest rules"
```

---

## Task 12: Final verification + push + PR

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: `564 passed`. If even one fails (other than a single re-run-fixable flaky `test_tampered_token_raises`), STOP and surface.

- [ ] **Step 2: Run `make check`**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; lint count not worse than baseline. If this branch introduced any new lint errors, fix before pushing.

- [ ] **Step 3: Hand-verify PHI_ENCRYPTION_KEY fail-loud**

```bash
.venv/bin/python -c "
import os
os.environ.pop('PHI_ENCRYPTION_KEY', None)
try:
    import importlib
    import healthflow.auth.phi_crypto as p
    importlib.reload(p)
    print('FAIL: import did not raise')
except RuntimeError as e:
    print(f'OK: {e}')
"
```

Expected: `OK: PHI_ENCRYPTION_KEY environment variable is required. ...`. Then restore the env or just spawn a fresh shell.

- [ ] **Step 4: Hand-verify end-to-end encryption against a real session**

```bash
PHI_ENCRYPTION_KEY="$(python -c 'import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())')" \
JWT_SECRET=test-secret-not-for-production \
.venv/bin/python -c "
import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Base, Broker, Client

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///', echo=False)
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with f() as s:
        with system_context('hv'):
            b = Broker(email='hv@t.test', hashed_password=hash_password('xPass-1234!'), full_name='HV')
            s.add(b); await s.flush()
            c = Client(broker_id=b.id, full_name='Plain Patient', zip_code='10001', age=40,
                       income_level='low', doctors=[{'name':'Dr.X'}], prescriptions=['Metformin'], procedures=[])
            s.add(c); await s.commit()

            # ORM read returns plaintext
            client = (await s.execute(select(Client))).scalar_one()
            assert client.full_name == 'Plain Patient'
            assert client.doctors == [{'name': 'Dr.X'}]
            # Raw read returns ciphertext
            raw = (await s.execute(text('SELECT full_name, doctors FROM clients'))).first()
            assert raw.full_name.startswith('v1:')
            assert 'Plain Patient' not in raw.full_name
            assert raw.doctors.startswith('v1:')
        print('encryption at rest end-to-end: OK')
    await engine.dispose()

asyncio.run(main())
"
```

Expected: `encryption at rest end-to-end: OK`.

- [ ] **Step 5: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 10 commits (Tasks 1 and 12 don't commit):
- `skill: healthflow-security — document encryption at rest rules`
- `scripts: encrypt_existing_phi one-time migration + test`
- `encrypted_types: plaintext-passthrough toggle for migration window`
- `models: encrypt Feedback.comment (all 8 PHI columns now encrypted)`
- `models: encrypt ActionHistory.request_data, response_summary`
- `models: encrypt Client.doctors, prescriptions, procedures (EncryptedJSON)`
- `models: encrypt Client.full_name (first column migration)`
- `encrypted_types: EncryptedString + EncryptedJSON TypeDecorators (strict mode)`
- `phi_crypto: AES-256-GCM with versioned key envelope + fail-loud key loading`
- `deps + tests: add cryptography>=42 and PHI_ENCRYPTION_KEY conftest fixture`

Each message terse, no `Co-Authored-By` trailer.

- [ ] **Step 6: Push the branch**

```bash
git push -u origin encryption-at-rest/foundation 2>&1 | tail -5
```

- [ ] **Step 7: Open the PR**

```bash
gh pr create --title "Encryption at rest: AES-256-GCM field encryption on 8 PHI columns" --body "$(cat <<'EOF'
## Summary

Sub-project #5 of the HIPAA-readiness foundation — the last one. PHI in `healthflow.db` is now AES-256-GCM ciphertext at rest, defending against stolen-disk / DBA-level read access even if every other security layer fails.

- `healthflow/auth/phi_crypto.py` (new) — AES-256-GCM via `cryptography`, fail-loud key loading at module import (same pattern as `JWT_SECRET`), versioned wire format `vN:nonce:ciphertext` for additive rotation, custom `PhiDecryptionError`.
- `healthflow/database/encrypted_types.py` (new) — `EncryptedString` and `EncryptedJSON` SQLAlchemy `TypeDecorator`s. Same mechanism the codebase already uses for `GUID`. App code never sees ciphertext.
- `healthflow/database/models.py` — 8 column type swaps: `Client.full_name`, `Client.doctors`, `Client.prescriptions`, `Client.procedures`, `ActionHistory.request_data`, `ActionHistory.response_summary`, `Feedback.comment`.
- `scripts/encrypt_existing_phi.py` (new) — one-time migration that re-saves all PHI rows through the ORM, triggering encryption.
- `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1` toggle (read by `encrypted_types._decrypt_or_passthrough`) — opens a brief migration window. Off in prod = strict mode = `PhiDecryptionError` on any leftover plaintext.
- `requirements.txt` — adds `cryptography>=42`.
- `healthflow/tests/conftest.py` — sets `PHI_ENCRYPTION_KEY` at import time (same pattern as `JWT_SECRET`).
- `.claude/skills/healthflow-security/SKILL.md` — six new enforcement rules.

## ⚠ Deploy notes (read carefully — encryption is data-loss-sensitive)

**1. Set `PHI_ENCRYPTION_KEY` in your deploy environment.** Generate one:
```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```
The backend will refuse to start without it.

**2. One-time migration for existing databases.** After deploying this PR (but before un-toggling the next step), run:
```bash
PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 python scripts/encrypt_existing_phi.py
```
This re-encrypts every existing row's PHI columns in place. Safe to re-run (idempotent).

**3. Then unset `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` and restart the app.** Strict mode resumes; any leftover plaintext now raises `PhiDecryptionError` loudly instead of silently passing through.

**4. Back up your `PHI_ENCRYPTION_KEY` securely.** Losing the key = losing all encrypted data. There is no recovery path. Store it in a secrets manager (AWS Secrets Manager, 1Password, etc.).

**5. Future rotation:** add `PHI_ENCRYPTION_KEY_V2` alongside the existing one. New writes use v2 automatically. Old `v1:` rows keep decrypting because `v1` is still loaded. Never drop a key version while any row exists encrypted under it.

## What this protects + what it doesn't

**Protects:** Stolen DB file. DBA-level read access. Backups pulled from cloud storage. An attacker who escalates from any other vuln into filesystem access.

**Does not protect:** A running app with the key in memory. An attacker with both the DB file AND the env var. (Defending against the latter requires KMS — out of scope.)

## Test Plan

- [x] 19 new tests: `phi_crypto` (11 incl. cross-version roundtrip), `encrypted_types` (6 incl. toggle), migration script (1), cross-sub-project integration with tenant filter + PHI audit log (1)
- [x] Full backend suite: 564/564 (was 545; +19)
- [x] Hand-verification: `PHI_ENCRYPTION_KEY` unset crashes import; round-tripped Client returns plaintext via ORM, ciphertext via raw `SELECT`
- [x] Tenant filter, PHI audit log, and prompt-input redaction all keep working unchanged on encrypted-column queries (the TypeDecorator decrypts before any of them see the value)
- [ ] CI green on this PR (requires `PHI_ENCRYPTION_KEY` to be set in CI env)

## Out of scope / follow-ups

- KMS / external key-management integration (env-var-based today; `PHI_ENCRYPTION_KEY` is the single config that production would swap to a KMS-derived value).
- Automated v1→v2 re-encryption sweep (rotation is supported via the versioned format; the sweep script is a separate small follow-up).
- Blind-index columns for searchable encryption (`WHERE full_name = X`) — none exist today; if a flow needs it, add an HMAC sibling column.
- Alembic migration for the `EncryptedJSON` column-type change (relevant on a future Postgres migration; no-op on SQLite).
- Account management sub-project (admin RBAC, change-password, forgot-password with email reset) — separate, was deferred from the auth hardening work.
- Encryption of plan/drug/ZIP/audit/refresh-token tables (not patient data).
EOF
)" 2>&1 | tail -3
```

Expected: a GitHub PR URL. Capture and report it.

No new commit for this task.
