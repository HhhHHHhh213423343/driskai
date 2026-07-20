from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import asyncio
import sys
import unittest
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import akshare_profile


class _NoNetworkAkShare:
    def __getattr__(self, name: str):
        raise AssertionError(f"known company lookup unexpectedly called {name}")


class _ExchangeFallbackAkShare:
    def stock_info_sz_name_code(self, *, symbol: str):
        raise ConnectionError("深交所临时不可用")

    def stock_info_sh_name_code(self, *, symbol: str):
        if symbol == "主板A股":
            return pd.DataFrame(
                [
                    {
                        "证券代码": "600000",
                        "证券简称": "浦发银行",
                        "公司全称": "上海浦东发展银行股份有限公司",
                    }
                ]
            )
        return pd.DataFrame()

    def stock_info_bj_name_code(self):
        return pd.DataFrame()


class _UnavailableAkShare:
    def stock_info_sz_name_code(self, *, symbol: str):
        raise ConnectionError("sz unavailable")

    def stock_info_sh_name_code(self, *, symbol: str):
        raise ConnectionError("sh unavailable")

    def stock_info_bj_name_code(self):
        raise ConnectionError("bj unavailable")


class _FakeCompany:
    name = "比亚迪股份有限公司"
    industry = "汽车"
    description = ""

    def __init__(self) -> None:
        self.company_profile = {
            "akshare_profile": {
                "status": "available",
                "financial_highlights": {"revenue": ""},
            }
        }


class _FakeSession:
    def add(self, company) -> None:
        self.company = company

    def commit(self) -> None:
        pass

    def refresh(self, company) -> None:
        pass


class AkShareProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_akshare = akshare_profile.ak

    def tearDown(self) -> None:
        akshare_profile.ak = self.original_akshare

    def test_known_company_alias_resolves_without_live_directory(self) -> None:
        akshare_profile.ak = _NoNetworkAkShare()

        match = akshare_profile._resolve_stock("比亚迪股份有限公司")

        self.assertEqual(match["stock_code"], "002594")
        self.assertEqual(match["stock_name"], "比亚迪")
        self.assertEqual(match["matched_name"], "比亚迪股份有限公司")
        self.assertEqual(match["resolution_source"], "local_alias")

    def test_provided_code_preserves_known_stock_name(self) -> None:
        akshare_profile.ak = _NoNetworkAkShare()

        match = akshare_profile._resolve_stock(
            "比亚迪股份有限公司",
            stock_code="002594",
        )

        self.assertEqual(match["stock_code"], "002594")
        self.assertEqual(match["stock_name"], "比亚迪")
        self.assertEqual(match["matched_name"], "比亚迪股份有限公司")
        self.assertEqual(match["resolution_source"], "provided_stock_code")

    def test_exchange_directory_failure_does_not_block_other_markets(self) -> None:
        akshare_profile.ak = _ExchangeFallbackAkShare()

        match = akshare_profile._resolve_stock("上海浦东发展银行股份有限公司")

        self.assertEqual(match["stock_code"], "600000")
        self.assertEqual(match["stock_name"], "浦发银行")
        self.assertEqual(match["resolution_source"], "上交所主板")
        self.assertEqual(match["resolution_errors"][0]["source"], "深交所")

    def test_all_directory_failures_are_reported_as_source_error(self) -> None:
        akshare_profile.ak = _UnavailableAkShare()

        profile = akshare_profile.build_akshare_profile("任意上市公司")

        self.assertEqual(profile["status"], "unavailable")
        self.assertEqual(profile["reason"], "source_error")
        self.assertIn("股票名单数据源暂时不可用", profile["message"])
        self.assertGreaterEqual(len(profile["resolution_errors"]), 3)

    def test_financial_highlights_parse_metric_by_reporting_period(self) -> None:
        financial_rows = [
            {
                "选项": "常用指标",
                "指标": "营业总收入",
                "20231231": 100,
                "20240930": 130,
            },
            {
                "选项": "常用指标",
                "指标": "归母净利润",
                "20231231": 10,
                "20240930": 13,
            },
        ]
        financial_indicators = [
            {"日期": "2023-12-31", "销售毛利率(%)": 18},
            {"日期": "2024-09-30", "销售毛利率(%)": 21},
            {"日期": "2024-12-31", "销售毛利率(%)": None},
        ]

        highlights = akshare_profile._build_financial_highlights(
            {"总市值": 123456, "行业": "汽车"},
            financial_rows,
            financial_indicators,
        )

        self.assertEqual(highlights["revenue"], "130")
        self.assertEqual(highlights["net_profit"], "13")
        self.assertEqual(highlights["gross_margin"], "21")
        self.assertEqual(highlights["market_value"], "123456")
        self.assertEqual(highlights["industry"], "汽车")

    def test_explicit_search_can_force_refresh_an_available_profile(self) -> None:
        company = _FakeCompany()
        refreshed_profile = {
            "status": "available",
            "stock_code": "002594",
            "stock_name": "比亚迪",
            "individual_info": {},
            "financial_highlights": {"revenue": "150225314000.0"},
        }

        with patch.object(
            akshare_profile,
            "build_akshare_profile",
            return_value=refreshed_profile,
        ) as build_profile:
            asyncio.run(
                akshare_profile.refresh_company_akshare_profile(
                    _FakeSession(),
                    company,
                    force=True,
                )
            )

        build_profile.assert_called_once_with(
            "比亚迪股份有限公司",
            stock_code="",
        )
        self.assertEqual(
            company.company_profile["akshare_profile"]["financial_highlights"]["revenue"],
            "150225314000.0",
        )
        self.assertEqual(company.company_profile["stock_code"], "002594")

    def test_dataframe_records_are_safe_for_json_storage(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "日期": date(2026, 3, 31),
                    "营业收入": 150225314000,
                    "毛利率": float("nan"),
                }
            ]
        )

        records = akshare_profile._records_from_dataframe(dataframe)

        self.assertEqual(records[0]["日期"], "2026-03-31")
        self.assertEqual(records[0]["营业收入"], 150225314000)
        self.assertIsNone(records[0]["毛利率"])
        json.dumps(records, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
