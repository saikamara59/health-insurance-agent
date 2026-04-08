import json
import logging
from healthflow.logs.audit import AuditLogger


def test_audit_log_creates_structured_entry(caplog):
    logger = AuditLogger()
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        logger.log("input_validated", {"zip_code": "10001", "age": 65})

    assert len(caplog.records) == 1
    record = caplog.records[0]
    data = json.loads(record.getMessage())
    assert data["event_type"] == "input_validated"
    assert data["details"]["zip_code"] == "10001"
    assert "timestamp" in data


def test_audit_log_event_types(caplog):
    logger = AuditLogger()
    event_types = [
        "input_validated",
        "tool_called",
        "plans_fetched",
        "costs_estimated",
        "recommendation_generated",
        "output_filtered",
    ]
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        for et in event_types:
            logger.log(et, {"test": True})

    assert len(caplog.records) == 6


def test_audit_log_timestamp_is_iso_format(caplog):
    logger = AuditLogger()
    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        logger.log("tool_called", {"tool": "cms_fetcher"})

    data = json.loads(caplog.records[0].getMessage())
    assert "T" in data["timestamp"]
