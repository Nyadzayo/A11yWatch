import json
import logging
import sys

from a11ywatch.core.logging import StructuredFormatter, configure_logging


def _record(**kw):
    base = dict(
        name="a11y", level=logging.INFO, pathname="x", lineno=1, msg="m", args=(), exc_info=None
    )
    base.update(kw)
    return logging.LogRecord(**base)


def test_structured_formatter_emits_json_with_message_and_extras():
    rec = _record(msg="enqueued %d", args=(3,))
    rec.event = "scheduler_cycle"
    rec.scan_id = "s1"
    data = json.loads(StructuredFormatter().format(rec))
    assert data["level"] == "INFO"
    assert data["logger"] == "a11y"
    assert data["message"] == "enqueued 3"
    assert data["event"] == "scheduler_cycle"
    assert data["scan_id"] == "s1"


def test_structured_formatter_includes_exception_text():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = _record(level=logging.ERROR, msg="failed", exc_info=sys.exc_info())
    data = json.loads(StructuredFormatter().format(rec))
    assert "boom" in data["exception"]


def test_configure_logging_attaches_single_structured_handler():
    lg = logging.getLogger("a11ywatch-test-configure")
    lg.handlers = []
    configure_logging(level=logging.WARNING, logger=lg)
    assert lg.level == logging.WARNING
    assert len(lg.handlers) == 1
    assert isinstance(lg.handlers[0].formatter, StructuredFormatter)
    # Idempotent: re-configuring does not stack duplicate handlers.
    configure_logging(level=logging.WARNING, logger=lg)
    assert len(lg.handlers) == 1
