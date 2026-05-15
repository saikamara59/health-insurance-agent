import json
import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from healthflow.auth.tenant_context import current_endpoint
from healthflow.logs.server import ServerLogger, get_server_logger


EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}


class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request to a ServerLogger.

    user_id is populated only when an upstream middleware has set
    request.state.user before this middleware runs. HealthFlow's current
    auth uses fastapi.Depends, not middleware, so user_id is typically
    None in production. A future auth-middleware can populate it without
    changes here.
    """

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
            if response.status_code >= 400 and error_message is None:
                error_message = await self._extract_error_detail(response)
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

    _MAX_ERROR_BODY_PARSE = 64 * 1024

    @staticmethod
    async def _extract_error_detail(response: Response) -> Optional[str]:
        if response.status_code < 400:
            return None
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        # Always replay the full body so the client still receives the response.
        response.body_iterator = _replay_iterator(body)
        # Skip parsing oversized bodies — cap protects the dev log from pulling
        # multi-MB error responses into memory just to find a 'detail' string.
        if len(body) > HTTPLoggingMiddleware._MAX_ERROR_BODY_PARSE:
            return None
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        if isinstance(parsed, dict):
            detail = parsed.get("detail")
            if isinstance(detail, str):
                return detail
        return None


async def _replay_iterator(body: bytes):
    yield body


class EndpointContextMiddleware(BaseHTTPMiddleware):
    """Set `current_endpoint` for the duration of each HTTP request.

    The PHI access audit listener (healthflow/database/phi_audit.py) reads
    this ContextVar to record WHICH request triggered a PHI query. Background
    work has no request — it runs inside `system_context(reason=...)`, which
    sets `current_endpoint` to `system:<reason>` instead.
    """

    async def dispatch(self, request: Request, call_next):
        token = current_endpoint.set(f"{request.method} {request.url.path}")
        try:
            return await call_next(request)
        finally:
            current_endpoint.reset(token)
