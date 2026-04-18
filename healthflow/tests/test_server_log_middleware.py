import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from healthflow.api.middleware import HTTPLoggingMiddleware
from healthflow.logs import server as server_log_module


def _build_app(log_dir: Path) -> FastAPI:
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(log_dir))

    def _override():
        return logger

    app = FastAPI()
    app.dependency_overrides = {}
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=_override)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def _read_log(log_dir: Path) -> list[dict]:
    path = log_dir / "server.log"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().strip().splitlines() if line]


@pytest.mark.anyio
async def test_successful_request_is_logged(tmp_path):
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping")

    assert response.status_code == 200
    entries = _read_log(tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["method"] == "GET"
    assert entry["path"] == "/ping"
    assert entry["status"] == 200
    assert entry["duration_ms"] > 0
    assert entry["error"] is None
    assert entry["level"] == "INFO"


from fastapi import HTTPException


@pytest.mark.anyio
async def test_4xx_response_logs_warning_with_detail(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Client not found")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    entries = _read_log(tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["level"] == "WARNING"
    assert entry["status"] == 404
    assert entry["error"] == "Client not found"
