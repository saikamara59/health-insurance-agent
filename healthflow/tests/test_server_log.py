import json
from pathlib import Path

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
