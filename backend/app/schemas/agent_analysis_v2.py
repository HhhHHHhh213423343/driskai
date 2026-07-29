from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CoverageStatus = Literal[
    "available",
    "partial",
    "stale",
    "no_hit",
    "not_connected",
    "fetch_failed",
    "not_applicable",
]


class MetricCoverage(BaseModel):
    key: str
    label: str
    status: CoverageStatus
    weight: float = 1
    reason: str = ""
    source_ids: list[str] = Field(default_factory=list)
    as_of: Optional[datetime] = None
    applicable: bool = True


class QualityComponents(BaseModel):
    completeness: int = 0
    freshness: int = 0
    authority: int = 0
    corroboration: int = 0


class DataQualityV2(BaseModel):
    status: Literal["complete", "partial", "insufficient"]
    coverage_percent: int
    evidence_count: int
    warnings: list[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None
    boundary_summary: str = ""
    components: QualityComponents = Field(default_factory=QualityComponents)
    metric_coverage: list[MetricCoverage] = Field(default_factory=list)


class SourceCoverageV2(BaseModel):
    code: str
    source: str
    status: Literal["success", "no_hit", "not_connected", "failed", "partial"]
    authority: Literal["official", "association", "aggregator", "licensed", "internal"] = "official"
    points: int = 0
    message: str = ""
    categories: list[str] = Field(default_factory=list)
    last_checked_at: Optional[datetime] = None


class AgentAnalysisPreviewV2(BaseModel):
    company_name: str
    category: Literal["macro", "operations", "finance", "legal", "brand"]
    report_type: str
    retrieval_stage: str
    industry_template: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    data_quality: DataQualityV2
    source_coverage: list[SourceCoverageV2] = Field(default_factory=list)
    generated_at: datetime
