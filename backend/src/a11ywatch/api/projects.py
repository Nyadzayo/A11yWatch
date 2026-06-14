import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from a11ywatch.api.deps import CurrentUser, PaginationDep, SessionDep
from a11ywatch.api.errors import api_error
from a11ywatch.models.schemas import Page, ProjectCreate, ProjectOut, ProjectUpdate
from a11ywatch.models.tables import Project, User

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


async def _get_owned(session, user: User, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise api_error(404, "not_found", "Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, current_user: CurrentUser, session: SessionDep
) -> Project:
    project = Project(user_id=current_user.id, **payload.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("", response_model=Page[ProjectOut])
async def list_projects(
    current_user: CurrentUser, session: SessionDep, pagination: PaginationDep
) -> Page[ProjectOut]:
    base = select(Project).where(Project.user_id == current_user.id)
    total = await session.scalar(
        select(func.count()).select_from(Project).where(Project.user_id == current_user.id)
    )
    rows = (
        await session.scalars(
            base.order_by(Project.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
    ).all()
    return Page[ProjectOut](
        items=[ProjectOut.model_validate(r) for r in rows],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> Project:
    return await _get_owned(session, current_user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> Project:
    project = await _get_owned(session, current_user, project_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> None:
    project = await _get_owned(session, current_user, project_id)
    await session.delete(project)
    await session.commit()
