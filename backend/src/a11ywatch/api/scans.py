import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from a11ywatch.api.deps import CurrentUser, PaginationDep, ScanQueueDep, SessionDep
from a11ywatch.api.errors import api_error
from a11ywatch.core.config import settings
from a11ywatch.jobs.dispatch import enqueue_scan
from a11ywatch.models.schemas import Page, ScanOut, ScanTriggerResponse, ViolationOut
from a11ywatch.models.tables import Project, Scan, User, Violation

router = APIRouter(prefix="/api/v1", tags=["scans"])


async def _get_owned_project(session, user: User, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise api_error(404, "not_found", "Project not found")
    return project


async def _get_owned_scan(session, user: User, scan_id: uuid.UUID) -> Scan:
    scan = await session.get(Scan, scan_id)
    if scan is not None:
        project = await session.get(Project, scan.project_id)
        if project is not None and project.user_id == user.id:
            return scan
    raise api_error(404, "not_found", "Scan not found")


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
    response: Response,
) -> ScanTriggerResponse:
    project = await _get_owned_project(session, current_user, project_id)
    scan, created = await enqueue_scan(
        session,
        project,
        "on_demand",
        redis_conn=queue.connection,
        queue=queue,
        site_timeout_seconds=settings.scan_site_timeout_seconds,
        max_retries=settings.scan_max_retries,
    )
    if scan is None:
        raise api_error(409, "conflict", "A scan is already in progress for this project")
    if not created:
        response.status_code = status.HTTP_200_OK  # idempotent: returning the in-flight scan
    return ScanTriggerResponse(scan_id=scan.id, job_id=scan.job_id or "", status=scan.status)


@router.get("/scans/{scan_id}", response_model=ScanOut)
async def get_scan(scan_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> Scan:
    return await _get_owned_scan(session, current_user, scan_id)


@router.get("/scans/{scan_id}/violations", response_model=Page[ViolationOut])
async def list_violations(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
    pagination: PaginationDep,
    impact: Annotated[str | None, Query()] = None,
) -> Page[ViolationOut]:
    scan = await _get_owned_scan(session, current_user, scan_id)
    conds = [Violation.scan_id == scan.id]
    if impact is not None:
        conds.append(Violation.impact == impact)
    total = await session.scalar(select(func.count()).select_from(Violation).where(*conds))
    rows = (
        await session.scalars(
            select(Violation)
            .where(*conds)
            .order_by(Violation.created_at.asc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
    ).all()
    return Page[ViolationOut](
        items=[ViolationOut.model_validate(r) for r in rows],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )


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
