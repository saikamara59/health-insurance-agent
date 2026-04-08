import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


class AuditLogger:
    def __init__(self, log_file: str = "healthflow.log"):
        self._logger = logging.getLogger("healthflow.audit")
        if not self._logger.handlers:
            self._logger.setLevel(logging.INFO)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self._logger.addHandler(console_handler)

            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3
            )
            file_handler.setLevel(logging.INFO)
            self._logger.addHandler(file_handler)

    def log(self, event_type: str, details: dict) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        self._logger.info(json.dumps(entry))
