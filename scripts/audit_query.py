#!/usr/bin/env python3
"""Read the PHI access audit log.

Usage:
    python scripts/audit_query.py --patient <uuid>   # who touched this patient's records
    python scripts/audit_query.py --broker <uuid>    # everything this broker did

Runs inside system_context() — phi_access_log is a system table, and reading
it for a breach investigation is a legitimate cross-tenant operation.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path so we can import healthflow
sys.path.insert(0, str(Path(__file__).parent.parent))

from healthflow.auth.tenant_context import system_context
from healthflow.database.config import async_session_factory
from healthflow.database.phi_audit import query_by_broker, query_by_patient


def _print_entries(entries) -> None:
    if not entries:
        print("  (no matching audit entries)")
        return
    for e in entries:
        broker = str(e.broker_id) if e.broker_id else "system"
        ids = ", ".join(e.row_ids) if e.row_ids else "—"
        print(
            f"  {e.created_at.isoformat()}  {e.operation:6}  {e.table_name:14}  "
            f"broker={broker}  endpoint={e.endpoint}  rows=[{ids}]"
        )


async def _main(args) -> int:
    async with async_session_factory() as session:
        with system_context("audit query CLI"):
            if args.patient:
                print(f"PHI access entries mentioning patient {args.patient}:")
                _print_entries(await query_by_patient(session, args.patient))
            else:
                print(f"PHI access entries for broker {args.broker}:")
                _print_entries(await query_by_broker(session, args.broker))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the PHI access audit log.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--patient", help="Patient (client) UUID to search for")
    group.add_argument("--broker", help="Broker UUID to search for")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
