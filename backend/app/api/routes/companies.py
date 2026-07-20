from __future__ import annotations

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import AnalysisReport, Company, RiskEvent
from app.schemas.company import (
    CompanyCreate,
    CompanyRead,
    CompanySearchIngestRequest,
    CompanySearchIngestResponse,
    DashboardSummary,
)
from app.services.akshare_profile import refresh_company_akshare_profile
from app.services.generic_ingestion import DailyIngestionService
from app.services.qichacha_profile import refresh_company_qichacha_profile
from app.services.risk_context import get_company_by_ref
from app.utils.pydantic import model_to_dict


router = APIRouter(prefix="/companies", tags=["companies"])


def serialize_company(company: Company) -> CompanyRead:
    return CompanyRead(
        id=company.id,
        name=company.name,
        credit_code=company.credit_code,
        industry=company.industry,
        region=company.region,
        description=company.description,
        official_website=company.official_website,
        company_profile=company.company_profile,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.get("", response_model=list[CompanyRead])
def list_companies(db: Session = Depends(db_session.get_db)) -> list[CompanyRead]:
    companies = db.execute(select(Company).order_by(Company.created_at.desc())).scalars()
    return [serialize_company(company) for company in companies]


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(db_session.get_db),
) -> CompanyRead:
    existing = db.execute(select(Company).where(Company.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="公司名称已存在。",
        )

    company = Company(**model_to_dict(payload))
    db.add(company)
    db.commit()
    db.refresh(company)
    return serialize_company(company)


@router.post("/search-and-ingest", response_model=CompanySearchIngestResponse)
async def search_and_ingest_company(
    payload: CompanySearchIngestRequest,
    db: Session = Depends(db_session.get_db),
) -> CompanySearchIngestResponse:
    company_name = payload.name.strip()
    if not company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="公司名称不能为空。",
        )

    company = get_company_by_ref(db, company_name=company_name)
    created = False
    if not company:
        company = Company(name=company_name)
        db.add(company)
        created = True

    profile = dict(company.company_profile or {})
    if payload.stock_code.strip():
        profile["stock_code"] = payload.stock_code.strip()
    if payload.market.strip():
        profile["market"] = payload.market.strip()
    if profile != (company.company_profile or {}):
        company.company_profile = profile

    db.commit()
    db.refresh(company)
    company = await refresh_company_akshare_profile(db, company, force=True)
    company = await refresh_company_qichacha_profile(db, company)

    ingestion_payload = None
    if payload.trigger_ingestion:
        stock_lookup = {}
        stock_code = str(company.company_profile.get("stock_code") or "").strip()
        if stock_code:
            stock_lookup[company.name] = stock_code

        run = await DailyIngestionService(db).run(
            company_ids=[company.id],
            stock_code_by_company=stock_lookup,
            max_results_per_source=payload.max_results_per_source,
            enabled_source_codes=payload.enabled_source_codes,
            dry_run=False,
        )
        ingestion_payload = {
            "id": str(run.id),
            "status": run.status,
            "scanned_company_count": run.scanned_company_count,
            "total_raw_count": run.total_raw_count,
            "inserted_count": run.inserted_count,
            "skipped_count": run.skipped_count,
            "source_breakdown": run.source_breakdown or {},
            "failures": run.failures or [],
        }

    return CompanySearchIngestResponse(
        company=serialize_company(company),
        created=created,
        ingestion_run=ingestion_payload,
    )


@router.get("/resolve", response_model=CompanyRead)
def resolve_company(
    name: str = Query(..., min_length=1),
    db: Session = Depends(db_session.get_db),
) -> CompanyRead:
    company = get_company_by_ref(db, company_name=name)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")
    return serialize_company(company)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: UUID, db: Session = Depends(db_session.get_db)) -> CompanyRead:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")
    return serialize_company(company)


@router.get("/{company_id}/dashboard", response_model=DashboardSummary)
def get_dashboard_summary(
    company_id: UUID,
    db: Session = Depends(db_session.get_db),
) -> DashboardSummary:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    risk_events = list(
        db.execute(
            select(RiskEvent).where(RiskEvent.company_id == company_id)
        ).scalars()
    )
    latest_report = db.execute(
        select(AnalysisReport)
        .where(AnalysisReport.company_id == company_id)
        .order_by(AnalysisReport.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return DashboardSummary(
        company=serialize_company(company),
        severity_breakdown=dict(Counter(item.severity for item in risk_events)),
        category_breakdown=dict(Counter(item.category for item in risk_events)),
        latest_report_id=latest_report.id if latest_report else None,
    )
