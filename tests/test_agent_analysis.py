from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.models import AnalysisReport, Company
from app.services.agent_analysis import build_agent_preview, compose_comprehensive_report


def make_event(
    category: str,
    title: str,
    *,
    severity: str = "important",
    sentiment: str = "neutral",
    source_name: str = "测试来源",
    source_url: str = "https://example.com/evidence",
):
    return SimpleNamespace(
        category=category,
        title=title,
        content=f"{title}的证据正文",
        severity=severity,
        sentiment=sentiment,
        source_name=source_name,
        source_url=source_url,
        occurred_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        extra_payload={"page_hint": "公告第 3 页"},
    )


class AgentAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = SimpleNamespace(
            name="测试汽车股份有限公司",
            industry="汽车",
            company_profile={
                "stock_code": "002594",
                "akshare_profile": {
                    "status": "available",
                    "source": "akshare",
                    "stock_code": "002594",
                    "updated_at": "2026-07-20T12:00:00+00:00",
                    "financial_abstract": [
                        {
                            "指标": "营业总收入",
                            "20240331": 100_000_000_000,
                            "20241231": 600_000_000_000,
                            "20250331": 120_000_000_000,
                            "20251231": 720_000_000_000,
                            "20260331": 150_000_000_000,
                        },
                        {
                            "指标": "归母净利润",
                            "20240331": 4_000_000_000,
                            "20241231": 30_000_000_000,
                            "20250331": 6_000_000_000,
                            "20251231": 36_000_000_000,
                            "20260331": 7_500_000_000,
                        },
                    ],
                    "financial_indicators": [
                        {
                            "日期": "2026-03-31",
                            "资产负债率(%)": 72.5,
                            "存货周转天数(天)": 68.2,
                            "应收账款周转天数(天)": 31.4,
                            "经营现金净流量与净利润的比率(%)": 1.3,
                        }
                    ],
                },
            },
        )

    def build(self, category: str, events=None):
        return build_agent_preview(
            company=self.company,
            category=category,
            risk_events=events or [],
        )

    def test_finance_uses_akshare_periods_and_computed_metrics(self) -> None:
        result = self.build(
            "finance",
            [make_event("finance", "2026 年一季度报告")],
        )

        metrics = {item["key"]: item for item in result["metrics"]}
        series = {item["key"]: item for item in result["series"]}

        self.assertEqual(result["report_type"], "financial_health_report")
        self.assertEqual(metrics["revenue"]["value"], "1,500.00")
        self.assertEqual(metrics["revenue_growth"]["value"], "25.0")
        self.assertEqual(metrics["debt_safety_margin"]["value"], "27.5")
        self.assertEqual(series["revenue"]["points"][-1]["period"], "2026Q1")
        self.assertEqual(series["net_profit"]["points"][-1]["value"], 75.0)
        self.assertEqual(result["data_quality"]["status"], "complete")

    def test_operations_marks_missing_business_system_data(self) -> None:
        result = self.build(
            "operations",
            [make_event("operations", "匈牙利工厂认证节点")],
        )

        metrics = {item["key"]: item for item in result["metrics"]}
        self.assertEqual(metrics["inventory_days"]["value"], "68.2")
        self.assertEqual(metrics["order_fulfillment"]["value"], "待接入")
        self.assertTrue(
            any("订单" in warning for warning in result["data_quality"]["warnings"])
        )
        self.assertTrue(any(section["kind"] == "timeline" for section in result["sections"]))

    def test_macro_is_event_driven_and_does_not_invent_market_size(self) -> None:
        result = self.build(
            "macro",
            [
                make_event(
                    "macro",
                    "欧盟反补贴调查",
                    sentiment="negative",
                )
            ],
        )

        metrics = {item["key"]: item for item in result["metrics"]}
        self.assertEqual(metrics["event_count"]["value"], "1")
        self.assertEqual(metrics["negative_share"]["value"], "100.0")
        self.assertNotIn("市场规模", {item["label"] for item in result["metrics"]})
        self.assertTrue(any("市场规模" in item for item in result["data_quality"]["warnings"]))

    def test_legal_builds_timeline_and_risk_transmission(self) -> None:
        result = self.build(
            "legal",
            [make_event("legal", "海外知识产权争议", sentiment="negative")],
        )

        self.assertEqual(result["report_type"], "legal_risk_report")
        timeline = next(item for item in result["sections"] if item["kind"] == "timeline")
        self.assertEqual(timeline["items"][0]["title"], "海外知识产权争议")
        self.assertTrue(any(item["key"] == "risk_transmission" for item in result["sections"]))

    def test_brand_calculates_sentiment_and_source_distribution(self) -> None:
        result = self.build(
            "brand",
            [
                make_event("brand", "智驾口碑", sentiment="positive", source_name="新闻媒体"),
                make_event("brand", "价格战讨论", sentiment="negative", source_name="社交平台"),
                make_event("brand", "电池技术", sentiment="neutral", source_name="新闻媒体"),
            ],
        )

        sentiment = next(
            item for item in result["sections"] if item["key"] == "sentiment_distribution"
        )
        source_distribution = next(
            item for item in result["sections"] if item["key"] == "source_distribution"
        )
        self.assertEqual(sum(item["value"] for item in sentiment["items"]), 100.0)
        self.assertEqual(source_distribution["items"][0]["label"], "新闻媒体")
        self.assertEqual(source_distribution["items"][0]["value"], 2)

    def test_empty_events_returns_honest_partial_analysis(self) -> None:
        result = self.build("legal")

        self.assertEqual(result["retrieval_stage"], "knowledge_base_fallback")
        self.assertEqual(result["data_quality"]["status"], "insufficient")
        self.assertEqual(result["sources"], [])


class ComprehensiveReportTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.db = sessionmaker(bind=engine, future=True)()
        self.company = Company(name="报告测试股份有限公司", company_profile={})
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)

    def tearDown(self) -> None:
        self.db.close()

    def test_compose_preserves_latest_agent_analysis_snapshots(self) -> None:
        for report_type, category in (
            ("macro_environment_report", "macro"),
            ("financial_health_report", "finance"),
        ):
            self.db.add(
                AnalysisReport(
                    company_id=self.company.id,
                    report_type=report_type,
                    title=f"{category} 单项报告",
                    summary=f"{category} 实时摘要",
                    snapshot={
                        "analysis": {
                            "category": category,
                            "data_quality": {"coverage_percent": 80},
                        }
                    },
                    model_name="d-trust-agent",
                )
            )
        self.db.commit()

        report = compose_comprehensive_report(
            self.db,
            company_id=self.company.id,
            report_types=["macro_environment_report", "financial_health_report"],
        )

        assembled = report.snapshot["assembled_reports"]
        self.assertEqual(len(assembled), 2)
        self.assertEqual(assembled[0]["snapshot"]["analysis"]["category"], "macro")
        self.assertEqual(assembled[1]["snapshot"]["analysis"]["category"], "finance")
        self.assertEqual(report.report_type, "comprehensive_risk_report")


if __name__ == "__main__":
    unittest.main()
