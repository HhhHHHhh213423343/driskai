from __future__ import annotations

import secrets
from typing import Optional, Union
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session as db_session
from app.models import Company
from app.schemas.company_profile import (
    CompanyProfileComplete,
    CompanyProfileFailure,
    CompanyProfileHeartbeat,
    CompanyProfileRunCreate,
    CompanyProfileRunStartRead,
    CompanyProfileSnapshotRead,
    CompanyProfileStateRead,
    CompanyProfileWorkerClaim,
    CompanyProfileWorkerJob,
)
from app.services.company_profile import (
    claim_next_run,
    complete_run,
    create_or_reuse_run,
    fail_run,
    get_profile_state,
    heartbeat_run,
    latest_snapshot,
)


router = APIRouter(tags=["company-profile"])


def require_collection_key(
    x_collection_key: Optional[str] = Header(default=None),
) -> None:
    expected = get_settings().collection_api_key.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务端尚未配置 COLLECTION_API_KEY。",
        )
    if not x_collection_key or not secrets.compare_digest(x_collection_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少有效的采集任务访问密钥。",
        )


def get_company(db: Session, company_id: UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="公司不存在。")
    return company


@router.post(
    "/companies/{company_id}/company-profile/runs",
    response_model=CompanyProfileRunStartRead,
)
def start_company_profile_run(
    company_id: UUID,
    payload: CompanyProfileRunCreate,
    db: Session = Depends(db_session.get_db),
) -> CompanyProfileRunStartRead:
    company = get_company(db, company_id)
    return CompanyProfileRunStartRead(
        **create_or_reuse_run(db, company, force=payload.force)
    )


@router.get(
    "/companies/{company_id}/company-profile",
    response_model=CompanyProfileStateRead,
)
def read_company_profile(
    company_id: UUID,
    db: Session = Depends(db_session.get_db),
) -> CompanyProfileStateRead:
    company = get_company(db, company_id)
    return CompanyProfileStateRead(**get_profile_state(db, company))


@router.get("/companies/{company_id}/company-profile/export")
def export_company_profile(
    company_id: UUID,
    db: Session = Depends(db_session.get_db),
) -> Response:
    company = get_company(db, company_id)
    snapshot = latest_snapshot(db, company.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="尚无可导出的完整企业全景 Excel。")
    encoded = quote(snapshot.excel_filename)
    return Response(
        content=snapshot.excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Content-Length": str(len(snapshot.excel_file)),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/company-profile/worker/claim",
    response_model=CompanyProfileWorkerJob,
    responses={204: {"description": "当前没有待领取任务"}},
    dependencies=[Depends(require_collection_key)],
)
def claim_company_profile_run(
    payload: CompanyProfileWorkerClaim,
    db: Session = Depends(db_session.get_db),
) -> Union[CompanyProfileWorkerJob, Response]:
    job = claim_next_run(db, payload.worker_id)
    if job is None:
        return Response(status_code=204)
    return CompanyProfileWorkerJob(**job)


@router.post(
    "/company-profile/worker/runs/{run_id}/heartbeat",
    dependencies=[Depends(require_collection_key)],
)
def heartbeat_company_profile_run(
    run_id: UUID,
    payload: CompanyProfileHeartbeat,
    db: Session = Depends(db_session.get_db),
) -> dict:
    try:
        return heartbeat_run(
            db,
            run_id,
            payload.worker_id,
            progress_current=payload.progress_current,
            current_module=payload.current_module,
            module_statuses=payload.module_statuses,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/company-profile/worker/runs/{run_id}/complete",
    response_model=CompanyProfileSnapshotRead,
    dependencies=[Depends(require_collection_key)],
)
def complete_company_profile_run(
    run_id: UUID,
    payload: CompanyProfileComplete,
    db: Session = Depends(db_session.get_db),
) -> CompanyProfileSnapshotRead:
    try:
        return CompanyProfileSnapshotRead(**complete_run(db, run_id, payload))
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/company-profile/worker/runs/{run_id}/fail",
    dependencies=[Depends(require_collection_key)],
)
def fail_company_profile_run(
    run_id: UUID,
    payload: CompanyProfileFailure,
    db: Session = Depends(db_session.get_db),
) -> dict:
    try:
        return fail_run(db, run_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
