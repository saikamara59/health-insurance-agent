"""ASGI middleware that sets `case_id` ContextVar for the request scope.

Reads `X-Case-Id` from the request headers; validates as UUID. If absent or
malformed, generates a fresh uuid4(). Resets the ContextVar on teardown so
per-request isolation is clean under asyncio concurrency (same pattern as
`get_current_broker`).
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from healthflow.auth.case_context import case_id, parse_case_id_header


class CaseContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header_value = request.headers.get("x-case-id")
        new_case = parse_case_id_header(header_value)
        token = case_id.set(new_case)
        try:
            response = await call_next(request)
            # Echo the case_id back so callers can correlate logs across systems.
            response.headers["X-Case-Id"] = str(new_case)
            return response
        finally:
            case_id.reset(token)
