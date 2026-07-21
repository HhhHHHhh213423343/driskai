import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

import platform_server as platform


CORE_SCHEMA = """
CREATE TABLE companies (
    id CHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    credit_code VARCHAR(64),
    industry VARCHAR(128),
    region VARCHAR(128),
    description TEXT NOT NULL DEFAULT '',
    official_website VARCHAR(255) NOT NULL DEFAULT '',
    company_profile JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE TABLE risk_events (
    id CHAR(32) PRIMARY KEY,
    company_id CHAR(32) NOT NULL,
    category VARCHAR(80) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    source_name VARCHAR(128) NOT NULL DEFAULT '',
    occurred_at DATETIME,
    sentiment VARCHAR(16) NOT NULL DEFAULT 'neutral',
    extra_payload JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE TABLE analysis_reports (
    id CHAR(32) PRIMARY KEY,
    company_id CHAR(32) NOT NULL,
    report_type VARCHAR(80) NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    snapshot JSON NOT NULL,
    model_name VARCHAR(120) NOT NULL,
    generated_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
"""


class MacroIndustryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_database = platform.DATABASE
        platform.DATABASE = Path(self.tempdir.name) / "test.db"
        connection = sqlite3.connect(platform.DATABASE)
        connection.executescript(CORE_SCHEMA)
        connection.close()
        platform.ensure_extended_schema()
        self.company_id = uuid.uuid4().hex
        timestamp = platform.now_iso()
        with platform.connect() as connection:
            connection.execute(
                "INSERT INTO companies (id, name, industry, region, description, official_website, company_profile, created_at, updated_at) VALUES (?, '测试汽车公司', '汽车制造业', '广东', '', '', ?, ?, ?)",
                (self.company_id, json.dumps({"akshare_profile": {"stock_code": "002594"}}, ensure_ascii=False), timestamp, timestamp),
            )
            connection.commit()

    def tearDown(self) -> None:
        platform.DATABASE = self.original_database
        self.tempdir.cleanup()

    def insert_indicator(self, code: str, name: str, period: str, value: float, unit: str = "%") -> None:
        with platform.connect() as connection:
            connection.execute(
                "INSERT INTO macro_indicator_points (id, indicator_code, indicator_name, period, value, unit, frequency, region_scope, source_name, source_url, raw_payload, collected_at) VALUES (?, ?, ?, ?, ?, ?, '月度', '全国', '权威公开源（AkShare 聚合）', 'https://data.stats.gov.cn/', '{}', ?)",
                (uuid.uuid4().hex, code, name, period, value, unit, platform.now_iso()),
            )
            connection.commit()

    def test_period_normalization(self) -> None:
        self.assertEqual(platform.normalize_period("2026年06月份"), "2026-06")
        self.assertEqual(platform.normalize_period("2026年第1-2季度"), "2026-Q2")
        self.assertEqual(platform.normalize_period("2026-07-21"), "2026-07-21")

    def test_official_policy_listing_and_industry_match(self) -> None:
        page = '<li><a href="./202607/t20260701_1.html" target="_blank">关于开展新能源汽车下乡活动的通知</a><span>2026/07/01</span></li>'
        items = platform.parse_ndrc_policy_listing(page, "https://www.ndrc.gov.cn/xxgk/zcfb/tz/wap_index.html")
        self.assertEqual(items[0]["published_at"], "2026-07-01")
        self.assertTrue(items[0]["source_url"].startswith("https://www.ndrc.gov.cn/"))
        self.assertTrue(platform.policy_matches_industry(items[0]["title"], "汽车制造业"))
        self.assertFalse(platform.policy_matches_industry(items[0]["title"], "货币金融服务"))

    def test_event_upsert_is_idempotent(self) -> None:
        event = {
            "scope_type": "macro", "scope_key": "全国", "dimension": "macroeconomy",
            "event_type": "macro_indicator_release", "indicator_code": "gdp_yoy",
            "title": "2026-Q2 GDP 同比增长为4.7%", "summary": "公开指标记录。",
            "source_name": "国家统计局", "source_url": "https://data.stats.gov.cn/",
            "published_at": "2026-Q2", "impact_direction": "neutral", "severity": "normal",
        }
        with platform.connect() as connection:
            self.assertTrue(platform.upsert_macro_event(connection, event))
            self.assertFalse(platform.upsert_macro_event(connection, event))
            connection.commit()
            count = connection.execute("SELECT COUNT(*) FROM macro_industry_events").fetchone()[0]
        self.assertEqual(count, 1)

    def test_macro_preview_combines_indicators_and_industry_signals(self) -> None:
        self.insert_indicator("gdp_yoy", "GDP 同比增长", "2026-Q1", 5.0)
        self.insert_indicator("gdp_yoy", "GDP 同比增长", "2026-Q2", 4.7)
        self.insert_indicator("manufacturing_pmi", "制造业 PMI", "2026-05", 50.0, "点")
        self.insert_indicator("manufacturing_pmi", "制造业 PMI", "2026-06", 50.3, "点")
        with platform.connect() as connection:
            inserted, _ = platform.generate_indicator_events(connection, "汽车制造业")
            self.assertGreater(inserted, 0)
            company = platform.company_from_row(connection.execute("SELECT * FROM companies WHERE id=?", (self.company_id,)).fetchone())
            preview = platform.macro_preview(company, connection)
        self.assertEqual(preview["category"], "macro")
        self.assertGreaterEqual(len(preview["macro_indicators"]), 2)
        self.assertGreaterEqual(len(preview["industry_signals"]), 2)
        self.assertTrue(preview["impact_chains"])
        self.assertTrue(all(source.get("source_url") for source in preview["sources"]))

    def test_ingestion_run_exposes_progress_contract(self) -> None:
        with platform.connect() as connection:
            run = platform.create_ingestion_run(connection, platform.api_id(self.company_id), "test")
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["progress_current"], 0)
        self.assertEqual(run["progress_total"], len(platform.MACRO_INDICATORS) + 3)
        self.assertEqual(run["failed_sources"], [])


if __name__ == "__main__":
    unittest.main()
