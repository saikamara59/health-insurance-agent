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
