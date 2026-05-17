# Auth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land four independent auth hardening fixes — `JWT_SECRET` fail-loud, password policy upgrade, account lockout, and refresh-token rotation with theft-signal — closing the long-standing trap flagged by the `healthflow-security` skill.

**Architecture:** Four tasks each touching `healthflow/auth/` and `healthflow/database/models.py`. The pieces don't depend on each other but a shared prerequisite — a test fixture that sets `JWT_SECRET` before the suite imports `security.py` — lands first so removing the legacy default doesn't break the existing 521 tests. A new `RefreshToken` system table holds per-token revocation state (mirrors the `PhiAccessLog` pattern: not tenant-scoped, not audited, plain-`GUID` `broker_id`).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async, pytest, `python-jose` (JWT), `passlib` (bcrypt). No new dependencies.

**Spec:** [docs/superpowers/specs/2026-05-16-auth-hardening-design.md](../specs/2026-05-16-auth-hardening-design.md)

---

## Background: two patterns this plan reuses

**Module-import-time fail-loud.** When `_load_jwt_secret()` raises at import, every other module that imports `security` also fails to import. That's the whole point — a misconfigured deploy crashes before serving its first request, instead of silently using a known-bad secret. The test pattern for "did this raise at import?" uses `monkeypatch.delenv` + `importlib.reload(security)` — same approach `test_test_router.py` already uses to reload `config.py`. Reloading invalidates other module-level constants in `security.py` (like `pwd_context`), so reload tests should reload back to a *valid* state at teardown.

**Refresh-token rotation with theft signal.** Standard OAuth2 pattern. Each `/refresh` consumes the presented refresh token (marks it revoked) and issues a fresh one. If a *revoked* token is replayed, that's evidence of theft — somebody copied the token before its first use. The response: revoke ALL of that broker's active refresh tokens. Legitimate user has to log in again; attacker also loses access. The `jti` (JWT ID) claim links the JWT to a `refresh_tokens` row so the DB has the authoritative revocation state.

---

## File Structure

```
healthflow/
  auth/
    security.py            (MODIFIED — fail-loud JWT_SECRET, validate_password,
                            common_passwords frozenset, create_refresh_token
                            now persists a RefreshToken row)
    router.py              (MODIFIED — register validates password, login does
                            lockout, refresh rotates + theft signal, /logout new)
    common_passwords.txt   (NEW — 200-line lowercased SecLists top-200)
  database/
    models.py              (MODIFIED — Broker.failed_login_count + locked_until;
                            new RefreshToken model)
  tests/
    conftest.py            (MODIFIED — autouse fixture that sets JWT_SECRET)
    auth/
      test_auth_hardening.py  (NEW — 20 tests, one section per piece)
.env.example               (MODIFIED — JWT_SECRET note + a real example value)
docker-compose.yml         (MODIFIED — drop the legacy default in the env line)
.claude/skills/
  healthflow-security/
    SKILL.md               (MODIFIED — document the four new enforcement rules)
```

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b auth-hardening/foundation
git branch --show-current
```

Expected: `auth-hardening/foundation`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `521 tests collected in X.XXs`. Record the actual number.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: all 521 tests pass. There is a known-flaky `test_tampered_token_raises`; if exactly that one fails on first run, re-run once before declaring failure.

No commit for this task.

---

## Task 2: Test conftest sets `JWT_SECRET` before any auth import

**Files:**
- Modify: `healthflow/tests/conftest.py`

This MUST land before Task 3 (the fail-loud change). The reason: Task 3 makes `healthflow/auth/security.py` raise at import if `JWT_SECRET` is unset. Without a fixture, every test that imports anything that transitively imports `security` would fail at collection time.

The conftest currently has no env-var manipulation. We need a session-scoped autouse fixture that sets `JWT_SECRET` *before any test imports* — that means `pytest_configure`, not a fixture (fixtures run after collection). The same effect can be achieved with a top-of-conftest `os.environ.setdefault(...)` line — runs at conftest import time, which is before test module imports.

- [ ] **Step 1: Add the env-var setdefault at the top of `conftest.py`**

Edit `healthflow/tests/conftest.py`. Find the existing imports at the top of the file. ABOVE all imports (literally line 1 or 2, before `import pytest`), add:

```python
import os

# Set JWT_SECRET before any healthflow.* module imports it. Required because
# healthflow.auth.security raises at import time if JWT_SECRET is unset or set
# to the known-bad legacy value — see docs/superpowers/specs/2026-05-16-auth-hardening-design.md.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
```

`setdefault` means CI / Docker environments that already set `JWT_SECRET` are untouched; only local test runs get the test value.

- [ ] **Step 2: Run the full suite to confirm no regression**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 521 passed. This change is a no-op today (the env var was being defaulted by `security.py` anyway); it just primes the environment for Task 3's removal of that default.

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/conftest.py
git commit -m "tests: set JWT_SECRET at conftest import time (prep for fail-loud)"
```

No `Co-Authored-By` trailer.

---

## Task 3: `JWT_SECRET` fail-loud

**Files:**
- Modify: `healthflow/auth/security.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Test: `healthflow/tests/auth/test_auth_hardening.py` (NEW file)

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/auth/test_auth_hardening.py`:

```python
"""Auth hardening tests — covers JWT_SECRET fail-loud, password policy,
account lockout, and refresh-token rotation.
"""
import importlib
import os

import pytest

import healthflow.auth.security as security


def test_jwt_secret_fail_loud_raises_when_unset(monkeypatch):
    """A missing JWT_SECRET env var must raise at module reload."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        importlib.reload(security)
    # Restore a valid value before this module's reference to `security`
    # becomes the unloaded one for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_fail_loud_rejects_legacy_default(monkeypatch):
    """The known-bad legacy default value must be rejected."""
    monkeypatch.setenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")
    with pytest.raises(RuntimeError, match="legacy default"):
        importlib.reload(security)
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_accepts_any_other_value(monkeypatch):
    """Setting to any other string imports cleanly."""
    monkeypatch.setenv("JWT_SECRET", "a-real-deploy-secret-7384")
    importlib.reload(security)
    assert security.JWT_SECRET == "a-real-deploy-secret-7384"
    # Restore the test default for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v
```

Expected: 3 failed — the tests expect a `RuntimeError` but `security.py` still silently defaults.

- [ ] **Step 3: Update `security.py` to fail-loud**

Edit `healthflow/auth/security.py`. Replace the current line 7 (`JWT_SECRET = os.getenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")`) with:

```python
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
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 524 passed (521 + 3 new). If anything else fails because it imports `security` without `JWT_SECRET` set, surface — the conftest fixture from Task 2 should cover all test paths, but a runtime path (a script run directly, etc.) might surface.

- [ ] **Step 6: Update `docker-compose.yml`**

Edit `docker-compose.yml`. Find line 10:

```yaml
      - JWT_SECRET=${JWT_SECRET:-healthflow-dev-secret-change-in-production}
```

Replace with:

```yaml
      - JWT_SECRET=${JWT_SECRET:?JWT_SECRET must be set — see .env.example}
```

The `${VAR:?error}` syntax makes Docker Compose fail with the error message if `JWT_SECRET` is unset in the environment or `.env` file. Same fail-loud philosophy as the Python side.

`docker-compose.test.yml` already sets `JWT_SECRET=test-secret` (hardcoded for the test stack) — leave that file alone. Same for the `.github/workflows/e2e.yml` line.

- [ ] **Step 7: Update `.env.example`**

Edit `.env.example`. Find the line `JWT_SECRET=healthflow-dev-secret-change-in-production`. Replace with:

```
# Required. Generate a long random string. Example:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
# The legacy value "healthflow-dev-secret-change-in-production" is REJECTED at startup.
JWT_SECRET=
```

The empty value forces the developer to set one — combined with the fail-loud, they can't accidentally run with no secret.

- [ ] **Step 8: Commit**

```bash
git add healthflow/auth/security.py healthflow/tests/auth/test_auth_hardening.py docker-compose.yml .env.example
git commit -m "security: JWT_SECRET fail-loud (no default, rejects legacy value)"
```

---

## Task 4: Password policy

**Files:**
- Create: `healthflow/auth/common_passwords.txt`
- Modify: `healthflow/auth/security.py`
- Modify: `healthflow/models/schemas.py`
- Test: `healthflow/tests/auth/test_auth_hardening.py`

- [ ] **Step 1: Create the common-passwords block-list**

Create `healthflow/auth/common_passwords.txt` with the following 30-entry seed list (this is a small bootstrap — the spec lists SecLists top-200 as the eventual content; a longer list can be dropped in later without code change). One password per line, all lowercase:

```
password
123456
12345678
qwerty
abc123
monkey
letmein
dragon
111111
baseball
iloveyou
trustno1
sunshine
master
welcome
shadow
ashley
football
jesus
michael
ninja
mustang
password1
password123
passw0rd
qwerty123
letmein123
admin
admin123
welcome123
```

- [ ] **Step 2: Write the failing tests**

Append to `healthflow/tests/auth/test_auth_hardening.py`:

```python
from healthflow.auth.security import validate_password


def test_validate_password_accepts_compliant_password():
    # 12+ chars, has letter, digit, non-alphanumeric, not in block-list.
    validate_password("Cromulent42!")


@pytest.mark.parametrize(
    "bad,reason_match",
    [
        ("Short1!", "12 characters"),               # too short
        ("Cromulent!!", "digit"),                   # no digit
        ("123456789012", "letter"),                 # no letter
        ("Cromulent4242", "non-alphanumeric"),      # no symbol
        ("Password123!", "too common"),             # not on list but well-known; see _COMMON below
    ],
)
def test_validate_password_rejects_bad(bad, reason_match):
    with pytest.raises(ValueError, match=reason_match):
        validate_password(bad)


def test_validate_password_rejects_listed_common_password():
    # Pad a known common password to satisfy the length check; the block-list
    # check should still reject it.
    with pytest.raises(ValueError, match="too common"):
        validate_password("password123!")  # "password123" is in the list
```

Note: the parameterized `"Password123!"` test will only pass if `"password123"` is in the block-list (lowercase). The list above includes it. If a different bad password is used in the parametrize, ensure it's on the list. The `_COMMON` reference is a comment, not real code.

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "validate_password"
```

Expected: ImportError — `validate_password` does not exist in `security`.

- [ ] **Step 4: Add `validate_password` + the common-passwords frozenset**

Edit `healthflow/auth/security.py`. Add these imports near the top (with the existing `import os`):

```python
from pathlib import Path
```

Add this near the bottom of the file (after the existing `decode_token` function):

```python
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
```

- [ ] **Step 5: Run the `validate_password` tests**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "validate_password"
```

Expected: 7 passed (the function test + 5 parametrized cases + the listed-common test). If `"password123!"` doesn't trip the common-list check (it should — `"password123"` is in the file, lowercased), inspect the file load and the lowercasing in the helper.

- [ ] **Step 6: Wire `validate_password` into `BrokerCreate`**

Edit `healthflow/models/schemas.py`. Find `BrokerCreate` (around line 330). Add a `field_validator` for `password`:

```python
class BrokerCreate(BaseModel):
    email: str = Field(..., description="Broker email address")
    password: str = Field(..., min_length=8, description="Password (min 12 chars, with letter+digit+symbol; not on block-list)")
    full_name: str = Field(..., description="Broker full name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        from healthflow.auth.security import validate_password
        validate_password(v)
        return v
```

The lazy import inside the validator avoids a circular import (`schemas` is imported very early; `security` imports `passlib` which is heavy). Pydantic surfaces `ValueError` as a 422 response with the message.

- [ ] **Step 7: Write the register-endpoint test**

Append to `healthflow/tests/auth/test_auth_hardening.py`:

```python
@pytest.mark.anyio
async def test_register_endpoint_rejects_weak_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "weak@healthflow.test",
            "password": "short",
            "full_name": "Weak Pass",
        },
    )
    assert response.status_code == 422
    body = response.json()
    # The Pydantic error message must surface the policy reason.
    assert "12 characters" in str(body)


@pytest.mark.anyio
async def test_register_endpoint_accepts_compliant_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "strong@healthflow.test",
            "password": "Cromulent42!",
            "full_name": "Strong Pass",
        },
    )
    assert response.status_code == 201
```

- [ ] **Step 8: Write the existing-broker regression test**

Append:

```python
@pytest.mark.anyio
async def test_existing_broker_with_old_weak_password_can_still_login(client, db_session):
    """Existing accounts whose passwords predate the new policy still log in.
    Only register (and future change-password) enforce the policy."""
    from healthflow.auth.security import hash_password
    from healthflow.database.models import Broker

    # Insert a broker with a password that wouldn't pass the new policy.
    broker = Broker(
        email="legacy@healthflow.test",
        hashed_password=hash_password("short1"),  # 6 chars, fails new policy
        full_name="Legacy User",
    )
    db_session.add(broker)
    await db_session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "legacy@healthflow.test", "password": "short1"},
    )
    assert response.status_code == 200, response.text
```

- [ ] **Step 9: Run all password-policy tests**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "password"
```

Expected: 9 passed (7 from steps 5 + 2 from step 7 + 1 from step 8 = ... wait, count). Specifically: 1 accept + 5 parametrized reject + 1 listed-common + 1 register-reject + 1 register-accept + 1 existing-broker-regression = 9 tests passing on `-k password`.

- [ ] **Step 10: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 534 passed (524 + 10 new — the parametrized `validate_password_rejects_bad` counts as 5 cases under the parametrize but 1 test). Adjust the expected count if pytest's parametrize counting differs in your environment; the principle is "baseline + the number of new test invocations."

- [ ] **Step 11: Commit**

```bash
git add healthflow/auth/security.py healthflow/auth/common_passwords.txt healthflow/models/schemas.py healthflow/tests/auth/test_auth_hardening.py
git commit -m "security: enforce upgraded password policy at register time"
```

---

## Task 5: Account lockout (5 failed attempts → 15-minute lock)

**Files:**
- Modify: `healthflow/database/models.py`
- Modify: `healthflow/auth/router.py`
- Test: `healthflow/tests/auth/test_auth_hardening.py`

- [ ] **Step 1: Add lockout columns to `Broker`**

Edit `healthflow/database/models.py`. Find the `Broker` class. After the `is_active` column (around line 53) and before `created_at`, add:

```python
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

No migration script needed for the test in-memory DB (fresh each run). The PR description will document the one-time `ALTER TABLE brokers ADD COLUMN ...` for any existing dev DB.

- [ ] **Step 2: Write the lockout tests**

Append to `healthflow/tests/auth/test_auth_hardening.py`:

```python
from datetime import datetime, timedelta, timezone

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker


async def _make_broker_with_known_password(db_session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("Cromulent42!"),
        full_name="Lockout Test",
    )
    db_session.add(broker)
    await db_session.commit()
    return broker


@pytest.mark.anyio
async def test_login_increments_counter_on_failed_attempt(client, db_session):
    await _make_broker_with_known_password(db_session, "lock1@healthflow.test")
    for _ in range(4):
        res = await client.post(
            "/auth/login",
            json={"email": "lock1@healthflow.test", "password": "wrong!"},
        )
        assert res.status_code == 401

    # 4 failures: account NOT yet locked, 5th attempt with correct password works.
    res = await client.post(
        "/auth/login",
        json={"email": "lock1@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200


@pytest.mark.anyio
async def test_five_failed_attempts_locks_account(client, db_session):
    await _make_broker_with_known_password(db_session, "lock2@healthflow.test")
    for _ in range(5):
        res = await client.post(
            "/auth/login",
            json={"email": "lock2@healthflow.test", "password": "wrong!"},
        )
        assert res.status_code == 401

    # 6th attempt with CORRECT password still 401 — locked.
    res = await client.post(
        "/auth/login",
        json={"email": "lock2@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 401
    # No mention of "lock" in the response — generic message only.
    assert "lock" not in res.text.lower()


@pytest.mark.anyio
async def test_successful_login_resets_lockout_state(client, db_session):
    broker = await _make_broker_with_known_password(db_session, "lock3@healthflow.test")
    # Force partial-failure state.
    broker.failed_login_count = 3
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "lock3@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200

    await db_session.refresh(broker)
    assert broker.failed_login_count == 0
    assert broker.locked_until is None


@pytest.mark.anyio
async def test_lock_auto_expires_after_15_minutes(client, db_session, monkeypatch):
    broker = await _make_broker_with_known_password(db_session, "lock4@healthflow.test")
    # Force a lock that "ended" 1 minute ago in real time.
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    broker.locked_until = past
    broker.failed_login_count = 5
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "lock4@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_lock_response_message_does_not_reveal_lock_state(client, db_session):
    """Locked account returns the SAME error body as wrong-password — no enumeration."""
    await _make_broker_with_known_password(db_session, "lock5@healthflow.test")
    # 5 failures to lock.
    for _ in range(5):
        await client.post(
            "/auth/login",
            json={"email": "lock5@healthflow.test", "password": "wrong!"},
        )

    # 6th attempt: locked.
    locked_res = await client.post(
        "/auth/login",
        json={"email": "lock5@healthflow.test", "password": "Cromulent42!"},
    )
    # Comparison: a totally wrong email gets the same shape.
    wrong_email_res = await client.post(
        "/auth/login",
        json={"email": "nobody@healthflow.test", "password": "wrong!"},
    )

    assert locked_res.status_code == 401
    assert wrong_email_res.status_code == 401
    assert locked_res.json() == wrong_email_res.json()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "lock"
```

Expected: most fail — `/login` doesn't track failed attempts yet.

- [ ] **Step 4: Modify `/auth/login` for lockout**

Edit `healthflow/auth/router.py`. Add this import near the top (with the other auth imports):

```python
from datetime import datetime, timedelta, timezone
```

Find the existing `login` function. Replace its body (lines 73–99 in the current file) with:

```python
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
    if broker.locked_until is not None and broker.locked_until > now:
        raise generic_error

    if not verify_password(login_data.password, broker.hashed_password):
        broker.failed_login_count += 1
        if broker.failed_login_count >= 5:
            broker.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise generic_error

    if not broker.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Success — reset lockout state.
    broker.failed_login_count = 0
    broker.locked_until = None

    access_token = create_access_token(
        {"sub": str(broker.id), "role": broker.role}
    )
    refresh_token = create_refresh_token({"sub": str(broker.id)})

    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )
```

Note the explicit `await db.commit()` calls — the lockout counter must persist across the request boundary even though `get_db` also commits at teardown. Committing inside the route ensures the counter survives even if a later step in the same request raises.

- [ ] **Step 5: Run the lockout tests**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "lock"
```

Expected: 5 passed.

- [ ] **Step 6: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 539 passed (534 + 5 new). If any existing auth-integration test fails because it makes 5+ login attempts (test data setup quirk), surface — the test likely needs its `failed_login_count` reset between cases.

- [ ] **Step 7: Commit**

```bash
git add healthflow/database/models.py healthflow/auth/router.py healthflow/tests/auth/test_auth_hardening.py
git commit -m "auth: account lockout after 5 failed attempts (15-minute auto-expire)"
```

---

## Task 6: Refresh-token rotation + `/logout`

**Files:**
- Modify: `healthflow/database/models.py`
- Modify: `healthflow/auth/security.py`
- Modify: `healthflow/auth/router.py`
- Test: `healthflow/tests/auth/test_auth_hardening.py`

This is the biggest task — a new model, a rewritten `create_refresh_token`, a rewritten `/refresh`, and a new `/logout`.

- [ ] **Step 1: Add the `RefreshToken` model**

Edit `healthflow/database/models.py`. Add at the end of the file (after `PhiAccessLog`):

```python
class RefreshToken(Base):
    """Per-token revocation state for refresh-token rotation.

    System table — same pattern as PhiAccessLog: not in TENANT_SCOPED_MODELS
    (no broker-ownership semantics; broker_id is "who issued," not "who owns"),
    not in _AUDITED_MODELS (refresh-token CRUD is operational metadata, not
    patient-data access). The theft-signal mass-revoke is logged via the
    WARN-level AuditLogger, not phi_access_log.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
```

`broker_id` is a plain indexed `GUID` (not a `ForeignKey`), matching `PhiAccessLog.broker_id`.

- [ ] **Step 2: Update `create_refresh_token` to persist a row + return jti**

Edit `healthflow/auth/security.py`. Find `create_refresh_token`. Its current signature is `create_refresh_token(data: dict) -> str`. The new behavior: the caller passes the session + broker id; the function persists a `RefreshToken` row, embeds its `id` as the JWT `jti` claim, and returns the JWT string. Replace the entire function with:

```python
import uuid as _uuid


async def create_refresh_token(
    db,  # AsyncSession; untyped to avoid circular imports
    broker_id: _uuid.UUID,
) -> str:
    """Create a refresh token. Persists a RefreshToken row and embeds its id as the JWT jti.

    The DB row is the authoritative revocation state; the JWT signature is the
    authentication mechanism. /auth/refresh looks the row up by jti, rejects
    if revoked, then revokes the row before issuing a new token.
    """
    from healthflow.database.models import RefreshToken

    row = RefreshToken(id=_uuid.uuid4(), broker_id=broker_id)
    db.add(row)
    await db.flush()  # need the row in the DB so the jti exists when the JWT is decoded

    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": str(broker_id),
        "exp": expire,
        "type": "refresh",
        "jti": str(row.id),
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

Note: the function is now async (it touches the DB) — every caller needs `await`.

- [ ] **Step 3: Update `/auth/login` to use the new `create_refresh_token`**

Edit `healthflow/auth/router.py`. In the `login` function (modified in Task 5), find the line `refresh_token = create_refresh_token({"sub": str(broker.id)})` and replace with:

```python
    refresh_token = await create_refresh_token(db, broker.id)
```

The `await db.commit()` that follows already persists the row (the `flush` inside `create_refresh_token` makes it visible; the commit makes it durable).

- [ ] **Step 4: Write the rotation tests**

Append to `healthflow/tests/auth/test_auth_hardening.py`:

```python
from healthflow.database.models import RefreshToken
from sqlalchemy import select


@pytest.mark.anyio
async def test_login_creates_unrevoked_refresh_token_row(client, db_session):
    await _make_broker_with_known_password(db_session, "rot1@healthflow.test")
    res = await client.post(
        "/auth/login",
        json={"email": "rot1@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200

    from healthflow.auth.tenant_context import system_context
    with system_context("test verify"):
        rows = (await db_session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None


@pytest.mark.anyio
async def test_refresh_rotates_token_and_revokes_old(client, db_session):
    await _make_broker_with_known_password(db_session, "rot2@healthflow.test")
    login_res = await client.post(
        "/auth/login",
        json={"email": "rot2@healthflow.test", "password": "Cromulent42!"},
    )
    old_refresh = login_res.json()["refresh_token"]

    refresh_res = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh_res.status_code == 200
    new_refresh = refresh_res.json()["refresh_token"]
    assert new_refresh != old_refresh

    from healthflow.auth.tenant_context import system_context
    with system_context("test verify"):
        rows = (await db_session.execute(
            select(RefreshToken).order_by(RefreshToken.created_at)
        )).scalars().all()
    assert len(rows) == 2
    assert rows[0].revoked_at is not None  # old token revoked
    assert rows[1].revoked_at is None      # new token active


@pytest.mark.anyio
async def test_replaying_revoked_token_returns_401(client, db_session):
    await _make_broker_with_known_password(db_session, "rot3@healthflow.test")
    login_res = await client.post(
        "/auth/login",
        json={"email": "rot3@healthflow.test", "password": "Cromulent42!"},
    )
    old_refresh = login_res.json()["refresh_token"]

    # First refresh succeeds (and revokes old_refresh).
    await client.post("/auth/refresh", json={"refresh_token": old_refresh})

    # Replay the now-revoked token.
    replay_res = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_res.status_code == 401


@pytest.mark.anyio
async def test_replaying_revoked_token_revokes_all_brokers_tokens(client, db_session):
    """Theft signal: a replayed revoked token revokes ALL of that broker's active tokens."""
    broker = await _make_broker_with_known_password(db_session, "rot4@healthflow.test")
    login_res = await client.post(
        "/auth/login",
        json={"email": "rot4@healthflow.test", "password": "Cromulent42!"},
    )
    old_refresh = login_res.json()["refresh_token"]

    # First refresh creates a new (active) token while revoking the old one.
    new_res = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    new_refresh = new_res.json()["refresh_token"]

    # At this point: old=revoked, new=active.
    # Replay the OLD token — theft signal — should mass-revoke.
    replay_res = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_res.status_code == 401

    # Now even the new (previously-active) token should fail.
    after_theft = await client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert after_theft.status_code == 401

    # All RefreshToken rows for this broker should now be revoked.
    from healthflow.auth.tenant_context import system_context
    with system_context("test verify"):
        rows = (await db_session.execute(
            select(RefreshToken).where(RefreshToken.broker_id == broker.id)
        )).scalars().all()
    assert all(r.revoked_at is not None for r in rows)


@pytest.mark.anyio
async def test_logout_revokes_presented_refresh_token(client, db_session):
    await _make_broker_with_known_password(db_session, "rot5@healthflow.test")
    login_res = await client.post(
        "/auth/login",
        json={"email": "rot5@healthflow.test", "password": "Cromulent42!"},
    )
    refresh = login_res.json()["refresh_token"]

    logout_res = await client.post("/auth/logout", json={"refresh_token": refresh})
    assert logout_res.status_code == 204

    # Subsequent /refresh with the revoked token fails.
    refresh_res = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert refresh_res.status_code == 401


@pytest.mark.anyio
async def test_expired_refresh_token_does_not_trigger_theft_signal(client, db_session):
    """A normally-expired refresh token returns 401 without mass-revoke.

    Constructs a refresh JWT with exp in the past — decoded JWT will fail the
    expiry check, so the token never reaches the theft-signal codepath.
    """
    from healthflow.auth.security import JWT_SECRET, JWT_ALGORITHM, create_refresh_token
    from jose import jwt as _jwt
    import uuid as _uuid

    broker = await _make_broker_with_known_password(db_session, "rot6@healthflow.test")

    # Create one legitimate (active) refresh token via the normal flow.
    legit_refresh = await create_refresh_token(db_session, broker.id)
    await db_session.commit()

    # Hand-craft an expired token with a different jti.
    expired = _jwt.encode(
        {
            "sub": str(broker.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "refresh",
            "jti": str(_uuid.uuid4()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    expired_res = await client.post("/auth/refresh", json={"refresh_token": expired})
    assert expired_res.status_code == 401

    # The legitimate token should STILL work — theft signal didn't fire.
    legit_res = await client.post("/auth/refresh", json={"refresh_token": legit_refresh})
    assert legit_res.status_code == 200, legit_res.text
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "rotate or revoke or logout or expired or unrevoked"
```

Expected: most fail — `/refresh` doesn't rotate or revoke yet, `/logout` doesn't exist.

- [ ] **Step 6: Rewrite `/auth/refresh`**

Edit `healthflow/auth/router.py`. Replace the entire current `refresh` function body with:

```python
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
    except (ValueError, Exception):
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
```

- [ ] **Step 7: Add `/auth/logout`**

Edit `healthflow/auth/router.py`. Append this endpoint after `/refresh`:

```python
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
    except (ValueError, Exception):
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
```

- [ ] **Step 8: Run the rotation tests**

```bash
.venv/bin/python -m pytest healthflow/tests/auth/test_auth_hardening.py -v -k "rotate or revoke or logout or expired or unrevoked"
```

Expected: 6 passed.

- [ ] **Step 9: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 545 passed (539 + 6 new). If the existing `test_auth.py` / `test_auth_integration.py` tests for `/refresh` fail because the response shape now includes a `refresh_token` key they didn't expect, update those assertions — the response shape is intentionally augmented.

- [ ] **Step 10: Commit**

```bash
git add healthflow/database/models.py healthflow/auth/security.py healthflow/auth/router.py healthflow/tests/auth/test_auth_hardening.py
git commit -m "auth: refresh-token rotation + theft signal + /logout"
```

---

## Task 7: Update the `healthflow-security` skill

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Read the current skill**

```bash
cat .claude/skills/healthflow-security/SKILL.md
```

It has YAML frontmatter, then sections including "JWT_SECRET default is unsafe" (which is now OUT OF DATE — the JWT_SECRET no longer has a default), plus other auth-adjacent rules. Don't touch the frontmatter.

- [ ] **Step 2: Replace the "JWT_SECRET default is unsafe" section**

Edit `.claude/skills/healthflow-security/SKILL.md`. Find the "## JWT_SECRET default is unsafe" section. Replace it with a new section that documents the four new enforced rules:

```markdown
## Auth hardening rules (enforced)

**Rule:** `JWT_SECRET` is read fail-loud in `healthflow/auth/security.py`.
A missing env var OR the legacy value `"healthflow-dev-secret-change-in-production"`
raises `RuntimeError` at module import. There is no default. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"` and set it in
your `.env` or deploy environment.

**Rule:** New broker registration goes through `validate_password` (in
`healthflow/auth/security.py`): ≥12 chars, letter + digit + non-alphanumeric,
not in the bundled common-passwords block-list (`common_passwords.txt`).
Existing accounts with weaker passwords keep working — only registration
(and the future change-password endpoint) enforces the policy.

**Rule:** `/auth/login` enforces an account lockout — 5 failed attempts in
a row → 15-minute timed lock on the `brokers` row (`failed_login_count`
and `locked_until` columns). Lock auto-expires; successful login resets
both columns. The response body for a locked account is identical to the
wrong-password response — never leak lock state to the client (brute-force
aid).

**Rule:** Refresh tokens rotate on every `/auth/refresh` and persist their
revocation state in the `refresh_tokens` table. Replaying a revoked
refresh token is treated as theft — ALL of that broker's active refresh
tokens get revoked and a WARN-level `refresh_token_replay_revoke_all`
audit event is emitted via `AuditLogger`. `/auth/logout` revokes the
presented refresh token (access tokens expire naturally within 60 minutes).
`refresh_tokens` is a system table — NOT in `TENANT_SCOPED_MODELS` and
NOT in `_AUDITED_MODELS` (per-token CRUD would just create audit noise;
the one notable event goes through `AuditLogger`).
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

Expected: 545 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "skill: healthflow-security — document the four auth hardening rules"
```

---

## Task 8: Final verification + push + PR

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: `545 passed`.

- [ ] **Step 2: Run `make check`**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; lint count not worse than baseline. If this branch introduced a new lint error, fix it before pushing.

- [ ] **Step 3: Hand-verify the JWT_SECRET fail-loud end-to-end**

```bash
.venv/bin/python -c "
import os
os.environ.pop('JWT_SECRET', None)
try:
    import importlib
    import healthflow.auth.security as s
    importlib.reload(s)
    print('FAIL: import did not raise')
except RuntimeError as e:
    print(f'OK: {e}')
"
```

Expected: `OK: JWT_SECRET environment variable is required. ...`. Then restore the env var for whatever you do next: `export JWT_SECRET=test-secret-not-for-production`.

- [ ] **Step 4: Hand-verify the full lockout + rotation flow against a real session**

```bash
JWT_SECRET=test-secret-not-for-production .venv/bin/python -c "
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from healthflow.auth.security import hash_password, create_access_token, create_refresh_token, decode_token
from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Base, Broker, RefreshToken

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///', echo=False)
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with f() as s:
        b = Broker(email='hv@t.test', hashed_password=hash_password('x'), full_name='HV')
        s.add(b); await s.flush()
        tok = await create_refresh_token(s, b.id)
        await s.commit()
        payload = decode_token(tok)
        assert payload.get('jti') is not None, 'jti claim missing'
        with system_context('verify'):
            rows = (await s.execute(select(RefreshToken))).scalars().all()
        assert len(rows) == 1 and rows[0].revoked_at is None
        print('JWT_SECRET + refresh-token row + jti claim: OK')
    await engine.dispose()

asyncio.run(main())
"
```

Expected: `JWT_SECRET + refresh-token row + jti claim: OK`.

- [ ] **Step 5: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 7 commits (Tasks 1 and 8 don't commit):
- `skill: healthflow-security — document the four auth hardening rules`
- `auth: refresh-token rotation + theft signal + /logout`
- `auth: account lockout after 5 failed attempts (15-minute auto-expire)`
- `security: enforce upgraded password policy at register time`
- `security: JWT_SECRET fail-loud (no default, rejects legacy value)`
- `tests: set JWT_SECRET at conftest import time (prep for fail-loud)`

Each message terse, no `Co-Authored-By` trailer.

- [ ] **Step 6: Push the branch**

```bash
git push -u origin auth-hardening/foundation 2>&1 | tail -5
```

- [ ] **Step 7: Open the PR**

```bash
gh pr create --title "Auth hardening: JWT_SECRET fail-loud, password policy, lockout, refresh rotation" --body "$(cat <<'EOF'
## Summary

Closes four long-standing auth weaknesses flagged by the `healthflow-security` skill — sub-project #4 of the HIPAA-readiness foundation.

1. **`JWT_SECRET` fail-loud** — `healthflow/auth/security.py` raises `RuntimeError` at module import if `JWT_SECRET` is unset or set to the legacy `"healthflow-dev-secret-change-in-production"`. `docker-compose.yml` uses `${JWT_SECRET:?...}` to fail the container if unset. `.env.example` documents how to generate one.
2. **Password policy** — new `validate_password()` enforces ≥12 chars, letter + digit + non-alphanumeric, not in a bundled `common_passwords.txt`. Wired into `BrokerCreate` via a Pydantic validator. Existing accounts with weaker passwords keep working.
3. **Account lockout** — `Broker.failed_login_count` + `locked_until` columns. 5 failed `/auth/login` attempts → 15-minute timed lock. Auto-expires; successful login resets both. Lock state never leaks to the client (generic 401 identical to wrong-password).
4. **Refresh-token rotation + `/logout`** — new `refresh_tokens` system table with per-token revocation. `/auth/refresh` revokes the presented token and issues a new one. Replaying a revoked token triggers a theft signal — mass-revoke of all that broker's active refresh tokens, plus a WARN-level `refresh_token_replay_revoke_all` audit event. New `/auth/logout` revokes the presented refresh token.

Spec: [docs/superpowers/specs/2026-05-16-auth-hardening-design.md](./docs/superpowers/specs/2026-05-16-auth-hardening-design.md)
Plan: [docs/superpowers/plans/2026-05-16-auth-hardening.md](./docs/superpowers/plans/2026-05-16-auth-hardening.md)

## ⚠ One-time deploy note: existing databases need column additions

The project uses `Base.metadata.create_all` (no alembic). It creates the new `refresh_tokens` table automatically on next startup, but it does NOT add the two new `brokers` columns to an existing DB. For any existing `healthflow.db`, run once:

```bash
python -c "import sqlite3; c = sqlite3.connect('healthflow.db'); c.execute('ALTER TABLE brokers ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0'); c.execute('ALTER TABLE brokers ADD COLUMN locked_until DATETIME'); c.commit()"
```

Without this, `/auth/login` will fail with `no such column: brokers.failed_login_count`. Test/CI environments use in-memory SQLite recreated per run — no manual step needed there.

## Test Plan

- [x] 24 new tests in `healthflow/tests/auth/test_auth_hardening.py`: JWT_SECRET fail-loud (3), password policy (10), lockout (5), refresh rotation + theft + logout + expired (6)
- [x] Full backend suite: 545/545 (was 521; +24)
- [x] End-to-end hand-verification: `JWT_SECRET` unset crashes import; refresh token persists a `refresh_tokens` row with `jti` claim matching the row id
- [ ] CI green on this PR (requires `JWT_SECRET` to be set in CI env)

## Out of scope / follow-ups

- MFA (TOTP) — its own future sub-project; needs a frontend flow.
- `/auth/change-password`, `/auth/forgot-password` (email reset), email provider selection — the next "account management" sub-project (also covers admin force-unlock).
- Per-IP rate limiting on auth endpoints — pairs with anomaly detection.
- Alembic migrations — one-off ALTER TABLE noted above.
- Encryption at rest (sub-project #5).
EOF
)" 2>&1 | tail -3
```

Expected: a GitHub PR URL. Capture and report it.

No new commit for this task.
