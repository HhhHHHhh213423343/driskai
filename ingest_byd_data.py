from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

DEFAULT_COMPANY_NAME = "比亚迪股份有限公司"
DEFAULT_STOCK_CODE = "002594"
DEFAULT_VECTOR_STORE_PATH = "backend/data/vector_store/byd_knowledge_docs.jsonl"

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BYD 全网数据注入引擎")
    parser.add_argument("--company-name", default=DEFAULT_COMPANY_NAME, help="目标公司名称")
    parser.add_argument("--stock-code", default=DEFAULT_STOCK_CODE, help="目标股票代码")
    parser.add_argument("--max-results-per-query", type=int, default=5, help="每个搜索词最多抓取结果数")
    parser.add_argument("--query-limit", type=int, default=None, help="仅执行前 N 条搜索词，便于调试")
    parser.add_argument("--sync-fastgpt", action="store_true", help="同步知识文档到 FastGPT 数据集")
    parser.add_argument("--dry-run", action="store_true", help="只抓取和结构化，不写数据库")
    parser.add_argument(
        "--vector-store-path",
        default=DEFAULT_VECTOR_STORE_PATH,
        help="本地向量库存储路径",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    try:
        from app.db.base import Base
        from app.db.session import SessionLocal
        from app.db.session import engine as db_engine
        from app.models import AnalysisReport, Company, RiskEvent  # noqa: F401
        from app.services.byd_ingestion import (
            AkShareCollector,
            BYDIngestionEngine,
            BroadSearchClient,
            KnowledgeSyncer,
            OpenAILLMStructurer,
            SemanticDeduper,
            SemanticEncoder,
            render_terminal_summary,
        )
    except ModuleNotFoundError as exc:
        print(
            f"缺少运行依赖: {exc.name}。请先执行 `pip install -r backend/requirements.txt`。",
            file=sys.stderr,
        )
        return 1

    Base.metadata.create_all(bind=db_engine)
    db = SessionLocal()
    try:
        encoder = SemanticEncoder()
        engine = BYDIngestionEngine(
            db=db,
            search_client=BroadSearchClient(api_key=_env("SERPER_API_KEY")),
            structurer=OpenAILLMStructurer(
                api_key=_env("LLM_API_KEY"),
                base_url=_env("LLM_BASE_URL"),
                model=_env("LLM_MODEL"),
            ),
            deduper=SemanticDeduper(encoder=encoder),
            knowledge_syncer=KnowledgeSyncer(
                encoder=encoder,
                vector_store_path=Path(args.vector_store_path),
            ),
            akshare_collector=AkShareCollector(symbol=args.stock_code),
        )
        result = await engine.run(
            company_name=args.company_name,
            stock_code=args.stock_code,
            max_results_per_query=args.max_results_per_query,
            query_limit=args.query_limit,
            sync_fastgpt=args.sync_fastgpt,
            dry_run=args.dry_run,
        )
        print(render_terminal_summary(result))
        return 0
    finally:
        db.close()


def _env(name: str) -> str:
    import os

    return os.getenv(name, "").strip()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
