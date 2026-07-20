from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskEventBase(BaseModel):
    category: str = Field(..., max_length=80)
    severity: str = Field(..., max_length=16)
    title: str = Field(..., max_length=255)
    content: str
    source_url: str = Field(..., max_length=512)
    source_name: str = Field(default="", max_length=128)
    occurred_at: Optional[datetime] = None
    sentiment: str = Field(default="neutral", max_length=16)
    extra_payload: dict = Field(default_factory=dict)


class RiskEventCreate(RiskEventBase):
    company_id: UUID


class RiskEventRead(RiskEventBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
