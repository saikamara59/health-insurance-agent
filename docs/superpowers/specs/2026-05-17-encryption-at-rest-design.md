# Encryption at Rest (Application-Level Field Encryption)

**Date:** 2026-05-17
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation (sub-project #5 of 5)

## Problem

PHI in `healthflow.db` is currently stored in plaintext. Anyone with read access to the SQLite file — a stolen laptop, a backup pulled from cloud storage, a database administrator at a future hosting provider, an attacker who escalates from any other vulnerability into filesystem access — gets every patient's name, doctors, prescriptions, and procedures.

For a portfolio-grade HIPAA-readiness story, the system needs to demonstrate that PHI is encrypted **independent of the disk it lives on**, not just relying on disk-level encryption at the hosting layer. The threat model is *defense in depth*: even if the running app, the encryption library, the tenant filter, the PHI access audit log, and the redaction layer all fail simultaneously, a separate file-level breach should not yield plaintext PHI.

This sub-project closes that gap with application-level field encryption on the highest-sensitivity columns.

## Goal

Patient identifiers and medical content in `healthflow.db` are stored as AES-256-GCM ciphertext at rest. Specifically:

- The encryption key loads fail-loud from `PHI_ENCRYPTION_KEY` at module-import time (same pattern as `JWT_SECRET` from sub-project #4).
- Eight columns across `Client`, `ActionHistory`, and `Feedback` use new `EncryptedString` and `EncryptedJSON` SQLAlchemy `TypeDecorator`s that transparently encrypt on write and decrypt on read.
- The on-wire format is `v1:<base64-nonce>:<base64-ciphertext+tag>` — a key version prefix makes future rotation additive (no destructive re-encryption sweep required).
- An opt-in `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` toggle allows reading legacy plaintext rows during a migration window; off in production, on briefly during a one-time `scripts/encrypt_existing_phi.py` run.
- Cross-sub-project interactions (tenant filter, PHI audit log, prompt-input redaction) keep working unchanged — application code never sees ciphertext.

## Threat model (settled during brainstorming)

- **In scope:** Stolen disk / DB file. DBA-level read access to the SQLite file. An attacker with filesystem but not memory access. Backups pulled from cloud storage.
- **Out of scope:** A running app with the key in memory (an attacker at that level already has plaintext). A compromised admin who can read both the DB and the env var (the key is required to decrypt — defending against this requires a key-management service like AWS KMS, deliberately deferred).
- **Decision:** Application-level field encryption, not full-disk / SQLCipher. SQLCipher only defends "the DB file itself"; application-level encryption defends individual columns *even against a DBA with full SQLite access*. Stronger portfolio claim, shows engineering depth, fits a typed `TypeDecorator` pattern already in the codebase (`GUID`).

## Field selection (settled)

| Model | Column | Decision | Rationale |
|---|---|---|---|
| `Client` | `full_name` | **Encrypt** (`EncryptedString(2000)`) | Direct identifier — top-priority PHI |
| `Client` | `doctors` | **Encrypt** (`EncryptedJSON`) | Care-team detail; medical-sensitive |
| `Client` | `prescriptions` | **Encrypt** (`EncryptedJSON`) | Medication list reveals conditions |
| `Client` | `procedures` | **Encrypt** (`EncryptedJSON`) | Medical history |
| `Client` | `zip_code` | Plaintext | Queried by value for plan matching; not directly identifying alone |
| `Client` | `age`, `income_level` | Plaintext | Quasi-identifiers; queried for filtering; not directly identifying |
| `Client` | UUIDs, timestamps | Plaintext | Not PHI |
| `ActionHistory` | `request_data` | **Encrypt** (`EncryptedJSON`) | Holds patient context shipped to agents |
| `ActionHistory` | `response_summary` | **Encrypt** (`EncryptedJSON`) | May reflect patient details in summary |
| `Feedback` | `comment` | **Encrypt** (`EncryptedString(4000)`) | Free-text broker notes; may mention patients |
| All system tables (`phi_access_log`, `refresh_tokens`, plan/drug/ZIP tables) | Plaintext | Not patient data |

**What you lose by encrypting these:** queries of the form `WHERE full_name = 'X'` no longer work — AES-GCM uses a random nonce, so the same plaintext produces different ciphertext each time. The codebase has zero such queries on the encrypted columns today; if one ever becomes necessary, the right addition is a blind index (HMAC of the value, stored in a sibling column). Explicitly out of scope.

## Non-Goals

- **No `WHERE encrypted_column = value` queries.** Blind-index columns for searchable encryption are a follow-up sub-project if a search-by-PHI flow ever ships.
- **No key-management service (KMS) integration.** `PHI_ENCRYPTION_KEY` is an env var. The plan documents how production deployments would inject a KMS-derived key (single env-var swap), but no KMS abstraction layer is built.
- **No automated key rotation.** The versioned-key format (`v1:`, `v2:`) makes rotation possible without an outage; a re-encryption sweep script is a future addition.
- **No encryption of plan/drug/ZIP/PromptVariant/audit tables.** Public reference data, system tables, and operational metadata stay plaintext.
- **No defense against an attacker who has both the DB and the running app's env var.** That requires KMS — deferred.
- **No alembic migrations.** Project still uses `Base.metadata.create_all`. The migration script handles the data side; the schema side relies on `create_all` creating new tables fresh and SQLite's permissive column types tolerating the underlying `JSON` → `String` shape change.
- **No deletion of plaintext data during the migration.** The migration script encrypts in place via the ORM, which writes ciphertext over the prior plaintext value — but the security claim is about *new state*, not "no plaintext ever existed on this disk." Documented in the PR.

## Design

### Architecture

A new `phi_crypto.py` module owns the AES-256-GCM math and key loading. A new `encrypted_types.py` module wraps the math in SQLAlchemy `TypeDecorator`s so the rest of the app never sees ciphertext. `models.py` swaps the column types on the eight encrypted fields. The application code (routes, agents, audit log, tenant filter) is untouched — the encryption is fully transparent above the persistence layer.

```
write path: app -> SQLAlchemy -> EncryptedString.process_bind_param -> phi_crypto.encrypt -> ciphertext -> SQLite
read path:  SQLite -> ciphertext -> EncryptedString.process_result_value -> phi_crypto.decrypt -> app
```

### `healthflow/auth/phi_crypto.py`

New module. Public surface:

```
_load_phi_keys() -> dict[str, bytes]    # at module import, fail-loud
_KEYS: dict[str, bytes]                 # {"v1": key1_bytes, "v2": ...}
_CURRENT_VERSION: str                   # the highest vN that exists in _KEYS

encrypt(plaintext: str) -> str          # uses _CURRENT_VERSION; returns "vN:nonce:ct"
decrypt(token: str) -> str              # parses "vN:" prefix, dispatches to the right key
class PhiDecryptionError(Exception): ...
```

**Key loading.** `_load_phi_keys()` reads `PHI_ENCRYPTION_KEY` (required) and any `PHI_ENCRYPTION_KEY_V2`, `_V3`, etc. (optional). Each is a base64-encoded 32-byte key (`python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`). Fail-loud at module import if `PHI_ENCRYPTION_KEY` is unset, or if it equals a known-bad placeholder string. Returns a dict like `{"v1": <bytes>, "v2": <bytes>}`. `_CURRENT_VERSION` is the lexically-greatest key in the dict.

**Wire format.** `<version>:<base64-nonce>:<base64-ciphertext+tag>`. Three colon-separated parts. The 12-byte nonce is randomly generated per encryption (AES-GCM's nonce-uniqueness requirement; nonce reuse with the same key destroys the security). The ciphertext includes the 16-byte GCM authentication tag — tampering with ciphertext makes decryption raise.

**`decrypt` dispatch.** Split on `:`, take the first part as the version, look up the key, decrypt with that key. An unknown version raises `PhiDecryptionError`. A missing or malformed token raises `PhiDecryptionError`. A tampered ciphertext (failed tag verification) raises `PhiDecryptionError`.

**Dependencies.** Adds `cryptography>=42` to `requirements.txt` — currently not present. `python-jose` (the JWT library) uses its own backend; `cryptography` is the standard library for AES-GCM.

### `healthflow/database/encrypted_types.py`

New module. Two `TypeDecorator`s following the existing `GUID` pattern in `models.py`:

```
class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return phi_crypto.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _decrypt_or_passthrough(value)


class EncryptedJSON(TypeDecorator):
    impl = String   # NOTE: not JSON — ciphertext is opaque text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return phi_crypto.encrypt(json.dumps(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(_decrypt_or_passthrough(value))
```

**`_decrypt_or_passthrough` and the migration toggle.** A module-private helper:

```
def _decrypt_or_passthrough(value: str) -> str:
    if value.startswith("v") and ":" in value[:6]:
        return phi_crypto.decrypt(value)  # raises PhiDecryptionError on failure
    if os.getenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ") == "1":
        logger.warning("encrypted_types: returning plaintext value during migration window")
        return value
    raise PhiDecryptionError(
        "Encrypted column contains plaintext. Run scripts/encrypt_existing_phi.py "
        "or set PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1 during a migration window."
    )
```

The plaintext-detection heuristic (`startswith("v") and ":" in value[:6]`) is approximate — it accepts any `vN:...` shape. A plaintext value that happens to start with `v` and contain `:` within 6 chars (e.g. `v1: yes`) would be misclassified as ciphertext and fail to decrypt — surfaced as `PhiDecryptionError`. Acceptable: real PHI shouldn't have this shape, and `PhiDecryptionError` is a loud failure, not silent data corruption.

### `models.py` changes

Eight column type swaps. The `Mapped[...]` Python type annotations stay (transparent round-trip). The argument to `mapped_column` changes:

| Before | After |
|---|---|
| `String(255)` on `Client.full_name` | `EncryptedString(2000)` |
| `JSON` on `Client.doctors`, `prescriptions`, `procedures` | `EncryptedJSON()` |
| `JSON` on `ActionHistory.request_data`, `response_summary` | `EncryptedJSON()` |
| `String(2000)` on `Feedback.comment` | `EncryptedString(4000)` |

Size doubling on String columns accounts for AES-GCM overhead (12-byte nonce + 16-byte tag + base64 encoding + `v1:` prefix ≈ 1.5×–2× plaintext length).

**SQLite specifics:** SQLite has no real type enforcement — `String` and `JSON` both store as `TEXT`. The shape change `JSON → String` (under the hood, since `EncryptedJSON.impl = String`) is a no-op on disk. A future Postgres migration would need an `ALTER COLUMN ... TYPE text` for the `EncryptedJSON` columns. Out of scope here.

### Interaction with other sub-projects

- **Tenant filter** (sub-project #2): only operates on `broker_id`, which stays plaintext. No interaction.
- **PHI access audit log** (sub-project #3): the `phi_access_log.row_ids` field captures UUIDs from query results, which are plaintext. The audit listener observes results via `Result.freeze()` — the results are already decrypted by the TypeDecorator at that point. No interaction.
- **PHI redaction in prompts** (sub-project #1): redacts at the prompt-building boundary, operating on Python strings. The ORM has already decrypted by the time strings reach the redactor. No interaction.
- **Auth hardening** (sub-project #4): no overlap; auth tables stay plaintext.

The fact that this works cleanly — five sub-projects layered without breaking each other — is itself a credibility marker. The plan calls out one explicit cross-test: assert the audit log captures correct `row_ids` for an encrypted Client query.

### Migration

Existing rows in `healthflow.db` contain plaintext in columns about to become ciphertext-only. Two paths handle this:

**Path A — `scripts/encrypt_existing_phi.py` (the proper path).** Run once during deploy. Pseudocode:

```
with async_session_factory() as session:
    with system_context("encrypt-existing-phi migration"):
        for model in (Client, ActionHistory, Feedback):
            offset = 0
            while True:
                rows = await session.execute(select(model).offset(offset).limit(100))
                rows = list(rows.scalars().all())
                if not rows: break
                # The ORM has already decrypted on read; setting fields to their
                # current value triggers TypeDecorator.process_bind_param on the
                # next flush, which encrypts the value on the way back to disk.
                for row in rows:
                    for col in _ENCRYPTED_COLUMNS[type(row)]:
                        setattr(row, col, getattr(row, col))
                await session.commit()
                offset += 100
```

Critical: the script must run with `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1` set, because on first run the rows contain plaintext that the TypeDecorator wouldn't otherwise be able to read.

**Path B — `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1` toggle.** Lets the app run during a migration window when some rows are plaintext and some are encrypted. Off in production. Documented as a temporary deploy aid.

**Operational sequence for production deploy:**

1. Set `PHI_ENCRYPTION_KEY` in the deploy environment.
2. Set `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1`.
3. Run `python scripts/encrypt_existing_phi.py`.
4. Verify a smoke read of an encrypted field returns sensible data.
5. Unset `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ`.
6. Restart the app — now in strict mode.

The PR description spells this out as a checklist.

### Test plan

One new file `healthflow/tests/auth/test_phi_crypto.py` plus additions to a model test file. 19 new test invocations total.

**1. `phi_crypto.py` unit tests (8)**
- `_load_phi_keys` raises if `PHI_ENCRYPTION_KEY` unset (use `importlib.reload` like JWT_SECRET tests).
- `_load_phi_keys` rejects a known-bad placeholder.
- `_load_phi_keys` returns `{"v1": bytes}` for a valid key; current version is `"v1"`.
- With v1 and v2 both set, current version is `"v2"`.
- `encrypt(s)` returns `"v1:base64:base64"` shape.
- `decrypt(encrypt(s)) == s` for ascii, unicode, and a 4000-char string (parameterized).
- `decrypt` raises `PhiDecryptionError` on garbage input.
- **Cross-version roundtrip:** encrypt under v1 (with v1 active), switch to v2 active, decrypt the v1 token still works.

**2. `encrypted_types.py` unit tests (3)**
- `EncryptedString` roundtrips through an in-memory SQLite session with a real `mapped_column(EncryptedString(...))` definition.
- `EncryptedJSON` roundtrips a `list[dict]` (the prescriptions/doctors shape).
- Reading the raw column value via `text("SELECT full_name FROM ...")` returns a ciphertext-shaped string starting with `v1:` (proves it's encrypted on disk, not just round-tripped in Python).

**3. Model + cross-sub-project integration (4)**
- Create + read a `Client` returns the same Python values for all encrypted + plaintext fields.
- Tenant filter still scopes by `broker_id` (plaintext) when reading an encrypted `Client`.
- PHI audit log's `row_ids` capture still works on a query against encrypted `Client` (UUIDs are plaintext; the listener observes decrypted results).
- A failed decrypt (tampered ciphertext) raises `PhiDecryptionError` to the route, which surfaces as a 500 — proves we fail loud on corruption, not silently return garbage.

**4. Plaintext-passthrough toggle (3)**
- `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ=1`: a legacy plaintext value reads back as plaintext (with WARN log).
- Without the toggle: same scenario raises `PhiDecryptionError`.
- Round-tripped (encrypt + decrypt) values work regardless of the toggle.

**5. Migration script test (1)**
- Seed a fresh DB with plaintext rows via `text()` INSERTs (bypassing the TypeDecorator). Run `scripts/encrypt_existing_phi.py` (with the toggle on). Verify the rows now contain ciphertext when read raw via `text("SELECT ...")`, and plaintext when read via the ORM with the toggle off.

### Rollout (per-task, each commit green)

1. **Branch + baseline.** Capture pre-impl test count (545), confirm green.
2. **Test conftest sets `PHI_ENCRYPTION_KEY`.** Same pattern as JWT_SECRET conftest fix. No-op today; primes for fail-loud.
3. **`phi_crypto.py` + 8 unit tests.** Add `cryptography>=42` to `requirements.txt`.
4. **`encrypted_types.py` + 3 unit tests** (without the plaintext-passthrough yet; strict mode only).
5. **Migrate `Client.full_name` only + cross-sub-project tests.** Smallest-blast-radius first column.
6. **Migrate `Client.doctors`, `prescriptions`, `procedures` (`EncryptedJSON`).** Now exercises the JSON path.
7. **Migrate `ActionHistory.request_data` + `response_summary`.**
8. **Migrate `Feedback.comment`.** All 8 columns now encrypted.
9. **`PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` toggle + 3 tests.** The dev escape hatch.
10. **`scripts/encrypt_existing_phi.py` + 1 test.** The one-time migration script.
11. **Update `healthflow-security` skill** with the encryption rules.
12. **Final verification + push + PR.**

### Risks

| Risk | Mitigation |
|---|---|
| Migration script fails partway; some rows encrypted, some plaintext | Script processes rows in chunks with explicit commit per chunk. Re-running is safe (plaintext re-encrypts, ciphertext round-trips). The plaintext-passthrough toggle lets the app run while migration completes. |
| `PHI_ENCRYPTION_KEY` forgotten in prod | Fail-loud at module import, same pattern as `JWT_SECRET`. Deploy crashes immediately. PR description includes the deploy checklist. |
| Key version `v1` env var deleted while v1 rows still exist | Documented hard rule in the updated skill: never delete a key version while any row exists encrypted under it. Practical rotation sequence: add `v2`, sweep `v1` rows, then drop `v1`. (Sweep script not built today; out of scope.) |
| Column-size assumptions wrong, causes truncation | All `EncryptedString` columns sized at 2× the old max. Roundtrip test uses a 4000-char string. SQLite enforces no length anyway, so size is documentary; Postgres migration would honor the new sizes. |
| `EncryptedJSON.impl = String` breaks reads on existing rows that have `JSON` storage | SQLite stores both as TEXT — no on-disk change. Postgres migration would need `ALTER COLUMN ... TYPE text`. Out of scope. |
| Tests mock encryption and miss real bugs | No mocking. The TypeDecorator tests use a real in-memory SQLite session, a real generated key, a real round-trip. The `phi_crypto` unit tests use real `cryptography.AESGCM`. The migration script test seeds plaintext via raw `text()` and runs the real script. |
| First-request-after-deploy crashes (migration not run) | Strict mode: `PhiDecryptionError` is a loud 500. Operations spot it in the first 30 seconds, set the toggle, run the migration, unset the toggle. Documented in the deploy checklist. |
| Plaintext-detection heuristic in `_decrypt_or_passthrough` misclassifies real PHI starting with `vN:` | Acceptable: the misclassification surfaces as `PhiDecryptionError` (loud), not silent data corruption. Real PHI doesn't have this shape (names, doctor lists, etc.). |
| The `cryptography` library is a new dep | It's the standard Python AES library, maintained by the PyCA group, used by `python-jose`'s alternate backend already. Stable, audited, well-supported. Added to `requirements.txt` with `>=42` (version current as of 2026). |

## Acceptance

This sub-project is done when:

1. `PHI_ENCRYPTION_KEY` is read fail-loud (no default, no legacy placeholder); a misconfigured deploy raises at import.
2. Eight columns (`Client.full_name`, `Client.doctors`, `Client.prescriptions`, `Client.procedures`, `ActionHistory.request_data`, `ActionHistory.response_summary`, `Feedback.comment`) are encrypted at rest. Raw `SELECT` returns ciphertext; ORM reads return plaintext.
3. The `v1:nonce:ciphertext` format is in use and `decrypt` correctly dispatches on the `vN:` prefix.
4. `scripts/encrypt_existing_phi.py` encrypts existing plaintext rows in place. The `PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ` toggle gates the migration window.
5. Tenant filter, PHI audit log, and prompt-input redaction continue to work unchanged on encrypted-column queries.
6. The full test suite (existing + 19 new) is green.
7. The `healthflow-security` skill documents the encryption rules, the deploy checklist, and the never-delete-a-key-version rule.

## Out of Scope

- KMS / external key-management integration.
- Automated key rotation sweep.
- Blind-index columns for searchable encryption (`WHERE full_name = X`).
- Encryption of plan/drug/ZIP/audit/refresh-token tables (not patient data).
- Alembic migrations for `EncryptedJSON` column-type change (Postgres migration concern).
- Full-disk encryption / SQLCipher (different threat model; deferred or never).
- Deletion of plaintext data physically (file shredding etc.); the migration encrypts in place but doesn't guarantee old plaintext is unrecoverable from disk sectors.
- Defense against an attacker who has both the DB and the running app's environment.
- Account management sub-project (admin RBAC, forgot-password, change-password) — separate.
