from __future__ import annotations

import json
import importlib.util
import sys
import types
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

SERVICE_PATH = SERVICES_PATH / "agent_analysis_v2.py"
SPEC = importlib.util.spec_from_file_location("agent_analysis_v2_under_test", SERVICE_PATH)
assert SPEC and SPEC.loader
SERVICE_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SERVICE_MODULE
SPEC.loader.exec_module(SERVICE_MODULE)
build_agent_preview_v2 = SERVICE_MODULE.build_agent_preview_v2

SCHEMA_PATH = Path(__file__).parents[1] / "backend" / "app" / "schemas" / "agent_analysis_v2.py"
SCHEMA_SPEC = importlib.util.spec_from_file_location("agent_analysis_schema_under_test", SCHEMA_PATH)
assert SCHEMA_SPEC and SCHEMA_SPEC.loader
SCHEMA_MODULE = importlib.util.module_from_spec(SCHEMA_SPEC)
sys.modules[SCHEMA_SPEC.name] = SCHEMA_MODULE
SCHEMA_SPEC.loader.exec_module(SCHEMA_MODULE)


def _database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT,
                region TEXT,
                official_website TEXT,
                company_profile TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE risk_events (
                id TEXT PRIMARY KEY,
                company_id TEXT,
                category TEXT,
                severity TEXT,
                title TEXT,
                content TEXT,
                source_url TEXT,
                source_name TEXT,
                occurred_at TEXT,
                created_at TEXT,
                sentiment TEXT,
                extra_payload TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE ingestion_runs (
                id TEXT PRIMARY KEY,
                started_at TEXT,
                finished_at TEXT,
                summary TEXT,
                failures TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE macro_indicator_points (
                indicator_code TEXT,
                indicator_name TEXT,
                period TEXT,
                value REAL,
                unit TEXT,
                frequency TEXT,
                source_name TEXT,
                source_url TEXT,
                collected_at TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE macro_industry_events (
                dimension TEXT,
                title TEXT,
                summary TEXT,
                source_name TEXT,
                source_url TEXT,
                published_at TEXT,
                impact_direction TEXT,
                severity TEXT
            )
        """))
    return Session(engine)


def _insert_bank(db: Session) -> None:
    profile = {
        "akshare_profile": {
            "status": "available",
            "updated_at": "2026-07-20T00:00:00+00:00",
            "financial_abstract": [
                {"指标": "营业总收入", "20250630": 10000000000, "20260630": 11000000000},
                {"指标": "归母净利润", "20250630": 3000000000, "20260630": 3300000000},
                {"指标": "净息差", "20260630": 1.42},
                {"指标": "不良贷款率", "20260630": 1.35},
                {"指标": "核心一级资本充足率", "20260630": 13.9},
            ],
            "financial_indicators": [],
        }
    }
    db.execute(
        text("""
            INSERT INTO companies(id, name, industry, region, official_website, company_profile)
            VALUES ('bank-1', '测试银行', '货币金融服务', '北京', 'https://bank.example', :profile)
        """),
        {"profile": json.dumps(profile, ensure_ascii=False)},
    )
    db.execute(
        text("""
            INSERT INTO risk_events VALUES (
                'event-1', 'bank-1', 'legal', '重要', '监管处罚公告', '因贷款管理不到位受到处罚',
                'https://www.nfra.gov.cn/example', '国家金融监督管理总局',
                '2026-07-18T00:00:00+00:00', '2026-07-18T00:00:00+00:00', 'negative',
                '{"source_code":"nfra_penalties","source_authority_label":"监管机构"}'
            )
        """),
    )
    db.execute(
        text("""
            INSERT INTO ingestion_runs VALUES (
                'run-1', '2026-07-20T00:00:00+00:00', '2026-07-20T00:05:00+00:00',
                '{"enabled_sources":["cninfo_announcements","exchange_disclosure","nfra_penalties"]}', '[]'
            )
        """),
    )
    db.commit()


def test_bank_finance_uses_bank_specific_metrics() -> None:
    db = _database()
    _insert_bank(db)

    preview = build_agent_preview_v2(db, company_id="bank-1", category="finance")
    metric_keys = {item["key"] for item in preview["metrics"]}

    assert preview["industry_template"] == "banking"
    assert "net_interest_margin" in metric_keys
    assert "npl_ratio" in metric_keys
    assert "cet1_ratio" in metric_keys
    assert "debt_safety_margin" not in metric_keys
    assert preview["data_quality"]["coverage_percent"] < 100
    assert preview["data_quality"]["components"]["corroboration"] < 100
    assert SCHEMA_MODULE.AgentAnalysisPreviewV2(**preview).industry_template == "banking"


def test_bank_operations_does_not_show_manufacturing_funnel() -> None:
    db = _database()
    _insert_bank(db)

    preview = build_agent_preview_v2(db, company_id="bank-1", category="operations")
    metric_keys = {item["key"] for item in preview["metrics"]}
    section_keys = {item["key"] for item in preview["sections"]}

    assert "inventory_days" not in metric_keys
    assert "order_fulfillment" not in metric_keys
    assert "complaint_resolution" in metric_keys
    assert "system_availability" in metric_keys
    assert "bank_operations" in section_keys
    assert "operations_funnel" not in section_keys


def test_source_status_distinguishes_no_hit_from_not_connected() -> None:
    db = _database()
    _insert_bank(db)

    preview = build_agent_preview_v2(db, company_id="bank-1", category="legal")
    statuses = {item["code"]: item["status"] for item in preview["source_coverage"]}

    assert statuses["nfra_penalties"] == "success"
    assert statuses["cninfo_announcements"] == "no_hit"
    assert statuses["enterprise_credit"] == "not_connected"


def test_missing_legal_evidence_is_not_reported_as_zero_risk() -> None:
    db = _database()
    _insert_bank(db)

    preview = build_agent_preview_v2(db, company_id="bank-1", category="brand")
    metrics = {item["key"]: item["value"] for item in preview["metrics"]}

    assert metrics["mention_count"] == "待接入"
    assert "不表示现实中不存在风险" in preview["data_quality"]["warnings"][-1]


def test_macro_uses_dedicated_indicator_and_policy_tables() -> None:
    db = _database()
    _insert_bank(db)
    db.execute(text("""
        INSERT INTO macro_indicator_points VALUES
        ('gdp_yoy', 'GDP同比增长', '2026-Q2', 5.1, '%', '季度', '国家统计局', 'https://data.stats.gov.cn', '2026-07-20T00:00:00+00:00'),
        ('m2_yoy', 'M2同比增长', '2026-06', 8.3, '%', '月度', '中国人民银行', 'https://www.pbc.gov.cn', '2026-07-20T00:00:00+00:00')
    """))
    db.execute(text("""
        INSERT INTO macro_industry_events VALUES
        ('policy_regulatory', '金融支持政策', '支持实体经济', '国家发展和改革委员会',
         'https://www.ndrc.gov.cn/example', '2026-07-19T00:00:00+00:00', 'positive', 'important')
    """))
    db.commit()

    preview = build_agent_preview_v2(db, company_id="bank-1", category="macro")

    assert any(item["key"] == "gdp_yoy" and item["value"] == "5.10" for item in preview["metrics"])
    assert any(section["key"] == "policy_timeline" and section["items"] for section in preview["sections"])
    assert preview["data_quality"]["evidence_count"] >= 3
