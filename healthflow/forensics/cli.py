"""click CLI for the forensics replay tool.

Usage:
    python -m healthflow.forensics replay case <case_id> --tenant-id <uuid>
    python -m healthflow.forensics replay member <client_id> --tenant-id <uuid> --from <iso> --to <iso>
    python -m healthflow.forensics replay agent <agent> --tenant-id <uuid> --from <iso> --to <iso>

Operator identity for the self-audit row uses the supplied --tenant-id
(same value used to scope the query). The CLI does not infer a separate
operator; document this constraint in the README.
"""
import json
import uuid
from datetime import datetime

import click

from healthflow.database.config import async_session_factory
from healthflow.forensics.replay import (
    replay_agent,
    replay_case,
    replay_member,
)


def _get_session_factory():
    """Indirection point so tests can monkeypatch."""
    return async_session_factory


def _run(coro):
    """Run an async coroutine from a sync CLI handler.

    Normally `asyncio.run(coro)` is fine — that's the production path. But
    `click.testing.CliRunner.invoke()` is called from inside pytest-asyncio's
    event loop, where `asyncio.run()` raises `RuntimeError: cannot be called
    from a running event loop`. Detect that case and dispatch the coroutine
    to a fresh loop on a worker thread.
    """
    import asyncio as _asyncio

    try:
        _asyncio.get_running_loop()
    except RuntimeError:
        return _asyncio.run(coro)

    # A loop is already running (test context). Run on a thread with its own loop.
    import concurrent.futures

    def _runner():
        return _asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


@click.group()
def cli():
    """HealthFlow forensics — read-only audit replay over agent_invocation_log."""


@cli.group("replay")
def replay_group():
    """Replay an agent timeline by case / member / agent."""


def _emit(result_dict, fmt: str) -> None:
    if fmt == "json":
        click.echo(json.dumps(result_dict, default=str, indent=2))
        return
    # Text format — compact human summary.
    if "invocations" in result_dict:
        click.echo(f"Case: {result_dict.get('case_id')}")
        click.echo(f"Tenant: {result_dict.get('tenant_id')}")
        click.echo(f"{len(result_dict['invocations'])} invocations")
        for inv in result_dict["invocations"]:
            click.echo(
                f"  {inv['timestamp']}  {inv['agent']:>20}  {inv['event_type']:>20}"
                f"  ({inv.get('duration_ms', '?')}ms)"
            )
        if result_dict.get("integrity", {}).get("notes"):
            click.echo("Notes:")
            for note in result_dict["integrity"]["notes"]:
                click.echo(f"  - {note}")
    else:
        # list[AgentInvocation] from replay_agent
        click.echo(f"{len(result_dict)} invocations")
        for inv in result_dict:
            click.echo(
                f"  {inv['timestamp']}  {inv['agent']:>20}  {inv['event_type']:>20}"
                f"  ({inv.get('duration_ms', '?')}ms)"
            )


@replay_group.command("case")
@click.argument("case_id")
@click.option("--tenant-id", required=True, help="Tenant (broker) UUID to scope to.")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_case(case_id, tenant_id, fmt):
    """Replay an agent timeline for a case_id."""
    factory = _get_session_factory()
    timeline = _run(replay_case(
        uuid.UUID(case_id), tenant_id=uuid.UUID(tenant_id), session_factory=factory
    ))
    _emit(timeline.model_dump(mode="json"), fmt)


@replay_group.command("member")
@click.argument("client_id")
@click.option("--tenant-id", required=True)
@click.option("--from", "from_ts", required=True, help="ISO 8601 datetime (e.g. 2026-04-01T00:00:00).")
@click.option("--to", "to_ts", required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_member(client_id, tenant_id, from_ts, to_ts, fmt):
    """Replay agent invocations that accessed a client within a time range."""
    factory = _get_session_factory()
    timeline = _run(replay_member(
        uuid.UUID(client_id),
        time_range=(datetime.fromisoformat(from_ts), datetime.fromisoformat(to_ts)),
        tenant_id=uuid.UUID(tenant_id),
        session_factory=factory,
    ))
    _emit(timeline.model_dump(mode="json"), fmt)


@replay_group.command("agent")
@click.argument("agent")
@click.option("--tenant-id", required=True)
@click.option("--from", "from_ts", required=True)
@click.option("--to", "to_ts", required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_agent(agent, tenant_id, from_ts, to_ts, fmt):
    """Replay invocations of a specific agent in a time range."""
    factory = _get_session_factory()
    invocations = _run(replay_agent(
        agent,
        time_range=(datetime.fromisoformat(from_ts), datetime.fromisoformat(to_ts)),
        tenant_id=uuid.UUID(tenant_id),
        session_factory=factory,
    ))
    _emit([i.model_dump(mode="json") for i in invocations], fmt)


if __name__ == "__main__":
    cli()
