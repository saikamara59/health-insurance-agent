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
