import uuid
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.api.errors import api_error
from a11ywatch.core.db import get_session
from a11ywatch.core.security import decode_token
from a11ywatch.jobs import queue as job_queue
from a11ywatch.models.tables import User

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise api_error(401, "unauthorized", "Authentication required")
    subject = decode_token(creds.credentials)
    if subject is None:
        raise api_error(401, "unauthorized", "Invalid or expired token")
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise api_error(401, "unauthorized", "Invalid token subject") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise api_error(401, "unauthorized", "User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def get_scan_queue() -> Queue:
    return job_queue.get_scan_queue()


ScanQueueDep = Annotated[Queue, Depends(get_scan_queue)]
