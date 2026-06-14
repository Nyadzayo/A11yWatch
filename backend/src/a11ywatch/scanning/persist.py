from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.models.tables import Project, Scan, Violation
from a11ywatch.scanning.diff import FingerprintDiff, diff_fingerprints
from a11ywatch.scanning.types import ScanResult, ScanViolation


async def persist_scan_result(
    session: AsyncSession, scan: Scan, result: ScanResult
) -> FingerprintDiff:
    """Write violations, diff against the previous successful scan, finalize the scan.

    Returns the fingerprint diff (NEW/RESOLVED) so the caller can enqueue alerts.
    """
    previous = await session.scalar(
        select(Scan)
        .where(
            Scan.project_id == scan.project_id,
            Scan.status == "succeeded",
            Scan.id != scan.id,
            Scan.finished_at.is_not(None),
        )
        .order_by(Scan.finished_at.desc(), Scan.created_at.desc())
        .limit(1)
    )
    previous_fingerprints: set[str] = set()
    if previous is not None:
        previous_fingerprints = set(
            await session.scalars(
                select(Violation.fingerprint).where(Violation.scan_id == previous.id)
            )
        )

    diff = diff_fingerprints(result.fingerprints, previous_fingerprints)

    # One row per distinct fingerprint (enforced by uq_violation_scan_fingerprint).
    unique: dict[str, ScanViolation] = {}
    for v in result.violations:
        unique.setdefault(v.fingerprint, v)
    for v in unique.values():
        session.add(
            Violation(
                scan_id=scan.id,
                project_id=scan.project_id,
                page_url=v.page_url,
                rule_id=v.rule_id,
                impact=v.impact,
                help=v.help,
                help_url=v.help_url,
                target=v.target,
                html_snippet=v.html_snippet,
                fingerprint=v.fingerprint,
            )
        )

    finished = datetime.now(UTC)
    scan.status = "succeeded"
    scan.pages_scanned = result.pages_scanned
    scan.total_issues = len(unique)
    scan.new_issues = diff.new_count
    scan.resolved_issues = diff.resolved_count
    scan.finished_at = finished

    project = await session.get(Project, scan.project_id)
    if project is not None:
        project.status = "idle"
        project.last_scan_at = finished
        project.last_scan_id = scan.id

    await session.commit()
    return diff
