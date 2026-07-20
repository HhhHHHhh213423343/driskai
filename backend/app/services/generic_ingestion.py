from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisReport, Company, IngestionRun, RiskEvent

try:
    import akshare as ak
except ImportError:  # pragma: no cover - runtime optional dependency
    ak = None


CATEGORY_LABELS = {
    "macro": "宏观环境",
    "operations": "业务运营",
    "finance": "财务健康",
    "legal": "法律诉讼",
    "brand": "品牌舆情",
}

DEFAULT_CATEGORIES = ["macro", "operations", "finance", "legal", "brand"]


@dataclass(frozen=True)
class SourceSpec:
    code: str
    name: str
    categories: tuple[str, ...]
    requires_api_key: bool = False
    rate_limit: str = "每日批处理；单公司低频请求"
    enabled: bool = True
    notes: str = ""


@dataclass(frozen=True)
class IngestionContext:
    company: Company
    company_name: str
    stock_code: str = ""
    market: str = ""
    categories: tuple[str, ...] = tuple(DEFAULT_CATEGORIES)


@dataclass
class RawEvidence:
    source_code: str
    source_name: str
    category: str
    title: str
    source_url: str
    content: str = ""
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredInsight:
    category: str
    severity: str
    title: str
    content: str
    source_url: str
    source_name: str
    occurred_at: datetime | None
    sentiment: str
    raw_evidence: RawEvidence
    extra_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceCollectResult:
    source_code: str
    source_name: str
    items: list[RawEvidence] = field(default_factory=list)
    error: str = ""


@dataclass
class CompanyIngestionResult:
    company_id: Any
    company_name: str
    raw_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    source_counts: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, str]] = field(default_factory=list)


class DataSourceAdapter:
    spec: SourceSpec

    def is_available(self) -> bool:
        return self.spec.enabled

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        raise NotImplementedError


class CninfoAnnouncementSource(DataSourceAdapter):
    spec = SourceSpec(
        code="cninfo_announcements",
        name="巨潮资讯公告",
        categories=("finance", "legal", "operations"),
        notes="上市公司公告与财报优先来源；不需要登录态。",
    )

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        if not context.stock_code:
            return SourceCollectResult(self.spec.code, self.spec.name)

        endpoint = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
        since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "pageNum": "1",
            "pageSize": str(max_results),
            "column": _cninfo_column(context.market, context.stock_code),
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": context.company_name,
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{since}~{today}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.cninfo.com.cn",
            "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch",
            "User-Agent": _user_agent(),
        }

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.post(endpoint, data=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return SourceCollectResult(self.spec.code, self.spec.name, error=str(exc))

        items: list[RawEvidence] = []
        for row in data.get("announcements") or []:
            title = _clean_html(str(row.get("announcementTitle") or ""))
            if not title:
                continue
            adjunct_url = str(row.get("adjunctUrl") or "")
            source_url = urljoin("https://static.cninfo.com.cn/", adjunct_url)
            occurred_at = _parse_timestamp(row.get("announcementTime"))
            items.append(
                RawEvidence(
                    source_code=self.spec.code,
                    source_name=self.spec.name,
                    category=_infer_category(title, "", fallback="finance"),
                    title=title,
                    source_url=source_url,
                    content=f"{context.company_name}公告：{title}",
                    occurred_at=occurred_at,
                    metadata={
                        "announcement_id": row.get("announcementId"),
                        "sec_code": row.get("secCode"),
                        "sec_name": row.get("secName"),
                    },
                )
            )
        return SourceCollectResult(self.spec.code, self.spec.name, items=items)


class ExchangeDisclosureSource(DataSourceAdapter):
    spec = SourceSpec(
        code="exchange_disclosure",
        name="交易所公开披露",
        categories=("finance", "legal", "operations"),
        rate_limit="每日批处理；仅抓取公开搜索页摘要",
        notes="用于补充交易所官网披露页，不绕过验证码或登录。",
    )

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        if not context.stock_code:
            return SourceCollectResult(self.spec.code, self.spec.name)

        if context.stock_code.startswith(("6", "9")) or context.market.lower() == "sse":
            url = f"https://www.sse.com.cn/home/search/?webswd={quote_plus(context.stock_code)}"
        else:
            url = f"https://www.szse.cn/application/search/index.html?keyword={quote_plus(context.stock_code)}"

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": _user_agent()},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception as exc:
            return SourceCollectResult(self.spec.code, self.spec.name, error=str(exc))

        soup = BeautifulSoup(response.text, "html.parser")
        items: list[RawEvidence] = []
        seen_titles: set[str] = set()
        for link in soup.select("a"):
            title = " ".join(link.get_text(" ", strip=True).split())
            href = link.get("href") or ""
            if not title or title in seen_titles:
                continue
            if context.stock_code not in title and context.company_name[:4] not in title:
                continue
            source_url = urljoin(url, href)
            items.append(
                RawEvidence(
                    source_code=self.spec.code,
                    source_name=self.spec.name,
                    category=_infer_category(title, "", fallback="legal"),
                    title=title,
                    source_url=source_url,
                    content=title,
                    metadata={"search_url": url},
                )
            )
            seen_titles.add(title)
            if len(items) >= max_results:
                break

        return SourceCollectResult(self.spec.code, self.spec.name, items=items)


class AkShareFinanceSource(DataSourceAdapter):
    spec = SourceSpec(
        code="akshare_finance",
        name="AkShare金融数据",
        categories=("finance",),
        notes="依赖本地 akshare 包；用于行情、财务摘要、研报等补充数据。",
    )

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        if ak is None or not context.stock_code:
            return SourceCollectResult(self.spec.code, self.spec.name)
        try:
            items = await asyncio.to_thread(self._collect_sync, context, max_results)
        except Exception as exc:
            return SourceCollectResult(self.spec.code, self.spec.name, error=str(exc))
        return SourceCollectResult(self.spec.code, self.spec.name, items=items)

    def _collect_sync(
        self,
        context: IngestionContext,
        max_results: int,
    ) -> list[RawEvidence]:
        items: list[RawEvidence] = []
        now = datetime.now(timezone.utc)

        if hasattr(ak, "stock_individual_info_em"):
            info_df = ak.stock_individual_info_em(symbol=context.stock_code)
            info = _records_from_dataframe(info_df)
            if info:
                content = "；".join(
                    f"{row.get('item') or row.get('指标')}: {row.get('value') or row.get('值')}"
                    for row in info[:max_results]
                )
                items.append(
                    RawEvidence(
                        source_code=self.spec.code,
                        source_name=self.spec.name,
                        category="finance",
                        title=f"{context.company_name} 基础行情与公司信息",
                        source_url=f"akshare://stock_individual_info_em/{context.stock_code}",
                        content=content,
                        occurred_at=now,
                        metadata={"provider": "akshare", "function": "stock_individual_info_em"},
                    )
                )

        if hasattr(ak, "stock_financial_abstract"):
            financial_df = ak.stock_financial_abstract(symbol=context.stock_code)
            records = _records_from_dataframe(financial_df)
            if records:
                first = records[0]
                content = "；".join(f"{key}: {value}" for key, value in list(first.items())[:12])
                items.append(
                    RawEvidence(
                        source_code=self.spec.code,
                        source_name=self.spec.name,
                        category="finance",
                        title=f"{context.company_name} 最新财务摘要",
                        source_url=f"akshare://stock_financial_abstract/{context.stock_code}",
                        content=content,
                        occurred_at=now,
                        metadata={"provider": "akshare", "function": "stock_financial_abstract"},
                    )
                )

        return items[:max_results]


class SearchApiNewsSource(DataSourceAdapter):
    spec = SourceSpec(
        code="news_search_api",
        name="新闻搜索API",
        categories=("macro", "operations", "legal", "brand"),
        requires_api_key=True,
        rate_limit="每日批处理；按 SERPER_API_KEY 配额限流",
        notes="仅在配置 SERPER_API_KEY 后启用；优先白名单新闻与官方站点。",
    )

    def is_available(self) -> bool:
        return bool(os.getenv("SERPER_API_KEY", "").strip())

    async def collect(
        self,
        context: IngestionContext,
        *,
        max_results: int,
    ) -> SourceCollectResult:
        api_key = os.getenv("SERPER_API_KEY", "").strip()
        if not api_key:
            return SourceCollectResult(self.spec.code, self.spec.name)

        queries = [
            f"{context.company_name} 风险 公告",
            f"{context.company_name} 监管 处罚",
            f"{context.company_name} 舆情 投诉",
        ]
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        items: list[RawEvidence] = []
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                for query in queries:
                    response = await client.post(
                        "https://google.serper.dev/news",
                        headers=headers,
                        json={"q": query, "num": max_results},
                    )
                    response.raise_for_status()
                    data = response.json()
                    for row in data.get("news") or []:
                        link = str(row.get("link") or "")
                        title = str(row.get("title") or "").strip()
                        if not title or not link or not _is_whitelisted_news_url(link, context):
                            continue
                        snippet = str(row.get("snippet") or "")
                        items.append(
                            RawEvidence(
                                source_code=self.spec.code,
                                source_name=str(row.get("source") or self.spec.name),
                                category=_infer_category(title, snippet, fallback="brand"),
                                title=title,
                                source_url=link,
                                content=snippet,
                                occurred_at=_parse_date(str(row.get("date") or "")),
                                metadata={"query": query},
                            )
                        )
                        if len(items) >= max_results:
                            break
                    if len(items) >= max_results:
                        break
        except Exception as exc:
            return SourceCollectResult(self.spec.code, self.spec.name, error=str(exc))

        return SourceCollectResult(self.spec.code, self.spec.name, items=items)


class GenericStructurer:
    def structure(self, evidence: RawEvidence) -> StructuredInsight:
        text = f"{evidence.title}\n{evidence.content}"
        return StructuredInsight(
            category=_infer_category(evidence.title, evidence.content, fallback=evidence.category),
            severity=_infer_severity(text),
            title=evidence.title[:255],
            content=evidence.content or evidence.title,
            source_url=evidence.source_url[:512],
            source_name=evidence.source_name[:128],
            occurred_at=evidence.occurred_at,
            sentiment=_infer_sentiment(text),
            raw_evidence=evidence,
            extra_payload={
                "source_code": evidence.source_code,
                "raw_metadata": evidence.metadata,
            },
        )


class DailyIngestionService:
    def __init__(
        self,
        db: Session,
        *,
        adapters: list[DataSourceAdapter] | None = None,
    ) -> None:
        self.db = db
        self.adapters = adapters or build_default_adapters()
        self.structurer = GenericStructurer()

    def list_source_specs(self) -> list[SourceSpec]:
        return [adapter.spec for adapter in self.adapters]

    async def run(
        self,
        *,
        company_ids: list[Any] | None = None,
        company_names: list[str] | None = None,
        stock_code_by_company: dict[str, str] | None = None,
        max_results_per_source: int = 5,
        enabled_source_codes: list[str] | None = None,
        dry_run: bool = False,
    ) -> IngestionRun:
        companies = self._resolve_companies(company_ids or [], company_names or [])
        stock_lookup = stock_code_by_company or {}
        started_at = datetime.now(timezone.utc)
        run_kwargs: dict[str, Any] = {}
        if dry_run:
            run_kwargs["id"] = uuid.uuid4()
        run = IngestionRun(
            status="running",
            started_at=started_at,
            requested_company_count=len(companies),
            source_breakdown={},
            failures=[],
            summary={},
            **run_kwargs,
        )
        if not dry_run:
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)

        source_filter = set(enabled_source_codes or [])
        adapters = [
            adapter
            for adapter in self.adapters
            if adapter.is_available() and (not source_filter or adapter.spec.code in source_filter)
        ]

        company_results: list[CompanyIngestionResult] = []
        for company in companies:
            result = await self._ingest_company(
                company=company,
                stock_code=stock_lookup.get(company.name, ""),
                adapters=adapters,
                max_results_per_source=max_results_per_source,
                dry_run=dry_run,
            )
            company_results.append(result)

        source_breakdown: Counter[str] = Counter()
        failures: list[dict[str, str]] = []
        for result in company_results:
            source_breakdown.update(result.source_counts)
            failures.extend(result.failures)

        run.status = "partial_failed" if failures else "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.scanned_company_count = len(company_results)
        run.total_raw_count = sum(item.raw_count for item in company_results)
        run.inserted_count = sum(item.inserted_count for item in company_results)
        run.skipped_count = sum(item.skipped_count for item in company_results)
        run.source_breakdown = dict(source_breakdown)
        run.failures = failures
        run.summary = {
            "dry_run": dry_run,
            "enabled_sources": [adapter.spec.code for adapter in adapters],
            "companies": [
                {
                    "company_id": str(item.company_id),
                    "company_name": item.company_name,
                    "raw_count": item.raw_count,
                    "inserted_count": item.inserted_count,
                    "skipped_count": item.skipped_count,
                }
                for item in company_results
            ],
        }

        if not dry_run:
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
        return run

    async def _ingest_company(
        self,
        *,
        company: Company,
        stock_code: str,
        adapters: list[DataSourceAdapter],
        max_results_per_source: int,
        dry_run: bool,
    ) -> CompanyIngestionResult:
        stock_code = stock_code or _company_stock_code(company)
        context = IngestionContext(
            company=company,
            company_name=company.name,
            stock_code=stock_code,
            market=_company_market(company),
        )
        collect_results = await asyncio.gather(
            *[
                adapter.collect(context, max_results=max_results_per_source)
                for adapter in adapters
            ],
            return_exceptions=True,
        )

        raw_items: list[RawEvidence] = []
        failures: list[dict[str, str]] = []
        for adapter, collect_result in zip(adapters, collect_results):
            if isinstance(collect_result, Exception):
                failures.append(
                    {
                        "company_name": company.name,
                        "source_code": adapter.spec.code,
                        "source_name": adapter.spec.name,
                        "error": str(collect_result),
                    }
                )
                continue
            if collect_result.error:
                failures.append(
                    {
                        "company_name": company.name,
                        "source_code": collect_result.source_code,
                        "source_name": collect_result.source_name,
                        "error": collect_result.error,
                    }
                )
            raw_items.extend(collect_result.items)

        insights = [self.structurer.structure(item) for item in raw_items]
        inserted, skipped = self._upsert_risk_events(company=company, insights=insights, dry_run=dry_run)
        source_counts = Counter(item.raw_evidence.source_name for item in insights)
        return CompanyIngestionResult(
            company_id=company.id,
            company_name=company.name,
            raw_count=len(raw_items),
            inserted_count=len(inserted),
            skipped_count=skipped,
            source_counts=dict(source_counts),
            failures=failures,
        )

    def _upsert_risk_events(
        self,
        *,
        company: Company,
        insights: list[StructuredInsight],
        dry_run: bool,
    ) -> tuple[list[RiskEvent], int]:
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
        inserted: list[RiskEvent] = []
        skipped = 0

        for item in insights:
            if item.source_url in existing_urls or item.title in existing_titles:
                skipped += 1
                continue
            risk_event = RiskEvent(
                company_id=company.id,
                category=item.category,
                severity=item.severity,
                title=item.title,
                content=item.content,
                source_url=item.source_url,
                source_name=item.source_name,
                occurred_at=item.occurred_at,
                sentiment=item.sentiment,
                extra_payload=item.extra_payload,
            )
            inserted.append(risk_event)
            existing_urls.add(item.source_url)
            existing_titles.add(item.title)

        if dry_run or not inserted:
            return inserted, skipped

        self.db.add_all(inserted)
        self.db.commit()
        for item in inserted:
            self.db.refresh(item)
        return inserted, skipped

    def _resolve_companies(
        self,
        company_ids: list[Any],
        company_names: list[str],
    ) -> list[Company]:
        statement = select(Company)
        if company_ids:
            statement = statement.where(Company.id.in_(company_ids))
        elif company_names:
            normalized = [item.strip() for item in company_names if item.strip()]
            statement = statement.where(Company.name.in_(normalized))
        return list(self.db.execute(statement.order_by(Company.created_at.desc())).scalars())


def build_default_adapters() -> list[DataSourceAdapter]:
    return [
        CninfoAnnouncementSource(),
        ExchangeDisclosureSource(),
        AkShareFinanceSource(),
        SearchApiNewsSource(),
    ]


def create_dashboard_summary(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=6)
    events = list(db.execute(select(RiskEvent)).scalars())
    reports = list(db.execute(select(AnalysisReport)).scalars())
    latest_run = db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    by_day: dict[str, int] = {}
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        by_day[day.strftime("%m-%d")] = 0

    for event in events:
        event_time = event.occurred_at or event.created_at
        if not event_time:
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if event_time >= start:
            by_day[event_time.strftime("%m-%d")] = by_day.get(event_time.strftime("%m-%d"), 0) + 1

    category_counts = Counter(item.category for item in events)
    report_type_counts = Counter(item.report_type for item in reports)
    latest_event = max(events, key=lambda item: item.created_at, default=None)
    source_breakdown = Counter(item.source_name or "未标注来源" for item in events)

    return {
        "total_events": len(events),
        "last_7_days_events": sum(by_day.values()),
        "high_priority_events": sum(
            1 for item in events if item.severity in {"high", "重要", "致命"}
        ),
        "report_count": len(reports),
        "latest_scan_label": _format_run_label(latest_run),
        "latest_change_label": _format_event_label(latest_event),
        "trend_series": [{"label": label, "value": value} for label, value in by_day.items()],
        "category_distribution": {
            CATEGORY_LABELS.get(category, category): count
            for category, count in category_counts.items()
        },
        "report_output": dict(report_type_counts),
        "source_breakdown": dict(source_breakdown),
        "latest_run": latest_run,
    }


def _cninfo_column(market: str, stock_code: str) -> str:
    normalized = market.lower().strip()
    if normalized in {"sse", "sh", "shse"} or stock_code.startswith(("6", "9")):
        return "sse"
    if normalized in {"bj", "bse", "neeq"} or stock_code.startswith(("4", "8")):
        return "neeq"
    return "szse"


def _company_stock_code(company: Company) -> str:
    profile = company.company_profile or {}
    return str(profile.get("stock_code") or profile.get("stockCode") or "").strip()


def _company_market(company: Company) -> str:
    profile = company.company_profile or {}
    return str(profile.get("market") or profile.get("exchange") or "").strip()


def _records_from_dataframe(dataframe: Any) -> list[dict[str, Any]]:
    if dataframe is None:
        return []
    if hasattr(dataframe, "to_dict"):
        return list(dataframe.to_dict(orient="records"))
    return []


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value, "html.parser").get_text(" ", strip=True)).strip()


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _parse_date(str(value))
    if number > 10_000_000_000:
        number = number / 1000
    return datetime.fromtimestamp(number, tz=timezone.utc)


def _parse_date(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _infer_category(title: str, content: str, *, fallback: str) -> str:
    text = f"{title} {content}"
    rules = [
        ("finance", ("财报", "年报", "季报", "业绩", "利润", "营收", "分红", "回购", "融资")),
        ("legal", ("诉讼", "仲裁", "处罚", "监管", "问询", "立案", "执行", "裁判", "违规")),
        ("brand", ("舆情", "投诉", "召回", "质量", "口碑", "用户", "媒体")),
        ("operations", ("项目", "投产", "采购", "产能", "供应链", "经营", "合同", "中标")),
        ("macro", ("政策", "关税", "行业", "出口", "贸易", "宏观")),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return fallback if fallback in CATEGORY_LABELS else "operations"


def _infer_severity(text: str) -> str:
    if any(keyword in text for keyword in ("重大", "处罚", "诉讼", "仲裁", "退市", "立案", "亏损", "监管问询")):
        return "重要"
    if any(keyword in text for keyword in ("公告", "风险", "变更", "下滑", "问询", "投诉")):
        return "重要"
    return "一般"


def _infer_sentiment(text: str) -> str:
    if any(keyword in text for keyword in ("处罚", "诉讼", "仲裁", "亏损", "下滑", "投诉", "违规", "召回")):
        return "negative"
    if any(keyword in text for keyword in ("增长", "中标", "回购", "分红", "投产", "突破")):
        return "positive"
    return "neutral"


def _is_whitelisted_news_url(url: str, context: IngestionContext) -> bool:
    whitelisted_hosts = (
        "people.com.cn",
        "xinhuanet.com",
        "cninfo.com.cn",
        "sse.com.cn",
        "szse.cn",
    )
    official = (context.company.official_website or "").replace("https://", "").replace("http://", "")
    if official:
        whitelisted_hosts = (*whitelisted_hosts, official.split("/")[0])
    return any(host in url for host in whitelisted_hosts)


def _format_run_label(run: IngestionRun | None) -> str:
    if not run:
        return "暂无批处理记录"
    started = run.started_at.strftime("%Y-%m-%d %H:%M:%S")
    finished = run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "运行中"
    return f"{started} 至 {finished}"


def _format_event_label(event: RiskEvent | None) -> str:
    if not event:
        return "暂无风险事件"
    happened_at = event.occurred_at or event.created_at
    date_label = happened_at.strftime("%Y-%m-%d") if happened_at else "未知日期"
    return f"{date_label} / {event.category} / {event.source_name or '未标注来源'}"


def _user_agent() -> str:
    return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
