import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from a11ywatch.api.deps import CurrentUser, PaginationDep, ScanQueueDep, SessionDep
from a11ywatch.api.errors import api_error
from a11ywatch.jobs.noop import noop_scan
from a11ywatch.models.schemas import Page, ScanOut, ScanTriggerResponse
from a11ywatch.models.tables import Project, Scan, User

router = APIRouter(prefix="/api/v1", tags=["scans"])


async def _get_owned_project(session, user: User, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise api_error(404, "not_found", "Project not found")
    return project


@router.post(
    "/projects/{project_id}/scans",
    response_model=ScanTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_scan(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
    queue: ScanQueueDep,
) -> ScanTriggerResponse:
    project = await _get_owned_project(session, current_user, project_id)
    scan = Scan(project_id=project.id, trigger="on_demand", status="queued")
    session.add(scan)
    await session.flush()  # assign scan.id without committing

    # Enqueue off the event loop; if it fails, the uncommitted scan rolls back (no orphan row).
    job = await run_in_threadpool(queue.enqueue, noop_scan, str(scan.id))
    scan.job_id = job.id
    await session.commit()
    await session.refresh(scan)

    return ScanTriggerResponse(scan_id=scan.id, job_id=scan.job_id, status=scan.status)


@router.get("/scans/{scan_id}", response_model=ScanOut)
async def get_scan(scan_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> Scan:
    scan = await session.get(Scan, scan_id)
    if scan is not None:
        project = await session.get(Project, scan.project_id)
        if project is not None and project.user_id == current_user.id:
            return scan
    raise api_error(404, "not_found", "Scan not found")


@router.get("/projects/{project_id}/scans", response_model=Page[ScanOut])
async def list_scans(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
    pagination: PaginationDep,
) -> Page[ScanOut]:
    project = await _get_owned_project(session, current_user, project_id)
    base = select(Scan).where(Scan.project_id == project.id)
    total = await session.scalar(
        select(func.count()).select_from(Scan).where(Scan.project_id == project.id)
    )
    rows = (
        await session.scalars(
            base.order_by(Scan.created_at.desc()).limit(pagination.limit).offset(pagination.offset)
        )
    ).all()
    return Page[ScanOut](
        items=[ScanOut.model_validate(r) for r in rows],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )
