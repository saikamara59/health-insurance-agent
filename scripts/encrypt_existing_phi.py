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
from sqlalchemy.orm.attributes import flag_modified

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
                    # flag_modified explicitly marks each encrypted field dirty so
                    # the next flush triggers process_bind_param → encrypt.
                    # This is more reliable than the setattr no-op trick when
                    # SQLAlchemy is smart enough to skip unchanged assignments.
                    for field in fields:
                        flag_modified(row, field)
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
