from __future__ import annotations

import hashlib
import io
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import JSON, bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.source_registry import (
    SourceSpec,
    domains_for,
    source_plan_for,
    source_to_dict,
)


USER_AGENT = "D-Risk-AI-EvidenceBot/1.0 (+risk-research; respects robots.txt)"
MAX_TEXT_CHARS = 120_000

SOURCE_CATALOG: dict[str, dict[str, str]] = {
    "nfra_penalties": {
        "name": "国家金融监督管理总局行政处罚",
        "url": "https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=4113&itemName=%E6%80%BB%E5%B1%80%E6%9C%BA%E5%85%B3&itemPId=923&itemUrl=ItemListRightList.html&itemsubPId=931",
        "authority": "official",
    },
    "pbc_official": {"name": "中国人民银行", "url": "https://www.pbc.gov.cn/", "authority": "official"},
    "csrc_enforcement": {"name": "中国证券监督管理委员会", "url": "https://www.csrc.gov.cn/", "authority": "official"},
    "enterprise_credit": {"name": "国家企业信用信息公示系统", "url": "https://www.gsxt.gov.cn/", "authority": "official"},
    "cninfo_announcements": {"name": "巨潮资讯", "url": "https://www.cninfo.com.cn/new/index", "authority": "official"},
}

TRUSTED_DOMAINS = {
    "nfra.gov.cn", "pbc.gov.cn", "csrc.gov.cn", "samr.gov.cn", "gsxt.gov.cn",
    "cninfo.com.cn", "sse.com.cn", "szse.cn", "gov.cn", "stats.gov.cn",
    "ndrc.gov.cn", "xinhuanet.com", "people.com.cn", "cnstock.com", "stcn.com",
    "21jingji.com", "caixin.com", "hkexnews.hk", "creditchina.gov.cn",
    "court.gov.cn", "chinacourt.org", "chinamoney.com.cn", "chinabond.com.cn",
    "miit.gov.cn", "customs.gov.cn", "mee.gov.cn", "mem.gov.cn", "nmpa.gov.cn",
    "cde.org.cn", "nhsa.gov.cn", "mohurd.gov.cn", "mnr.gov.cn", "cac.gov.cn",
    "nea.gov.cn", "12315.cn",
    "bse.cn", "china-cba.net",
}

MEDIA_DOMAINS = {"xinhuanet.com", "people.com.cn", "cnstock.com", "stcn.com", "21jingji.com", "caixin.com"}

CATEGORY_KEYWORDS = {
    "finance": ("年报", "季报", "业绩", "营业收入", "净利润", "资本充足", "净息差", "不良贷款", "拨备覆盖", "分红", "债券", "资产减值"),
    "operations": ("经营", "业务", "客户", "贷款", "存款", "服务", "系统", "中断", "网点", "供应链", "订单", "产能", "交付"),
    "legal": ("处罚", "罚款", "诉讼", "仲裁", "监管", "违法", "调查", "纪律处分", "问询", "执行", "整改"),
    "brand": ("舆情", "投诉", "声誉", "回应", "澄清", "媒体", "消费者", "热搜", "服务体验"),
}

QUERY_TERMS = {
    "finance": "年报 OR 季报 OR 业绩 OR 资本充足率 OR 不良贷款率",
    "operations": "经营 OR 业务 OR 服务 OR 系统 OR 客户 OR 贷款 OR 存款",
    "legal": "处罚 OR 罚款 OR 诉讼 OR 监管 OR 问询 OR 整改",
    "brand": "投诉 OR 舆情 OR 声誉 OR 回应 OR 澄清",
}


@dataclass
class CompanyTarget:
    id: Any
    name: str
    aliases: list[str]
    official_website: str = ""
    industry: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    stock_codes: list[str] = field(default_factory=list)
    credit_code: str = ""


@dataclass
class Candidate:
    url: str
    source_code: str
    source_name: str
    authority: str
    authority_score: int = 100
    expected_categories: list[str] = field(default_factory=list)
    title_hint: str = ""
    published_at_hint: datetime | None = None
    is_discovery_page: bool = False


@dataclass
class Document:
    url: str
    source_code: str
    source_name: str
    authority: str
    authority_score: int
    title: str
    text: str
    published_at: datetime | None
    content_hash: str


def _rows(db: Session, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = db.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings()]


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _company(db: Session, company_id: Any) -> CompanyTarget:
    company_key = str(company_id).replace("-", "")
    rows = _rows(
        db,
        "SELECT * FROM companies WHERE REPLACE(CAST(id AS TEXT), '-', '') = :company_key LIMIT 1",
        {"company_key": company_key},
    )
    if not rows:
        raise ValueError("未找到目标公司。")
    row = rows[0]
    profile = _json(row.get("company_profile"), {})
    akshare = profile.get("akshare_profile") or {}
    individual = akshare.get("individual_info") or {}
    aliases = [str(item).strip() for item in profile.get("aliases", []) if str(item).strip()]
    stock_codes = [
        str(value).strip()
        for value in (
            row.get("stock_code"),
            individual.get("股票代码"),
            individual.get("A股代码"),
            individual.get("H股代码"),
            profile.get("stock_code"),
        )
        if value
    ]
    aliases.extend(
        str(value).strip()
        for value in (
            individual.get("股票简称"),
            individual.get("A股简称"),
            individual.get("H股简称"),
            profile.get("short_name"),
        )
        if value
    )
    website = str(
        row.get("official_website")
        or profile.get("official_website")
        or individual.get("网址")
        or individual.get("公司网址")
        or ""
    ).strip()
    if website and not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    name = str(row.get("name") or "").strip()
    return CompanyTarget(
        id=row.get("id"),
        name=name,
        aliases=list(dict.fromkeys([name, *aliases])),
        official_website=website,
        industry=str(row.get("industry") or profile.get("industry") or ""),
        profile=profile,
        stock_codes=list(dict.fromkeys(stock_codes)),
        credit_code=str(
            row.get("credit_code")
            or profile.get("credit_code")
            or profile.get("unified_social_credit_code")
            or ""
        ),
    )


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _trusted(url: str, company_domain: str = "") -> bool:
    host = _domain(url)
    if not host:
        return False
    allowed = TRUSTED_DOMAINS | ({company_domain} if company_domain else set())
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed)


def _contains_company(text_value: str, target: CompanyTarget) -> bool:
    compact = re.sub(r"\s+", "", text_value)
    identifiers = [*target.aliases, *target.stock_codes, target.credit_code]
    return any(identifier and re.sub(r"\s+", "", identifier) in compact for identifier in identifiers)


def _entity_match_score(text_value: str, target: CompanyTarget) -> float:
    compact = re.sub(r"\s+", "", text_value)
    scores = []
    if target.name and re.sub(r"\s+", "", target.name) in compact:
        scores.append(1.0)
    if any(alias != target.name and re.sub(r"\s+", "", alias) in compact for alias in target.aliases if alias):
        scores.append(0.85)
    if any(code and code in compact for code in target.stock_codes):
        scores.append(0.9)
    if target.credit_code and target.credit_code in compact:
        scores.append(1.0)
    return max(scores, default=0.0)


def _classify(text_value: str) -> list[str]:
    return [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in text_value for keyword in keywords)
    ]


def _source_identity(url: str, company_domain: str, fallback_name: str) -> tuple[str, str, str]:
    host = _domain(url)
    mappings = (
        ("nfra.gov.cn", "nfra_penalties", "国家金融监督管理总局", "official"),
        ("pbc.gov.cn", "pbc_official", "中国人民银行", "official"),
        ("csrc.gov.cn", "csrc_enforcement", "中国证券监督管理委员会", "official"),
        ("gsxt.gov.cn", "enterprise_credit", "国家企业信用信息公示系统", "official"),
        ("samr.gov.cn", "enterprise_credit", "国家市场监督管理总局", "official"),
        ("cninfo.com.cn", "cninfo_announcements", "巨潮资讯", "official"),
        ("sse.com.cn", "exchange_disclosure", "上海证券交易所", "official"),
        ("szse.cn", "exchange_disclosure", "深圳证券交易所", "official"),
        ("bse.cn", "bse_disclosure", "北京证券交易所", "official"),
        ("hkexnews.hk", "hkex_disclosure", "香港交易所披露易", "official"),
        ("chinamoney.com.cn", "interbank_market", "中国货币网", "official"),
        ("chinabond.com.cn", "china_bond", "中国债券信息网", "official"),
        ("china-cba.net", "banking_association", "中国银行业协会", "association"),
        ("nmpa.gov.cn", "nmpa", "国家药品监督管理局", "official"),
        ("nhsa.gov.cn", "nhsa", "国家医疗保障局", "official"),
        ("cac.gov.cn", "cac", "国家互联网信息办公室", "official"),
        ("nea.gov.cn", "nea", "国家能源局", "official"),
    )
    if company_domain and (host == company_domain or host.endswith(f".{company_domain}")):
        return "company_official_site", "公司官网", "official"
    for domain, code, name, authority in mappings:
        if host == domain or host.endswith(f".{domain}"):
            return code, name, authority
    authority = "licensed" if any(host == domain or host.endswith(f".{domain}") for domain in MEDIA_DOMAINS) else "official"
    return "authoritative_web_search", fallback_name or host or "权威网页", authority


def _select_candidates(
    candidates: list[Candidate],
    max_documents: int,
) -> list[Candidate]:
    discovery_pages = [
        candidate for candidate in candidates if candidate.is_discovery_page
    ]
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        if candidate.is_discovery_page:
            continue
        grouped.setdefault(candidate.source_code, []).append(candidate)
    selected_documents: list[Candidate] = []
    while grouped and len(selected_documents) < max_documents:
        exhausted = []
        for source_code, source_candidates in grouped.items():
            if source_candidates:
                selected_documents.append(source_candidates.pop(0))
                if len(selected_documents) >= max_documents:
                    break
            if not source_candidates:
                exhausted.append(source_code)
        for source_code in exhausted:
            grouped.pop(source_code, None)
    return [*discovery_pages, *selected_documents]


def _severity(text_value: str) -> str:
    if any(keyword in text_value for keyword in ("重大", "严重", "刑事", "吊销", "停业", "巨额")):
        return "high"
    if any(keyword in text_value for keyword in ("处罚", "罚款", "诉讼", "调查", "中断", "下滑")):
        return "important"
    return "normal"


def _sentiment(category: str, text_value: str) -> str:
    if category in {"legal", "brand"} and any(
        keyword in text_value for keyword in ("处罚", "罚款", "诉讼", "投诉", "违法", "中断", "下滑", "风险")
    ):
        return "negative"
    if any(keyword in text_value for keyword in ("增长", "提升", "获批", "增持", "改善")):
        return "positive"
    return "neutral"


def _published_at(text_value: str) -> datetime | None:
    match = re.search(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?", text_value[:5000])
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


class AuthoritativeCollector:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        self._robots: dict[str, RobotFileParser] = {}

    def close(self) -> None:
        self.client.close()

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self._robots:
            parser = RobotFileParser()
            parser.set_url(urljoin(root, "/robots.txt"))
            try:
                response = self.client.get(parser.url)
                parser.parse(response.text.splitlines() if response.status_code < 400 else [])
            except httpx.HTTPError:
                parser.parse([])
            self._robots[root] = parser
        return self._robots[root].can_fetch(USER_AGENT, url)

    def fetch(self, candidate: Candidate) -> Document:
        if not self._allowed(candidate.url):
            raise PermissionError("robots.txt 不允许抓取该地址")
        last_error: Exception | None = None
        for _ in range(3):
            try:
                response = self.client.get(candidate.url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" in content_type or candidate.url.lower().split("?")[0].endswith(".pdf"):
                    reader = PdfReader(io.BytesIO(response.content))
                    text_value = "\n".join((page.extract_text() or "") for page in reader.pages[:100])
                    title = candidate.title_hint or candidate.url.rsplit("/", 1)[-1]
                else:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for node in soup(["script", "style", "noscript", "nav", "footer"]):
                        node.decompose()
                    title = candidate.title_hint or (soup.title.get_text(" ", strip=True) if soup.title else "")
                    text_value = soup.get_text("\n", strip=True)
                normalized = re.sub(r"\s+", " ", text_value).strip()[:MAX_TEXT_CHARS]
                if not normalized:
                    raise ValueError("页面没有可提取正文")
                return Document(
                    url=str(response.url),
                    source_code=candidate.source_code,
                    source_name=candidate.source_name,
                    authority=candidate.authority,
                    authority_score=candidate.authority_score,
                    title=title.strip()[:255] or "未命名权威材料",
                    text=normalized,
                    published_at=candidate.published_at_hint or _published_at(normalized),
                    content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                )
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(str(last_error or "抓取失败"))

    def official_site_candidates(self, target: CompanyTarget, limit: int = 30) -> list[Candidate]:
        if not target.official_website:
            return []
        base = target.official_website.rstrip("/") + "/"
        company_domain = _domain(base)
        candidates = [
            Candidate(
                base,
                "company_official_site",
                "公司官网",
                "official",
                is_discovery_page=True,
            )
        ]
        try:
            if not self._allowed(base):
                return candidates
            home = self.client.get(base)
            home.raise_for_status()
            soup = BeautifulSoup(home.text, "html.parser")
            keywords = ("news", "notice", "announcement", "investor", "ir", "公告", "新闻", "投资者")
            for anchor in soup.select("a[href]"):
                url = urljoin(base, str(anchor.get("href") or ""))
                label = anchor.get_text(" ", strip=True)
                if _domain(url) != company_domain or not any(keyword in f"{url.lower()} {label}" for keyword in keywords):
                    continue
                candidates.append(Candidate(url, "company_official_site", "公司官网", "official"))
                if len(candidates) >= limit:
                    break
        except httpx.HTTPError:
            pass
        return list({candidate.url.split("#", 1)[0]: candidate for candidate in candidates}.values())[:limit]

    def listing_candidates(
        self,
        target: CompanyTarget,
        source: SourceSpec,
        limit: int = 30,
    ) -> list[Candidate]:
        if not source.url:
            return []
        seed = Candidate(
            url=source.url,
            source_code=source.code,
            source_name=source.name,
            authority=source.authority,
            authority_score=source.authority_score,
            expected_categories=list(source.categories),
            is_discovery_page=True,
        )
        candidates = [seed]
        try:
            if not self._allowed(source.url):
                return candidates
            response = self.client.get(source.url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            identifiers = [*target.aliases, *target.stock_codes, target.credit_code]
            terms = [*source.query_terms, *identifiers]
            source_domain = _domain(source.url)
            for anchor in soup.select("a[href]"):
                label = anchor.get_text(" ", strip=True)
                url = urljoin(source.url, str(anchor.get("href") or ""))
                haystack = f"{label} {url}"
                if _domain(url) != source_domain:
                    continue
                if not any(term and term.lower() in haystack.lower() for term in terms):
                    continue
                candidates.append(Candidate(
                    url=url,
                    source_code=source.code,
                    source_name=source.name,
                    authority=source.authority,
                    authority_score=source.authority_score,
                    expected_categories=list(source.categories),
                    title_hint=label[:255],
                ))
                if len(candidates) >= limit:
                    break
        except httpx.HTTPError:
            pass
        return list({candidate.url.split("#", 1)[0]: candidate for candidate in candidates}.values())[:limit]

    def serper_candidates(
        self,
        target: CompanyTarget,
        category: str,
        limit: int = 10,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Candidate]:
        api_key = os.getenv("SERPER_API_KEY", "").strip()
        if not api_key:
            raise ConnectionError("SERPER_API_KEY 未配置")
        domains = " OR ".join(f"site:{domain}" for domain in sorted(TRUSTED_DOMAINS))
        query = f'"{target.name}" ({QUERY_TERMS[category]}) ({domains})'
        payload: dict[str, Any] = {
            "q": query,
            "gl": "cn",
            "hl": "zh-cn",
            "num": min(limit, 20),
        }
        if date_from and date_to:
            payload["tbs"] = (
                "cdr:1,"
                f"cd_min:{date_from.strftime('%m/%d/%Y')},"
                f"cd_max:{date_to.strftime('%m/%d/%Y')}"
            )
        response = self.client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        result = []
        company_domain = _domain(target.official_website)
        for item in response.json().get("organic", []):
            url = str(item.get("link") or "")
            if not _trusted(url, company_domain):
                continue
            source_code, source_name, authority = _source_identity(
                url,
                company_domain,
                str(item.get("source") or ""),
            )
            result.append(Candidate(
                url=url,
                source_code=source_code,
                source_name=source_name,
                authority=authority,
                authority_score=100 if authority == "official" else 75,
                expected_categories=[category],
                title_hint=str(item.get("title") or ""),
            ))
        return result


def _ensure_retrieval_table(db: Session) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS source_retrieval_runs (
            id VARCHAR(36) PRIMARY KEY,
            company_id VARCHAR(64) NOT NULL,
            source_code VARCHAR(80) NOT NULL,
            category VARCHAR(40) NOT NULL,
            status VARCHAR(24) NOT NULL,
            checked_at TIMESTAMP NOT NULL,
            discovered_count INTEGER NOT NULL DEFAULT 0,
            ingested_count INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT ''
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS evidence_review_queue (
            id VARCHAR(36) PRIMARY KEY,
            company_id VARCHAR(64) NOT NULL,
            source_code VARCHAR(80) NOT NULL,
            source_name VARCHAR(160) NOT NULL,
            category VARCHAR(40) NOT NULL,
            query_url TEXT NOT NULL,
            reason TEXT NOT NULL,
            priority VARCHAR(16) NOT NULL DEFAULT 'normal',
            status VARCHAR(24) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            resolution_note TEXT NOT NULL DEFAULT ''
        )
    """))
    db.commit()


def _enqueue_review(
    db: Session,
    target: CompanyTarget,
    source: SourceSpec,
    category: str,
    reason: str,
    priority: str = "normal",
) -> bool:
    existing = _rows(
        db,
        """
        SELECT id FROM evidence_review_queue
        WHERE company_id = :company_id
          AND source_code = :source_code
          AND category = :category
          AND status = 'pending'
        LIMIT 1
        """,
        {
            "company_id": str(target.id),
            "source_code": source.code,
            "category": category,
        },
    )
    if existing:
        return False
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO evidence_review_queue
        (id, company_id, source_code, source_name, category, query_url, reason,
         priority, status, created_at, updated_at, resolution_note)
        VALUES
        (:id, :company_id, :source_code, :source_name, :category, :query_url, :reason,
         :priority, 'pending', :created_at, :updated_at, '')
    """), {
        "id": str(uuid.uuid4()),
        "company_id": str(target.id),
        "source_code": source.code,
        "source_name": source.name,
        "category": category,
        "query_url": source.url,
        "reason": reason,
        "priority": priority,
        "created_at": now,
        "updated_at": now,
    })
    return True


def _record_check(db: Session, target: CompanyTarget, source_code: str, category: str, status: str, discovered: int, ingested: int, error: str = "") -> None:
    db.execute(text("""
        INSERT INTO source_retrieval_runs
        (id, company_id, source_code, category, status, checked_at, discovered_count, ingested_count, error)
        VALUES (:id, :company_id, :source_code, :category, :status, :checked_at, :discovered, :ingested, :error)
    """), {
        "id": str(uuid.uuid4()), "company_id": str(target.id), "source_code": source_code,
        "category": category, "status": status, "checked_at": datetime.now(timezone.utc),
        "discovered": discovered, "ingested": ingested, "error": error[:500],
    })


def _upsert_event(db: Session, target: CompanyTarget, document: Document, category: str) -> bool:
    existing = _rows(db, """
        SELECT id, extra_payload FROM risk_events
        WHERE company_id = :company_id AND category = :category AND source_url = :source_url
        LIMIT 1
    """, {"company_id": target.id, "category": category, "source_url": document.url})
    excerpt = document.text[:4000]
    entity_match_score = _entity_match_score(f"{document.title} {document.text}", target)
    evidence_grade = (
        "A"
        if document.authority == "official" and document.authority_score >= 95
        else "B"
        if document.authority_score >= 85
        else "C"
        if document.authority_score >= 70
        else "D"
    )
    extra = {
        "source_code": document.source_code,
        "source_authority": document.authority,
        "source_authority_label": {
            "official": "官方一手来源",
            "association": "行业自律组织",
            "licensed": "权威媒体/持牌来源",
        }.get(document.authority, "其他可追溯来源"),
        "source_authority_score": document.authority_score,
        "evidence_grade": evidence_grade,
        "entity_match_score": entity_match_score,
        "requires_original_verification": document.authority != "official",
        "content_hash": document.content_hash,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "published_at": document.published_at.isoformat() if document.published_at else None,
        "retrieval_status": "success",
        "evidence_excerpt": excerpt[:800],
    }
    payload = extra
    now = datetime.now(timezone.utc)
    values = {
        "company_id": target.id, "category": category, "severity": _severity(document.text),
        "title": document.title, "content": excerpt, "source_url": document.url,
        "source_name": document.source_name, "occurred_at": document.published_at,
        "sentiment": _sentiment(category, document.text), "extra_payload": payload,
        "updated_at": now,
    }
    if existing:
        if _json(existing[0].get("extra_payload"), {}).get("content_hash") == document.content_hash:
            return False
        statement = text("""
            UPDATE risk_events SET title=:title, content=:content, source_name=:source_name,
                occurred_at=:occurred_at, severity=:severity, sentiment=:sentiment,
                extra_payload=:extra_payload, updated_at=:updated_at WHERE id=:id
        """).bindparams(bindparam("extra_payload", type_=JSON))
        db.execute(statement, {**values, "id": existing[0]["id"]})
        return True
    statement = text("""
        INSERT INTO risk_events
        (id, company_id, category, severity, title, content, source_url, source_name,
         occurred_at, sentiment, extra_payload, created_at, updated_at)
        VALUES (:id, :company_id, :category, :severity, :title, :content, :source_url,
         :source_name, :occurred_at, :sentiment, :extra_payload, :created_at, :updated_at)
    """).bindparams(bindparam("extra_payload", type_=JSON))
    db.execute(statement, {**values, "id": str(uuid.uuid4()), "created_at": now})
    return True


def collect_authoritative_sources(
    db: Session,
    *,
    company_id: Any,
    max_documents: int = 60,
    mode: str = "daily",
    backfill_years: int = 5,
    lookback_days: int = 2,
    source_codes: list[str] | None = None,
) -> dict[str, Any]:
    if mode not in {"daily", "backfill"}:
        raise ValueError("mode 仅支持 daily 或 backfill。")
    _ensure_retrieval_table(db)
    target = _company(db, company_id)
    plugin, planned_sources = source_plan_for(target.industry, target.name, target.profile)
    if source_codes:
        allowed_codes = set(source_codes)
        planned_sources = tuple(source for source in planned_sources if source.code in allowed_codes)
    cutoff = datetime.now(timezone.utc) - (
        timedelta(days=365 * backfill_years)
        if mode == "backfill"
        else timedelta(days=lookback_days)
    )
    collector = AuthoritativeCollector()
    candidates: list[Candidate] = []
    source_errors: dict[str, str] = {}
    manual_review_count = 0
    source_by_code = {source.code: source for source in planned_sources}
    try:
        for source in planned_sources:
            if source.access_mode == "manual_authorized":
                for category in source.categories:
                    if _enqueue_review(
                        db,
                        target,
                        source,
                        category,
                        source.notes or "该来源需要授权接口或人工核验原文。",
                        priority="high" if plugin.code == "banking" else "normal",
                    ):
                        manual_review_count += 1
                    _record_check(
                        db,
                        target,
                        source.code,
                        category,
                        "not_connected",
                        0,
                        0,
                        "已进入授权接口/人工原文核验队列",
                    )
                continue
            if source.access_mode == "company_site":
                if target.official_website:
                    candidates.extend(
                        collector.official_site_candidates(
                            target,
                            limit=min(max_documents, 30),
                        )
                    )
                else:
                    for category in source.categories:
                        _record_check(
                            db,
                            target,
                            source.code,
                            category,
                            "not_connected",
                            0,
                            0,
                            "企业档案尚未配置官网地址",
                        )
                continue
            if source.access_mode == "search_api":
                for category in source.categories:
                    search_windows: list[tuple[datetime | None, datetime | None]]
                    if mode == "backfill":
                        search_windows = []
                        window_start = cutoff
                        now = datetime.now(timezone.utc)
                        while window_start < now:
                            window_end = min(
                                datetime(
                                    window_start.year + 1,
                                    1,
                                    1,
                                    tzinfo=timezone.utc,
                                ),
                                now,
                            )
                            search_windows.append((window_start, window_end))
                            window_start = window_end
                    else:
                        search_windows = [(None, None)]
                    try:
                        for date_from, date_to in search_windows:
                            candidates.extend(
                                collector.serper_candidates(
                                    target,
                                    category,
                                    limit=12,
                                    date_from=date_from,
                                    date_to=date_to,
                                )
                            )
                    except (ConnectionError, httpx.HTTPError) as exc:
                        source_errors[f"{source.code}:{category}"] = str(exc)
                continue
            candidates.extend(
                collector.listing_candidates(
                    target,
                    source,
                    limit=min(max_documents, 30),
                )
            )

        company_domain = _domain(target.official_website)
        trusted_domains = domains_for(planned_sources)
        unique = {
            (candidate.source_code, candidate.url.split("#", 1)[0]): candidate
            for candidate in candidates
            if _trusted(candidate.url, company_domain)
            or _domain(candidate.url) in trusted_domains
        }
        selected = _select_candidates(list(unique.values()), max_documents)
        source_stats: dict[tuple[str, str], dict[str, int]] = {}
        attempts: dict[tuple[str, str], int] = {}
        failed_attempts: dict[tuple[str, str], int] = {}
        errors: list[dict[str, str]] = []
        document_count = 0
        ingested = 0
        for candidate in selected:
            tracked_categories = candidate.expected_categories or list(CATEGORY_KEYWORDS)
            for tracked_category in tracked_categories:
                key = (candidate.source_code, tracked_category)
                attempts[key] = attempts.get(key, 0) + 1
            try:
                document = collector.fetch(candidate)
                if candidate.is_discovery_page:
                    continue
                combined_text = f"{document.title} {document.text}"
                entity_match_score = _entity_match_score(combined_text, target)
                if entity_match_score == 0 and _domain(document.url) != company_domain:
                    continue
                if document.published_at and document.published_at < cutoff:
                    continue
                categories = _classify(combined_text)
                if not categories:
                    continue
                document_count += 1
                for category in categories:
                    key = (candidate.source_code, category)
                    source_stats.setdefault(key, {"discovered": 0, "ingested": 0})["discovered"] += 1
                    if _upsert_event(db, target, document, category):
                        source_stats[key]["ingested"] += 1
                        ingested += 1
                    source = source_by_code.get(candidate.source_code)
                    if source and (
                        document.authority != "official"
                        or entity_match_score < 0.9
                        or source.requires_original_verification
                        and document.authority != "official"
                    ):
                        if _enqueue_review(
                            db,
                            target,
                            source,
                            category,
                            "需要核验官方原文或确认企业主体匹配。",
                            priority="high" if category == "legal" else "normal",
                        ):
                            manual_review_count += 1
            except (RuntimeError, PermissionError) as exc:
                errors.append({"source_code": candidate.source_code, "url": candidate.url, "error": str(exc)[:300]})
                for tracked_category in tracked_categories:
                    key = (candidate.source_code, tracked_category)
                    failed_attempts[key] = failed_attempts.get(key, 0) + 1

        for (source_code, category), stats in source_stats.items():
            _record_check(db, target, source_code, category, "success", stats["discovered"], stats["ingested"])
        for (source_code, category), attempt_count in attempts.items():
            if (source_code, category) in source_stats:
                continue
            failure_count = failed_attempts.get((source_code, category), 0)
            status = "failed" if failure_count == attempt_count else "no_hit"
            message = "该来源本轮请求全部失败" if status == "failed" else "检索已执行，但未找到与企业及该维度同时匹配的材料"
            _record_check(db, target, source_code, category, status, 0, 0, message if status == "failed" else "")
        for source in planned_sources:
            if source.access_mode == "manual_authorized":
                continue
            for category in source.categories:
                search_error = source_errors.get(f"{source.code}:{category}")
                if search_error:
                    _record_check(
                        db,
                        target,
                        source.code,
                        category,
                        "not_connected",
                        0,
                        0,
                        search_error,
                    )
                elif (
                    source.access_mode == "search_api"
                    and (source.code, category) not in source_stats
                ):
                    _record_check(
                        db,
                        target,
                        source.code,
                        category,
                        "no_hit",
                        0,
                        0,
                    )
        db.commit()
        return {
            "company_id": str(target.id), "company_name": target.name,
            "industry_plugin": plugin.code,
            "industry_plugin_name": plugin.name,
            "mode": mode,
            "cutoff": cutoff.isoformat(),
            "candidate_count": len(selected), "document_count": document_count,
            "ingested_event_count": ingested,
            "manual_review_count": manual_review_count,
            "planned_sources": [source_to_dict(source) for source in planned_sources],
            "source_checks": [
                {"source_code": code, "category": category, **stats}
                for (code, category), stats in sorted(source_stats.items())
            ],
            "errors": errors, "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except (SQLAlchemyError, httpx.HTTPError):
        db.rollback()
        raise
    finally:
        collector.close()
