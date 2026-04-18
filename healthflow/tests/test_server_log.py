import json
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from healthflow.logs.server import ServerLogger


def test_log_request_writes_json_line_to_file(tmp_path: Path):
    logger = ServerLogger(log_dir=str(tmp_path))

    logger.log_request(
        method="POST",
        path="/api/plans/compare",
        query="",
        status=200,
        duration_ms=142.3,
        client_ip="127.0.0.1",
        user_id=42,
        response_size=4821,
        error=None,
    )

    log_file = tmp_path / "server.log"
    assert log_file.exists()

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["method"] == "POST"
    assert entry["path"] == "/api/plans/compare"
    assert entry["query"] == ""
    assert entry["status"] == 200
    assert entry["duration_ms"] == 142.3
    assert entry["client_ip"] == "127.0.0.1"
    assert entry["user_id"] == 42
    assert entry["response_size"] == 4821
    assert entry["error"] is None
    assert entry["level"] == "INFO"
    assert "timestamp" in entry


@pytest.mark.parametrize(
    "status,expected_level",
    [
        (200, "INFO"),
        (302, "INFO"),
        (404, "WARNING"),
        (422, "WARNING"),
        (500, "ERROR"),
        (503, "ERROR"),
    ],
)
def test_log_level_matches_status_class(tmp_path, status, expected_level):
    logger = ServerLogger(log_dir=str(tmp_path))

    logger.log_request(
        method="GET",
        path="/x",
        query="",
        status=status,
        duration_ms=1.0,
        client_ip=None,
        user_id=None,
        response_size=None,
        error=None if status < 400 else "boom",
    )

    entry = json.loads((tmp_path / "server.log").read_text().strip().splitlines()[-1])
    assert entry["level"] == expected_level


def test_file_handler_uses_daily_utc_rotation_with_seven_backups(tmp_path):
    logger = ServerLogger(log_dir=str(tmp_path))

    file_handlers = [
        h for h in logger._logger.handlers if isinstance(h, TimedRotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    handler = file_handlers[0]
    assert handler.when == "MIDNIGHT"
    assert handler.backupCount == 7
    assert handler.utc is True


def test_get_server_logger_returns_singleton(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from healthflow.logs import server as server_module

    server_module.reset_server_logger_for_tests()

    first = server_module.get_server_logger()
    second = server_module.get_server_logger()

    assert first is second
