from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import IngestionRun
from app.schemas.ingestion import (
    DailyIngestionRequest,
    IngestionDashboardSummary,
    IngestionRunRead,
    SourceSpecRead,
)
from app.services.generic_ingestion import (
    DailyIngestionService,
    SourceSpec,
    create_dashboard_summary,
)


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def serialize_source_spec(spec: SourceSpec, *, enabled: bool | None = None) -> SourceSpecRead:
    return SourceSpecRead(
        code=spec.code,
        name=spec.name,
        categories=list(spec.categories),
        requires_api_key=spec.requires_api_key,
        rate_limit=spec.rate_limit,
        enabled=spec.enabled if enabled is None else enabled,
        notes=spec.notes,
    )


def serialize_ingestion_run(run: IngestionRun) -> IngestionRunRead:
    created_at = run.created_at or run.started_at or datetime.now(timezone.utc)
    updated_at = run.updated_at or run.finished_at or created_at
    return IngestionRunRead(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        requested_company_count=run.requested_company_count,
        scanned_company_count=run.scanned_company_count,
        total_raw_count=run.total_raw_count,
        inserted_count=run.inserted_count,
        skipped_count=run.skipped_count,
        source_breakdown=run.source_breakdown or {},
        failures=run.failures or [],
        summary=run.summary or {},
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("/sources", response_model=list[SourceSpecRead])
def list_ingestion_sources(
    db: Session = Depends(db_session.get_db),
) -> list[SourceSpecRead]:
    service = DailyIngestionService(db)
    return [
        serialize_source_spec(adapter.spec, enabled=adapter.is_available())
        for adapter in service.adapters
    ]


@router.post("/daily-run", response_model=IngestionRunRead)
async def run_daily_ingestion(
    payload: DailyIngestionRequest,
    db: Session = Depends(db_session.get_db),
) -> IngestionRunRead:
    service = DailyIngestionService(db)
    run = await service.run(
        company_ids=payload.company_ids,
        company_names=payload.company_names,
        stock_code_by_company=payload.stock_code_by_company,
        max_results_per_source=payload.max_results_per_source,
        enabled_source_codes=payload.enabled_source_codes,
        dry_run=payload.dry_run,
    )
    return serialize_ingestion_run(run)


@router.get("/runs/latest", response_model=Optional[IngestionRunRead])
def get_latest_ingestion_run(
    db: Session = Depends(db_session.get_db),
) -> Optional[IngestionRunRead]:
    run = db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()
    return serialize_ingestion_run(run) if run else None


@router.get("/dashboard-summary", response_model=IngestionDashboardSummary)
def get_ingestion_dashboard_summary(
    max_sources: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(db_session.get_db),
) -> IngestionDashboardSummary:
    summary = create_dashboard_summary(db)
    latest_run = summary.pop("latest_run")
    source_breakdown = summary.get("source_breakdown") or {}
    summary["source_breakdown"] = dict(
        sorted(source_breakdown.items(), key=lambda item: item[1], reverse=True)[:max_sources]
    )
    summary["latest_run"] = serialize_ingestion_run(latest_run) if latest_run else None
    return IngestionDashboardSummary(**summary)
