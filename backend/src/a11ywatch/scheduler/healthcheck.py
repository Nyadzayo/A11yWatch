import logging
from collections.abc import Callable

log = logging.getLogger(__name__)


def _default_get(url: str) -> None:
    import httpx

    httpx.get(url, timeout=5)


def ping_healthcheck(url: str, *, http_get: Callable[[str], object] | None = None) -> bool:
    """Best-effort ping of an external dead-man's-switch (e.g. Healthchecks.io) each cycle.

    A missed ping is what alerts the operator that the scheduler died, so the ping itself
    must never raise — a failed ping is logged and swallowed. Returns True if the ping was sent.
    """
    if not url:
        return False
    do_get = http_get or _default_get
    try:
        do_get(url)
        return True
    except Exception:
        log.warning("healthcheck ping failed", extra={"event": "healthcheck_failed", "url": url})
        return False
