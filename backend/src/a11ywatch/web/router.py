import uuid
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from a11ywatch.api.deps import ScanQueueDep, SessionDep
from a11ywatch.api.errors import api_error
from a11ywatch.core.config import settings
from a11ywatch.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from a11ywatch.jobs.dispatch import enqueue_scan
from a11ywatch.models.tables import Project, Scan, User, Violation

router = APIRouter(tags=["dashboard"], include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

COOKIE_NAME = "a11ywatch_session"
_IMPACT_ORDER = ["critical", "serious", "moderate", "minor"]
# A full-site crawl can produce thousands of issues; cap how many we render per page.
_SCAN_DISPLAY_LIMIT = 200


async def current_dashboard_user(request: Request, session: SessionDep) -> User | None:
    """Resolve the logged-in user from the session cookie, or None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    sub = decode_token(token)
    if sub is None:
        return None
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        return None
    return await session.get(User, user_id)


DashboardUser = Annotated[User | None, Depends(current_dashboard_user)]


def verify_origin(request: Request) -> None:
    """Reject cross-site state-changing POSTs (login-CSRF guard for the cookie session).

    Same-origin form posts carry an Origin matching the Host (or omit it); a forged
    cross-site submit carries a foreign Origin, which we block.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    if urlsplit(origin).netloc != request.headers.get("host"):
        raise api_error(403, "forbidden", "Cross-site request blocked")


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        path="/",
    )


def _group_by_impact(violations: list[Violation]) -> list[dict]:
    buckets: dict[str, list[Violation]] = {}
    for v in violations:
        buckets.setdefault(v.impact or "unknown", []).append(v)
    ordered: list[dict] = []
    for impact in _IMPACT_ORDER:
        if impact in buckets:
            ordered.append({"impact": impact, "violations": buckets.pop(impact)})
    for impact, items in buckets.items():
        ordered.append({"impact": impact, "violations": items})
    return ordered


# --- auth ------------------------------------------------------------------ #
@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None, "error": None})


@router.post("/login", dependencies=[Depends(verify_origin)])
async def login_submit(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    create_account: Annotated[str | None, Form()] = None,
):
    email = email.strip().lower()
    # Validate password length BEFORE looking up the account, so a short password yields the
    # same response whether or not the email exists (no account-enumeration oracle).
    if create_account and len(password) < 8:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Password must be at least 8 characters"},
            status_code=400,
        )
    user = await session.scalar(select(User).where(User.email == email))
    if create_account and user is None:
        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(select(User).where(User.email == email))

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Invalid credentials"},
            status_code=401,
        )

    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, create_access_token(str(user.id)))
    return response


@router.post("/logout", dependencies=[Depends(verify_origin)])
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# --- pages ----------------------------------------------------------------- #
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: SessionDep, user: DashboardUser):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    projects = (
        await session.scalars(
            select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
        )
    ).all()
    return templates.TemplateResponse(
        request, "dashboard.html", {"user": user, "projects": projects}
    )


@router.post("/projects", dependencies=[Depends(verify_origin)])
async def create_project_web(
    request: Request,
    session: SessionDep,
    user: DashboardUser,
    name: Annotated[str, Form()],
    base_url: Annotated[str, Form()],
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    base_url = base_url.strip()
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        projects = (
            await session.scalars(
                select(Project)
                .where(Project.user_id == user.id)
                .order_by(Project.created_at.desc())
            )
        ).all()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "projects": projects,
                "error": "URL must start with http:// or https://",
            },
            status_code=400,
        )
    project = Project(user_id=user.id, name=name.strip(), base_url=base_url)
    session.add(project)
    await session.commit()
    return RedirectResponse(f"/projects/{project.id}", status_code=303)


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(
    project_id: uuid.UUID, request: Request, session: SessionDep, user: DashboardUser
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        return RedirectResponse("/", status_code=303)
    scans = (
        await session.scalars(
            select(Scan)
            .where(Scan.project_id == project.id)
            .order_by(Scan.created_at.desc())
            .limit(25)
        )
    ).all()
    return templates.TemplateResponse(
        request, "project.html", {"user": user, "project": project, "scans": scans}
    )


@router.post("/projects/{project_id}/scan", dependencies=[Depends(verify_origin)])
async def scan_now(
    project_id: uuid.UUID,
    session: SessionDep,
    user: DashboardUser,
    queue: ScanQueueDep,
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        return RedirectResponse("/", status_code=303)
    scan, _created = await enqueue_scan(
        session,
        project,
        "on_demand",
        redis_conn=queue.connection,
        queue=queue,
        site_timeout_seconds=settings.scan_site_timeout_seconds,
        max_retries=settings.scan_max_retries,
    )
    if scan is not None:
        return RedirectResponse(f"/scans/{scan.id}", status_code=303)
    return RedirectResponse(f"/projects/{project.id}", status_code=303)


@router.get("/scans/{scan_id}", response_class=HTMLResponse)
async def scan_detail(
    scan_id: uuid.UUID, request: Request, session: SessionDep, user: DashboardUser
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    scan = await session.get(Scan, scan_id)
    if scan is None:
        return RedirectResponse("/", status_code=303)
    project = await session.get(Project, scan.project_id)
    if project is None or project.user_id != user.id:
        return RedirectResponse("/", status_code=303)
    total = await session.scalar(
        select(func.count()).select_from(Violation).where(Violation.scan_id == scan.id)
    )
    impact_rows = (
        await session.execute(
            select(Violation.impact, func.count())
            .where(Violation.scan_id == scan.id)
            .group_by(Violation.impact)
        )
    ).all()
    impact_counts = {(impact or "unknown"): count for impact, count in impact_rows}
    # Render only a bounded sample so a huge scan can't produce a multi-megabyte page.
    sample = list(
        await session.scalars(
            select(Violation).where(Violation.scan_id == scan.id).limit(_SCAN_DISPLAY_LIMIT)
        )
    )
    return templates.TemplateResponse(
        request,
        "scan.html",
        {
            "user": user,
            "scan": scan,
            "project": project,
            "groups": _group_by_impact(sample),
            "impact_counts": impact_counts,
            "total": total or 0,
            "shown": len(sample),
            "truncated": (total or 0) > len(sample),
        },
    )
