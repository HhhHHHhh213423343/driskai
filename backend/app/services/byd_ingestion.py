from __future__ import annotations

import asyncio
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AnalysisReport, Company, RiskEvent
from app.services.fastgpt import FastGPTService

try:
    import akshare as ak
except ImportError:  # pragma: no cover - runtime optional dependency
    ak = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - runtime optional dependency
    np = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - runtime optional dependency
    PdfReader = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - runtime optional dependency
    SentenceTransformer = None


CANONICAL_COMPANY_NAME = "比亚迪股份有限公司"
CANONICAL_STOCK_CODE = "002594"
VECTOR_STORE_PATH = Path("backend/data/vector_store/byd_knowledge_docs.jsonl")


@dataclass(frozen=True)
class SearchSeed:
    category: str
    query: str
    search_type: str = "news"


@dataclass
class RawEvidence:
    category: str
    query: str
    title: str
    source_url: str
    source_name: str
    snippet: str = ""
    content: str = ""
    published_at: datetime | None = None
    pdf_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def combined_text(self) -> str:
        return "\n".join(
            part.strip()
            for part in [self.title, self.snippet, self.content]
            if part and part.strip()
        )


@dataclass
class StructuredInsight:
    category: str
    title: str
    summary: str
    content: str
    severity: str
    sentiment: str
    amount_or_ratio: str
    source_url: str
    source_name: str
    occurred_at: datetime | None
    query: str
    tags: list[str]
    raw_evidence: RawEvidence
    knowledge_worthy: bool = False
    report_excerpt: str = ""
    extra_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def similarity_text(self) -> str:
        parts = [self.title, self.summary, self.amount_or_ratio]
        return " | ".join(part for part in parts if part)


@dataclass
class AkShareSnapshot:
    quote_item: RawEvidence | None
    financial_item: RawEvidence | None
    research_items: list[RawEvidence]
    metrics: dict[str, Any]


@dataclass
class KnowledgeSyncResult:
    mode: str
    fastgpt_statuses: list[int] = field(default_factory=list)
    local_vector_path: str = ""
    document_count: int = 0


@dataclass
class IngestionRunResult:
    company_id: Any | None
    inserted_count: int
    skipped_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    total_raw_count: int
    total_structured_count: int
    total_deduped_count: int
    analysis_report_id: Any | None
    knowledge_sync_result: KnowledgeSyncResult
    counts_by_category: dict[str, int]
    counts_by_severity: dict[str, int]


class BroadSearchClient:
    def __init__(
        self,
        *,
        api_key: str = "",
        timeout: float = 20.0,
        max_concurrency: int = 6,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def collect(
        self,
        seeds: list[SearchSeed],
        *,
        max_results_per_query: int,
        fetch_page_content: bool = True,
    ) -> list[RawEvidence]:
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": self._user_agent()},
        ) as client:
            search_tasks = [
                self._search_with_seed(
                    client=client,
                    seed=seed,
                    max_results=max_results_per_query,
                )
                for seed in seeds
            ]
            batches = await asyncio.gather(*search_tasks, return_exceptions=True)

            evidences: list[RawEvidence] = []
            for batch in batches:
                if isinstance(batch, Exception):
                    continue
                evidences.extend(batch)

            if not fetch_page_content:
                return evidences

            content_tasks = [self._hydrate_content(client, item) for item in evidences]
            hydrated = await asyncio.gather(*content_tasks, return_exceptions=True)
            results: list[RawEvidence] = []
            for item, content in zip(evidences, hydrated):
                if isinstance(content, Exception):
                    results.append(item)
                    continue
                item.content = content
                results.append(item)
            return results

    async def _search_with_seed(
        self,
        *,
        client: httpx.AsyncClient,
        seed: SearchSeed,
        max_results: int,
    ) -> list[RawEvidence]:
        if self.api_key:
            return await self._search_with_serper(
                client=client,
                seed=seed,
                max_results=max_results,
            )
        return await self._search_with_public_engines(
            client=client,
            seed=seed,
            max_results=max_results,
        )

    async def _search_with_serper(
        self,
        *,
        client: httpx.AsyncClient,
        seed: SearchSeed,
        max_results: int,
    ) -> list[RawEvidence]:
        endpoint = "https://google.serper.dev/news"
        if seed.search_type != "news":
            endpoint = "https://google.serper.dev/search"

        response = await client.post(
            endpoint,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "q": seed.query,
                "gl": "cn",
                "hl": "zh-cn",
                "num": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("news") if seed.search_type == "news" else payload.get("organic")
        if not isinstance(items, list):
            return []

        results: list[RawEvidence] = []
        for row in items[:max_results]:
            link = str(row.get("link") or "").strip()
            title = str(row.get("title") or "").strip()
            if not link or not title:
                continue
            results.append(
                RawEvidence(
                    category=seed.category,
                    query=seed.query,
                    title=title,
                    source_url=link,
                    source_name=str(row.get("source") or _derive_source_name(link)),
                    snippet=str(row.get("snippet") or ""),
                    published_at=_parse_flexible_datetime(str(row.get("date") or "")),
                    metadata={
                        "position": row.get("position"),
                        "search_type": seed.search_type,
                    },
                )
            )
        return results

    async def _search_with_public_engines(
        self,
        *,
        client: httpx.AsyncClient,
        seed: SearchSeed,
        max_results: int,
    ) -> list[RawEvidence]:
        google_url = f"https://www.google.com/search?q={quote_plus(seed.query)}&hl=zh-CN&num={max_results}"
        baidu_url = f"https://www.baidu.com/s?wd={quote_plus(seed.query)}"

        for url, parser in (
            (google_url, self._parse_google_results),
            (baidu_url, self._parse_baidu_results),
        ):
            try:
                response = await client.get(url)
                response.raise_for_status()
                results = parser(
                    html=response.text,
                    category=seed.category,
                    query=seed.query,
                )
                if results:
                    return results[:max_results]
            except Exception:
                continue
        return []

    def _parse_google_results(
        self,
        *,
        html: str,
        category: str,
        query: str,
    ) -> list[RawEvidence]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[RawEvidence] = []
        for anchor in soup.select("a[href^='/url?q=']"):
            href = anchor.get("href", "")
            if "/url?q=" not in href:
                continue
            target = href.split("/url?q=", 1)[1].split("&", 1)[0]
            title_node = anchor.find("h3")
            title = title_node.get_text(" ", strip=True) if title_node else ""
            snippet_node = anchor.find_parent().find_next("span") if anchor.find_parent() else None
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if target and title:
                results.append(
                    RawEvidence(
                        category=category,
                        query=query,
                        title=title,
                        source_url=target,
                        source_name=_derive_source_name(target),
                        snippet=snippet,
                        metadata={"search_type": "google-public"},
                    )
                )
        return results

    def _parse_baidu_results(
        self,
        *,
        html: str,
        category: str,
        query: str,
    ) -> list[RawEvidence]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[RawEvidence] = []
        for item in soup.select("div.result, div.c-container"):
            anchor = item.select_one("h3 a")
            if not anchor:
                continue
            link = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            snippet_node = item.select_one(".c-abstract, .content-right_8Zs40, .c-span-last")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if link and title:
                results.append(
                    RawEvidence(
                        category=category,
                        query=query,
                        title=title,
                        source_url=link,
                        source_name=_derive_source_name(link),
                        snippet=snippet,
                        metadata={"search_type": "baidu-public"},
                    )
                )
        return results

    async def _hydrate_content(self, client: httpx.AsyncClient, item: RawEvidence) -> str:
        async with self._semaphore:
            try:
                response = await client.get(item.source_url, headers={"User-Agent": self._user_agent()})
                response.raise_for_status()
            except Exception:
                return item.snippet

            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type or item.source_url.lower().endswith(".pdf"):
                item.pdf_url = item.source_url
                return _extract_pdf_text(response.content)[:4000] or item.snippet
            return _extract_html_text(response.text)[:5000] or item.snippet

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )


class AkShareCollector:
    def __init__(self, *, symbol: str = CANONICAL_STOCK_CODE) -> None:
        self.symbol = symbol

    def collect(self) -> AkShareSnapshot:
        if ak is None:
            return AkShareSnapshot(
                quote_item=None,
                financial_item=None,
                research_items=[],
                metrics={"error": "akshare 未安装，跳过行情与财务采集。"},
            )

        quote_item, quote_metrics = self._build_quote_evidence()
        financial_item, financial_metrics = self._build_financial_evidence()
        research_items = self._build_research_report_evidences()

        metrics = {
            "quote": quote_metrics,
            "financials": financial_metrics,
            "research_report_count": len(research_items),
        }
        return AkShareSnapshot(
            quote_item=quote_item,
            financial_item=financial_item,
            research_items=research_items,
            metrics=metrics,
        )

    def _build_quote_evidence(self) -> tuple[RawEvidence | None, dict[str, Any]]:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")

        try:
            hist_df = ak.stock_zh_a_hist(
                symbol=self.symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        except Exception as exc:
            return None, {"error": str(exc)}

        if hist_df is None or hist_df.empty:
            return None, {"error": "stock_zh_a_hist 返回空数据。"}

        hist_df = hist_df.tail(2)
        latest = hist_df.iloc[-1].to_dict()
        previous = hist_df.iloc[0].to_dict() if len(hist_df) > 1 else latest

        close_price = _safe_number(latest.get("收盘"))
        previous_close = _safe_number(previous.get("收盘"))
        delta = close_price - previous_close if close_price is not None and previous_close is not None else None
        pct_change = (delta / previous_close * 100) if delta is not None and previous_close else _safe_number(latest.get("涨跌幅"))

        summary = (
            f"比亚迪A股最新收盘价{_format_number(close_price)}元，较前一交易日"
            f"{'上涨' if (pct_change or 0) >= 0 else '下跌'}{_format_number(abs(pct_change), suffix='%')}，"
            f"成交额{_format_large_number(_safe_number(latest.get('成交额')))}。"
        )
        evidence = RawEvidence(
            category="finance",
            query="AkShare 股价行情",
            title="比亚迪最新股价波动",
            source_url="https://quote.eastmoney.com/sz002594.html",
            source_name="AKShare / 东方财富",
            snippet=summary,
            content=json.dumps(latest, ensure_ascii=False, default=str),
            published_at=_parse_flexible_datetime(str(latest.get("日期") or "")),
            metadata={"quote_row": latest},
        )
        return evidence, {
            "date": latest.get("日期"),
            "close": close_price,
            "pct_change": pct_change,
            "turnover": _safe_number(latest.get("成交额")),
        }

    def _build_financial_evidence(self) -> tuple[RawEvidence | None, dict[str, Any]]:
        abstract_metrics = self._collect_financial_metrics()
        if "error" in abstract_metrics:
            return None, abstract_metrics

        summary = (
            f"最新报告期营业总收入{_format_large_number(abstract_metrics.get('revenue'))}，"
            f"归母净利润{_format_large_number(abstract_metrics.get('net_profit'))}，"
            f"研发投入{_format_large_number(abstract_metrics.get('rd_expense'))}，"
            f"研发投入占比{_format_number(abstract_metrics.get('rd_ratio'), suffix='%')}。"
        )
        content = json.dumps(abstract_metrics, ensure_ascii=False, default=str)
        evidence = RawEvidence(
            category="finance",
            query="AkShare 核心财务指标",
            title="比亚迪最新季度营收与研发投入",
            source_url="https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/002594.phtml",
            source_name="AKShare / 新浪财经",
            snippet=summary,
            content=content,
            published_at=_parse_flexible_datetime(str(abstract_metrics.get("report_date") or "")),
            metadata=abstract_metrics,
        )
        return evidence, abstract_metrics

    def _collect_financial_metrics(self) -> dict[str, Any]:
        long_df = None
        long_error = None
        try:
            long_df = ak.stock_financial_abstract_new_ths(symbol=self.symbol, indicator="按报告期")
        except Exception as exc:
            long_error = str(exc)

        if long_df is not None and not long_df.empty:
            return _extract_financial_metrics_from_long_df(long_df)

        pivot_df = None
        pivot_error = None
        try:
            pivot_df = ak.stock_financial_abstract(symbol=self.symbol)
        except Exception as exc:
            pivot_error = str(exc)

        if pivot_df is not None and not pivot_df.empty:
            return _extract_financial_metrics_from_pivot_df(pivot_df)

        indicator_df = None
        indicator_error = None
        try:
            indicator_df = ak.stock_financial_analysis_indicator_em(
                symbol=f"{self.symbol}.SZ",
                indicator="按报告期",
            )
        except Exception as exc:
            indicator_error = str(exc)

        if indicator_df is not None and not indicator_df.empty:
            latest = indicator_df.iloc[0].to_dict()
            return {
                "report_date": latest.get("REPORT_DATE"),
                "revenue": _safe_number(latest.get("TOTALOPERATEREVE")),
                "net_profit": _safe_number(latest.get("PARENTNETPROFIT")),
                "gross_margin": _safe_number(latest.get("XSMLL")),
                "roe": _safe_number(latest.get("ROEJQ")),
                "rd_expense": None,
                "rd_ratio": None,
            }

        return {
            "error": "无法从 AkShare 获取财务摘要。",
            "long_error": long_error,
            "pivot_error": pivot_error,
            "indicator_error": indicator_error,
        }

    def _build_research_report_evidences(self) -> list[RawEvidence]:
        try:
            reports_df = ak.stock_research_report_em(symbol=self.symbol)
        except Exception:
            return []

        if reports_df is None or reports_df.empty:
            return []

        items: list[RawEvidence] = []
        for _, row in reports_df.head(10).iterrows():
            pdf_url = str(row.get("报告PDF链接") or "").strip()
            report_name = str(row.get("报告名称") or "比亚迪研报")
            date_str = str(row.get("日期") or "")
            snippet = (
                f"{row.get('机构', '机构未披露')} 发布《{report_name}》，"
                f"评级 {row.get('东财评级', '未披露')}，"
                f"2025年预测市盈率 {row.get('2025-盈利预测-市盈率', '未披露')}。"
            )
            items.append(
                RawEvidence(
                    category="finance",
                    query="AkShare 个股研报",
                    title=report_name,
                    source_url=pdf_url or "https://data.eastmoney.com/report/stock.jshtml",
                    source_name="AKShare / 东方财富研报",
                    snippet=snippet,
                    content=json.dumps(row.to_dict(), ensure_ascii=False, default=str),
                    published_at=_parse_flexible_datetime(date_str),
                    pdf_url=pdf_url,
                    metadata={
                        "institution": row.get("机构"),
                        "rating": row.get("东财评级"),
                        "raw_row": row.to_dict(),
                    },
                )
            )
        return items


class OpenAILLMStructurer:
    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout: float = 40.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def structure(self, evidence: RawEvidence) -> StructuredInsight | None:
        if not evidence.title.strip():
            return None
        if not self.api_key or not self.base_url or not self.model:
            return self._fallback_structure(evidence)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "你是商业风险数据清洗器。"
                                    "请把输入内容整理为 JSON，字段必须包含："
                                    "category, topic, importance, sentiment, summary, "
                                    "amount_or_ratio, knowledge_worthy, report_excerpt, tags。"
                                    "importance 只能是 一般/重要/致命；"
                                    "sentiment 只能是 正面/负面/中性；"
                                    "summary 必须在 100 字以内。"
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "company": CANONICAL_COMPANY_NAME,
                                        "target_category": evidence.category,
                                        "query": evidence.query,
                                        "title": evidence.title,
                                        "snippet": evidence.snippet,
                                        "content": evidence.content[:3500],
                                        "source_name": evidence.source_name,
                                        "source_url": evidence.source_url,
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return self._fallback_structure(evidence)

        text = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        data = _safe_json_parse(text)
        if not isinstance(data, dict):
            return self._fallback_structure(evidence)

        summary = _clip_text(str(data.get("summary") or evidence.snippet or evidence.title), 100)
        content = evidence.content or evidence.snippet or evidence.title

        return StructuredInsight(
            category=_normalize_category(str(data.get("category") or evidence.category)),
            title=evidence.title,
            summary=summary,
            content=_clip_text(content, 2000),
            severity=_normalize_importance(str(data.get("importance") or "")),
            sentiment=_normalize_sentiment(str(data.get("sentiment") or "")),
            amount_or_ratio=_clip_text(str(data.get("amount_or_ratio") or _extract_amount_or_ratio(content)), 60),
            source_url=evidence.source_url,
            source_name=evidence.source_name,
            occurred_at=evidence.published_at,
            query=evidence.query,
            tags=_coerce_tags(data.get("tags")),
            raw_evidence=evidence,
            knowledge_worthy=bool(data.get("knowledge_worthy")),
            report_excerpt=_clip_text(str(data.get("report_excerpt") or ""), 500),
            extra_payload={
                "topic": data.get("topic"),
                "llm_structured": data,
            },
        )

    def _fallback_structure(self, evidence: RawEvidence) -> StructuredInsight:
        sentiment = _heuristic_sentiment(evidence.combined_text)
        severity = _heuristic_importance(evidence.combined_text, evidence.category)
        summary = _heuristic_summary(evidence)
        return StructuredInsight(
            category=_normalize_category(evidence.category),
            title=evidence.title,
            summary=summary,
            content=_clip_text(evidence.content or evidence.snippet or evidence.title, 2000),
            severity=severity,
            sentiment=sentiment,
            amount_or_ratio=_extract_amount_or_ratio(evidence.combined_text),
            source_url=evidence.source_url,
            source_name=evidence.source_name,
            occurred_at=evidence.published_at,
            query=evidence.query,
            tags=_guess_tags(evidence),
            raw_evidence=evidence,
            knowledge_worthy=_is_knowledge_worthy(evidence),
            report_excerpt=_clip_text(evidence.content or evidence.snippet, 500),
            extra_payload={"fallback": True},
        )


class SemanticEncoder:
    def __init__(self, *, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self.model_name = model_name
        self._model = None

    def encode(self, texts: list[str]) -> list[list[float]] | None:
        normalized = [text.strip() for text in texts if text and text.strip()]
        if not normalized:
            return []
        if SentenceTransformer is None or np is None:
            return None
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception:
                return None
        try:
            vectors = self._model.encode(
                normalized,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception:
            return None
        return vectors.tolist()

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if np is None:
            return 0.0
        left_array = np.array(left)
        right_array = np.array(right)
        denominator = float(np.linalg.norm(left_array) * np.linalg.norm(right_array))
        if denominator == 0:
            return 0.0
        return float(np.dot(left_array, right_array) / denominator)


class SemanticDeduper:
    def __init__(self, *, encoder: SemanticEncoder, threshold: float = 0.84) -> None:
        self.encoder = encoder
        self.threshold = threshold

    def dedupe(self, items: list[StructuredInsight]) -> tuple[list[StructuredInsight], int]:
        if not items:
            return [], 0

        texts = [item.similarity_text for item in items]
        vectors = self.encoder.encode(texts)

        kept: list[StructuredInsight] = []
        kept_vectors: list[list[float]] = []
        deduped_count = 0

        for index, item in enumerate(items):
            is_duplicate = False
            if vectors:
                current_vector = vectors[index]
                for existing_vector in kept_vectors:
                    similarity = self.encoder.cosine_similarity(current_vector, existing_vector)
                    if similarity >= self.threshold:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    kept.append(item)
                    kept_vectors.append(current_vector)
                    continue

            if not vectors:
                for existing in kept:
                    ratio = _lexical_similarity(item.similarity_text, existing.similarity_text)
                    if ratio >= 0.88:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    kept.append(item)
                    continue

            deduped_count += 1

        return kept, deduped_count


class KnowledgeSyncer:
    def __init__(
        self,
        *,
        encoder: SemanticEncoder,
        vector_store_path: Path = VECTOR_STORE_PATH,
    ) -> None:
        self.fastgpt = FastGPTService()
        self.encoder = encoder
        self.vector_store_path = vector_store_path

    async def sync(
        self,
        *,
        company_name: str,
        insights: list[StructuredInsight],
        research_items: list[RawEvidence],
        sync_fastgpt: bool,
        dry_run: bool,
    ) -> KnowledgeSyncResult:
        documents = self._build_documents(company_name=company_name, insights=insights, research_items=research_items)
        if not documents:
            return KnowledgeSyncResult(mode="skipped", document_count=0)

        statuses: list[int] = []
        mode = "payload_only"
        if sync_fastgpt and not dry_run:
            for document in documents:
                payload = {
                    "dataset_id": self.fastgpt.settings.fastgpt_dataset_id,
                    "document_id": document["document_id"],
                    "title": document["title"],
                    "metadata": document["metadata"],
                    "content": document["content"],
                    "blocks": document["blocks"],
                }
                try:
                    sync_mode, status_code = await self.fastgpt.sync_dataset_payload(payload)
                    mode = sync_mode
                    if status_code:
                        statuses.append(status_code)
                except Exception:
                    mode = "fastgpt_error"

        vector_path = ""
        if not dry_run:
            vector_path = self._write_local_vector_store(documents)

        return KnowledgeSyncResult(
            mode=mode,
            fastgpt_statuses=statuses,
            local_vector_path=vector_path,
            document_count=len(documents),
        )

    def _build_documents(
        self,
        *,
        company_name: str,
        insights: list[StructuredInsight],
        research_items: list[RawEvidence],
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        knowledge_items = [
            item
            for item in insights
            if item.knowledge_worthy or item.category == "finance" or item.raw_evidence.pdf_url
        ]

        for index, item in enumerate(knowledge_items):
            documents.append(
                {
                    "document_id": f"{company_name}-insight-{index + 1}",
                    "title": f"{company_name} {item.category} - {item.title}",
                    "content": "\n".join(
                        [
                            f"摘要: {item.summary}",
                            f"正文: {item.content}",
                            f"来源: {item.source_name} {item.source_url}",
                            f"重要性: {item.severity}",
                            f"情绪: {item.sentiment}",
                            f"相关指标: {item.amount_or_ratio or '未提取'}",
                        ]
                    ),
                    "metadata": {
                        "company_name": company_name,
                        "category": item.category,
                        "severity": item.severity,
                        "sentiment": item.sentiment,
                        "source_url": item.source_url,
                    },
                    "blocks": [
                        {
                            "summary": item.summary,
                            "excerpt": item.report_excerpt or item.content[:500],
                            "source_url": item.source_url,
                        }
                    ],
                }
            )

        for index, item in enumerate(research_items):
            content = item.content if item.content else item.snippet
            documents.append(
                {
                    "document_id": f"{company_name}-report-{index + 1}",
                    "title": f"{company_name} 研报 - {item.title}",
                    "content": "\n".join(
                        [
                            item.title,
                            content,
                            f"PDF: {item.pdf_url or '未提供'}",
                            f"来源: {item.source_name} {item.source_url}",
                        ]
                    ),
                    "metadata": {
                        "company_name": company_name,
                        "category": "finance",
                        "source_url": item.source_url,
                        "pdf_url": item.pdf_url,
                    },
                    "blocks": [
                        {
                            "summary": item.snippet,
                            "pdf_url": item.pdf_url,
                            "source_url": item.source_url,
                        }
                    ],
                }
            )
        return documents

    def _write_local_vector_store(self, documents: list[dict[str, Any]]) -> str:
        self.vector_store_path.parent.mkdir(parents=True, exist_ok=True)

        embeddings = self.encoder.encode([item["content"] for item in documents]) or []
        with self.vector_store_path.open("w", encoding="utf-8") as handle:
            for index, document in enumerate(documents):
                row = dict(document)
                row["embedding"] = embeddings[index] if embeddings else []
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return str(self.vector_store_path)


class DatabaseWriter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_company(self, *, name: str, stock_code: str, dry_run: bool) -> Company:
        statement = select(Company).where(
            or_(
                Company.name == name,
                Company.credit_code == stock_code,
            )
        )
        company = self.db.execute(statement).scalar_one_or_none()
        if company:
            profile = dict(company.company_profile or {})
            if profile.get("stock_code") != stock_code:
                profile["stock_code"] = stock_code
                company.company_profile = profile
                if not dry_run:
                    self.db.add(company)
                    self.db.commit()
                    self.db.refresh(company)
            return company

        company = Company(
            name=name,
            credit_code=stock_code,
            industry="新能源汽车",
            region="中国 / 全球化经营",
            description="BYD 商业分析 Demo 的核心样本企业。",
            official_website="https://www.byd.com",
            company_profile={
                "stock_code": stock_code,
                "aliases": ["比亚迪", "BYD"],
                "demo_seeded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if dry_run:
            return company
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def upsert_risk_events(
        self,
        *,
        company: Company,
        insights: list[StructuredInsight],
        dry_run: bool,
    ) -> tuple[list[RiskEvent], int]:
        inserted: list[RiskEvent] = []
        skipped = 0

        existing_urls: set[str] = set()
        existing_titles: set[str] = set()
        if company.id is not None:
            existing_urls = set(
                self.db.execute(
                    select(RiskEvent.source_url).where(RiskEvent.company_id == company.id)
                ).scalars()
            )
            existing_titles = set(
                self.db.execute(
                    select(RiskEvent.title).where(RiskEvent.company_id == company.id)
                ).scalars()
            )

        for item in insights:
            if item.source_url in existing_urls or item.title in existing_titles:
                skipped += 1
                continue

            risk_event = RiskEvent(
                company_id=company.id,
                category=item.category,
                severity=item.severity,
                title=item.title,
                content=item.summary,
                source_url=item.source_url,
                source_name=item.source_name,
                occurred_at=item.occurred_at,
                sentiment=item.sentiment,
                extra_payload={
                    "amount_or_ratio": item.amount_or_ratio,
                    "query": item.query,
                    "tags": item.tags,
                    "full_content": item.content,
                    "knowledge_worthy": item.knowledge_worthy,
                    "report_excerpt": item.report_excerpt,
                    "raw_metadata": item.raw_evidence.metadata,
                    **item.extra_payload,
                },
            )
            inserted.append(risk_event)
            existing_urls.add(item.source_url)
            existing_titles.add(item.title)

        if dry_run or not inserted:
            return inserted, skipped

        self.db.add_all(inserted)
        self.db.commit()
        for event in inserted:
            self.db.refresh(event)
        return inserted, skipped

    def create_analysis_report(
        self,
        *,
        company: Company,
        insights: list[StructuredInsight],
        akshare_snapshot: AkShareSnapshot,
        knowledge_sync: KnowledgeSyncResult,
        dry_run: bool,
    ) -> AnalysisReport | None:
        if not insights:
            return None

        counts_by_category = _count_by_key(insights, lambda item: item.category)
        counts_by_severity = _count_by_key(insights, lambda item: item.severity)
        counts_by_sentiment = _count_by_key(insights, lambda item: item.sentiment)

        top_items = sorted(
            insights,
            key=lambda item: _severity_score(item.severity),
            reverse=True,
        )[:8]

        summary = (
            f"本次比亚迪扫描共形成 {len(insights)} 条结构化动态，"
            f"其中负面 {counts_by_sentiment.get('负面', 0)} 条，"
            f"正面 {counts_by_sentiment.get('正面', 0)} 条，"
            f"重点聚焦欧盟反补贴、海外建厂、季度财务与品牌价格战舆情。"
        )

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts_by_category": counts_by_category,
            "counts_by_severity": counts_by_severity,
            "counts_by_sentiment": counts_by_sentiment,
            "akshare_metrics": akshare_snapshot.metrics,
            "knowledge_sync": {
                "mode": knowledge_sync.mode,
                "document_count": knowledge_sync.document_count,
                "local_vector_path": knowledge_sync.local_vector_path,
                "fastgpt_statuses": knowledge_sync.fastgpt_statuses,
            },
            "highlights": [
                {
                    "category": item.category,
                    "title": item.title,
                    "summary": item.summary,
                    "severity": item.severity,
                    "sentiment": item.sentiment,
                    "source_url": item.source_url,
                }
                for item in top_items
            ],
        }

        report = AnalysisReport(
            company_id=company.id,
            report_type="byd_full_scan",
            title="比亚迪全网扫描快照",
            summary=summary,
            snapshot=snapshot,
            model_name=os.getenv("LLM_MODEL", "rule-based"),
        )

        if dry_run:
            return report

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report


class BYDIngestionEngine:
    def __init__(
        self,
        *,
        db: Session,
        search_client: BroadSearchClient,
        structurer: OpenAILLMStructurer,
        deduper: SemanticDeduper,
        knowledge_syncer: KnowledgeSyncer,
        akshare_collector: AkShareCollector,
    ) -> None:
        self.db = db
        self.search_client = search_client
        self.structurer = structurer
        self.deduper = deduper
        self.knowledge_syncer = knowledge_syncer
        self.akshare_collector = akshare_collector
        self.writer = DatabaseWriter(db)

    async def run(
        self,
        *,
        company_name: str = CANONICAL_COMPANY_NAME,
        stock_code: str = CANONICAL_STOCK_CODE,
        max_results_per_query: int = 5,
        query_limit: int | None = None,
        sync_fastgpt: bool = False,
        dry_run: bool = False,
    ) -> IngestionRunResult:
        company = self.writer.ensure_company(
            name=company_name,
            stock_code=stock_code,
            dry_run=dry_run,
        )

        search_seeds = build_byd_search_seeds()
        if query_limit is not None:
            search_seeds = search_seeds[:query_limit]

        search_items = await self.search_client.collect(
            search_seeds,
            max_results_per_query=max_results_per_query,
            fetch_page_content=True,
        )

        akshare_snapshot = await asyncio.to_thread(self.akshare_collector.collect)
        raw_items = list(search_items)
        if akshare_snapshot.quote_item:
            raw_items.append(akshare_snapshot.quote_item)
        if akshare_snapshot.financial_item:
            raw_items.append(akshare_snapshot.financial_item)
        raw_items.extend(akshare_snapshot.research_items)

        structured_batches = await asyncio.gather(
            *(self.structurer.structure(item) for item in raw_items),
            return_exceptions=True,
        )

        structured_items: list[StructuredInsight] = []
        for row in structured_batches:
            if isinstance(row, Exception) or row is None:
                continue
            structured_items.append(row)

        deduped_items, deduped_count = self.deduper.dedupe(structured_items)
        inserted_events, skipped_count = self.writer.upsert_risk_events(
            company=company,
            insights=deduped_items,
            dry_run=dry_run,
        )
        knowledge_sync = await self.knowledge_syncer.sync(
            company_name=company.name,
            insights=deduped_items,
            research_items=akshare_snapshot.research_items,
            sync_fastgpt=sync_fastgpt,
            dry_run=dry_run,
        )
        report = self.writer.create_analysis_report(
            company=company,
            insights=deduped_items,
            akshare_snapshot=akshare_snapshot,
            knowledge_sync=knowledge_sync,
            dry_run=dry_run,
        )

        counts_by_sentiment = _count_by_key(deduped_items, lambda item: item.sentiment)
        counts_by_category = _count_by_key(deduped_items, lambda item: item.category)
        counts_by_severity = _count_by_key(deduped_items, lambda item: item.severity)

        return IngestionRunResult(
            company_id=company.id,
            inserted_count=len(inserted_events),
            skipped_count=skipped_count,
            positive_count=counts_by_sentiment.get("正面", 0),
            negative_count=counts_by_sentiment.get("负面", 0),
            neutral_count=counts_by_sentiment.get("中性", 0),
            total_raw_count=len(raw_items),
            total_structured_count=len(structured_items),
            total_deduped_count=len(deduped_items),
            analysis_report_id=getattr(report, "id", None),
            knowledge_sync_result=knowledge_sync,
            counts_by_category=counts_by_category,
            counts_by_severity=counts_by_severity,
        )


def build_byd_search_seeds() -> list[SearchSeed]:
    return [
        SearchSeed(category="macro", query="比亚迪 欧盟 反补贴 关税 最新动态", search_type="news"),
        SearchSeed(category="macro", query="比亚迪 美国 关税 新能源汽车 最新政策", search_type="search"),
        SearchSeed(category="macro", query="比亚迪 全球 新能源车 市占率 变化", search_type="news"),
        SearchSeed(category="operations", query="比亚迪 仰望 品牌 销量 最新", search_type="news"),
        SearchSeed(category="operations", query="比亚迪 巴西 建厂 进度 最新", search_type="news"),
        SearchSeed(category="operations", query="比亚迪 匈牙利 建厂 进度 最新", search_type="news"),
        SearchSeed(category="finance", query="比亚迪 最新季度 营收 研发投入 占比", search_type="news"),
        SearchSeed(category="finance", query="比亚迪 2025 财报 解读", search_type="search"),
        SearchSeed(category="finance", query="比亚迪 研报 PDF", search_type="search"),
        SearchSeed(category="legal", query="比亚迪 欧盟 反补贴 调查 最新动态", search_type="news"),
        SearchSeed(category="legal", query="比亚迪 海外 知识产权 诉讼", search_type="news"),
        SearchSeed(category="brand", query="比亚迪 价格战 用户 评价", search_type="search"),
        SearchSeed(category="brand", query="比亚迪 智驾 水平 用户 评价", search_type="search"),
        SearchSeed(category="brand", query="比亚迪 刀片电池 舆情", search_type="news"),
        SearchSeed(category="brand", query="比亚迪 出海 风险", search_type="news"),
    ]


def render_terminal_summary(result: IngestionRunResult) -> str:
    lines = [
        "==== 比亚迪扫描摘要报告 ====",
        f"原始抓取: {result.total_raw_count} 条",
        f"结构化完成: {result.total_structured_count} 条",
        f"语义去重后: {result.total_deduped_count} 条",
        f"写入 risk_events: {result.inserted_count} 条",
        f"跳过重复: {result.skipped_count} 条",
        f"正面: {result.positive_count} 条",
        f"负面: {result.negative_count} 条",
        f"中性: {result.neutral_count} 条",
        f"analysis_report ID: {result.analysis_report_id or 'dry-run / 未生成'}",
        f"知识库同步: {result.knowledge_sync_result.mode}",
        f"知识文档数: {result.knowledge_sync_result.document_count}",
    ]
    if result.knowledge_sync_result.local_vector_path:
        lines.append(f"本地向量库: {result.knowledge_sync_result.local_vector_path}")
    lines.append(f"分类分布: {json.dumps(result.counts_by_category, ensure_ascii=False)}")
    lines.append(f"重要性分布: {json.dumps(result.counts_by_severity, ensure_ascii=False)}")
    return "\n".join(lines)


def _extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def _extract_pdf_text(content: bytes) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(BytesIO(content))
    except Exception:
        return ""

    texts: list[str] = []
    for page in reader.pages[:8]:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(texts)


def _safe_json_parse(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _clip_text(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 0)] + "…"


def _heuristic_summary(evidence: RawEvidence) -> str:
    text = evidence.snippet or evidence.content or evidence.title
    return _clip_text(text, 100)


def _heuristic_sentiment(text: str) -> str:
    lowered = text.lower()
    negative_keywords = ["诉讼", "调查", "反补贴", "关税", "下滑", "风险", "价格战", "召回", "违规"]
    positive_keywords = ["增长", "上升", "盈利", "突破", "落地", "投产", "签约", "销量增长"]
    negative_hits = sum(1 for item in negative_keywords if item in lowered)
    positive_hits = sum(1 for item in positive_keywords if item in lowered)
    if negative_hits > positive_hits:
        return "负面"
    if positive_hits > negative_hits:
        return "正面"
    return "中性"


def _heuristic_importance(text: str, category: str) -> str:
    lowered = text.lower()
    fatal_keywords = ["致命", "禁售", "大规模召回", "重大诉讼", "反补贴调查", "被执行", "刑事"]
    important_keywords = ["关税", "调查", "价格战", "下滑", "亏损", "工厂延期", "诉讼", "投诉"]
    if any(keyword in lowered for keyword in fatal_keywords):
        return "致命"
    if any(keyword in lowered for keyword in important_keywords):
        return "重要"
    if category in {"finance", "legal"}:
        return "重要"
    return "一般"


def _extract_amount_or_ratio(text: str) -> str:
    pattern = re.compile(
        r"(\d+(?:\.\d+)?\s*(?:亿|万|亿元|万元|亿美元|万欧元|欧元|元|%|个百分点|万辆|万台|台|座))"
    )
    matches = []
    for raw in pattern.findall(text):
        value = raw.replace(" ", "")
        if value not in matches:
            matches.append(value)
        if len(matches) >= 3:
            break
    return " / ".join(matches)


def _coerce_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[，,、/]", value) if item.strip()]
    return []


def _guess_tags(evidence: RawEvidence) -> list[str]:
    tags: list[str] = [evidence.category]
    for keyword in ("欧盟", "美国", "巴西", "匈牙利", "价格战", "智驾", "刀片电池", "仰望", "财报"):
        if keyword in evidence.combined_text and keyword not in tags:
            tags.append(keyword)
    return tags


def _is_knowledge_worthy(evidence: RawEvidence) -> bool:
    text = evidence.combined_text
    if evidence.pdf_url:
        return True
    keywords = ["财报", "研报", "季度", "解读", "市占率", "建厂", "反补贴"]
    return any(keyword in text for keyword in keywords)


def _normalize_importance(value: str) -> str:
    mapping = {
        "一般": "一般",
        "低": "一般",
        "普通": "一般",
        "important": "重要",
        "重要": "重要",
        "高": "重要",
        "critical": "致命",
        "致命": "致命",
        "严重": "致命",
    }
    return mapping.get(value.strip().lower(), "一般")


def _normalize_sentiment(value: str) -> str:
    mapping = {
        "positive": "正面",
        "正面": "正面",
        "利好": "正面",
        "negative": "负面",
        "负面": "负面",
        "利空": "负面",
        "neutral": "中性",
        "中性": "中性",
    }
    return mapping.get(value.strip().lower(), "中性")


def _normalize_category(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"macro", "宏观"}:
        return "macro"
    if lowered in {"operations", "业务", "运营"}:
        return "operations"
    if lowered in {"finance", "财务"}:
        return "finance"
    if lowered in {"legal", "法律", "诉讼"}:
        return "legal"
    if lowered in {"brand", "舆情", "品牌"}:
        return "brand"
    return "macro"


def _count_by_key(items: list[StructuredInsight], key_getter) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = key_getter(item)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _severity_score(value: str) -> int:
    return {"一般": 1, "重要": 2, "致命": 3}.get(value, 0)


def _safe_number(value: Any) -> float | None:
    if value in (None, "", "-", "nan"):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("%", "").strip()
        if not cleaned:
            return None
        return float(cleaned)
    except Exception:
        return None


def _format_number(value: float | None, *, suffix: str = "") -> str:
    if value is None:
        return "未披露"
    return f"{value:.2f}{suffix}"


def _format_large_number(value: float | None) -> str:
    if value is None:
        return "未披露"
    abs_value = abs(value)
    if abs_value >= 100000000:
        return f"{value / 100000000:.2f}亿元"
    if abs_value >= 10000:
        return f"{value / 10000:.2f}万元"
    return f"{value:.2f}元"


def _parse_flexible_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    zh_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if zh_match:
        year, month, day = [int(item) for item in zh_match.groups()]
        return datetime(year, month, day, tzinfo=timezone.utc)

    english_date = re.match(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s+(\d{4})", raw)
    if english_date:
        try:
            return datetime.strptime(raw, "%b %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                return datetime.strptime(raw, "%B %d, %Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    relative_match = re.match(r"(\d+)\s+(day|days|hour|hours)\s+ago", raw.lower())
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        now = datetime.now(timezone.utc)
        if unit.startswith("day"):
            return now - timedelta(days=amount)
        return now - timedelta(hours=amount)

    return None


def _derive_source_name(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or url
    return host.replace("www.", "")


def _lexical_similarity(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", left))
    right_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return overlap / union if union else 0.0


def _extract_financial_metrics_from_long_df(frame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"error": "财务长表为空。"}
    working = frame.copy()
    column_map = {
        "报告期": "report_date",
        "报告日期": "report_date",
        "report_date": "report_date",
        "指标": "metric_name",
        "指标名称": "metric_name",
        "metric_name": "metric_name",
        "值": "value",
        "数值": "value",
        "value": "value",
    }
    working.rename(columns={key: value for key, value in column_map.items() if key in working.columns}, inplace=True)
    if "report_date" not in working.columns or "metric_name" not in working.columns:
        return {"error": f"财务长表字段不匹配: {list(working.columns)}"}
    working = working.sort_values(by="report_date", ascending=False)

    def pick_metric(*keywords: str) -> tuple[Any, Any]:
        for keyword in keywords:
            matches = working[working["metric_name"].astype(str).str.contains(keyword, na=False)]
            if not matches.empty:
                row = matches.iloc[0]
                return row.get("report_date"), _safe_number(row.get("value"))
        return None, None

    report_date, revenue = pick_metric("营业总收入", "营业收入")
    _, net_profit = pick_metric("归母净利润", "归属于母公司所有者的净利润", "归属净利润")
    _, rd_expense = pick_metric("研发费用", "研发投入")
    _, rd_ratio = pick_metric("研发投入占营业收入比例", "研发投入占营收比例", "研发费用率")

    if rd_ratio is None and rd_expense and revenue:
        rd_ratio = rd_expense / revenue * 100

    return {
        "report_date": report_date,
        "revenue": revenue,
        "net_profit": net_profit,
        "rd_expense": rd_expense,
        "rd_ratio": rd_ratio,
    }


def _extract_financial_metrics_from_pivot_df(frame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"error": "财务透视表为空。"}

    report_columns = [column for column in frame.columns if re.fullmatch(r"\d{8}", str(column))]
    if not report_columns:
        return {"error": "未识别到财务报告期字段。"}
    report_columns.sort(reverse=True)
    latest_column = report_columns[0]
    metric_column = "指标" if "指标" in frame.columns else frame.columns[0]

    def pick_metric(*keywords: str) -> float | None:
        for keyword in keywords:
            rows = frame[frame[metric_column].astype(str).str.contains(keyword, na=False)]
            if not rows.empty:
                return _safe_number(rows.iloc[0].get(latest_column))
        return None

    revenue = pick_metric("营业总收入", "营业收入")
    net_profit = pick_metric("归母净利润", "归属净利润")
    rd_expense = pick_metric("研发费用", "研发投入")
    rd_ratio = pick_metric("研发投入占营业收入比例", "研发费用率")
    if rd_ratio is None and rd_expense and revenue:
        rd_ratio = rd_expense / revenue * 100

    return {
        "report_date": latest_column,
        "revenue": revenue,
        "net_profit": net_profit,
        "rd_expense": rd_expense,
        "rd_ratio": rd_ratio,
    }
