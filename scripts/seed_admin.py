"""Bootstrap the demo admin account.

Registers admin@healthflow.com via /auth/register (always defaults role=broker
and is_active=False), then:
  1. activates the demo broker (demo@healthflow.com) so the pre-seeded
     account is immediately usable without admin approval
  2. activates + promotes the admin (admin@healthflow.com) to role=admin

Idempotent: re-running on a deploy that already has the account is a no-op
(promotion of an already-admin row is a write but not a state change; same
for activation of an already-active row).
"""
import asyncio
import os
import sys

import httpx
from sqlalchemy import update as sa_update

from healthflow.auth.tenant_context import system_context
from healthflow.database.config import async_session_factory
from healthflow.database.models import Broker
from scripts.promote_admin import _promote

ADMIN = {
    "email": "admin@healthflow.com",
    "password": "Healthflow123!",
    "full_name": "HealthFlow Admin",
}
BASE_URL = os.getenv("HEALTHFLOW_BASE_URL", "http://localhost:8000")


async def _activate(emails: list[str]) -> None:
    """Flip is_active=True for each seeded broker so they don't need admin
    approval to log in. Uses system_context to bypass tenant scoping; the
    SET targets the brokers table which isn't tenant-scoped anyway, but
    consistent with other admin DB writes from operator scripts."""
    async with async_session_factory() as session:
        with system_context("seed: activate seeded brokers"):
            for email in emails:
                await session.execute(
                    sa_update(Broker).where(Broker.email == email).values(is_active=True)
                )
            await session.commit()


def main() -> None:
    resp = httpx.post(f"{BASE_URL}/auth/register", json=ADMIN)
    if resp.status_code == 201:
        print(f"  admin registered: {ADMIN['email']}")
    elif resp.status_code == 409:
        print(f"  admin already exists: {ADMIN['email']}")
    else:
        print(f"  registration failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    # Activate both the admin we just registered and the demo broker that
    # seed.py registered earlier in demo_entrypoint.sh. Production
    # /auth/register now creates accounts as pending, so without this step
    # neither pre-seeded login would work on first boot.
    asyncio.run(_activate([ADMIN["email"], "demo@healthflow.com"]))
    print(f"  activated: admin + demo broker")

    exit_code = asyncio.run(_promote(ADMIN["email"], async_session_factory))
    if exit_code != 0:
        sys.exit(exit_code)

    print()
    print("  Admin credentials:")
    print(f"    Email:    {ADMIN['email']}")
    print(f"    Password: {ADMIN['password']}")


if __name__ == "__main__":
    main()
