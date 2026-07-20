from __future__ import annotations

from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.schemas.knowledge_base import (
    KnowledgeBaseChatRequest,
    KnowledgeBaseChatResponse,
    KnowledgeBaseContextResponse,
    KnowledgeBaseSyncResponse,
)
from app.services.fastgpt import FastGPTService
from app.services.risk_context import (
    build_risk_digest,
    build_system_prompt,
    fetch_recent_risk_events,
)


router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/context", response_model=KnowledgeBaseContextResponse)
def get_knowledge_base_context(
    company_id: Optional[UUID] = Query(default=None),
    company_name: Optional[str] = Query(default=None),
    question: str = Query(default=""),
    max_events: int = Query(default=8, ge=1, le=50),
    db: Session = Depends(db_session.get_db),
) -> KnowledgeBaseContextResponse:
    try:
        company, risk_events = fetch_recent_risk_events(
            db,
            company_id=company_id,
            company_name=company_name,
            limit=max_events,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    risk_digest = build_risk_digest(risk_events)
    return KnowledgeBaseContextResponse(
        company_name=company.name,
        system_prompt=build_system_prompt(
            company=company,
            risk_events=risk_events,
            question=question,
        ),
        risk_digest=risk_digest,
    )


@router.post("/chat", response_model=KnowledgeBaseChatResponse)
async def ask_knowledge_base(
    payload: KnowledgeBaseChatRequest,
    db: Session = Depends(db_session.get_db),
) -> KnowledgeBaseChatResponse:
    try:
        company, risk_events = fetch_recent_risk_events(
            db,
            company_id=payload.company_id,
            company_name=payload.company_name,
            limit=payload.max_events,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    question = payload.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="问题内容不能为空。",
        )

    risk_digest = build_risk_digest(risk_events)
    system_prompt = build_system_prompt(
        company=company,
        risk_events=risk_events,
        question=question,
    )
    service = FastGPTService()
    try:
        answer = await service.create_chat_completion(
            company_name=company.name,
            question=question,
            system_prompt=system_prompt,
            risk_digest=risk_digest,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"FastGPT 对话请求失败: {exc}",
        ) from exc

    return KnowledgeBaseChatResponse(
        company_name=company.name,
        answer=answer,
        risk_digest=risk_digest,
    )


@router.post("/sync", response_model=KnowledgeBaseSyncResponse)
async def sync_knowledge_base_context(
    company_id: Optional[UUID] = Query(default=None),
    company_name: Optional[str] = Query(default=None),
    max_events: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(db_session.get_db),
) -> KnowledgeBaseSyncResponse:
    try:
        company, risk_events = fetch_recent_risk_events(
            db,
            company_id=company_id,
            company_name=company_name,
            limit=max_events,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    risk_digest = build_risk_digest(risk_events)
    system_prompt = build_system_prompt(company=company, risk_events=risk_events)
    service = FastGPTService()
    payload = service.build_dataset_payload(
        company_name=company.name,
        system_prompt=system_prompt,
        risk_digest=risk_digest,
    )
    try:
        mode, upstream_status = await service.sync_dataset_payload(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"FastGPT 数据集同步失败: {exc}",
        ) from exc

    return KnowledgeBaseSyncResponse(
        mode=mode,
        payload=payload,
        upstream_status=upstream_status,
    )
