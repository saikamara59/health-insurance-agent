"""Promote a broker to admin role.

Usage:
    python scripts/promote_admin.py --email someone@example.com

The first admin must be created this way (no API path creates admins).
The change is audit-logged via AuditLogger (event: admin_promoted).
"""
import asyncio
import sys

import click
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Broker
from healthflow.logs.audit import AuditLogger


async def _promote(email: str, factory: async_sessionmaker) -> int:
    """Returns exit code: 0 on success, 1 if no broker matches."""
    async with factory() as db:
        with system_context("admin promotion CLI"):
            broker = (await db.execute(
                select(Broker).where(Broker.email == email)
            )).scalar_one_or_none()
            if broker is None:
                click.echo(f"No broker found with email {email}.", err=True)
                return 1
            broker.role = "admin"
            await db.commit()
            AuditLogger().log(
                "admin_promoted",
                {"target_broker_id": str(broker.id), "via": "promote_admin.py"},
            )
            click.echo(f"Promoted {email} to admin.")
            return 0


@click.command()
@click.option("--email", required=True, help="Email of the broker to promote.")
def main(email: str) -> None:
    from healthflow.database.config import async_session_factory

    exit_code = asyncio.run(_promote(email, async_session_factory))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
