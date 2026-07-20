from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import Company, RiskEvent
from app.schemas.risk_event import RiskEventCreate, RiskEventRead
from app.utils.pydantic import model_to_dict


router = APIRouter(tags=["risk-events"])


def serialize_risk_event(risk_event: RiskEvent) -> RiskEventRead:
    return RiskEventRead(
        id=risk_event.id,
        company_id=risk_event.company_id,
        category=risk_event.category,
        severity=risk_event.severity,
        title=risk_event.title,
        content=risk_event.content,
        source_url=risk_event.source_url,
        source_name=risk_event.source_name,
        occurred_at=risk_event.occurred_at,
        sentiment=risk_event.sentiment,
        extra_payload=risk_event.extra_payload,
        created_at=risk_event.created_at,
        updated_at=risk_event.updated_at,
    )


@router.get(
    "/companies/{company_id}/risk-events",
    response_model=list[RiskEventRead],
)
def list_company_risk_events(
    company_id: UUID,
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(db_session.get_db),
) -> list[RiskEventRead]:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    statement = select(RiskEvent).where(RiskEvent.company_id == company_id)
    if category:
        statement = statement.where(RiskEvent.category == category)
    if severity:
        statement = statement.where(RiskEvent.severity == severity)
    statement = statement.order_by(
        RiskEvent.occurred_at.desc().nullslast(),
        RiskEvent.created_at.desc(),
    ).limit(limit)

    events = db.execute(statement).scalars()
    return [serialize_risk_event(item) for item in events]


@router.post(
    "/risk-events",
    response_model=RiskEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_risk_event(
    payload: RiskEventCreate,
    db: Session = Depends(db_session.get_db),
) -> RiskEventRead:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    risk_event = RiskEvent(**model_to_dict(payload))
    db.add(risk_event)
    db.commit()
    db.refresh(risk_event)
    return serialize_risk_event(risk_event)
