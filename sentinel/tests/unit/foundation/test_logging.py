"""Tests de logging JSON (BR-09..BR-12)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from sentinel.foundation.logging import JsonFormatter, get_logger


@pytest.fixture(autouse=True)
def _clean_loggers() -> None:
    for name in list(logging.Logger.manager.loggerDict):
        if name.startswith("sentinel."):
            logging.getLogger(name).handlers.clear()
            logging.getLogger(name).propagate = True
    yield
    for name in list(logging.Logger.manager.loggerDict):
        if name.startswith("sentinel."):
            logging.getLogger(name).handlers.clear()


def test_single_handler_idempotent() -> None:
    logger1 = get_logger("core")
    logger2 = get_logger("core")
    assert logger1 is logger2
    assert len(logger1.handlers) == 1


def test_json_line_has_required_fields(capsys: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("discovery")
    logger.info("hello", extra={"event": "sensor_heartbeat", "host": "lab"})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert set(data) >= {"ts", "level", "component", "event", "msg"}
    assert data["component"] == "discovery"
    assert data["event"] == "sensor_heartbeat"
    assert data["msg"] == "hello"
    assert data["host"] == "lab"
    assert data["level"] == "INFO"


def test_ts_is_utc_iso8601_with_z(capsys: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("core")
    logger.info("x", extra={"event": "sensor_heartbeat"})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    ts = json.loads(line)["ts"]
    assert ts.endswith("Z")
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.tzinfo == UTC


def test_event_fallback_unnamed(capsys: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("core")
    logger.warning("no event")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line)["event"] == "unnamed"


def test_formatter_direct() -> None:
    record = logging.LogRecord(
        name="sentinel.core",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    data = json.loads(JsonFormatter().format(record))
    assert data["msg"] == "m"
    assert data["event"] == "unnamed"
    assert data["component"] == "core"
