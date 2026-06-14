import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from a11ywatch.api.deps import CurrentUser, SessionDep, get_owned_project
from a11ywatch.api.errors import api_error
from a11ywatch.models.schemas import (
    AlertChannelCreate,
    AlertChannelOut,
    AlertChannelUpdate,
    validate_channel_target,
)
from a11ywatch.models.tables import AlertChannel

router = APIRouter(prefix="/api/v1/projects", tags=["alert-channels"])


async def _get_owned_channel(session, user, project_id, channel_id) -> AlertChannel:
    await get_owned_project(session, user, project_id)
    channel = await session.get(AlertChannel, channel_id)
    if channel is None or channel.project_id != project_id:
        raise api_error(404, "not_found", "Alert channel not found")
    return channel


@router.post(
    "/{project_id}/alert-channels",
    response_model=AlertChannelOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    project_id: uuid.UUID,
    payload: AlertChannelCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> AlertChannel:
    await get_owned_project(session, current_user, project_id)
    channel = AlertChannel(
        project_id=project_id,
        type=payload.type,
        target=payload.target,
        events=payload.events or ["new_issues"],
        enabled=payload.enabled,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.get("/{project_id}/alert-channels", response_model=list[AlertChannelOut])
async def list_channels(
    project_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> list[AlertChannel]:
    await get_owned_project(session, current_user, project_id)
    rows = (
        await session.scalars(
            select(AlertChannel)
            .where(AlertChannel.project_id == project_id)
            .order_by(AlertChannel.created_at.asc())
        )
    ).all()
    return list(rows)


@router.patch("/{project_id}/alert-channels/{channel_id}", response_model=AlertChannelOut)
async def update_channel(
    project_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: AlertChannelUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> AlertChannel:
    channel = await _get_owned_channel(session, current_user, project_id, channel_id)
    updates = payload.model_dump(exclude_unset=True)
    if "target" in updates:
        try:
            validate_channel_target(channel.type, updates["target"])
        except ValueError as exc:
            raise api_error(422, "validation_error", str(exc)) from exc
    for key, value in updates.items():
        setattr(channel, key, value)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.delete("/{project_id}/alert-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    project_id: uuid.UUID,
    channel_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    channel = await _get_owned_channel(session, current_user, project_id, channel_id)
    await session.delete(channel)
    await session.commit()
