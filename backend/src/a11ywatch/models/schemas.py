import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _validate_http_url(value: str | None) -> str | None:
    if value is None:
        return value
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ValueError("must be an http(s) URL")
    return value


class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        local, _, domain = v.partition("@")
        if not local or "." not in domain:
            raise ValueError("invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def _min_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str
    base_url: str
    scan_frequency_minutes: int = 1440
    sitemap_url: str | None = None
    url_list: list[str] | None = None
    max_pages: int | None = None

    _check_urls = field_validator("base_url", "sitemap_url")(_validate_http_url)


class ProjectUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    scan_frequency_minutes: int | None = None
    sitemap_url: str | None = None
    url_list: list[str] | None = None
    max_pages: int | None = None

    _check_urls = field_validator("base_url", "sitemap_url")(_validate_http_url)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data):
        # Explicit JSON null for a NOT NULL column is a client error (422), not a 500.
        if isinstance(data, dict):
            for field in ("name", "base_url", "scan_frequency_minutes"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return data


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    scan_frequency_minutes: int
    sitemap_url: str | None
    url_list: list[str] | None
    max_pages: int | None
    status: str
    created_at: datetime
    updated_at: datetime


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    trigger: str
    job_id: str | None
    pages_scanned: int
    total_issues: int
    new_issues: int
    resolved_issues: int
    created_at: datetime


class ScanTriggerResponse(BaseModel):
    scan_id: uuid.UUID
    job_id: str
    status: Literal["queued", "running"] = "queued"


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    page_url: str
    rule_id: str
    impact: str | None
    help: str | None
    help_url: str | None
    target: str | None
    html_snippet: str | None
    fingerprint: str
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


# --- Alert channels -------------------------------------------------------- #
ALLOWED_ALERT_EVENTS = {"new_issues"}


def validate_channel_target(channel_type: str, target: str) -> None:
    """Raise ValueError if ``target`` is malformed for ``channel_type``."""
    if channel_type == "email":
        local, _, domain = target.partition("@")
        if not local or "." not in domain:
            raise ValueError("email target must be a valid email address")
    elif not (target.startswith("http://") or target.startswith("https://")):
        raise ValueError(f"{channel_type} target must be an http(s) URL")


def _validate_events(value: list[str] | None) -> list[str] | None:
    if value is None:
        return value
    if not value:
        # An empty subscription is a no-op; mute a channel with `enabled: false` instead.
        raise ValueError("events must list at least one event type")
    unsupported = sorted(set(value) - ALLOWED_ALERT_EVENTS)
    if unsupported:
        raise ValueError(f"unsupported events: {unsupported}")
    return value


class AlertChannelCreate(BaseModel):
    type: Literal["email", "webhook", "slack"]
    target: str
    events: list[str] | None = None
    enabled: bool = True

    _check_events = field_validator("events")(_validate_events)

    @model_validator(mode="after")
    def _check_target(self) -> "AlertChannelCreate":
        validate_channel_target(self.type, self.target)
        return self


class AlertChannelUpdate(BaseModel):
    target: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None

    _check_events = field_validator("events")(_validate_events)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data):
        # Omitting a field means "leave unchanged" (exclude_unset); an explicit JSON null is
        # a client error. To stop alerts on a channel, set enabled: false rather than nulling.
        if isinstance(data, dict):
            for field in ("target", "enabled", "events"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return data


class AlertChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    target: str
    events: list[str] | None
    enabled: bool
    created_at: datetime


# --- Branding (white-label report settings) -------------------------------- #
class BrandingUpdate(BaseModel):
    company_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    report_footer: str | None = None

    _check_logo = field_validator("logo_url")(_validate_http_url)


class BrandingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    company_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    report_footer: str | None = None
