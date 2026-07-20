from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.models import Company, IngestionRun, RiskEvent
from app.services.generic_ingestion import (
    DataSourceAdapter,
    DailyIngestionService,
    IngestionContext,
    RawEvidence,
    SourceCollectResult,
    SourceSpec,
    create_dashboard_summary,
)


class GoodSource(DataSourceAdapter):
    spec = SourceSpec(
        code="good",
        name="稳定测试源",
        categories=("legal",),
    )

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        return SourceCollectResult(
            source_code=self.spec.code,
            source_name=self.spec.name,
            items=[
                RawEvidence(
                    source_code=self.spec.code,
                    source_name=self.spec.name,
                    category="legal",
                    title=f"{context.company_name} 监管问询公告",
                    source_url="https://example.com/a",
                    content="监管问询公告",
                    occurred_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
                ),
                RawEvidence(
                    source_code=self.spec.code,
                    source_name=self.spec.name,
                    category="legal",
                    title=f"{context.company_name} 监管问询公告",
                    source_url="https://example.com/a",
                    content="监管问询公告",
                    occurred_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
                ),
            ],
        )


class FailingSource(DataSourceAdapter):
    spec = SourceSpec(
        code="failing",
        name="失败测试源",
        categories=("finance",),
    )

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        return SourceCollectResult(
            source_code=self.spec.code,
            source_name=self.spec.name,
            error="upstream unavailable",
        )


class GenericIngestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            future=True,
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.db = self.SessionLocal()
        self.company = Company(
            name="测试股份有限公司",
            company_profile={"stock_code": "000001", "market": "szse"},
        )
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)

    def tearDown(self) -> None:
        self.db.close()

    async def test_run_continues_when_one_source_fails_and_dedupes(self) -> None:
        service = DailyIngestionService(
            self.db,
            adapters=[GoodSource(), FailingSource()],
        )

        run = await service.run(company_names=[self.company.name])

        self.assertEqual(run.status, "partial_failed")
        self.assertEqual(run.scanned_company_count, 1)
        self.assertEqual(run.total_raw_count, 2)
        self.assertEqual(run.inserted_count, 1)
        self.assertEqual(run.skipped_count, 1)
        self.assertEqual(run.source_breakdown, {"稳定测试源": 2})
        self.assertEqual(run.failures[0]["source_code"], "failing")

        events = list(self.db.query(RiskEvent).all())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, "重要")

    async def test_dashboard_summary_uses_ingested_events_and_latest_run(self) -> None:
        service = DailyIngestionService(self.db, adapters=[GoodSource()])
        await service.run(company_names=[self.company.name])

        summary = create_dashboard_summary(self.db)

        self.assertEqual(summary["total_events"], 1)
        self.assertEqual(summary["high_priority_events"], 1)
        self.assertEqual(summary["source_breakdown"], {"稳定测试源": 1})
        self.assertIsInstance(summary["latest_run"], IngestionRun)

    async def test_run_can_target_newly_created_company_by_id(self) -> None:
        company = Company(name="任意新公司", company_profile={"stock_code": "600000"})
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        service = DailyIngestionService(self.db, adapters=[GoodSource()])
        run = await service.run(company_ids=[company.id])

        self.assertEqual(run.scanned_company_count, 1)
        self.assertEqual(run.inserted_count, 1)
        event = self.db.query(RiskEvent).filter(RiskEvent.company_id == company.id).one()
        self.assertEqual(event.title, "任意新公司 监管问询公告")
