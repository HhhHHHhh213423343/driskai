from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyBase(BaseModel):
    name: str = Field(..., max_length=255)
    credit_code: Optional[str] = Field(default=None, max_length=64)
    industry: Optional[str] = Field(default=None, max_length=128)
    region: Optional[str] = Field(default=None, max_length=128)
    description: str = ""
    official_website: str = ""
    company_profile: dict = Field(default_factory=dict)


class CompanyCreate(CompanyBase):
    pass


class CompanyRead(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class CompanySearchIngestRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    stock_code: str = Field(default="", max_length=32)
    market: str = Field(default="", max_length=32)
    max_results_per_source: int = Field(default=5, ge=1, le=20)
    enabled_source_codes: list[str] = Field(default_factory=list)
    trigger_ingestion: bool = True


class CompanySearchIngestResponse(BaseModel):
    company: CompanyRead
    created: bool
    ingestion_run: Optional[dict] = None


class DashboardSummary(BaseModel):
    company: CompanyRead
    severity_breakdown: dict[str, int]
    category_breakdown: dict[str, int]
    latest_report_id: Optional[UUID] = None
