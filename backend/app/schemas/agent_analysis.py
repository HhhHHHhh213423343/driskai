from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentSourceRead(BaseModel):
    title: str
    source_name: str
    source_url: str
    source_tag: str = "来源"
    page_hint: str = ""
    published_at: Optional[datetime] = None
    severity: str = ""
    sentiment: str = ""


class AgentMetricRead(BaseModel):
    key: str
    label: str
    value: str
    unit: str = ""
    delta: str = ""
    tone: str = "neutral"
    description: str = ""
    source_ids: list[str] = Field(default_factory=list)


class AgentSeriesPointRead(BaseModel):
    period: str
    value: float


class AgentSeriesRead(BaseModel):
    key: str
    label: str
    unit: str = ""
    points: list[AgentSeriesPointRead] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class AgentSectionRead(BaseModel):
    key: str
    title: str
    kind: str
    summary: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class AgentDataQualityRead(BaseModel):
    status: str
    coverage_percent: int = Field(ge=0, le=100)
    evidence_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class AgentAnalysisPreview(BaseModel):
    company_name: str
    category: str
    report_type: str
    retrieval_stage: str = Field(
        ...,
        description="risk_events_first 表示命中了结构化事件；knowledge_base_fallback 表示当前应回退到知识库。",
    )
    summary: str
    key_points: list[str]
    next_actions: list[str]
    sources: list[AgentSourceRead]
    metrics: list[AgentMetricRead] = Field(default_factory=list)
    series: list[AgentSeriesRead] = Field(default_factory=list)
    sections: list[AgentSectionRead] = Field(default_factory=list)
    data_quality: AgentDataQualityRead
    generated_at: datetime


class ComposeAnalysisReportRequest(BaseModel):
    company_id: UUID
    report_types: list[str] = Field(default_factory=list)
    title: str = ""
