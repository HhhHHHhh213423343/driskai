from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D.Risk 每日公开数据接入任务")
    parser.add_argument("--company-name", action="append", default=[], help="只扫描指定公司，可重复传入")
    parser.add_argument("--source", action="append", default=[], help="只运行指定来源 code，可重复传入")
    parser.add_argument("--max-results-per-source", type=int, default=5, help="每个来源单家公司最多抓取条数")
    parser.add_argument("--stock-code", default="", help="单公司运行时可显式传入股票代码")
    parser.add_argument("--dry-run", action="store_true", help="只采集和结构化，不写入数据库")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    try:
        from app.db.base import Base
        from app.db.session import SessionLocal
        from app.db.session import engine as db_engine
        from app.models import AnalysisReport, Company, IngestionRun, RiskEvent  # noqa: F401
        from app.services.generic_ingestion import DailyIngestionService
    except ModuleNotFoundError as exc:
        print(
            f"缺少运行依赖: {exc.name}。请先执行 `pip install -r backend/requirements.txt`。",
            file=sys.stderr,
        )
        return 1

    Base.metadata.create_all(bind=db_engine)
    db = SessionLocal()
    try:
        stock_lookup = {}
        if len(args.company_name) == 1 and args.stock_code:
            stock_lookup[args.company_name[0]] = args.stock_code
        if args.company_name:
            _ensure_cli_companies(
                db=db,
                company_names=args.company_name,
                stock_lookup=stock_lookup,
                dry_run=args.dry_run,
            )

        service = DailyIngestionService(db)
        run = await service.run(
            company_names=args.company_name,
            stock_code_by_company=stock_lookup,
            max_results_per_source=args.max_results_per_source,
            enabled_source_codes=args.source,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {
                    "run_id": str(run.id),
                    "status": run.status,
                    "scanned_company_count": run.scanned_company_count,
                    "total_raw_count": run.total_raw_count,
                    "inserted_count": run.inserted_count,
                    "skipped_count": run.skipped_count,
                    "source_breakdown": run.source_breakdown,
                    "failures": run.failures,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    finally:
        db.close()


def _ensure_cli_companies(
    *,
    db: Any,
    company_names: list[str],
    stock_lookup: dict[str, str],
    dry_run: bool,
) -> None:
    from sqlalchemy import select

    from app.models import Company

    changed = False
    for raw_name in company_names:
        name = raw_name.strip()
        if not name:
            continue
        company = db.execute(select(Company).where(Company.name == name)).scalar_one_or_none()
        stock_code = stock_lookup.get(name, "").strip()

        if company:
            if stock_code:
                profile = dict(company.company_profile or {})
                if not profile.get("stock_code"):
                    profile["stock_code"] = stock_code
                    company.company_profile = profile
                    changed = True
            continue

        company = Company(
            name=name,
            company_profile={"stock_code": stock_code} if stock_code else {},
        )
        db.add(company)
        changed = True

    if changed and not dry_run:
        db.commit()
    if changed and dry_run:
        db.flush()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
