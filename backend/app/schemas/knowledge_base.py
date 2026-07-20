from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeBaseContextResponse(BaseModel):
    company_name: str
    system_prompt: str
    risk_digest: list[dict[str, str]]


class KnowledgeBaseSyncResponse(BaseModel):
    mode: str = Field(
        ...,
        description="payload_only 表示仅返回待写入 FastGPT 的数据；synced 表示已提交到外部接口。",
    )
    payload: dict
    upstream_status: Optional[int] = None


class KnowledgeBaseChatRequest(BaseModel):
    company_id: Optional[UUID] = None
    company_name: Optional[str] = None
    question: str = Field(..., min_length=1)
    max_events: int = Field(default=8, ge=1, le=50)


class KnowledgeBaseChatResponse(BaseModel):
    company_name: str
    answer: str
    risk_digest: list[dict[str, str]]
