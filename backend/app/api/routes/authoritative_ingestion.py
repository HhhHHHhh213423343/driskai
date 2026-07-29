from __future__ import annotations

import os
import secrets
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.services.collection_operations import (
    get_company_source_plan,
    list_collection_runs,
    list_review_queue,
    resolve_review_item,
    run_collection_batch,
)
from app.services.authoritative_ingestion import collect_authoritative_sources


router = APIRouter(prefix="/authoritative-ingestion", tags=["authoritative-ingestion"])


class ReviewResolution(BaseModel):
    status: str
    resolution_note: str = Field(default="", max_length=1000)


def require_collection_key(
    x_collection_key: Optional[str] = Header(default=None),
) -> None:
    expected = os.getenv("COLLECTION_API_KEY", "").strip()
    if expected and (
        not x_collection_key
        or not secrets.compare_digest(x_collection_key, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少有效的采集任务访问密钥。",
        )


@router.post("/companies/{company_id}/run")
def run_authoritative_ingestion(
    company_id: UUID,
    max_documents: int = Query(default=60, ge=5, le=200),
    mode: str = Query(default="daily", pattern="^(daily|backfill)$"),
    backfill_years: int = Query(default=5, ge=1, le=10),
    lookback_days: int = Query(default=2, ge=1, le=30),
    db: Session = Depends(db_session.get_db),
) -> dict[str, Any]:
    try:
        return collect_authoritative_sources(
            db,
            company_id=company_id,
            max_documents=max_documents,
            mode=mode,
            backfill_years=backfill_years,
            lookback_days=lookback_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/companies/{company_id}/source-plan")
def company_source_plan(
    company_id: UUID,
    db: Session = Depends(db_session.get_db),
) -> dict[str, Any]:
    try:
        return get_company_source_plan(db, company_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/daily/run", dependencies=[Depends(require_collection_key)])
def run_daily_ingestion(
    company_id: Optional[UUID] = Query(default=None),
    mode: str = Query(default="daily", pattern="^(daily|backfill)$"),
    max_companies: int = Query(default=100, ge=1, le=1000),
    max_documents_per_company: int = Query(default=80, ge=5, le=200),
    backfill_years: int = Query(default=5, ge=1, le=10),
    lookback_days: int = Query(default=2, ge=1, le=30),
    db: Session = Depends(db_session.get_db),
) -> dict[str, Any]:
    return run_collection_batch(
        db,
        mode=mode,
        company_id=company_id,
        max_companies=max_companies,
        max_documents_per_company=max_documents_per_company,
        backfill_years=backfill_years,
        lookback_days=lookback_days,
    )


@router.get("/runs")
def collection_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_session.get_db),
) -> list[dict[str, Any]]:
    return list_collection_runs(db, limit=limit)


@router.get("/review-queue")
def review_queue(
    company_id: Optional[UUID] = Query(default=None),
    review_status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(db_session.get_db),
) -> list[dict[str, Any]]:
    return list_review_queue(
        db,
        company_id=company_id,
        status=review_status,
        limit=limit,
    )


@router.patch(
    "/review-queue/{item_id}",
    dependencies=[Depends(require_collection_key)],
)
def update_review_item(
    item_id: str,
    payload: ReviewResolution,
    db: Session = Depends(db_session.get_db),
) -> dict[str, Any]:
    try:
        return resolve_review_item(
            db,
            item_id=item_id,
            status=payload.status,
            resolution_note=payload.resolution_note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
