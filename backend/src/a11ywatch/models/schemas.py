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
    status: Literal["queued"] = "queued"


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
