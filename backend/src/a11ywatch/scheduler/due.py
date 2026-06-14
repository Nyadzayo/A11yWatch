from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.models.tables import Project


async def select_due_projects(session: AsyncSession, now: datetime) -> list[Project]:
    """Idle projects whose last scan is older than their scan frequency (or never scanned).

    Frequency is per-project, so we filter in Python over the idle set. Fine for the MVP;
    revisit with a SQL interval predicate if the idle set grows large.
    """
    idle = (await session.scalars(select(Project).where(Project.status == "idle"))).all()
    due: list[Project] = []
    for project in idle:
        if project.last_scan_at is None:
            due.append(project)
        elif project.last_scan_at <= now - timedelta(minutes=project.scan_frequency_minutes):
            due.append(project)
    return due
