from __future__ import annotations

import argparse
import json
from typing import Any

from app.db.session import SessionLocal
from app.services.collection_operations import run_collection_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 D.Risk AI 权威数据每日增量或历史回补任务。"
    )
    parser.add_argument(
        "--mode",
        choices=("daily", "backfill"),
        default="daily",
    )
    parser.add_argument("--company-id", default=None)
    parser.add_argument("--max-companies", type=int, default=100)
    parser.add_argument("--max-documents", type=int, default=80)
    parser.add_argument("--backfill-years", type=int, default=5)
    parser.add_argument("--lookback-days", type=int, default=2)
    return parser.parse_args()


def main() -> dict[str, Any]:
    args = parse_args()
    with SessionLocal() as db:
        result = run_collection_batch(
            db,
            mode=args.mode,
            company_id=args.company_id,
            max_companies=args.max_companies,
            max_documents_per_company=args.max_documents,
            backfill_years=args.backfill_years,
            lookback_days=args.lookback_days,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
