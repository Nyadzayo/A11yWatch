import pytest

from a11ywatch.scanning.engine import run_scan
from a11ywatch.scanning.types import RawViolation


class FakeScanner:
    """Stands in for the real Playwright+axe scanner (one browser per scan)."""

    def __init__(self, per_page=None, raise_on=None, raise_all=False):
        self.closed = False
        self.scanned = []
        self._per_page = per_page or {}
        self._raise_on = raise_on
        self._raise_all = raise_all

    def scan_page(self, url):
        self.scanned.append(url)
        if self._raise_all or url == self._raise_on:
            raise TimeoutError(f"page failed: {url}")
        return self._per_page.get(url, [])

    def close(self):
        self.closed = True


def test_run_scan_respects_page_cap():
    scanner = FakeScanner()
    urls = [f"https://ex.com/{i}" for i in range(10)]
    result = run_scan(urls, scanner, page_cap=3)
    assert result.pages_scanned == 3
    assert len(scanner.scanned) == 3
    assert scanner.closed is True


def test_run_scan_assigns_fingerprints():
    rv = RawViolation(page_url="https://ex.com/a", rule_id="image-alt", target="img")
    scanner = FakeScanner(per_page={"https://ex.com/a": [rv]})
    result = run_scan(["https://ex.com/a"], scanner, page_cap=50)
    assert len(result.violations) == 1
    assert result.violations[0].fingerprint
    assert result.fingerprints == {result.violations[0].fingerprint}


def test_run_scan_skips_a_failed_page_and_continues():
    rv = RawViolation(page_url="https://ex.com/a", rule_id="image-alt", target="img")
    scanner = FakeScanner(per_page={"https://ex.com/a": [rv]}, raise_on="https://ex.com/b")
    result = run_scan(
        ["https://ex.com/a", "https://ex.com/b", "https://ex.com/c"], scanner, page_cap=50
    )
    assert result.pages_scanned == 2  # a and c succeeded
    assert result.failed_pages == 1  # b skipped
    assert len(result.violations) == 1
    assert scanner.closed is True


def test_run_scan_raises_and_closes_when_all_pages_fail():
    scanner = FakeScanner(raise_all=True)
    with pytest.raises(TimeoutError):
        run_scan(["https://ex.com/a", "https://ex.com/b"], scanner, page_cap=50)
    assert scanner.closed is True  # R7: browser closed even on total failure
