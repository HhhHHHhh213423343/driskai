from __future__ import annotations

import unittest
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.models import Company
from app.services.qichacha_profile import (
    build_qichacha_token,
    normalize_qichacha_profile,
    refresh_company_qichacha_profile,
    unavailable_qichacha_profile,
)


class FakeQichachaClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def fetch_profile(self, search_key: str) -> dict:
        return self.payload


class QichachaProfileTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            future=True,
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()

    def test_build_qichacha_token_uses_uppercase_md5(self) -> None:
        token = build_qichacha_token("app", "secret", "1700000000")

        self.assertEqual(token, "D1377D2D63F40B670CFC8E9448EF9BBD")

    def test_normalize_qichacha_profile_maps_business_fields(self) -> None:
        profile = normalize_qichacha_profile(
            {
                "Status": "200",
                "Result": {
                    "Name": "测试股份有限公司",
                    "OperName": "张三",
                    "StartDate": "2020-01-02",
                    "Status": "存续",
                    "CreditCode": "91310000TEST",
                    "RegistCapi": "1000万元人民币",
                    "EconKind": "股份有限公司",
                    "Address": "上海市浦东新区测试路1号",
                    "Scope": "企业管理咨询。",
                    "BelongOrg": "上海市市场监督管理局",
                    "Industry": {"Industry": "租赁和商务服务业", "SubIndustry": "商务服务业"},
                    "Employees": [{"Name": "李四", "Job": "董事"}],
                    "Partners": [{"StockName": "王五", "StockPercent": "20%", "ShouldCapi": "200万元"}],
                    "ChangeRecords": [
                        {
                            "ProjectName": "法定代表人变更",
                            "BeforeContent": "赵六",
                            "AfterContent": "张三",
                            "ChangeDate": "2024-01-01",
                        }
                    ],
                },
            },
            "测试股份有限公司",
        )

        self.assertEqual(profile["status"], "available")
        self.assertEqual(profile["company_name"], "测试股份有限公司")
        self.assertEqual(profile["legal_representative"], "张三")
        self.assertEqual(profile["industry"], "租赁和商务服务业 / 商务服务业")
        self.assertEqual(profile["major_personnel"][0]["name"], "李四")
        self.assertEqual(profile["shareholders"][0]["ratio"], "20%")
        self.assertEqual(profile["change_records"][0]["project"], "法定代表人变更")

    async def test_refresh_company_profile_records_unavailable_state(self) -> None:
        company = Company(name="未配置公司")
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        await refresh_company_qichacha_profile(
            self.db,
            company,
            client=FakeQichachaClient(
                unavailable_qichacha_profile(
                    "missing_credentials",
                    "暂未配置企查查官方 API Key。",
                )
            ),
        )

        self.assertEqual(
            company.company_profile["qichacha_profile"]["status"],
            "unavailable",
        )
        self.assertEqual(
            company.company_profile["qichacha_profile"]["reason"],
            "missing_credentials",
        )

    async def test_refresh_company_profile_keeps_company_on_api_failure(self) -> None:
        company = Company(name="失败公司")
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        await refresh_company_qichacha_profile(
            self.db,
            company,
            client=FakeQichachaClient(
                unavailable_qichacha_profile(
                    "request_failed",
                    "企查查官方 API 请求失败。",
                )
            ),
        )

        persisted = self.db.get(Company, company.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.name, "失败公司")
        self.assertEqual(
            persisted.company_profile["qichacha_profile"]["status"],
            "unavailable",
        )


if __name__ == "__main__":
    unittest.main()
