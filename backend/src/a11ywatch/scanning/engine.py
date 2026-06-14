import logging
from collections.abc import Sequence
from typing import Protocol

from a11ywatch.scanning.fingerprint import compute_fingerprint
from a11ywatch.scanning.types import RawViolation, ScanResult, ScanViolation

log = logging.getLogger(__name__)


class PageScanner(Protocol):
    """One browser per scan, reused across pages, closed by the engine."""

    def scan_page(self, url: str) -> list[RawViolation]: ...

    def close(self) -> None: ...


def run_scan(urls: Sequence[str], scanner: PageScanner, *, page_cap: int) -> ScanResult:
    """Scan up to ``page_cap`` URLs with ``scanner``, fingerprinting each issue.

    A single page failure (e.g. a per-page timeout) is logged and skipped so one bad page
    can't sink the whole scan. If EVERY attempted page fails, the last error is re-raised so
    the job fails (and can retry). The scanner is always closed (R7), even on error.
    """
    violations: list[ScanViolation] = []
    pages_scanned = 0
    failed_pages = 0
    last_error: Exception | None = None
    try:
        for url in list(urls)[:page_cap]:
            try:
                page_violations = scanner.scan_page(url)
            except Exception as exc:
                failed_pages += 1
                last_error = exc
                log.warning("scan_page failed for %s: %r", url, exc)
                continue
            pages_scanned += 1
            for rv in page_violations:
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
    if pages_scanned == 0 and last_error is not None:
        raise last_error
    return ScanResult(pages_scanned=pages_scanned, violations=violations, failed_pages=failed_pages)
