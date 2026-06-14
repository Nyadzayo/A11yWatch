from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

from a11ywatch.scanning.types import RawViolation


class PlaywrightScanner:
    """Real scanner: one headless Chromium per scan, reused across pages.

    Sync API — intended to run inside a (sync) worker process, never in an async
    request handler. The engine calls ``close()`` in a finally block (R7).
    """

    def __init__(self, *, page_timeout_ms: int = 30_000) -> None:
        self._page_timeout_ms = page_timeout_ms
        self._axe = Axe()
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(headless=True)
        except BaseException:
            self._pw.stop()  # don't leak the driver subprocess if launch fails
            raise

    def scan_page(self, url: str) -> list[RawViolation]:
        context = self._browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, timeout=self._page_timeout_ms, wait_until="load")
            results = self._axe.run(page)
        finally:
            page.close()
            context.close()
        return _to_raw_violations(url, results.response)

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            self._pw.stop()


def _to_raw_violations(url: str, response: dict) -> list[RawViolation]:
    raw: list[RawViolation] = []
    for violation in response.get("violations", []):
        for node in violation.get("nodes", []):
            target = node.get("target")
            target_str = " ".join(target) if isinstance(target, list) else target
            raw.append(
                RawViolation(
                    page_url=url,
                    rule_id=violation.get("id"),
                    impact=violation.get("impact"),
                    help=violation.get("help"),
                    help_url=violation.get("helpUrl"),
                    target=target_str,
                    html_snippet=node.get("html"),
                )
            )
    return raw
