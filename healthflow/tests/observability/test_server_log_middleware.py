import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from healthflow.api.middleware import HTTPLoggingMiddleware
from healthflow.logs import server as server_log_module


def _build_app(log_dir: Path) -> FastAPI:
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(log_dir))

    def _override():
        return logger

    app = FastAPI()
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


@pytest.mark.anyio
async def test_unhandled_exception_logged_and_reraised(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(RuntimeError, match="kaboom"):
            await client.get("/boom")

    entries = _read_log(tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["level"] == "ERROR"
    assert entry["status"] == 500
    assert entry["error"] == "kaboom"


@pytest.mark.anyio
async def test_excluded_paths_are_not_logged(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/openapi.json")
    def openapi():
        return {"openapi": "3.0.0"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/openapi.json")

    assert _read_log(tmp_path) == []


@pytest.mark.anyio
async def test_query_string_is_captured(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)

    @app.get("/clients")
    def list_clients():
        return {"items": []}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/clients", params={"limit": 5})

    entries = _read_log(tmp_path)
    assert len(entries) == 1
    assert entries[0]["query"] == "limit=5"


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = SimpleNamespace(id=42)
        return await call_next(request)


@pytest.mark.anyio
async def test_user_id_captured_from_request_state(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    # Simulates a future auth middleware. Production auth uses fastapi.Depends,
    # so user_id will be None in real traffic until that wiring lands.
    # Middlewares execute in reverse order of registration; register the fake
    # auth last so it runs before logging.
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)
    app.add_middleware(_FakeAuthMiddleware)

    @app.get("/me")
    def me():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/me")

    entries = _read_log(tmp_path)
    assert len(entries) == 1
    assert entries[0]["user_id"] == 42


@pytest.mark.anyio
async def test_oversized_4xx_body_does_not_parse_detail(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    app.add_middleware(HTTPLoggingMiddleware, logger_factory=lambda: logger)

    huge_detail = "x" * (HTTPLoggingMiddleware._MAX_ERROR_BODY_PARSE + 1)

    @app.get("/huge")
    def huge():
        raise HTTPException(status_code=400, detail=huge_detail)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/huge")

    # Client still gets the full body back (replay works).
    assert response.status_code == 400
    assert huge_detail in response.text

    entries = _read_log(tmp_path)
    assert len(entries) == 1
    # Log entry exists at WARNING level with status 400, but error stays None
    # because the body exceeded the parse cap.
    assert entries[0]["level"] == "WARNING"
    assert entries[0]["status"] == 400
    assert entries[0]["error"] is None
