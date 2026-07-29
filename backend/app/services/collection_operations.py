from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, bindparam, text
from sqlalchemy.orm import Session

from app.services.authoritative_ingestion import (
    _ensure_retrieval_table,
    collect_authoritative_sources,
)
from app.services.source_registry import source_plan_for, source_to_dict


def _rows(
    db: Session,
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    result = db.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings()]


def ensure_collection_tables(db: Session) -> None:
    _ensure_retrieval_table(db)
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS authoritative_collection_runs (
            id VARCHAR(36) PRIMARY KEY,
            mode VARCHAR(24) NOT NULL,
            status VARCHAR(24) NOT NULL,
            company_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            inserted_count INTEGER NOT NULL DEFAULT 0,
            review_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP NULL,
            summary JSON NOT NULL
        )
    """))
    db.commit()


def get_company_source_plan(db: Session, company_id: Any) -> dict[str, Any]:
    key = str(company_id).replace("-", "")
    rows = _rows(
        db,
        """
        SELECT * FROM companies
        WHERE REPLACE(CAST(id AS TEXT), '-', '') = :company_key
        LIMIT 1
        """,
        {"company_key": key},
    )
    if not rows:
        raise ValueError("未找到目标公司。")
    company = rows[0]
    profile = company.get("company_profile") or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except (TypeError, ValueError, json.JSONDecodeError):
            profile = {}
    plugin, sources = source_plan_for(
        str(company.get("industry") or ""),
        str(company.get("name") or ""),
        profile,
    )
    return {
        "company_id": str(company.get("id")),
        "company_name": str(company.get("name") or ""),
        "industry": str(company.get("industry") or ""),
        "plugin": {
            "code": plugin.code,
            "name": plugin.name,
            "metric_keys": list(plugin.metric_keys),
        },
        "sources": [source_to_dict(source) for source in sources],
    }


def run_collection_batch(
    db: Session,
    *,
    mode: str = "daily",
    company_id: Any | None = None,
    max_companies: int = 100,
    max_documents_per_company: int = 80,
    backfill_years: int = 5,
    lookback_days: int = 2,
) -> dict[str, Any]:
    if mode not in {"daily", "backfill"}:
        raise ValueError("mode 仅支持 daily 或 backfill。")
    ensure_collection_tables(db)
    params: dict[str, Any] = {"limit": max_companies}
    where = ""
    if company_id is not None:
        where = "WHERE REPLACE(CAST(id AS TEXT), '-', '') = :company_key"
        params["company_key"] = str(company_id).replace("-", "")
    companies = _rows(
        db,
        f"SELECT id, name FROM companies {where} ORDER BY name LIMIT :limit",
        params,
    )
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    insert = text("""
        INSERT INTO authoritative_collection_runs
        (id, mode, status, company_count, completed_count, failed_count,
         inserted_count, review_count, started_at, finished_at, summary)
        VALUES
        (:id, :mode, 'running', :company_count, 0, 0, 0, 0,
         :started_at, NULL, :summary)
    """).bindparams(bindparam("summary", type_=JSON))
    db.execute(
        insert,
        {
            "id": run_id,
            "mode": mode,
            "company_count": len(companies),
            "started_at": started_at,
            "summary": {"companies": [], "errors": []},
        },
    )
    db.commit()

    results = []
    errors = []
    inserted_count = 0
    review_count = 0
    for company in companies:
        try:
            result = collect_authoritative_sources(
                db,
                company_id=company["id"],
                max_documents=max_documents_per_company,
                mode=mode,
                backfill_years=backfill_years,
                lookback_days=lookback_days,
            )
            results.append(result)
            inserted_count += int(result.get("ingested_event_count") or 0)
            review_count += int(result.get("manual_review_count") or 0)
        except Exception as exc:
            db.rollback()
            errors.append(
                {
                    "company_id": str(company["id"]),
                    "company_name": str(company.get("name") or ""),
                    "error": str(exc)[:500],
                }
            )

    finished_at = datetime.now(timezone.utc)
    status = "completed" if not errors else "partial" if results else "failed"
    summary = {
        "companies": [
            {
                "company_id": result["company_id"],
                "company_name": result["company_name"],
                "industry_plugin": result["industry_plugin"],
                "ingested_event_count": result["ingested_event_count"],
                "manual_review_count": result["manual_review_count"],
            }
            for result in results
        ],
        "errors": errors,
        "lookback_days": lookback_days,
        "backfill_years": backfill_years,
    }
    update = text("""
        UPDATE authoritative_collection_runs
        SET status=:status, completed_count=:completed_count,
            failed_count=:failed_count, inserted_count=:inserted_count,
            review_count=:review_count, finished_at=:finished_at,
            summary=:summary
        WHERE id=:id
    """).bindparams(bindparam("summary", type_=JSON))
    db.execute(
        update,
        {
            "id": run_id,
            "status": status,
            "completed_count": len(results),
            "failed_count": len(errors),
            "inserted_count": inserted_count,
            "review_count": review_count,
            "finished_at": finished_at,
            "summary": summary,
        },
    )
    db.commit()
    return {
        "id": run_id,
        "mode": mode,
        "status": status,
        "company_count": len(companies),
        "completed_count": len(results),
        "failed_count": len(errors),
        "inserted_count": inserted_count,
        "review_count": review_count,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "summary": summary,
    }


def list_collection_runs(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    ensure_collection_tables(db)
    return _rows(
        db,
        """
        SELECT * FROM authoritative_collection_runs
        ORDER BY started_at DESC LIMIT :limit
        """,
        {"limit": limit},
    )


def list_review_queue(
    db: Session,
    *,
    company_id: Any | None = None,
    status: str = "pending",
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_collection_tables(db)
    conditions = ["status = :status"]
    params: dict[str, Any] = {"status": status, "limit": limit}
    if company_id is not None:
        conditions.append(
            "REPLACE(CAST(company_id AS TEXT), '-', '') = :company_key"
        )
        params["company_key"] = str(company_id).replace("-", "")
    return _rows(
        db,
        f"""
        SELECT * FROM evidence_review_queue
        WHERE {' AND '.join(conditions)}
        ORDER BY
          CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
          created_at DESC
        LIMIT :limit
        """,
        params,
    )


def resolve_review_item(
    db: Session,
    *,
    item_id: str,
    status: str,
    resolution_note: str = "",
) -> dict[str, Any]:
    if status not in {"verified", "rejected", "deferred"}:
        raise ValueError("核验状态仅支持 verified、rejected 或 deferred。")
    ensure_collection_tables(db)
    now = datetime.now(timezone.utc)
    result = db.execute(
        text("""
            UPDATE evidence_review_queue
            SET status=:status, resolution_note=:resolution_note, updated_at=:updated_at
            WHERE id=:id
        """),
        {
            "id": item_id,
            "status": status,
            "resolution_note": resolution_note[:1000],
            "updated_at": now,
        },
    )
    if result.rowcount == 0:
        raise ValueError("未找到待核验记录。")
    db.commit()
    rows = _rows(
        db,
        "SELECT * FROM evidence_review_queue WHERE id=:id LIMIT 1",
        {"id": item_id},
    )
    return rows[0]
