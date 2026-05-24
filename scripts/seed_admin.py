"""Bootstrap the demo admin account.

Registers admin@healthflow.com via /auth/register (always defaults role=broker)
then delegates to scripts.promote_admin._promote, which performs the role
update inside a system_context and emits an `admin_promoted` audit event.

Idempotent: re-running on a deploy that already has the account is a no-op
(promotion of an already-admin row is a write but not a state change).
"""
import asyncio
import os
import sys

import httpx

from healthflow.database.config import async_session_factory
from scripts.promote_admin import _promote

ADMIN = {
    "email": "admin@healthflow.com",
    "password": "Healthflow123!",
    "full_name": "HealthFlow Admin",
}
BASE_URL = os.getenv("HEALTHFLOW_BASE_URL", "http://localhost:8000")


def main() -> None:
    resp = httpx.post(f"{BASE_URL}/auth/register", json=ADMIN)
    if resp.status_code == 201:
        print(f"  admin registered: {ADMIN['email']}")
    elif resp.status_code == 409:
        print(f"  admin already exists: {ADMIN['email']}")
    else:
        print(f"  registration failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    exit_code = asyncio.run(_promote(ADMIN["email"], async_session_factory))
    if exit_code != 0:
        sys.exit(exit_code)

    print()
    print("  Admin credentials:")
    print(f"    Email:    {ADMIN['email']}")
    print(f"    Password: {ADMIN['password']}")


if __name__ == "__main__":
    main()
