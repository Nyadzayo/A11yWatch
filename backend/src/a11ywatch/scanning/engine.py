from collections.abc import Sequence
from typing import Protocol

from a11ywatch.scanning.fingerprint import compute_fingerprint
from a11ywatch.scanning.types import RawViolation, ScanResult, ScanViolation


class PageScanner(Protocol):
    """One browser per scan, reused across pages, closed by the engine."""

    def scan_page(self, url: str) -> list[RawViolation]: ...

    def close(self) -> None: ...


def run_scan(urls: Sequence[str], scanner: PageScanner, *, page_cap: int) -> ScanResult:
    """Scan up to ``page_cap`` URLs with ``scanner``, fingerprinting each issue.

    The scanner is always closed (R7), including when a page scan raises.
    """
    violations: list[ScanViolation] = []
    pages_scanned = 0
    try:
        for url in list(urls)[:page_cap]:
            pages_scanned += 1
            # Per-page error handling (skip/retry, per-page timeouts) is deferred to Phase 4;
            # for now a page failure aborts the scan — the scanner is still closed below (R7).
            for rv in scanner.scan_page(url):
                fingerprint = compute_fingerprint(rv.rule_id, rv.page_url, rv.target or "")
                violations.append(
                    ScanViolation(
                        page_url=rv.page_url,
                        rule_id=rv.rule_id,
                        impact=rv.impact,
                        help=rv.help,
                        help_url=rv.help_url,
                        target=rv.target,
                        html_snippet=rv.html_snippet,
                        fingerprint=fingerprint,
                    )
                )
    finally:
        scanner.close()
    return ScanResult(pages_scanned=pages_scanned, violations=violations)
