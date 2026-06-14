import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from a11ywatch.core.security import hash_password
from a11ywatch.models.tables import Project, Scan, User, Violation
from a11ywatch.scanning.persist import persist_scan_result
from a11ywatch.scanning.types import ScanResult, ScanViolation


def _sv(fingerprint, *, url="https://ex.com/a", rule="image-alt", target="img"):
    return ScanViolation(
        page_url=url,
        rule_id=rule,
        impact="serious",
        help=None,
        help_url=None,
        target=target,
        html_snippet=None,
        fingerprint=fingerprint,
    )


async def _project(session):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    session.add(project)
    await session.flush()
    return project


async def test_persist_writes_violations_and_counts(db_session):
    project = await _project(db_session)
    scan = Scan(project_id=project.id, trigger="on_demand", status="running")
    db_session.add(scan)
    await db_session.flush()

    result = ScanResult(pages_scanned=2, violations=[_sv("fp1"), _sv("fp2", target="h1")])
    diff = await persist_scan_result(db_session, scan, result)

    assert scan.status == "succeeded"
    assert scan.pages_scanned == 2
    assert scan.total_issues == 2
    assert scan.new_issues == 2  # first scan -> everything new
    assert diff.new_count == 2
    count = await db_session.scalar(
        select(func.count()).select_from(Violation).where(Violation.scan_id == scan.id)
    )
    assert count == 2

    project = await db_session.get(Project, project.id)
    assert project.status == "idle"
    assert project.last_scan_id == scan.id


async def test_persist_diffs_against_previous_successful_scan(db_session):
    project = await _project(db_session)
    prev = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="succeeded",
        finished_at=datetime.now(UTC),
    )
    db_session.add(prev)
    await db_session.flush()
    for fp in ("fp1", "fp2"):
        db_session.add(
            Violation(
                scan_id=prev.id,
                project_id=project.id,
                page_url="https://ex.com/a",
                rule_id="r",
                fingerprint=fp,
            )
        )
    await db_session.flush()

    scan = Scan(project_id=project.id, trigger="on_demand", status="running")
    db_session.add(scan)
    await db_session.flush()
    result = ScanResult(pages_scanned=1, violations=[_sv("fp2"), _sv("fp3", target="x")])
    diff = await persist_scan_result(db_session, scan, result)

    assert diff.new == {"fp3"}
    assert diff.resolved == {"fp1"}
    assert scan.new_issues == 1
    assert scan.resolved_issues == 1


async def test_persist_dedups_duplicate_fingerprints(db_session):
    project = await _project(db_session)
    scan = Scan(project_id=project.id, trigger="on_demand", status="running")
    db_session.add(scan)
    await db_session.flush()

    result = ScanResult(pages_scanned=1, violations=[_sv("dup"), _sv("dup", target="other")])
    await persist_scan_result(db_session, scan, result)

    assert scan.total_issues == 1
    count = await db_session.scalar(
        select(func.count()).select_from(Violation).where(Violation.scan_id == scan.id)
    )
    assert count == 1


async def test_persist_ignores_succeeded_scan_with_null_finished_at(db_session):
    project = await _project(db_session)
    ghost = Scan(project_id=project.id, trigger="scheduled", status="succeeded", finished_at=None)
    db_session.add(ghost)
    await db_session.flush()
    db_session.add(
        Violation(
            scan_id=ghost.id, project_id=project.id, page_url="u", rule_id="r", fingerprint="ghost"
        )
    )
    good = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="succeeded",
        finished_at=datetime.now(UTC),
    )
    db_session.add(good)
    await db_session.flush()
    db_session.add(
        Violation(
            scan_id=good.id, project_id=project.id, page_url="u", rule_id="r", fingerprint="fp1"
        )
    )
    await db_session.flush()

    scan = Scan(project_id=project.id, trigger="on_demand", status="running")
    db_session.add(scan)
    await db_session.flush()
    diff = await persist_scan_result(
        db_session, scan, ScanResult(pages_scanned=1, violations=[_sv("fp1")])
    )
    assert diff.new == set()
    assert diff.resolved == set()
