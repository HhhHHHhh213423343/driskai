from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


BACKEND_PATH = Path(__file__).parents[1] / "backend"
APP_PATH = BACKEND_PATH / "app"
SERVICES_PATH = APP_PATH / "services"
for package_name, package_path in (
    ("app", APP_PATH),
    ("app.services", SERVICES_PATH),
):
    package = sys.modules.setdefault(package_name, types.ModuleType(package_name))
    package.__path__ = [str(package_path)]

SERVICE_PATH = SERVICES_PATH / "collection_operations.py"
SPEC = importlib.util.spec_from_file_location(
    "app.services.collection_operations",
    SERVICE_PATH,
)
assert SPEC and SPEC.loader
OPERATIONS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OPERATIONS
SPEC.loader.exec_module(OPERATIONS)


def _database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT,
                company_profile TEXT
            )
        """))
        connection.execute(text("""
            INSERT INTO companies (id, name, industry, company_profile)
            VALUES
              ('bank-1', '测试银行', '货币金融服务', '{}'),
              ('pharma-1', '测试制药', '生物医药', '{}')
        """))
    return Session(engine)


def test_company_source_plan_is_industry_aware() -> None:
    db = _database()
    plan = OPERATIONS.get_company_source_plan(db, "bank-1")
    source_codes = {source["code"] for source in plan["sources"]}

    assert plan["plugin"]["code"] == "banking"
    assert "nfra_penalties" in source_codes
    assert "pbc_penalties" in source_codes


def test_batch_run_records_counts_and_parameters(monkeypatch) -> None:
    db = _database()
    calls = []

    def fake_collect(_db, **kwargs):
        calls.append(kwargs)
        company_id = str(kwargs["company_id"])
        return {
            "company_id": company_id,
            "company_name": company_id,
            "industry_plugin": "banking" if company_id == "bank-1" else "pharma",
            "ingested_event_count": 2,
            "manual_review_count": 3,
        }

    monkeypatch.setattr(OPERATIONS, "collect_authoritative_sources", fake_collect)
    result = OPERATIONS.run_collection_batch(
        db,
        mode="backfill",
        max_companies=10,
        max_documents_per_company=40,
        backfill_years=5,
    )

    assert result["status"] == "completed"
    assert result["company_count"] == 2
    assert result["inserted_count"] == 4
    assert result["review_count"] == 6
    assert all(call["mode"] == "backfill" for call in calls)
    assert all(call["backfill_years"] == 5 for call in calls)


def test_review_queue_can_be_resolved_without_deleting_audit_history() -> None:
    db = _database()
    OPERATIONS.ensure_collection_tables(db)
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO evidence_review_queue
            (id, company_id, source_code, source_name, category, query_url,
             reason, priority, status, created_at, updated_at, resolution_note)
            VALUES
            ('review-1', 'bank-1', 'judicial_disclosure', '中国裁判文书网',
             'legal', 'https://wenshu.court.gov.cn/', '需要登录后核验原文',
             'high', 'pending', :now, :now, '')
        """),
        {"now": now},
    )
    db.commit()

    pending = OPERATIONS.list_review_queue(db, company_id="bank-1")
    assert [item["id"] for item in pending] == ["review-1"]

    resolved = OPERATIONS.resolve_review_item(
        db,
        item_id="review-1",
        status="verified",
        resolution_note="已在官方原文中确认。",
    )
    assert resolved["status"] == "verified"
    assert resolved["resolution_note"] == "已在官方原文中确认。"
    assert OPERATIONS.list_review_queue(db, company_id="bank-1") == []
    assert OPERATIONS.list_review_queue(
        db,
        company_id="bank-1",
        status="verified",
    )[0]["id"] == "review-1"
