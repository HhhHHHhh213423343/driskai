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

SERVICE_PATH = SERVICES_PATH / "authoritative_ingestion.py"
SPEC = importlib.util.spec_from_file_location("authoritative_ingestion_under_test", SERVICE_PATH)
assert SPEC and SPEC.loader
SERVICE_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SERVICE_MODULE
SPEC.loader.exec_module(SERVICE_MODULE)


def test_multilabel_classification_preserves_cross_agent_evidence() -> None:
    categories = SERVICE_MODULE._classify(
        "某银行因贷款管理不到位被监管处罚并罚款，同时引发客户投诉和声誉风险。"
    )

    assert "operations" in categories
    assert "legal" in categories
    assert "brand" in categories


def test_trusted_domains_reject_unlisted_sources() -> None:
    assert SERVICE_MODULE._trusted("https://www.nfra.gov.cn/cn/view/pages/ItemList.html")
    assert SERVICE_MODULE._trusted("https://example.icbc.com.cn/news", "icbc.com.cn")
    assert not SERVICE_MODULE._trusted("https://unknown-blog.example/post")


def test_official_search_result_keeps_primary_source_identity() -> None:
    code, name, authority = SERVICE_MODULE._source_identity(
        "https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html",
        "icbc.com.cn",
        "搜索结果",
    )

    assert code == "nfra_penalties"
    assert name == "国家金融监督管理总局"
    assert authority == "official"


def test_candidate_selection_round_robins_sources_without_charging_discovery_pages() -> None:
    candidates = [
        SERVICE_MODULE.Candidate(
            "https://a.example/list",
            "source-a",
            "来源A",
            "official",
            is_discovery_page=True,
        ),
        *[
            SERVICE_MODULE.Candidate(
                f"https://a.example/{index}",
                "source-a",
                "来源A",
                "official",
            )
            for index in range(4)
        ],
        SERVICE_MODULE.Candidate(
            "https://b.example/1",
            "source-b",
            "来源B",
            "official",
        ),
    ]

    selected = SERVICE_MODULE._select_candidates(candidates, 3)

    assert selected[0].is_discovery_page
    assert [candidate.source_code for candidate in selected[1:]] == [
        "source-a",
        "source-b",
        "source-a",
    ]


def test_authorized_search_backfill_uses_explicit_date_window(monkeypatch) -> None:
    recorded = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"organic": []}

    class Client:
        def post(self, url, **kwargs):
            recorded["url"] = url
            recorded["json"] = kwargs["json"]
            return Response()

    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    collector = object.__new__(SERVICE_MODULE.AuthoritativeCollector)
    collector.client = Client()
    target = SERVICE_MODULE.CompanyTarget("company-1", "测试银行", ["测试银行"])

    collector.serper_candidates(
        target,
        "legal",
        date_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )

    assert recorded["url"] == "https://google.serper.dev/search"
    assert recorded["json"]["tbs"] == "cdr:1,cd_min:01/01/2022,cd_max:01/01/2023"


def test_event_upsert_deduplicates_by_url_and_category() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE risk_events (
                id TEXT PRIMARY KEY, company_id TEXT, category TEXT, severity TEXT,
                title TEXT, content TEXT, source_url TEXT, source_name TEXT,
                occurred_at TEXT, sentiment TEXT, extra_payload JSON,
                created_at TEXT, updated_at TEXT
            )
        """))
    db = Session(engine)
    target = SERVICE_MODULE.CompanyTarget("company-1", "测试银行", ["测试银行"])
    document = SERVICE_MODULE.Document(
        url="https://www.nfra.gov.cn/example",
        source_code="nfra_penalties",
        source_name="国家金融监督管理总局",
        authority="official",
        authority_score=100,
        title="监管处罚",
        text="测试银行因贷款管理不到位被处罚并罚款。",
        published_at=None,
        content_hash="hash-1",
    )

    assert SERVICE_MODULE._upsert_event(db, target, document, "legal") is True
    assert SERVICE_MODULE._upsert_event(db, target, document, "legal") is False
    assert SERVICE_MODULE._upsert_event(db, target, document, "operations") is True
    db.commit()

    count = db.execute(text("SELECT COUNT(*) FROM risk_events")).scalar_one()
    assert count == 2
