# Server Log for Local Dev — Design

**Date:** 2026-04-18
**Author:** Saidu Kamara
**Status:** Draft

## Problem

Devs running the FastAPI backend locally have no fast way to see what the frontend is actually sending and what came back. The existing `healthflow.log` is a structured audit log for domain events (input validated, tool called, recommendation generated) and is not suited for HTTP-level debugging. When a page breaks, devs can't easily answer "which request fired, what status, how long, what was the error."

## Goal

Add a second, dev-focused log that captures every HTTP request/response cycle in enough detail to reproduce frontend-to-backend bugs, without disturbing the existing audit log.

## Non-goals

- Replacing or merging with the audit log.
- Tracing agent internals, tool calls, DB queries, or non-HTTP `logger.*` calls.
- Full request/response bodies (kept out of scope — current pain point is seeing the request shape and the failure, not replaying payloads).
- Shipping logs off the dev machine.
- PHI redaction (dev log is local-only; `logs/` is gitignored).

## Scope

HTTP request/response lines at standard detail:

- method, path, query string
- status code, duration, response size
- client IP, authenticated user ID (if present)
- error message on 4xx/5xx

A small set of noisy paths (`/health`, `/docs`, `/openapi.json`, `/favicon.ico`) are excluded.

## Architecture

Three files, one wiring point.

### `healthflow/logs/server.py` (new)

Defines `ServerLogger`, analogous to the existing `AuditLogger` in `healthflow/logs/audit.py`. Configures the `healthflow.server` Python logger with two handlers:

- **Console handler** — `StreamHandler` → stdout, human-readable one-line formatter.
- **File handler** — `TimedRotatingFileHandler(filename="logs/server.log", when="midnight", backupCount=7, utc=True, encoding="utf-8")`. Emits one JSON object per line.

The constructor accepts a `log_dir` argument (default `"logs"`) and creates it via `Path(log_dir).mkdir(parents=True, exist_ok=True)` on first instantiation. Handlers are only attached if none exist yet, so repeated imports don't duplicate them. The module exposes a cached accessor (`get_server_logger()`) that returns the singleton instance.

Public API:

```python
logger = get_server_logger()
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
```

The log method selects the log level based on status:

- `2xx`/`3xx` → `INFO`
- `4xx` → `WARNING`
- `5xx` → `ERROR`

### `healthflow/api/middleware.py` (new)

Defines `HTTPLoggingMiddleware`, a Starlette `BaseHTTPMiddleware`. For each request it:

1. Records `start = time.perf_counter()`.
2. Short-circuits and returns `await call_next(request)` unchanged if `request.url.path` is in `EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}`.
3. Otherwise calls `response = await call_next(request)` inside a `try/except`.
4. Computes `duration_ms = round((time.perf_counter() - start) * 1000, 1)`.
5. Extracts fields (see below).
6. Calls `get_server_logger().log_request(...)`.
7. On exception, logs with `status=500` and `error=str(exc)`, then re-raises so FastAPI's normal exception handling still runs.

Field extraction:

| Field | Source |
| --- | --- |
| `method` | `request.method` |
| `path` | `request.url.path` |
| `query` | `request.url.query` (empty string if none) |
| `status` | `response.status_code` (or `500` on raised exception) |
| `duration_ms` | measured as above |
| `client_ip` | `request.client.host` (or `null` if missing) |
| `user_id` | `getattr(request.state, "user", None)` → `.id` if present, else `null` |
| `response_size` | `int(response.headers.get("content-length"))` if present, else `null` |
| `error` | on 4xx/5xx: exception message if raised; else the `detail` field from a JSON error response if parseable; else `null` |

### `healthflow/main.py` (modify)

Where the FastAPI app is constructed (alongside the existing `CORSMiddleware`), add:

```python
from healthflow.api.middleware import HTTPLoggingMiddleware
app.add_middleware(HTTPLoggingMiddleware)
```

No per-route changes.

### `.gitignore` (modify)

Add `logs/` so the raw dev log never ships. Existing `healthflow.log` entry (if any) is left alone.

## Output Format

### Console (stdout)

Fixed-width columns, grep-friendly:

```
2026-04-18 14:32:01 INFO  POST /api/plans/compare  200  142.3ms  user=42
2026-04-18 14:32:05 WARN  GET  /api/clients/999    404   12.1ms  user=42  error="Client not found"
2026-04-18 14:32:09 ERROR POST /api/appeal         500   87.4ms  user=42  error="sqlite OperationalError: no such column"
```

### File (`logs/server.log`)

One JSON object per line:

```json
{"timestamp":"2026-04-18T14:32:01.123Z","level":"INFO","method":"POST","path":"/api/plans/compare","query":"","status":200,"duration_ms":142.3,"client_ip":"127.0.0.1","user_id":42,"response_size":4821,"error":null}
```

## Rotation

- `when="midnight"`, UTC boundary.
- Rotated files: `server.log.2026-04-17`, `server.log.2026-04-16`, ...
- `backupCount=7`. The eighth rotation deletes the oldest.
- No size-based rotation — daily boundaries make bug reports easier to file ("I hit this around 2pm yesterday").

## Thread & Async Safety

Python's stdlib `logging` handlers are thread-safe. `TimedRotatingFileHandler` handles concurrent writes correctly for a single-process uvicorn dev server. No extra locking is added.

## Test Plan

New test file `healthflow/tests/test_server_log.py`. A `conftest.py` fixture points `ServerLogger` at `tmp_path` for isolation (no persistent test log file — devs needing per-test visibility use pytest's stdout capture).

Cases:

1. **Successful request logged.** GET a real endpoint; assert one JSON line in the file with `status=200`, correct `method` and `path`, `duration_ms > 0`, `error is null`.
2. **4xx logged with error detail.** Hit an endpoint with a bad payload; assert `level="WARNING"`, `status` is 422/404, `error` contains the detail string.
3. **5xx logged and exception re-raised.** Mount a temporary route that raises; assert the middleware wrote `status=500`, `error="..."`, and the exception propagates (TestClient sees 500).
4. **Excluded paths skipped.** Hit `/docs` and `/openapi.json`; assert no new lines.
5. **Query string captured.** `GET /api/clients?limit=5`; assert `query="limit=5"` in the entry.
6. **Authed user_id captured.** Request with auth header; assert `user_id` matches the authenticated user (reuses existing auth test fixtures).
7. **Rotation config sanity.** Instantiate `ServerLogger`; inspect its `TimedRotatingFileHandler` and assert `when="MIDNIGHT"`, `backupCount=7`, `utc=True`.

Console formatter output is not tested — stdout formatting is cosmetic and low-value to pin down.

## Files Touched

| File | Change |
| --- | --- |
| `healthflow/logs/server.py` | new |
| `healthflow/api/middleware.py` | new |
| `healthflow/main.py` | add `app.add_middleware(HTTPLoggingMiddleware)` |
| `.gitignore` | add `logs/` |
| `healthflow/tests/test_server_log.py` | new |
| `healthflow/tests/conftest.py` | fixture pointing `ServerLogger` at `tmp_path` |

## Open Questions

None.
