from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.schemas.agent_analysis import AgentAnalysisPreview
from app.services.agent_analysis import build_agent_preview, fetch_agent_risk_events


router = APIRouter(prefix="/agent-analysis", tags=["agent-analysis"])


@router.get("/preview", response_model=AgentAnalysisPreview)
def preview_agent_analysis(
    company_id: Optional[UUID] = Query(default=None),
    company_name: Optional[str] = Query(default=None),
    category: str = Query(..., pattern="^(macro|operations|finance|legal|brand)$"),
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(db_session.get_db),
) -> AgentAnalysisPreview:
    try:
        company, risk_events = fetch_agent_risk_events(
            db,
            company_id=company_id,
            company_name=company_name,
            category=category,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return AgentAnalysisPreview(
        **build_agent_preview(
            company=company,
            category=category,
            risk_events=risk_events,
        )
    )
