from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyProfileRunCreate(BaseModel):
    force: bool = False


class CompanyProfileWorkerClaim(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)


class CompanyProfileHeartbeat(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    progress_current: int = Field(default=0, ge=0, le=8)
    current_module: str = Field(default="", max_length=64)
    module_statuses: dict = Field(default_factory=dict)


class CompanyProfileComplete(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    captured_at: datetime
    sop_version: str = Field(..., min_length=1, max_length=64)
    company_code: str = Field(default="", max_length=128)
    module_statuses: dict
    normalized_data: dict
    raw_data: dict = Field(default_factory=dict)
    excel_filename: str = Field(..., min_length=1, max_length=512)
    excel_sha256: str = Field(..., min_length=64, max_length=64)
    excel_base64: str = Field(..., min_length=1)


class CompanyProfileFailure(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    status: Literal["waiting_for_login", "waiting_for_captcha", "failed"]
    error_code: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=4000)
    module_statuses: dict = Field(default_factory=dict)


class CompanyProfileRunRead(BaseModel):
    id: UUID
    company_id: UUID
    status: str
    mode: str
    force: bool
    worker_id: str
    progress_current: int
    progress_total: int
    current_module: str
    error_code: str
    error_message: str
    module_statuses: dict
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None


class CompanyProfileSnapshotRead(BaseModel):
    id: UUID
    company_id: UUID
    run_id: UUID
    captured_at: datetime
    sop_version: str
    module_statuses: dict
    normalized_data: dict
    excel_filename: str
    excel_sha256: str


class CompanyProfileStateRead(BaseModel):
    enabled: bool
    company_name: str
    qyyjt_company_code: str = ""
    active_run: Optional[CompanyProfileRunRead] = None
    latest_run: Optional[CompanyProfileRunRead] = None
    latest_snapshot: Optional[CompanyProfileSnapshotRead] = None


class CompanyProfileRunStartRead(BaseModel):
    enabled: bool
    reused: bool
    run: Optional[CompanyProfileRunRead] = None
    snapshot: Optional[CompanyProfileSnapshotRead] = None


class CompanyProfileWorkerJob(BaseModel):
    run: CompanyProfileRunRead
    company: dict
