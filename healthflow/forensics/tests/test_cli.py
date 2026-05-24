"""CLI tests using click's CliRunner. No live DB — monkeypatches the
session factory to point at the in-memory test DB."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from healthflow.forensics.cli import cli
from healthflow.forensics.tests.fixtures import make_invocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def _patch_cli_factory(db_session_factory, monkeypatch):
    from healthflow.forensics import cli as cli_mod
    monkeypatch.setattr(cli_mod, "_get_session_factory", lambda: db_session_factory)


@pytest.mark.asyncio
async def test_cli_case_json_emits_parseable_output(_patch_cli_factory, db_session):
    tenant = uuid.uuid4()
    case = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=tenant, timestamp=_T0))
    await db_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["replay", "case", str(case), "--tenant-id", str(tenant), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["case_id"] == str(case)
    assert len(body["invocations"]) == 1


@pytest.mark.asyncio
async def test_cli_agent_text_format_runs_and_exits_zero(_patch_cli_factory, db_session):
    tenant = uuid.uuid4()
    db_session.add(make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0))
    await db_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "replay", "agent", "comparison",
            "--tenant-id", str(tenant),
            "--from", "2026-04-01T00:00:00",
            "--to", "2026-06-01T00:00:00",
            "--format", "text",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "comparison" in result.output
