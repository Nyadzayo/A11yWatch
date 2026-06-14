from dataclasses import dataclass


@dataclass
class RawViolation:
    """One accessibility issue on one element, as produced by the scanner."""

    page_url: str
    rule_id: str
    impact: str | None = None
    help: str | None = None
    help_url: str | None = None
    target: str | None = None
    html_snippet: str | None = None


@dataclass
class ScanViolation:
    """A RawViolation plus its stable diff fingerprint."""

    page_url: str
    rule_id: str
    impact: str | None
    help: str | None
    help_url: str | None
    target: str | None
    html_snippet: str | None
    fingerprint: str


@dataclass
class ScanResult:
    pages_scanned: int
    violations: list[ScanViolation]
    failed_pages: int = 0

    @property
    def fingerprints(self) -> set[str]:
        return {v.fingerprint for v in self.violations}
