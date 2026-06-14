import json
import logging

# Standard LogRecord attributes — everything else on a record is a structured "extra".
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class StructuredFormatter(logging.Formatter):
    """Render each log record as one JSON line, including any ``extra=`` fields.

    One line per event keeps API/worker/scheduler logs greppable and machine-parseable.
    """

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                data[key] = value
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def configure_logging(level: int = logging.INFO, *, logger: logging.Logger | None = None) -> None:
    """Install a single structured handler on the target logger (root by default).

    Idempotent: replaces handlers rather than stacking them, so repeated calls (e.g. one
    per process entrypoint) don't duplicate output.
    """
    target = logger if logger is not None else logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    target.handlers = [handler]
    target.setLevel(level)
