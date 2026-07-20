from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisReportBase(BaseModel):
    report_type: str = Field(..., max_length=80)
    title: str = Field(..., max_length=255)
    summary: str = ""
    snapshot: dict = Field(default_factory=dict)
    model_name: str = Field(default="fastgpt", max_length=120)


class AnalysisReportCreate(AnalysisReportBase):
    company_id: UUID


class AnalysisReportRead(AnalysisReportBase):
    id: UUID
    company_id: UUID
    generated_at: datetime
    created_at: datetime
    updated_at: datetime

