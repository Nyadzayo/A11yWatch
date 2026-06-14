from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from a11ywatch.api.deps import CurrentUser, SessionDep
from a11ywatch.api.errors import api_error
from a11ywatch.core.security import create_access_token, hash_password, verify_password
from a11ywatch.models.schemas import LoginRequest, Token, UserCreate, UserOut
from a11ywatch.models.tables import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep) -> User:
    existing = await session.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise api_error(409, "conflict", "Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise api_error(409, "conflict", "Email already registered") from exc
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, session: SessionDep) -> Token:
    email = payload.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise api_error(401, "unauthorized", "Invalid credentials")
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> User:
    return current_user
