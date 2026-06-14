import uuid

from fastapi import APIRouter
from sqlalchemy import select

from a11ywatch.api.deps import CurrentUser, SessionDep, get_owned_project
from a11ywatch.models.schemas import BrandingOut, BrandingUpdate
from a11ywatch.models.tables import Branding

router = APIRouter(prefix="/api/v1/projects", tags=["branding"])


async def _get_branding(session, project_id: uuid.UUID) -> Branding | None:
    return await session.scalar(select(Branding).where(Branding.project_id == project_id))


@router.get("/{project_id}/branding", response_model=BrandingOut)
async def get_branding(
    project_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> BrandingOut:
    await get_owned_project(session, current_user, project_id)
    branding = await _get_branding(session, project_id)
    if branding is None:
        # Branding is optional; report empty defaults until the customer sets it.
        return BrandingOut(project_id=project_id)
    return BrandingOut.model_validate(branding)


@router.put("/{project_id}/branding", response_model=BrandingOut)
async def put_branding(
    project_id: uuid.UUID,
    payload: BrandingUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> BrandingOut:
    await get_owned_project(session, current_user, project_id)
    branding = await _get_branding(session, project_id)
    # PUT is replace semantics: fields omitted from the body are cleared.
    values = payload.model_dump()
    if branding is None:
        branding = Branding(project_id=project_id, **values)
        session.add(branding)
    else:
        for key, value in values.items():
            setattr(branding, key, value)
    await session.commit()
    await session.refresh(branding)
    return BrandingOut.model_validate(branding)
