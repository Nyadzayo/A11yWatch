import httpx
from playwright.sync_api import Error as PlaywrightError

from a11ywatch.jobs.retry import is_transient, should_retry


def test_timeouts_and_connection_errors_are_transient():
    assert is_transient(TimeoutError("x"))
    assert is_transient(ConnectionError("x"))
    assert is_transient(httpx.ConnectError("refused"))


def test_playwright_timeout_and_network_errors_are_transient():
    assert is_transient(PlaywrightError("Timeout 30000ms exceeded"))
    assert is_transient(PlaywrightError("net::ERR_CONNECTION_REFUSED"))


def test_value_error_and_unknown_playwright_are_permanent():
    assert not is_transient(ValueError("bad url"))
    assert not is_transient(PlaywrightError("some non-network selector error"))


def test_permanent_navigation_errors_are_not_retried():
    assert not is_transient(PlaywrightError("net::ERR_NAME_NOT_RESOLVED"))
    assert not is_transient(PlaywrightError("net::ERR_CERT_AUTHORITY_INVALID"))
    assert not is_transient(PlaywrightError("net::ERR_UNSAFE_PORT"))


def test_should_retry_only_for_transient_with_retries_left():
    assert should_retry(TimeoutError(), retries_left=2) is True
    assert should_retry(TimeoutError(), retries_left=0) is False
    assert should_retry(TimeoutError(), retries_left=None) is False
    assert should_retry(ValueError(), retries_left=2) is False
