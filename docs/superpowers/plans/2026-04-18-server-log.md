# Local Dev Server Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only `logs/server.log` that captures HTTP request/response activity so devs can debug frontend↔backend problems.

**Architecture:** A `ServerLogger` (in `healthflow/logs/server.py`) configures a Python logger with two handlers: a readable stdout `StreamHandler` and a daily-rotating JSON `TimedRotatingFileHandler`. An `HTTPLoggingMiddleware` (in `healthflow/api/middleware.py`) wraps every FastAPI request, measures duration, extracts fields, and hands them to the logger. Wired once in `healthflow/main.py`. Spec: `docs/superpowers/specs/2026-04-18-server-log-design.md`.

**Tech Stack:** Python 3, FastAPI, Starlette `BaseHTTPMiddleware`, stdlib `logging` + `logging.handlers.TimedRotatingFileHandler`, pytest + pytest-asyncio + httpx (existing test setup).

---

### Task 1: Ignore the logs directory

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `logs/` to `.gitignore`**

Open `.gitignore` and append a new line at the bottom:

```
logs/
```

- [ ] **Step 2: Verify git does not track the directory**

Run:

```bash
mkdir -p logs && touch logs/.keep
git status --short logs/
```

Expected output: empty (git ignores the path). Remove the temp dir:

```bash
rm -rf logs
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore logs/ directory for local dev server log"
```

---

### Task 2: Write failing test for ServerLogger JSON file output

**Files:**
- Create: `healthflow/tests/test_server_log.py`

- [ ] **Step 1: Write the failing test**

Create `healthflow/tests/test_server_log.py` with:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_log_request_writes_json_line_to_file -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'healthflow.logs.server'`.

---

### Task 3: Implement ServerLogger minimal JSON file output

**Files:**
- Create: `healthflow/logs/server.py`

- [ ] **Step 1: Create `healthflow/logs/server.py`**

Write the file with:

```python
import json
import logging
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


def _level_for_status(status: int) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    return logging.INFO


class _JSONFileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", None)
        if payload is None:
            return record.getMessage()
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            **payload,
        }
        return json.dumps(entry)


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", None)
        if payload is None:
            return record.getMessage()
        ts = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        level = record.levelname.ljust(5)
        method = payload["method"].ljust(4)
        path = payload["path"].ljust(24)
        status = str(payload["status"]).ljust(3)
        duration = f"{payload['duration_ms']:.1f}ms".rjust(8)
        user = payload.get("user_id")
        user_part = f"  user={user}" if user is not None else ""
        error = payload.get("error")
        error_part = f'  error="{error}"' if error else ""
        return (
            f"{ts} {level} {method} {path}  {status}  {duration}"
            f"{user_part}{error_part}"
        )


class ServerLogger:
    def __init__(self, log_dir: str = "logs"):
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"healthflow.server.{log_path.resolve()}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            console.setFormatter(_ConsoleFormatter())
            self._logger.addHandler(console)

            file_handler = TimedRotatingFileHandler(
                str(log_path / "server.log"),
                when="midnight",
                backupCount=7,
                utc=True,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(_JSONFileFormatter())
            self._logger.addHandler(file_handler)

    def log_request(
        self,
        *,
        method: str,
        path: str,
        query: str,
        status: int,
        duration_ms: float,
        client_ip: Optional[str],
        user_id: Optional[int],
        response_size: Optional[int],
        error: Optional[str],
    ) -> None:
        payload = {
            "method": method,
            "path": path,
            "query": query,
            "status": status,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "user_id": user_id,
            "response_size": response_size,
            "error": error,
        }
        level = _level_for_status(status)
        self._logger.log(level, "", extra={"payload": payload})
```

- [ ] **Step 2: Run the test and confirm it passes**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_log_request_writes_json_line_to_file -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/logs/server.py healthflow/tests/test_server_log.py
git commit -m "feat: add ServerLogger writing JSON lines to rotating file"
```

---

### Task 4: Test level selection by status code

**Files:**
- Modify: `healthflow/tests/test_server_log.py`

- [ ] **Step 1: Add the failing test**

Append to `healthflow/tests/test_server_log.py`:

```python
import pytest


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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_log_level_matches_status_class -v
```

Expected: PASS (the implementation from Task 3 already covers this).

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log.py
git commit -m "test: cover ServerLogger level selection by status code"
```

---

### Task 5: Test rotation handler config

**Files:**
- Modify: `healthflow/tests/test_server_log.py`

- [ ] **Step 1: Add the test**

Append to `healthflow/tests/test_server_log.py`:

```python
from logging.handlers import TimedRotatingFileHandler


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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_file_handler_uses_daily_utc_rotation_with_seven_backups -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log.py
git commit -m "test: pin ServerLogger rotation config to midnight/7/utc"
```

---

### Task 6: Add cached singleton accessor

**Files:**
- Modify: `healthflow/logs/server.py`
- Modify: `healthflow/tests/test_server_log.py`

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/test_server_log.py`:

```python
def test_get_server_logger_returns_singleton(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from healthflow.logs import server as server_module

    server_module._cached_logger = None  # reset cache for test isolation

    first = server_module.get_server_logger()
    second = server_module.get_server_logger()

    assert first is second
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_get_server_logger_returns_singleton -v
```

Expected: FAIL with `AttributeError: module 'healthflow.logs.server' has no attribute 'get_server_logger'`.

- [ ] **Step 3: Add the accessor**

Append to `healthflow/logs/server.py`:

```python
_cached_logger: Optional[ServerLogger] = None


def get_server_logger() -> ServerLogger:
    global _cached_logger
    if _cached_logger is None:
        _cached_logger = ServerLogger()
    return _cached_logger


def reset_server_logger_for_tests() -> None:
    """Reset the cached logger. Tests only."""
    global _cached_logger
    _cached_logger = None
```

- [ ] **Step 4: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log.py::test_get_server_logger_returns_singleton -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add healthflow/logs/server.py healthflow/tests/test_server_log.py
git commit -m "feat: add cached get_server_logger accessor"
```

---

### Task 7: Pytest fixture to isolate ServerLogger per test

**Files:**
- Modify: `healthflow/tests/conftest.py`

- [ ] **Step 1: Add the fixture**

Edit `healthflow/tests/conftest.py`. After the existing imports, add:

```python
from healthflow.logs import server as server_log_module
```

Then append this fixture to the bottom of the file:

```python
@pytest.fixture(autouse=True)
def isolate_server_log(tmp_path, monkeypatch):
    """Point ServerLogger at a per-test tmp_path so tests don't write to logs/server.log."""
    server_log_module.reset_server_logger_for_tests()
    monkeypatch.setattr(
        server_log_module,
        "get_server_logger",
        lambda: server_log_module.ServerLogger(log_dir=str(tmp_path / "logs")),
    )
    yield
    server_log_module.reset_server_logger_for_tests()
```

- [ ] **Step 2: Run the full existing test suite and confirm nothing breaks**

Run:

```bash
pytest healthflow/tests/ -x -q
```

Expected: all existing tests still pass (fixture is autouse but only affects tests that touch the logger).

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/conftest.py
git commit -m "test: add autouse fixture isolating ServerLogger per test"
```

---

### Task 8: Write failing test for middleware happy path

**Files:**
- Create: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the failing test**

Create `healthflow/tests/test_server_log_middleware.py`:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_successful_request_is_logged -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'healthflow.api.middleware'`.

---

### Task 9: Implement middleware happy path

**Files:**
- Create: `healthflow/api/middleware.py`

- [ ] **Step 1: Create `healthflow/api/middleware.py`**

Write the file with:

```python
import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from healthflow.logs.server import ServerLogger, get_server_logger


EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}


class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_factory: Callable[[], ServerLogger] = get_server_logger):
        super().__init__(app)
        self._logger_factory = logger_factory

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response: Optional[Response] = None
        error_message: Optional[str] = None
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            client_ip = request.client.host if request.client else None
            user_id = self._extract_user_id(request)
            response_size = self._extract_response_size(response)
            self._logger_factory().log_request(
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
                status=status,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_id=user_id,
                response_size=response_size,
                error=error_message,
            )

        return response

    @staticmethod
    def _extract_user_id(request: Request) -> Optional[int]:
        user = getattr(request.state, "user", None)
        if user is None:
            return None
        return getattr(user, "id", None)

    @staticmethod
    def _extract_response_size(response: Optional[Response]) -> Optional[int]:
        if response is None:
            return None
        length = response.headers.get("content-length")
        if length is None:
            return None
        try:
            return int(length)
        except ValueError:
            return None
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_successful_request_is_logged -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/api/middleware.py healthflow/tests/test_server_log_middleware.py
git commit -m "feat: HTTP logging middleware writes requests to server.log"
```

---

### Task 10: Test 4xx path logs warning with error detail

**Files:**
- Modify: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/test_server_log_middleware.py`:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_4xx_response_logs_warning_with_detail -v
```

Expected: FAIL. The middleware does not yet read `detail` from 4xx JSON bodies — `error` will be `None`.

- [ ] **Step 3: Extend middleware to extract error detail on 4xx/5xx responses**

In `healthflow/api/middleware.py`, first add `json` to the imports at the top of the file (alongside `time`):

```python
import json
```

Then add this helper method to the class (place it after `_extract_response_size`):

```python
    @staticmethod
    async def _extract_error_detail(response: Response) -> Optional[str]:
        if response.status_code < 400:
            return None
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            response.body_iterator = _replay_iterator(body)
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        if isinstance(parsed, dict):
            detail = parsed.get("detail")
            if isinstance(detail, str):
                return detail
        return None
```

Also add this module-level helper at the bottom of `healthflow/api/middleware.py`:

```python
async def _replay_iterator(body: bytes):
    yield body
```

Then in `dispatch`, after `status = response.status_code`, insert:

```python
            if response.status_code >= 400 and error_message is None:
                error_message = await self._extract_error_detail(response)
```

- [ ] **Step 4: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_4xx_response_logs_warning_with_detail -v
```

Expected: PASS.

- [ ] **Step 5: Re-run the happy-path test to check nothing regressed**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add healthflow/api/middleware.py healthflow/tests/test_server_log_middleware.py
git commit -m "feat: middleware extracts error detail on 4xx/5xx JSON responses"
```

---

### Task 11: Test 5xx exception path — entry written AND exception re-raised

**Files:**
- Modify: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/test_server_log_middleware.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_unhandled_exception_logged_and_reraised -v
```

Expected: PASS (the middleware already handles this via the `try/except/finally`).

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log_middleware.py
git commit -m "test: middleware logs and re-raises unhandled exceptions"
```

---

### Task 12: Excluded paths are not logged

**Files:**
- Modify: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the test**

Append to `healthflow/tests/test_server_log_middleware.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_excluded_paths_are_not_logged -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log_middleware.py
git commit -m "test: health and openapi paths are excluded from server.log"
```

---

### Task 13: Query string is captured

**Files:**
- Modify: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the test**

Append to `healthflow/tests/test_server_log_middleware.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_query_string_is_captured -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log_middleware.py
git commit -m "test: query string captured in server.log entry"
```

---

### Task 14: Authenticated user_id is captured

**Files:**
- Modify: `healthflow/tests/test_server_log_middleware.py`

- [ ] **Step 1: Write the test**

Append to `healthflow/tests/test_server_log_middleware.py`:

```python
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware


class _FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = SimpleNamespace(id=42)
        return await call_next(request)


@pytest.mark.anyio
async def test_user_id_captured_from_request_state(tmp_path):
    server_log_module.reset_server_logger_for_tests()
    logger = server_log_module.ServerLogger(log_dir=str(tmp_path))

    app = FastAPI()
    # Middlewares execute in reverse order of registration; register auth last
    # so it runs before logging.
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
```

- [ ] **Step 2: Run the test**

Run:

```bash
pytest healthflow/tests/test_server_log_middleware.py::test_user_id_captured_from_request_state -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add healthflow/tests/test_server_log_middleware.py
git commit -m "test: authenticated user_id captured from request.state.user"
```

---

### Task 15: Wire middleware into the real FastAPI app

**Files:**
- Modify: `healthflow/main.py`

- [ ] **Step 1: Add the middleware to the app**

In `healthflow/main.py`, add this import near the other middleware-related imports (after `from fastapi.middleware.cors import CORSMiddleware`):

```python
from healthflow.api.middleware import HTTPLoggingMiddleware
```

Then, after the `app.add_middleware(CORSMiddleware, ...)` block, add:

```python
app.add_middleware(HTTPLoggingMiddleware)
```

- [ ] **Step 2: Run the entire backend test suite**

Run:

```bash
pytest healthflow/tests/ -q
```

Expected: all tests pass. The `isolate_server_log` fixture from Task 7 ensures no test writes to a real `logs/server.log`.

- [ ] **Step 3: Smoke-test manually against a running server**

In one terminal, start the API:

```bash
python -m healthflow.main
```

In another terminal, make a couple of requests:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/plans/10001 | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/plans/not-a-zip
```

Verify:

```bash
cat logs/server.log
```

Expected: one JSON line for `/plans/10001` (INFO, status 200). One JSON line for `/plans/not-a-zip` (WARNING, status 422, `error` set). No entry for `/health`. Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add healthflow/main.py
git commit -m "feat: wire HTTPLoggingMiddleware into FastAPI app"
```

---

### Task 16: Final verification

**Files:** none

- [ ] **Step 1: Run the full backend test suite once more**

Run:

```bash
pytest healthflow/tests/ -q
```

Expected: all tests pass.

- [ ] **Step 2: Confirm `logs/` was not accidentally committed**

Run:

```bash
git status --short
git ls-files logs/ 2>/dev/null
```

Expected: `git status` shows a clean tree (or only unrelated pre-existing modifications). `git ls-files logs/` prints nothing.

- [ ] **Step 3: Confirm spec + plan are committed**

Run:

```bash
git log --oneline -20
```

Expected: commits for the spec, spec correction, gitignore, ServerLogger, middleware, and app wiring are all present.

---

## Notes on edge cases

- **Streaming responses** don't set `content-length`. `_extract_response_size` returns `None` in that case — `response_size` will be `null` in the log. This is fine.
- **`request.client` can be `None`** in ASGI setups without a real socket (notably older test transports). `client_ip` becomes `null`. Handled.
- **Body-iterator replay (Task 10):** after reading the response body to extract `detail`, we reassign `response.body_iterator` to re-yield the bytes so the HTTP layer still sends the real body to the client. Without this step the client would receive an empty body on 4xx/5xx.
- **Middleware order:** FastAPI executes middlewares in reverse registration order for requests, and forward order for responses. `HTTPLoggingMiddleware` is registered after `CORSMiddleware`, which puts logging innermost — it wraps the route handler directly and sees the unmodified status code before CORS headers are added. Correct for our purposes.
