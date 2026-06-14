import httpx
from playwright.sync_api import Error as PlaywrightError
from redis.exceptions import RedisError
from rq.timeouts import JobTimeoutException
from sqlalchemy.exc import InterfaceError, OperationalError

# Errors worth retrying: timeouts, network/connection blips, browser/infra hiccups.
_TRANSIENT_TYPES = (
    TimeoutError,
    ConnectionError,
    OSError,
    httpx.TransportError,
    RedisError,
    OperationalError,
    InterfaceError,
    JobTimeoutException,
)

# Connection-level Chromium failures worth retrying. Name-resolution, cert, unsafe-port,
# blocked-by-client and address-unreachable are permanent (a blanket net::/err_ match would
# retry-storm those), so they are deliberately excluded.
_TRANSIENT_PLAYWRIGHT_HINTS = (
    "timeout",
    "crash",
    "target closed",
    "err_connection_refused",
    "err_connection_reset",
    "err_connection_closed",
    "err_connection_timed_out",
    "err_timed_out",
    "err_network_changed",
    "err_internet_disconnected",
    "err_empty_response",
)


def is_transient(exc: BaseException) -> bool:
    """True for errors likely to succeed on retry; False for permanent failures."""
    if isinstance(exc, _TRANSIENT_TYPES):
        return True
    if isinstance(exc, PlaywrightError):
        message = str(exc).lower()
        return any(hint in message for hint in _TRANSIENT_PLAYWRIGHT_HINTS)
    return False


def should_retry(exc: BaseException, retries_left: int | None) -> bool:
    return is_transient(exc) and bool(retries_left) and retries_left > 0
