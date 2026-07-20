from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SourceSpecRead(BaseModel):
    code: str
    name: str
    categories: list[str]
    requires_api_key: bool = False
    rate_limit: str = ""
    enabled: bool = True
    notes: str = ""


class DailyIngestionRequest(BaseModel):
    company_ids: list[UUID] = Field(default_factory=list)
    company_names: list[str] = Field(default_factory=list)
    stock_code_by_company: dict[str, str] = Field(default_factory=dict)
    max_results_per_source: int = Field(default=5, ge=1, le=50)
    enabled_source_codes: list[str] = Field(default_factory=list)
    dry_run: bool = False


class IngestionRunRead(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    requested_company_count: int
    scanned_company_count: int
    total_raw_count: int
    inserted_count: int
    skipped_count: int
    source_breakdown: dict
    failures: list
    summary: dict
    created_at: datetime
    updated_at: datetime


class IngestionTrendPoint(BaseModel):
    label: str
    value: int


class IngestionDashboardSummary(BaseModel):
    total_events: int
    last_7_days_events: int
    high_priority_events: int
    report_count: int
    latest_scan_label: str
    latest_change_label: str
    trend_series: list[IngestionTrendPoint]
    category_distribution: dict[str, int]
    report_output: dict[str, int]
    source_breakdown: dict[str, int]
    latest_run: Optional[IngestionRunRead] = None
