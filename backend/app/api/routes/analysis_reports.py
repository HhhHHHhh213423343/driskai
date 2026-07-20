from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.models import AnalysisReport, Company
from app.schemas.analysis_report import AnalysisReportCreate, AnalysisReportRead
from app.schemas.agent_analysis import ComposeAnalysisReportRequest
from app.services.agent_analysis import compose_comprehensive_report
from app.utils.pydantic import model_to_dict


router = APIRouter(tags=["analysis-reports"])


def serialize_analysis_report(report: AnalysisReport) -> AnalysisReportRead:
    return AnalysisReportRead(
        id=report.id,
        company_id=report.company_id,
        report_type=report.report_type,
        title=report.title,
        summary=report.summary,
        snapshot=report.snapshot,
        model_name=report.model_name,
        generated_at=report.generated_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/analysis-reports",
    response_model=AnalysisReportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_report(
    payload: AnalysisReportCreate,
    db: Session = Depends(db_session.get_db),
) -> AnalysisReportRead:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    report = AnalysisReport(**model_to_dict(payload))
    db.add(report)
    db.commit()
    db.refresh(report)
    return serialize_analysis_report(report)


@router.get(
    "/companies/{company_id}/analysis-reports",
    response_model=list[AnalysisReportRead],
)
def list_analysis_reports(
    company_id: UUID,
    report_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_session.get_db),
) -> list[AnalysisReportRead]:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    statement = select(AnalysisReport).where(AnalysisReport.company_id == company_id)
    if report_type:
        statement = statement.where(AnalysisReport.report_type == report_type)
    statement = statement.order_by(AnalysisReport.generated_at.desc()).limit(limit)

    reports = db.execute(statement).scalars()
    return [serialize_analysis_report(report) for report in reports]


@router.post(
    "/analysis-reports/compose",
    response_model=AnalysisReportRead,
    status_code=status.HTTP_201_CREATED,
)
def compose_analysis_report(
    payload: ComposeAnalysisReportRequest,
    db: Session = Depends(db_session.get_db),
) -> AnalysisReportRead:
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")
    if not payload.report_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要一个 report_type。")

    try:
        report = compose_comprehensive_report(
            db,
            company_id=payload.company_id,
            report_types=payload.report_types,
            title=payload.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return serialize_analysis_report(report)


@router.get(
    "/companies/{company_id}/analysis-reports/latest",
    response_model=AnalysisReportRead,
)
def get_latest_analysis_report(
    company_id: UUID,
    report_type: Optional[str] = Query(default=None),
    db: Session = Depends(db_session.get_db),
) -> AnalysisReportRead:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公司不存在。")

    statement = select(AnalysisReport).where(AnalysisReport.company_id == company_id)
    if report_type:
        statement = statement.where(AnalysisReport.report_type == report_type)
    statement = statement.order_by(AnalysisReport.generated_at.desc()).limit(1)

    report = db.execute(statement).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有找到分析报告。")

    return serialize_analysis_report(report)
