from __future__ import annotations

import json
import hashlib
import html as html_lib
import math
import os
import re
import sqlite3
import sys
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("D_RISK_DATABASE", ROOT / "backend" / "demo.db"))
REPORT_TYPES = {
    "macro": "macro_environment_report",
    "operations": "business_operations_report",
    "finance": "financial_health_report",
    "legal": "legal_risk_report",
    "brand": "brand_sentiment_report",
}

app = FastAPI(title="D.Risk AI local platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


EXTENDED_SCHEMA = """
CREATE TABLE IF NOT EXISTS company_industry_links (
    company_id CHAR(32) NOT NULL,
    taxonomy VARCHAR(40) NOT NULL,
    industry_code VARCHAR(80) NOT NULL DEFAULT '',
    industry_name VARCHAR(128) NOT NULL,
    source_name VARCHAR(128) NOT NULL,
    source_url VARCHAR(512) NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (company_id, taxonomy),
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_company_industry_name ON company_industry_links(industry_name);

CREATE TABLE IF NOT EXISTS macro_indicator_points (
    id CHAR(32) PRIMARY KEY,
    indicator_code VARCHAR(80) NOT NULL,
    indicator_name VARCHAR(128) NOT NULL,
    period VARCHAR(40) NOT NULL,
    value REAL NOT NULL,
    unit VARCHAR(24) NOT NULL,
    frequency VARCHAR(24) NOT NULL,
    region_scope VARCHAR(40) NOT NULL DEFAULT '全国',
    source_name VARCHAR(128) NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    raw_payload JSON NOT NULL,
    collected_at DATETIME NOT NULL,
    UNIQUE(indicator_code, period, region_scope)
);
CREATE INDEX IF NOT EXISTS ix_macro_indicator_period ON macro_indicator_points(indicator_code, period);

CREATE TABLE IF NOT EXISTS macro_industry_events (
    id CHAR(32) PRIMARY KEY,
    scope_type VARCHAR(24) NOT NULL,
    scope_key VARCHAR(128) NOT NULL DEFAULT '',
    dimension VARCHAR(48) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    indicator_code VARCHAR(80) NOT NULL DEFAULT '',
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    source_name VARCHAR(128) NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    published_at DATETIME NOT NULL,
    impact_direction VARCHAR(16) NOT NULL DEFAULT 'neutral',
    severity VARCHAR(16) NOT NULL DEFAULT 'normal',
    relevance_score REAL NOT NULL DEFAULT 1,
    dedupe_hash CHAR(64) NOT NULL UNIQUE,
    raw_payload JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_macro_event_scope ON macro_industry_events(scope_type, scope_key, published_at);
CREATE INDEX IF NOT EXISTS ix_macro_event_dimension ON macro_industry_events(dimension, published_at);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id CHAR(32) PRIMARY KEY,
    company_id CHAR(32),
    run_type VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 1,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    failed_sources JSON NOT NULL,
    source_results JSON NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    finished_at DATETIME,
    requested_company_count INTEGER NOT NULL DEFAULT 0,
    scanned_company_count INTEGER NOT NULL DEFAULT 0,
    total_raw_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    source_breakdown JSON NOT NULL DEFAULT '{}',
    failures JSON NOT NULL DEFAULT '[]',
    summary JSON NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE SET NULL
);
"""


def ensure_extended_schema() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(EXTENDED_SCHEMA)
        existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(ingestion_runs)").fetchall()}
        migrations = {
            "company_id": "CHAR(32)", "run_type": "VARCHAR(40) NOT NULL DEFAULT 'legacy'",
            "progress_current": "INTEGER NOT NULL DEFAULT 0", "progress_total": "INTEGER NOT NULL DEFAULT 1",
            "updated_count": "INTEGER NOT NULL DEFAULT 0", "failed_sources": "JSON NOT NULL DEFAULT '[]'",
            "source_results": "JSON NOT NULL DEFAULT '[]'", "message": "TEXT NOT NULL DEFAULT ''", "completed_at": "DATETIME",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE ingestion_runs ADD COLUMN {column} {definition}")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_ingestion_company_updated ON ingestion_runs(company_id, updated_at)")
        connection.commit()


ensure_extended_schema()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def db_id(value: str) -> str:
    return value.replace("-", "").lower()


def api_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        return value


def parse_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def company_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "credit_code": row["credit_code"],
        "industry": row["industry"],
        "region": row["region"],
        "description": row["description"] or "",
        "official_website": row["official_website"] or "",
        "company_profile": parse_json(row["company_profile"], {}),
        "id": api_id(row["id"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def report_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": api_id(row["id"]),
        "company_id": api_id(row["company_id"]),
        "report_type": row["report_type"],
        "title": row["title"],
        "summary": row["summary"] or "",
        "snapshot": parse_json(row["snapshot"], {}),
        "model_name": row["model_name"] or "structured-agent-v1",
        "generated_at": row["generated_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_company_or_404(connection: sqlite3.Connection, company_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM companies WHERE id = ?", (db_id(company_id),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="未找到企业")
    return row


def dataframe_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return json_safe(json.loads(frame.to_json(orient="records", date_format="iso", force_ascii=False)))


def resolve_akshare(name: str, provided_code: str = "") -> dict[str, Any]:
    try:
        import akshare as ak

        listing = ak.stock_info_a_code_name()
        listing.columns = [str(column) for column in listing.columns]
        code_column = next((column for column in listing.columns if "code" in column.lower() or "代码" in column), listing.columns[0])
        name_column = next((column for column in listing.columns if "name" in column.lower() or "名称" in column), listing.columns[1])
        code = provided_code.strip()
        match = None
        if code:
            candidates = listing[listing[code_column].astype(str).str.zfill(6) == code.zfill(6)]
            if not candidates.empty:
                match = candidates.iloc[0]
        if match is None:
            normalized = name.strip()
            exact = listing[listing[name_column].astype(str) == normalized]
            if not exact.empty:
                match = exact.iloc[0]
            else:
                candidates = listing[listing[name_column].astype(str).map(lambda item: item in normalized or normalized in item)]
                if not candidates.empty:
                    match = candidates.iloc[0]
        if match is None:
            return {"status": "unavailable", "reason": "stock_not_found", "message": "AkShare 未匹配到上市公司"}
        code = str(match[code_column]).zfill(6)
        stock_name = str(match[name_column])
        abstract_errors: list[str] = []
        try:
            abstract = dataframe_records(ak.stock_financial_abstract(symbol=code))
        except Exception as exc:
            abstract = []
            abstract_errors.append(f"financial_abstract: {exc}")
        try:
            indicators = dataframe_records(ak.stock_financial_analysis_indicator(symbol=code))
        except Exception as exc:
            indicators = []
            abstract_errors.append(f"financial_indicators: {exc}")
        return {
            "status": "available",
            "source": "akshare",
            "search_key": name,
            "stock_code": code,
            "stock_name": stock_name,
            "matched_name": name if not name.isdigit() else stock_name,
            "resolution_source": "provided_stock_code" if provided_code else "name_match",
            "resolution_errors": abstract_errors,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "individual_info": {},
            "financial_abstract": abstract,
            "financial_indicators": indicators,
        }
    except Exception as exc:
        return {"status": "unavailable", "reason": "akshare_error", "message": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()}


MACRO_INDICATORS = [
    {"code": "gdp_yoy", "name": "GDP 同比增长", "function": "macro_china_gdp", "period": "季度", "value": "国内生产总值-同比增长", "unit": "%", "frequency": "季度", "source_name": "国家统计局（AkShare 聚合）", "source_url": "https://data.stats.gov.cn/"},
    {"code": "cpi_yoy", "name": "CPI 同比增长", "function": "macro_china_cpi", "period": "月份", "value": "全国-同比增长", "unit": "%", "frequency": "月度", "source_name": "国家统计局（AkShare 聚合）", "source_url": "https://data.stats.gov.cn/"},
    {"code": "ppi_yoy", "name": "PPI 同比增长", "function": "macro_china_ppi", "period": "月份", "value": "当月同比增长", "unit": "%", "frequency": "月度", "source_name": "国家统计局（AkShare 聚合）", "source_url": "https://data.stats.gov.cn/"},
    {"code": "manufacturing_pmi", "name": "制造业 PMI", "function": "macro_china_pmi", "period": "月份", "value": "制造业-指数", "unit": "点", "frequency": "月度", "source_name": "国家统计局（AkShare 聚合）", "source_url": "https://data.stats.gov.cn/"},
    {"code": "non_manufacturing_pmi", "name": "非制造业 PMI", "function": "macro_china_pmi", "period": "月份", "value": "非制造业-指数", "unit": "点", "frequency": "月度", "source_name": "国家统计局（AkShare 聚合）", "source_url": "https://data.stats.gov.cn/"},
    {"code": "lpr_1y", "name": "1 年期 LPR", "function": "macro_china_lpr", "period": "TRADE_DATE", "value": "LPR1Y", "unit": "%", "frequency": "月度", "source_name": "中国人民银行（AkShare 聚合）", "source_url": "https://www.pbc.gov.cn/"},
    {"code": "m2_yoy", "name": "M2 同比增长", "function": "macro_china_money_supply", "period": "月份", "value": "货币和准货币(M2)-同比增长", "unit": "%", "frequency": "月度", "source_name": "中国人民银行（AkShare 聚合）", "source_url": "https://www.pbc.gov.cn/"},
]

INDUSTRY_FALLBACKS = {
    "002594": ("汽车制造业", "广东"),
    "300750": ("电气机械和器材制造业", "福建"),
    "601398": ("货币金融服务", "北京"),
    "600612": ("零售业", "上海"),
}


def normalize_period(value: Any) -> str:
    text = str(value or "").strip()
    quarter = re.search(r"(20\d{2})年第(?:1-)?([1-4])季度", text)
    if quarter:
        return f"{quarter.group(1)}-Q{quarter.group(2)}"
    month = re.search(r"(20\d{2})年(\d{1,2})月份?", text)
    if month:
        return f"{month.group(1)}-{int(month.group(2)):02d}"
    date_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if date_match:
        return f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    return text[:40]


def numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(str(value).replace(",", "").replace("%", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def exchange_from_code(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "上海证券交易所"
    if code.startswith(("0", "3")):
        return "深圳证券交易所"
    if code.startswith(("4", "8")):
        return "北京证券交易所"
    return ""


def province_from_address(address: str) -> str:
    for region in ("北京", "上海", "天津", "重庆", "广东", "浙江", "江苏", "山东", "福建", "四川", "湖北", "湖南", "河南", "河北", "安徽", "江西", "陕西", "山西", "辽宁", "吉林", "黑龙江", "云南", "贵州", "海南", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆"):
        if region in address:
            return region
    return ""


def resolve_company_industry(connection: sqlite3.Connection, company: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    profile = company.get("company_profile", {})
    akshare_profile = profile.get("akshare_profile", {})
    code = str(akshare_profile.get("stock_code") or "")
    industry = str(company.get("industry") or "")
    region = str(company.get("region") or "")
    source_name = "企业现有档案"
    source_url = ""
    confidence = 0.8 if industry else 0.0
    cninfo_profile: dict[str, Any] = {}
    if not code:
        try:
            import akshare as ak

            listing = ak.stock_info_a_code_name()
            listing.columns = [str(column) for column in listing.columns]
            code_column = next((column for column in listing.columns if "code" in column.lower() or "代码" in column), listing.columns[0])
            name_column = next((column for column in listing.columns if "name" in column.lower() or "名称" in column), listing.columns[1])
            company_name = str(company.get("name") or "")
            candidates = listing[listing[name_column].astype(str).map(lambda item: str(item) in company_name or company_name in str(item))]
            if not candidates.empty:
                match = candidates.iloc[0]
                code = str(match[code_column]).zfill(6)
                akshare_profile.update({"status": "available", "source": "akshare", "stock_code": code, "stock_name": str(match[name_column]), "matched_name": company_name, "resolution_source": "industry_refresh_name_match", "updated_at": now_iso()})
                profile["akshare_profile"] = akshare_profile
        except Exception as exc:
            akshare_profile.setdefault("resolution_errors", []).append(f"industry_identity: {exc}")
    if code:
        try:
            import akshare as ak

            records = dataframe_records(ak.stock_profile_cninfo(symbol=code))
            if records:
                record = records[0]
                industry = str(record.get("所属行业") or industry)
                address = str(record.get("注册地址") or record.get("办公地址") or "")
                region = province_from_address(address) or region
                cninfo_profile = {
                    "company_name": record.get("公司名称"),
                    "stock_code": record.get("A股代码"),
                    "market": record.get("所属市场"),
                    "industry": record.get("所属行业"),
                    "registered_address": record.get("注册地址"),
                    "main_business": record.get("主营业务"),
                    "official_website": record.get("官方网站"),
                    "source": "巨潮资讯",
                    "source_url": "https://www.cninfo.com.cn/",
                    "updated_at": now_iso(),
                }
                source_name = "巨潮资讯"
                source_url = "https://www.cninfo.com.cn/"
                confidence = 1.0
        except Exception as exc:
            cninfo_profile = {"status": "unavailable", "message": str(exc), "updated_at": now_iso()}
    if not industry and code in INDUSTRY_FALLBACKS:
        industry, fallback_region = INDUSTRY_FALLBACKS[code]
        region = region or fallback_region
        source_name = "A股样例回退映射"
        confidence = 0.75
    if code:
        akshare_profile["exchange"] = exchange_from_code(code)
    if cninfo_profile:
        profile["cninfo_profile"] = cninfo_profile
    if industry:
        timestamp = now_iso()
        connection.execute(
            "INSERT INTO company_industry_links (company_id, taxonomy, industry_code, industry_name, source_name, source_url, confidence, created_at, updated_at) VALUES (?, 'CNINFO', '', ?, ?, ?, ?, ?, ?) ON CONFLICT(company_id, taxonomy) DO UPDATE SET industry_name=excluded.industry_name, source_name=excluded.source_name, source_url=excluded.source_url, confidence=excluded.confidence, updated_at=excluded.updated_at",
            (db_id(company["id"]), industry, source_name, source_url, confidence, timestamp, timestamp),
        )
    connection.execute(
        "UPDATE companies SET industry=?, region=?, company_profile=?, updated_at=? WHERE id=?",
        (industry or None, region or None, json.dumps(json_safe(profile), ensure_ascii=False), now_iso(), db_id(company["id"])),
    )
    connection.commit()
    return industry, region, cninfo_profile


def run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": api_id(row["id"]), "company_id": api_id(row["company_id"]) if row["company_id"] else None,
        "run_type": row["run_type"], "status": row["status"], "progress_current": row["progress_current"],
        "progress_total": row["progress_total"], "inserted_count": row["inserted_count"], "updated_count": row["updated_count"],
        "failed_sources": parse_json(row["failed_sources"], []), "source_results": parse_json(row["source_results"], []),
        "message": row["message"], "started_at": row["started_at"], "completed_at": row["completed_at"], "updated_at": row["updated_at"],
    }


def create_ingestion_run(connection: sqlite3.Connection, company_id: Optional[str], run_type: str = "company_refresh") -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    timestamp = now_iso()
    connection.execute(
        "INSERT INTO ingestion_runs (id, company_id, run_type, status, progress_current, progress_total, inserted_count, updated_count, failed_sources, source_results, message, started_at, completed_at, source_breakdown, failures, summary, updated_at) VALUES (?, ?, ?, 'queued', 0, ?, 0, 0, '[]', '[]', '等待采集', ?, NULL, '{}', '[]', '{}', ?)",
        (run_id, db_id(company_id) if company_id else None, run_type, len(MACRO_INDICATORS) + 3, timestamp, timestamp),
    )
    connection.commit()
    return run_from_row(connection.execute("SELECT * FROM ingestion_runs WHERE id=?", (run_id,)).fetchone())


def indicator_direction(code: str, value: float, previous: Optional[float]) -> tuple[str, str]:
    delta = value - previous if previous is not None else 0
    if code in {"manufacturing_pmi", "non_manufacturing_pmi"}:
        return ("positive", "normal") if value >= 50 else ("negative", "important")
    if code == "gdp_yoy":
        return ("positive", "normal") if value >= 5 else (("negative", "important") if value < 4 else ("neutral", "normal"))
    if code in {"cpi_yoy", "ppi_yoy"}:
        return ("negative", "important") if value < 0 else (("negative", "important") if abs(value) >= 5 else ("neutral", "normal"))
    if code == "m2_yoy":
        return ("positive", "normal") if delta >= 0 else ("neutral", "normal")
    if code == "lpr_1y":
        return ("positive", "normal") if delta < 0 else ("neutral", "normal")
    return "neutral", "normal"


def event_hash(title: str, source_name: str, published_at: str, scope_key: str = "") -> str:
    normalized = re.sub(r"\s+", "", title).lower()
    return hashlib.sha256(f"{normalized}|{source_name}|{published_at[:10]}|{scope_key}".encode("utf-8")).hexdigest()


def upsert_macro_event(connection: sqlite3.Connection, event: dict[str, Any]) -> bool:
    timestamp = now_iso()
    dedupe = event_hash(event["title"], event["source_name"], event["published_at"], event.get("scope_key", ""))
    existed = connection.execute("SELECT 1 FROM macro_industry_events WHERE dedupe_hash=?", (dedupe,)).fetchone() is not None
    connection.execute(
        "INSERT INTO macro_industry_events (id, scope_type, scope_key, dimension, event_type, indicator_code, title, summary, source_name, source_url, published_at, impact_direction, severity, relevance_score, dedupe_hash, raw_payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(dedupe_hash) DO UPDATE SET summary=excluded.summary, impact_direction=excluded.impact_direction, severity=excluded.severity, relevance_score=excluded.relevance_score, raw_payload=excluded.raw_payload, updated_at=excluded.updated_at",
        (uuid.uuid4().hex, event["scope_type"], event.get("scope_key", ""), event["dimension"], event["event_type"], event.get("indicator_code", ""), event["title"], event["summary"], event["source_name"], event["source_url"], event["published_at"], event.get("impact_direction", "neutral"), event.get("severity", "normal"), event.get("relevance_score", 1), dedupe, json.dumps(json_safe(event.get("raw_payload", {})), ensure_ascii=False), timestamp, timestamp),
    )
    return not existed


def collect_macro_indicators(connection: sqlite3.Connection, run_id: str) -> tuple[int, int, list[dict[str, Any]], list[str]]:
    import akshare as ak

    inserted = 0
    updated = 0
    results: list[dict[str, Any]] = []
    failed: list[str] = []
    frame_cache: dict[str, list[dict[str, Any]]] = {}
    for index, config in enumerate(MACRO_INDICATORS, start=1):
        try:
            if config["function"] not in frame_cache:
                frame_cache[config["function"]] = dataframe_records(getattr(ak, config["function"])())
            parsed: list[tuple[str, float, dict[str, Any]]] = []
            for record in frame_cache[config["function"]]:
                period = normalize_period(record.get(config["period"]))
                value = numeric_value(record.get(config["value"]))
                if period and value is not None:
                    parsed.append((period, value, record))
            parsed.sort(key=lambda item: item[0])
            max_points = 24 if config["frequency"] == "季度" else 60
            source_inserted = 0
            for period, value, record in parsed[-max_points:]:
                exists = connection.execute("SELECT 1 FROM macro_indicator_points WHERE indicator_code=? AND period=? AND region_scope='全国'", (config["code"], period)).fetchone()
                connection.execute(
                    "INSERT INTO macro_indicator_points (id, indicator_code, indicator_name, period, value, unit, frequency, region_scope, source_name, source_url, raw_payload, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, '全国', ?, ?, ?, ?) ON CONFLICT(indicator_code, period, region_scope) DO UPDATE SET value=excluded.value, source_name=excluded.source_name, source_url=excluded.source_url, raw_payload=excluded.raw_payload, collected_at=excluded.collected_at",
                    (uuid.uuid4().hex, config["code"], config["name"], period, value, config["unit"], config["frequency"], config["source_name"], config["source_url"], json.dumps(json_safe(record), ensure_ascii=False), now_iso()),
                )
                if exists:
                    updated += 1
                else:
                    inserted += 1
                    source_inserted += 1
            results.append({"source": config["code"], "status": "success", "points": len(parsed[-max_points:]), "inserted": source_inserted})
        except Exception as exc:
            failed.append(config["code"])
            results.append({"source": config["code"], "status": "failed", "message": str(exc)[:240]})
        connection.execute("UPDATE ingestion_runs SET status='running', progress_current=?, source_results=?, failed_sources=?, message=?, updated_at=? WHERE id=?", (index + 1, json.dumps(results, ensure_ascii=False), json.dumps(failed, ensure_ascii=False), f"已处理 {index}/{len(MACRO_INDICATORS)} 个宏观指标", now_iso(), run_id))
        connection.commit()
    return inserted, updated, results, failed


def cached_macro_sources(connection: sqlite3.Connection, max_age_hours: int = 24) -> Optional[list[dict[str, Any]]]:
    row = connection.execute("SELECT MAX(collected_at) AS latest FROM macro_indicator_points").fetchone()
    if row is None or not row["latest"]:
        return None
    try:
        latest = datetime.fromisoformat(str(row["latest"]).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
    if latest < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=max_age_hours):
        return None
    results = []
    for config in MACRO_INDICATORS:
        count = connection.execute("SELECT COUNT(*) FROM macro_indicator_points WHERE indicator_code=?", (config["code"],)).fetchone()[0]
        if count:
            results.append({"source": config["code"], "status": "success", "points": count, "cached": True})
    return results if len(results) == len(MACRO_INDICATORS) else None


def policy_matches_industry(title: str, industry: str) -> bool:
    groups = [
        (("汽车", "电气", "电池", "设备", "制造", "材料", "化工", "钢铁"), ("汽车", "充电", "电池", "储能", "新能源", "设备更新", "工业", "制造", "节能", "电力", "材料")),
        (("金融", "银行", "保险", "证券"), ("金融", "贷款", "利率", "信用", "基金", "融资", "REITs", "资本市场")),
        (("零售", "食品", "消费", "文教", "工美", "体育", "娱乐"), ("消费", "零售", "以旧换新", "价格", "文旅", "体育", "养老", "服务业")),
        (("软件", "信息", "通信", "互联网", "计算机"), ("数据", "人工智能", "数字", "软件", "通信", "算力", "信息")),
    ]
    return any(any(keyword in industry for keyword in industries) and any(keyword in title for keyword in policy_words) for industries, policy_words in groups)


def parse_ndrc_policy_listing(page: str, list_url: str) -> list[dict[str, str]]:
    pattern = re.compile(r'<li>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*<span>(20\d{2}/\d{2}/\d{2})</span>\s*</li>', re.S)
    return [{
        "title": html_lib.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip(),
        "published_at": date_text.replace("/", "-"),
        "source_url": urllib.parse.urljoin(list_url, href),
    } for href, raw_title, date_text in pattern.findall(page)]


def collect_ndrc_policy_events(connection: sqlite3.Connection, industry: str) -> tuple[int, int, dict[str, Any]]:
    import requests

    list_url = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/wap_index.html"
    response = requests.get(list_url, headers={"User-Agent": "Mozilla/5.0 D.Risk-AI/1.0"}, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    page = response.text
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)
    macro_keywords = ("民营经济", "全国统一大市场", "投资", "价格", "信用", "数据要素", "外商投资", "物流成本", "招标投标")
    inserted = 0
    updated = 0
    matched = 0
    for item in parse_ndrc_policy_listing(page, list_url):
        try:
            published = datetime.fromisoformat(item["published_at"])
        except ValueError:
            continue
        if published < cutoff:
            continue
        title = item["title"]
        industry_match = bool(industry and policy_matches_industry(title, industry))
        macro_match = any(keyword in title for keyword in macro_keywords)
        if not industry_match and not macro_match:
            continue
        scope_type = "industry" if industry_match else "macro"
        scope_key = industry if industry_match else "全国"
        source_url = item["source_url"]
        created = upsert_macro_event(connection, {
            "scope_type": scope_type, "scope_key": scope_key, "dimension": "policy_regulatory", "event_type": "official_policy_release",
            "title": title, "summary": f"国家发展改革委于 {published.date().isoformat()} 公开发布该政策文件。当前仅记录标题、日期和原文链接，具体影响需结合原文条款与企业业务核验。",
            "source_name": "国家发展和改革委员会", "source_url": source_url, "published_at": published.date().isoformat(),
            "impact_direction": "neutral", "severity": "important", "relevance_score": 0.95 if industry_match else 0.75,
            "raw_payload": {"list_url": list_url, "industry_match": industry_match},
        })
        inserted += int(created)
        updated += int(not created)
        matched += 1
    connection.commit()
    return inserted, updated, {"source": "ndrc_policy", "status": "success", "events": matched, "source_url": list_url}


def relevant_indicator_codes(industry: str) -> set[str]:
    if any(keyword in industry for keyword in ("银行", "金融", "保险", "证券")):
        return {"gdp_yoy", "lpr_1y", "m2_yoy"}
    if any(keyword in industry for keyword in ("零售", "食品", "饮料", "消费", "住宿", "餐饮")):
        return {"gdp_yoy", "cpi_yoy", "lpr_1y"}
    if any(keyword in industry for keyword in ("制造", "汽车", "设备", "电气", "材料", "化工", "钢铁", "电子")):
        return {"gdp_yoy", "manufacturing_pmi", "ppi_yoy", "lpr_1y"}
    return {"gdp_yoy", "cpi_yoy", "lpr_1y"}


def generate_indicator_events(connection: sqlite3.Connection, industry: str) -> tuple[int, int]:
    inserted = 0
    updated = 0
    latest_points: dict[str, list[sqlite3.Row]] = {}
    for config in MACRO_INDICATORS:
        rows = connection.execute("SELECT * FROM macro_indicator_points WHERE indicator_code=? ORDER BY period DESC LIMIT 2", (config["code"],)).fetchall()
        if not rows:
            continue
        latest_points[config["code"]] = rows
        latest = rows[0]
        previous = float(rows[1]["value"]) if len(rows) > 1 else None
        direction, severity = indicator_direction(config["code"], float(latest["value"]), previous)
        title = f"{latest['period']} {latest['indicator_name']}为{latest['value']:g}{latest['unit']}"
        delta_text = f"，较上期变化{float(latest['value']) - previous:+.2f}{latest['unit']}" if previous is not None else ""
        created = upsert_macro_event(connection, {
            "scope_type": "macro", "scope_key": "全国", "dimension": "macroeconomy", "event_type": "macro_indicator_release", "indicator_code": config["code"],
            "title": title, "summary": f"公开宏观指标显示：{title}{delta_text}。该记录仅描述已发布数据，不延伸生成无证据判断。",
            "source_name": latest["source_name"], "source_url": latest["source_url"], "published_at": latest["period"], "impact_direction": direction,
            "severity": severity, "relevance_score": 1, "raw_payload": {"period": latest["period"], "value": latest["value"], "unit": latest["unit"], "previous": previous},
        })
        inserted += int(created)
        updated += int(not created)
    if industry:
        for code in relevant_indicator_codes(industry):
            rows = latest_points.get(code)
            if not rows:
                continue
            latest = rows[0]
            previous = float(rows[1]["value"]) if len(rows) > 1 else None
            direction, severity = indicator_direction(code, float(latest["value"]), previous)
            if code == "lpr_1y" and any(keyword in industry for keyword in ("银行", "金融")) and previous is not None and float(latest["value"]) < previous:
                direction = "negative"
            title = f"{industry}关联信号：{latest['indicator_name']} {latest['value']:g}{latest['unit']}"
            created = upsert_macro_event(connection, {
                "scope_type": "industry", "scope_key": industry, "dimension": "industry_cycle", "event_type": "industry_indicator_signal", "indicator_code": code,
                "title": title, "summary": f"{industry}与{latest['indicator_name']}存在经营传导关系；当前公开值为{latest['value']:g}{latest['unit']}。影响方向为规则化初筛，需结合企业业务结构复核。",
                "source_name": latest["source_name"], "source_url": latest["source_url"], "published_at": latest["period"], "impact_direction": direction,
                "severity": severity, "relevance_score": 0.9, "raw_payload": {"period": latest["period"], "value": latest["value"], "unit": latest["unit"], "industry": industry},
            })
            inserted += int(created)
            updated += int(not created)
    connection.commit()
    return inserted, updated


def refresh_company_macro_data(run_id: str, company_id: str) -> None:
    with connect() as connection:
        try:
            connection.execute("UPDATE ingestion_runs SET status='running', progress_current=0, message='正在识别企业行业', updated_at=? WHERE id=?", (now_iso(), run_id))
            connection.commit()
            company = company_from_row(get_company_or_404(connection, company_id))
            industry, _, cninfo = resolve_company_industry(connection, company)
            connection.execute("UPDATE ingestion_runs SET progress_current=1, message=?, updated_at=? WHERE id=?", ("行业识别完成" if industry else "未识别行业，将保留全国宏观分析", now_iso(), run_id))
            connection.commit()
            cached_results = cached_macro_sources(connection)
            if cached_results is not None:
                inserted, updated, results, failed = 0, 0, cached_results, []
                connection.execute("UPDATE ingestion_runs SET status='running', progress_current=?, source_results=?, message='宏观指标在 24 小时有效期内，复用最新缓存', updated_at=? WHERE id=?", (len(MACRO_INDICATORS) + 1, json.dumps(results, ensure_ascii=False), now_iso(), run_id))
                connection.commit()
            else:
                inserted, updated, results, failed = collect_macro_indicators(connection, run_id)
            try:
                policy_inserted, policy_updated, policy_result = collect_ndrc_policy_events(connection, industry)
                inserted += policy_inserted
                updated += policy_updated
                results.append(policy_result)
            except Exception as exc:
                failed.append("ndrc_policy")
                results.append({"source": "ndrc_policy", "status": "failed", "message": str(exc)[:240], "source_url": "https://www.ndrc.gov.cn/xxgk/zcfb/tz/wap_index.html"})
            connection.execute("UPDATE ingestion_runs SET progress_current=?, source_results=?, failed_sources=?, message='权威政策源处理完成', updated_at=? WHERE id=?", (len(MACRO_INDICATORS) + 2, json.dumps(results, ensure_ascii=False), json.dumps(failed, ensure_ascii=False), now_iso(), run_id))
            connection.commit()
            event_inserted, event_updated = generate_indicator_events(connection, industry)
            inserted += event_inserted
            updated += event_updated
            if isinstance(cninfo, dict) and cninfo.get("status") == "unavailable":
                failed.append("cninfo_profile")
                results.insert(0, {"source": "cninfo_profile", "status": "failed", "message": cninfo.get("message", "行业识别失败")[:240]})
            else:
                results.insert(0, {"source": "cninfo_profile", "status": "success" if industry else "partial", "industry": industry or None})
            status = "partial" if failed else "completed"
            message = f"采集完成：新增 {inserted} 条，更新 {updated} 条" + (f"；{len(failed)} 个来源暂不可用" if failed else "")
            connection.execute("UPDATE ingestion_runs SET status=?, progress_current=progress_total, inserted_count=?, updated_count=?, failed_sources=?, source_results=?, message=?, completed_at=?, updated_at=? WHERE id=?", (status, inserted, updated, json.dumps(failed, ensure_ascii=False), json.dumps(results, ensure_ascii=False), message, now_iso(), now_iso(), run_id))
            connection.commit()
        except Exception as exc:
            connection.execute("UPDATE ingestion_runs SET status='failed', message=?, failed_sources=?, completed_at=?, updated_at=? WHERE id=?", (str(exc)[:500], json.dumps(["refresh_pipeline"], ensure_ascii=False), now_iso(), now_iso(), run_id))
            connection.commit()


def event_rows(connection: sqlite3.Connection, company_id: str, category: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM risk_events WHERE company_id = ? AND category = ? ORDER BY COALESCE(occurred_at, created_at) DESC LIMIT ?",
        (db_id(company_id), category, limit),
    ).fetchall()
    events = []
    for row in rows:
        extra = parse_json(row["extra_payload"], {})
        events.append({
            "id": api_id(row["id"]), "title": row["title"], "content": row["content"],
            "source_url": row["source_url"], "source_name": row["source_name"],
            "published_at": row["occurred_at"] or row["created_at"], "severity": row["severity"],
            "sentiment": row["sentiment"], "page_hint": extra.get("page_hint", ""),
        })
    return events


def source_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": event["title"], "source_name": event["source_name"] or "公开来源",
        "source_url": event["source_url"], "source_tag": "结构化事件", "page_hint": event.get("page_hint", ""),
        "published_at": event["published_at"], "severity": event["severity"], "sentiment": event["sentiment"],
    }


def period_label(period: str) -> str:
    year, month = period[:4], period[4:6]
    quarter = {"03": "1", "06": "2", "09": "3", "12": "4"}.get(month, month)
    return f"{year}Q{quarter}"


def metric_row(rows: list[dict[str, Any]], names: tuple[str, ...]) -> dict[str, Any]:
    for row in rows:
        label = str(row.get("指标", ""))
        if any(name in label for name in names):
            return row
    return {}


def finance_preview(company: dict[str, Any], connection: sqlite3.Connection) -> dict[str, Any]:
    profile = company.get("company_profile", {}).get("akshare_profile", {})
    rows = profile.get("financial_abstract") or []
    revenue_row = metric_row(rows, ("营业总收入", "营业收入"))
    profit_row = metric_row(rows, ("归母净利润",))
    periods = sorted({key for key in revenue_row if str(key).isdigit() and len(str(key)) == 8 and revenue_row.get(key) is not None})
    latest = periods[-1] if periods else ""
    comparable = f"{int(latest[:4]) - 1}{latest[4:]}" if latest else ""
    revenue = float(revenue_row.get(latest) or 0) / 1e8 if latest else 0
    profit = float(profit_row.get(latest) or 0) / 1e8 if latest else 0
    previous_revenue = float(revenue_row.get(comparable) or 0) / 1e8 if comparable else 0
    previous_profit = float(profit_row.get(comparable) or 0) / 1e8 if comparable else 0
    revenue_growth = (revenue / previous_revenue - 1) * 100 if previous_revenue else None
    profit_growth = (profit / previous_profit - 1) * 100 if previous_profit else None
    indicators = profile.get("financial_indicators") or []
    latest_indicator = indicators[-1] if indicators else {}
    cash_ratio = latest_indicator.get("经营现金净流量与净利润的比率(%)")
    debt_ratio = latest_indicator.get("资产负债率(%)")
    events = event_rows(connection, company["id"], "finance")
    sources = [{
        "title": f"{company['name']} 财务摘要与财务指标", "source_name": "AkShare（公开财务数据聚合）",
        "source_url": "https://www.cninfo.com.cn/new/index", "source_tag": "财务数据",
        "page_hint": "financial_abstract / financial_indicators", "published_at": None, "severity": "", "sentiment": "",
    }] if periods else []
    sources.extend(source_from_event(event) for event in events)
    series_periods = periods[-8:]
    metrics = [
        {"key": "revenue", "label": f"{period_label(latest)}营收" if latest else "最新报告期营收", "value": f"{revenue:,.2f}" if latest else "待接入", "unit": "亿元", "delta": "", "tone": "neutral", "description": "", "source_ids": ["akshare-financial"] if latest else []},
        {"key": "net_profit", "label": f"{period_label(latest)}归母净利润" if latest else "最新报告期归母净利润", "value": f"{profit:,.2f}" if latest else "待接入", "unit": "亿元", "delta": "", "tone": "neutral", "description": "", "source_ids": ["akshare-financial"] if latest else []},
        {"key": "revenue_growth", "label": "营收同比增长", "value": f"{revenue_growth:.1f}" if revenue_growth is not None else "待接入", "unit": "%", "delta": "", "tone": "positive" if revenue_growth is not None and revenue_growth >= 0 else "warning", "description": "与上年同一报告期比较", "source_ids": ["akshare-financial"] if revenue_growth is not None else []},
        {"key": "profit_growth", "label": "净利润同比增长", "value": f"{profit_growth:.1f}" if profit_growth is not None else "待接入", "unit": "%", "delta": "", "tone": "positive" if profit_growth is not None and profit_growth >= 0 else "warning", "description": "", "source_ids": ["akshare-financial"] if profit_growth is not None else []},
        {"key": "cash_flow_elasticity", "label": "现金流弹性", "value": f"{float(cash_ratio):.2f}" if cash_ratio is not None else "待接入", "unit": "倍", "delta": "", "tone": "neutral", "description": "经营现金净流量与净利润比率", "source_ids": ["akshare-financial"] if cash_ratio is not None else []},
        {"key": "debt_safety_margin", "label": "债务安全边际", "value": f"{100 - float(debt_ratio):.1f}" if debt_ratio is not None else "待接入", "unit": "%", "delta": "", "tone": "warning" if debt_ratio is not None and float(debt_ratio) > 70 else "neutral", "description": "100% - 资产负债率，仅作偿债结构观察指标", "source_ids": ["akshare-financial"] if debt_ratio is not None else []},
    ]
    warnings = []
    if not periods: warnings.append("未取得 AkShare 财务摘要，营收、利润和趋势暂不可计算。")
    if cash_ratio is None: warnings.append("缺少经营现金流与净利润比率，现金流弹性暂不可计算。")
    summary = f"{company['name']} {period_label(latest)}累计营收{revenue:,.2f}亿元、归母净利润{profit:,.2f}亿元" if latest else f"{company['name']} 尚未取得可计算的营收与归母净利润序列。"
    if revenue_growth is not None: summary += f"；同口径营收同比{revenue_growth:.1f}%"
    table_periods = periods[-6:]
    return {
        "company_name": company["name"], "category": "finance", "report_type": REPORT_TYPES["finance"],
        "retrieval_stage": "financial_data_first", "summary": summary,
        "key_points": [f"{event['title']}：{event['content']}" for event in events[:3]],
        "next_actions": ["对年度与季度累计口径分别分析，避免直接比较不同报告期。", "补充现金流量表、研发投入与资本开支，完成情景压力测试。"],
        "sources": sources, "metrics": metrics,
        "series": [
            {"key": "revenue", "label": "营业总收入", "unit": "亿元", "points": [{"period": period_label(period), "value": round(float(revenue_row.get(period) or 0) / 1e8, 2)} for period in series_periods], "source_ids": ["akshare-financial"]},
            {"key": "net_profit", "label": "归母净利润", "unit": "亿元", "points": [{"period": period_label(period), "value": round(float(profit_row.get(period) or 0) / 1e8, 2)} for period in series_periods], "source_ids": ["akshare-financial"]},
        ] if periods else [],
        "sections": [
            {"key": "period_analysis", "title": "年度 / 季度财务分析", "kind": "table", "summary": "AkShare 报告期累计口径；同比计算仅使用上年同一报告期。", "items": [{"period": period_label(period), "revenue": round(float(revenue_row.get(period) or 0) / 1e8, 2), "net_profit": round(float(profit_row.get(period) or 0) / 1e8, 2), "net_margin": round((float(profit_row.get(period) or 0) / float(revenue_row.get(period) or 1)) * 100, 2)} for period in table_periods], "source_ids": ["akshare-financial"]},
            {"key": "announcement_timeline", "title": "财务公告时间线", "kind": "timeline", "summary": "展示已入库公告和财务事件。", "items": [{"date": str(event["published_at"] or "")[:10], "title": event["title"], "detail": event["content"], "severity": event["severity"], "sentiment": event["sentiment"]} for event in events], "source_ids": [event["id"] for event in events]},
        ],
        "data_quality": {"status": "complete" if periods else "partial", "coverage_percent": 90 if periods else 25, "evidence_count": len(sources), "warnings": warnings, "updated_at": profile.get("updated_at")},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def transmission_channel(indicator_code: str, industry: str) -> tuple[str, str]:
    if indicator_code == "lpr_1y":
        if any(keyword in industry for keyword in ("银行", "金融")):
            return "利率与信贷", "贷款定价、净息差与融资需求可能受到传导"
        return "融资成本", "借款成本、资本开支与终端融资需求可能受到传导"
    if indicator_code == "m2_yoy":
        return "市场流动性", "信贷供给、估值与投资需求可能受到传导"
    if indicator_code in {"manufacturing_pmi", "non_manufacturing_pmi"}:
        return "行业景气", "订单、库存、产能利用率与供应商排产可能受到传导"
    if indicator_code == "ppi_yoy":
        return "工业品价格", "原材料采购成本与产品出厂价格可能受到传导"
    if indicator_code == "cpi_yoy":
        return "消费价格", "终端需求、产品定价和渠道库存可能受到传导"
    if indicator_code == "gdp_yoy":
        return "总需求", "收入预期、行业需求和经营增长可能受到传导"
    return "宏观环境", "企业经营环境可能受到传导"


def macro_event_rows(connection: sqlite3.Connection, industry: str, limit: int) -> list[dict[str, Any]]:
    per_dimension = max(6, limit // 3)
    rows = list(connection.execute("SELECT * FROM macro_industry_events WHERE scope_type='macro' AND dimension='macroeconomy' ORDER BY published_at DESC LIMIT ?", (per_dimension,)).fetchall())
    if industry:
        rows.extend(connection.execute("SELECT * FROM macro_industry_events WHERE scope_type='industry' AND scope_key=? AND dimension='industry_cycle' ORDER BY published_at DESC LIMIT ?", (industry, per_dimension)).fetchall())
        rows.extend(connection.execute("SELECT * FROM macro_industry_events WHERE dimension='policy_regulatory' AND (scope_type='macro' OR (scope_type='industry' AND scope_key=?)) ORDER BY published_at DESC, relevance_score DESC LIMIT ?", (industry, per_dimension)).fetchall())
    else:
        rows.extend(connection.execute("SELECT * FROM macro_industry_events WHERE scope_type='macro' AND dimension='policy_regulatory' ORDER BY published_at DESC LIMIT ?", (per_dimension,)).fetchall())
    rows.sort(key=lambda row: str(row["published_at"]), reverse=True)
    return [{
        "id": api_id(row["id"]), "scope_type": row["scope_type"], "scope_key": row["scope_key"], "dimension": row["dimension"],
        "event_type": row["event_type"], "indicator_code": row["indicator_code"], "title": row["title"], "content": row["summary"],
        "source_name": row["source_name"], "source_url": row["source_url"], "published_at": row["published_at"],
        "sentiment": row["impact_direction"], "severity": row["severity"], "relevance_score": row["relevance_score"],
        "page_hint": row["dimension"],
    } for row in rows]


def latest_ingestion_run(connection: sqlite3.Connection, company_id: str) -> Optional[dict[str, Any]]:
    row = connection.execute("SELECT * FROM ingestion_runs WHERE company_id=? ORDER BY updated_at DESC LIMIT 1", (db_id(company_id),)).fetchone()
    return run_from_row(row) if row else None


def macro_preview(company: dict[str, Any], connection: sqlite3.Connection, limit: int = 20) -> dict[str, Any]:
    industry = str(company.get("industry") or "")
    structured_events = macro_event_rows(connection, industry, limit)
    legacy_events = event_rows(connection, company["id"], "macro", limit)
    for event in legacy_events:
        event.update({"scope_type": "company", "scope_key": company["name"], "dimension": "policy_regulatory", "event_type": "legacy_company_event", "indicator_code": "", "relevance_score": 1})
    events = sorted(structured_events + legacy_events, key=lambda event: str(event.get("published_at") or ""), reverse=True)
    indicator_configs = {config["code"]: config for config in MACRO_INDICATORS}
    latest_indicators: list[dict[str, Any]] = []
    series: list[dict[str, Any]] = []
    for config in MACRO_INDICATORS:
        rows = connection.execute("SELECT * FROM macro_indicator_points WHERE indicator_code=? ORDER BY period DESC LIMIT 12", (config["code"],)).fetchall()
        if not rows:
            continue
        latest = rows[0]
        previous = float(rows[1]["value"]) if len(rows) > 1 else None
        direction, severity = indicator_direction(config["code"], float(latest["value"]), previous)
        latest_indicators.append({
            "code": config["code"], "name": latest["indicator_name"], "period": latest["period"], "value": latest["value"], "unit": latest["unit"],
            "frequency": latest["frequency"], "direction": direction, "severity": severity, "source_name": latest["source_name"], "source_url": latest["source_url"],
            "change": round(float(latest["value"]) - previous, 2) if previous is not None else None,
        })
        if config["code"] in relevant_indicator_codes(industry) | {"gdp_yoy"}:
            series.append({
                "key": config["code"], "label": latest["indicator_name"], "unit": latest["unit"],
                "points": [{"period": row["period"], "value": float(row["value"])} for row in reversed(rows[:8])],
                "source_ids": [f"indicator-{config['code']}"],
            })
    industry_signals = [event for event in events if event.get("scope_type") == "industry" and event.get("dimension") == "industry_cycle"]
    macro_events = [event for event in events if event.get("scope_type") == "macro" and event.get("dimension") == "macroeconomy"]
    policy_events = [event for event in events if event.get("dimension") == "policy_regulatory" or event.get("scope_type") == "company"]
    impact_chains = []
    for event in industry_signals[:6]:
        channel, impact = transmission_channel(str(event.get("indicator_code") or ""), industry)
        impact_chains.append({
            "event": event["title"], "channel": channel, "company": company["name"], "impact": impact,
            "direction": {"positive": "正向", "negative": "负向", "neutral": "中性"}.get(event.get("sentiment"), "中性"),
            "evidence": event["source_name"],
        })
    source_map: dict[str, dict[str, Any]] = {}
    for event in events:
        key = f"{event['title']}|{event['source_name']}"
        source_map[key] = source_from_event(event)
    for indicator in latest_indicators:
        key = f"indicator|{indicator['code']}"
        source_map[key] = {
            "title": f"{indicator['period']} {indicator['name']} {indicator['value']:g}{indicator['unit']}",
            "source_name": indicator["source_name"], "source_url": indicator["source_url"], "source_tag": "宏观指标",
            "page_hint": indicator["code"], "published_at": indicator["period"], "severity": indicator["severity"], "sentiment": indicator["direction"],
        }
    run = latest_ingestion_run(connection, company["id"])
    updated_at = run.get("completed_at") or run.get("updated_at") if run else None
    stale = True
    if updated_at:
        try:
            stale = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00")).replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
        except ValueError:
            stale = True
    source_coverage = run.get("source_results", []) if run else []
    successful_sources = sum(1 for item in source_coverage if item.get("status") == "success")
    warnings: list[str] = []
    if not industry:
        warnings.append("尚未识别企业所属行业，当前仅展示全国宏观指标和公司级事件。")
    if not policy_events:
        warnings.append("当前未命中可追溯的政策监管事件；不会基于空白数据生成政策判断。")
    if not industry_signals and industry:
        warnings.append("当前行业尚未形成可用的结构化景气信号。")
    if run and run.get("failed_sources"):
        warnings.append(f"本次刷新有 {len(run['failed_sources'])} 个来源暂不可用，其余结果仍可使用。")
    if stale:
        warnings.append("宏观与行业数据超过 24 小时未成功刷新，建议执行按需刷新。")
    metrics = []
    for indicator in latest_indicators[:6]:
        change = indicator.get("change")
        metrics.append({
            "key": indicator["code"], "label": indicator["name"], "value": f"{indicator['value']:g}", "unit": indicator["unit"],
            "delta": f"较上期 {change:+g}{indicator['unit']}" if change is not None else indicator["period"],
            "tone": "positive" if indicator["direction"] == "positive" else ("warning" if indicator["direction"] == "negative" else "neutral"),
            "description": indicator["period"], "source_ids": [f"indicator-{indicator['code']}"],
        })
    sections = [
        {"key": "macro_timeline", "title": "宏观经济事件时间线", "kind": "timeline", "summary": "依据已发布宏观指标生成，不包含无来源推断。", "items": [{"date": event["published_at"], "title": event["title"], "detail": event["content"], "severity": event["severity"], "sentiment": event["sentiment"]} for event in macro_events[:8]], "source_ids": [event["id"] for event in macro_events[:8]]},
        {"key": "industry_signals", "title": f"{industry or '待识别行业'}景气与风险信号", "kind": "table", "summary": "将企业所属行业与宏观指标建立规则化关联；影响方向需结合企业业务复核。", "items": [{"period": event["published_at"], "signal": event["title"], "direction": {"positive": "正向", "negative": "负向", "neutral": "中性"}.get(event["sentiment"], "中性"), "source": event["source_name"]} for event in industry_signals[:8]], "source_ids": [event["id"] for event in industry_signals[:8]]},
        {"key": "impact_chains", "title": "企业影响传导链", "kind": "table", "summary": "展示事件或指标如何通过行业渠道传导至企业，不将相关性表述为确定因果。", "items": impact_chains, "source_ids": [event["id"] for event in industry_signals[:6]]},
        {"key": "policy_regulatory", "title": "政策与监管事件", "kind": "timeline", "summary": "仅展示已经入库且可追溯的政策、监管或公司级宏观事件。", "items": [{"date": event["published_at"], "title": event["title"], "detail": event["content"], "source": event["source_name"]} for event in policy_events[:8]], "source_ids": [event["id"] for event in policy_events[:8]]},
    ]
    evidence_count = len(source_map)
    coverage = min(95, 20 + len(latest_indicators) * 7 + min(len(industry_signals), 4) * 5 + min(len(policy_events), 2) * 5)
    headline = f"{company['name']}已关联{industry}，当前获得 {len(latest_indicators)} 项宏观指标和 {len(industry_signals)} 条行业信号" if industry else f"{company['name']}当前获得 {len(latest_indicators)} 项全国宏观指标，行业仍待识别"
    key_points = [f"{event['title']}：{event['content']}" for event in industry_signals[:3]]
    if not key_points:
        key_points = [f"{item['period']} {item['name']}为{item['value']:g}{item['unit']}，来源：{item['source_name']}。" for item in latest_indicators[:3]]
    return {
        "company_name": company["name"], "category": "macro", "report_type": REPORT_TYPES["macro"], "retrieval_stage": "macro_industry_evidence_first",
        "summary": headline, "key_points": key_points,
        "next_actions": ["关注刷新后的指标方向变化，并结合企业主营业务复核影响传导。", "对政策监管、技术供应链和 ESG 空白项持续补充权威公开证据。"],
        "sources": list(source_map.values()), "metrics": metrics, "series": series[:5], "sections": sections,
        "macro_indicators": latest_indicators, "industry_signals": industry_signals, "impact_chains": impact_chains,
        "freshness": {"updated_at": updated_at, "stale": stale, "stale_after_hours": 24}, "source_coverage": source_coverage,
        "data_quality": {"status": "complete" if coverage >= 80 and not stale else "partial", "coverage_percent": coverage, "evidence_count": evidence_count, "warnings": warnings, "updated_at": updated_at or company.get("updated_at")},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def event_preview(company: dict[str, Any], connection: sqlite3.Connection, category: str) -> dict[str, Any]:
    events = event_rows(connection, company["id"], category)
    negative = sum(1 for event in events if event["sentiment"] == "negative")
    high = sum(1 for event in events if event["severity"] in {"important", "high", "重要"})
    label = {"macro": "宏观与行业", "operations": "业务运营", "legal": "法律合规", "brand": "品牌舆情"}[category]
    warnings = [] if events else [f"当前未入库{label}事件，相关结论和趋势暂不可计算。"]
    metrics = [
        {"key": "event_count", "label": f"{label}事件", "value": str(len(events)), "unit": "条", "delta": "", "tone": "neutral", "description": "当前入库样本", "source_ids": [event["id"] for event in events]},
        {"key": "high_priority", "label": "高优先级", "value": str(high), "unit": "条", "delta": "", "tone": "warning" if high else "neutral", "description": "", "source_ids": [event["id"] for event in events]},
        {"key": "negative_share", "label": "负面事件占比", "value": f"{negative / len(events) * 100:.1f}" if events else "待接入", "unit": "%", "delta": "", "tone": "warning" if negative else "neutral", "description": "仅代表当前入库样本", "source_ids": [event["id"] for event in events]},
    ]
    sections = [{
        "key": f"{category}_timeline", "title": f"{label}事件时间线", "kind": "timeline", "summary": "按发生时间展示当前已入库事件。",
        "items": [{"date": str(event["published_at"] or "")[:10], "title": event["title"], "detail": event["content"], "severity": event["severity"], "sentiment": event["sentiment"]} for event in events],
        "source_ids": [event["id"] for event in events],
    }]
    return {
        "company_name": company["name"], "category": category, "report_type": REPORT_TYPES[category],
        "retrieval_stage": "risk_events_first", "summary": f"{company['name']} {label}维度命中 {len(events)} 条可追溯事件，其中高优先级 {high} 条。" if events else f"{company['name']} 暂无可用于{label}分析的入库事件。",
        "key_points": [f"{event['title']}：{event['content']}" for event in events[:3]],
        "next_actions": ["补充权威来源和结构化字段，提高分析覆盖率。", "持续监控新增事件，并核验其对经营、财务和品牌的传导影响。"],
        "sources": [source_from_event(event) for event in events], "metrics": metrics, "series": [], "sections": sections,
        "data_quality": {"status": "partial", "coverage_percent": min(85, 20 + len(events) * 15), "evidence_count": len(events), "warnings": warnings, "updated_at": company.get("updated_at")},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/companies")
def list_companies() -> list[dict[str, Any]]:
    with connect() as connection:
        return [company_from_row(row) for row in connection.execute("SELECT * FROM companies ORDER BY updated_at DESC").fetchall()]


@app.get("/api/v1/companies/{company_id}")
def get_company(company_id: str) -> dict[str, Any]:
    with connect() as connection:
        return company_from_row(get_company_or_404(connection, company_id))


@app.post("/api/v1/companies/search-and-ingest")
def search_and_ingest(payload: dict[str, Any], background_tasks: BackgroundTasks) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    stock_code = str(payload.get("stock_code") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="请输入公司名称或股票代码")
    with connect() as connection:
        rows = connection.execute("SELECT * FROM companies").fetchall()
        existing = None
        for row in rows:
            profile = parse_json(row["company_profile"], {}).get("akshare_profile", {})
            if row["name"] == name or (stock_code and profile.get("stock_code") == stock_code) or (name.isdigit() and profile.get("stock_code") == name):
                existing = row
                break
        akshare_profile = resolve_akshare(name, stock_code or (name if name.isdigit() else ""))
        if existing:
            company_profile = parse_json(existing["company_profile"], {})
            if akshare_profile.get("status") == "available":
                company_profile["akshare_profile"] = akshare_profile
                description = f"AkShare 已匹配上市公司：{akshare_profile.get('stock_name')} / {akshare_profile.get('stock_code')}"
                connection.execute("UPDATE companies SET company_profile = ?, description = ?, updated_at = ? WHERE id = ?", (json.dumps(json_safe(company_profile), ensure_ascii=False), description, now_iso(), existing["id"]))
                connection.commit()
            refreshed = connection.execute("SELECT * FROM companies WHERE id = ?", (existing["id"],)).fetchone()
            run = create_ingestion_run(connection, api_id(existing["id"]), "search_refresh")
            background_tasks.add_task(refresh_company_macro_data, db_id(run["id"]), api_id(existing["id"]))
            return {"company": company_from_row(refreshed), "created": False, "ingestion_run": run}
        company_id = uuid.uuid4().hex
        display_name = name if not name.isdigit() else akshare_profile.get("stock_name", name)
        profile = {"akshare_profile": akshare_profile, "qichacha_profile": {"status": "unavailable", "reason": "missing_credentials", "message": "暂未配置企查查官方 API Key。"}}
        description = f"AkShare 已匹配上市公司：{akshare_profile.get('stock_name')} / {akshare_profile.get('stock_code')}" if akshare_profile.get("status") == "available" else "企业基础档案已创建，公开数据待补充"
        timestamp = now_iso()
        connection.execute("INSERT INTO companies (id, name, credit_code, industry, region, description, official_website, company_profile, created_at, updated_at) VALUES (?, ?, NULL, NULL, NULL, ?, '', ?, ?, ?)", (company_id, display_name, description, json.dumps(json_safe(profile), ensure_ascii=False), timestamp, timestamp))
        connection.commit()
        created = connection.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        run = create_ingestion_run(connection, api_id(company_id), "search_refresh")
        background_tasks.add_task(refresh_company_macro_data, db_id(run["id"]), api_id(company_id))
        return {"company": company_from_row(created), "created": True, "ingestion_run": run}


@app.post("/api/v1/companies/{company_id}/macro-industry/refresh", status_code=202)
def refresh_macro_industry(company_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    with connect() as connection:
        get_company_or_404(connection, company_id)
        active = connection.execute("SELECT * FROM ingestion_runs WHERE company_id=? AND status IN ('queued', 'running') ORDER BY updated_at DESC LIMIT 1", (db_id(company_id),)).fetchone()
        if active:
            return run_from_row(active)
        run = create_ingestion_run(connection, company_id)
    background_tasks.add_task(refresh_company_macro_data, db_id(run["id"]), company_id)
    return run


@app.get("/api/v1/ingestion-runs/{run_id}")
def get_ingestion_run(run_id: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute("SELECT * FROM ingestion_runs WHERE id=?", (db_id(run_id),)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        return run_from_row(row)


@app.get("/api/v1/agent-analysis/preview")
def preview_agent_analysis(company_id: str, category: str = Query(pattern="^(macro|operations|finance|legal|brand)$"), limit: int = 12) -> dict[str, Any]:
    with connect() as connection:
        company = company_from_row(get_company_or_404(connection, company_id))
        if category == "macro":
            return macro_preview(company, connection, max(limit, 20))
        latest = connection.execute("SELECT * FROM analysis_reports WHERE company_id = ? AND report_type = ? ORDER BY generated_at DESC, created_at DESC LIMIT 1", (db_id(company_id), REPORT_TYPES[category])).fetchone()
        if latest:
            snapshot = parse_json(latest["snapshot"], {})
            analysis = snapshot.get("analysis")
            if isinstance(analysis, dict) and analysis.get("metrics") is not None:
                analysis["generated_at"] = datetime.now(timezone.utc).isoformat()
                return analysis
        return finance_preview(company, connection) if category == "finance" else event_preview(company, connection, category)


@app.post("/api/v1/analysis-reports", status_code=201)
def create_analysis_report(payload: dict[str, Any]) -> dict[str, Any]:
    required = ("company_id", "report_type", "title")
    if any(not payload.get(key) for key in required):
        raise HTTPException(status_code=422, detail="报告缺少必填字段")
    report_id = uuid.uuid4().hex
    timestamp = now_iso()
    with connect() as connection:
        get_company_or_404(connection, str(payload["company_id"]))
        connection.execute("INSERT INTO analysis_reports (id, company_id, report_type, title, summary, snapshot, model_name, generated_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (report_id, db_id(str(payload["company_id"])), str(payload["report_type"]), str(payload["title"]), str(payload.get("summary") or ""), json.dumps(json_safe(payload.get("snapshot") or {}), ensure_ascii=False), str(payload.get("model_name") or "structured-agent-v1"), timestamp, timestamp, timestamp))
        connection.commit()
        row = connection.execute("SELECT * FROM analysis_reports WHERE id = ?", (report_id,)).fetchone()
        return report_from_row(row)


@app.get("/api/v1/companies/{company_id}/analysis-reports")
def list_analysis_reports(company_id: str, report_type: Optional[str] = None, limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    with connect() as connection:
        get_company_or_404(connection, company_id)
        if report_type:
            rows = connection.execute("SELECT * FROM analysis_reports WHERE company_id = ? AND report_type = ? ORDER BY generated_at DESC, created_at DESC LIMIT ?", (db_id(company_id), report_type, limit)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM analysis_reports WHERE company_id = ? ORDER BY generated_at DESC, created_at DESC LIMIT ?", (db_id(company_id), limit)).fetchall()
        return [report_from_row(row) for row in rows]


@app.get("/api/v1/companies/{company_id}/analysis-reports/latest")
def latest_analysis_report(company_id: str, report_type: Optional[str] = None) -> dict[str, Any]:
    reports = list_analysis_reports(company_id, report_type, 1)
    if not reports:
        raise HTTPException(status_code=404, detail="暂无报告")
    return reports[0]


@app.post("/api/v1/analysis-reports/compose", status_code=201)
def compose_analysis_report(payload: dict[str, Any]) -> dict[str, Any]:
    company_id = str(payload.get("company_id") or "")
    report_types = payload.get("report_types") or list(REPORT_TYPES.values())
    with connect() as connection:
        company = company_from_row(get_company_or_404(connection, company_id))
        assembled = []
        for report_type in report_types:
            row = connection.execute("SELECT * FROM analysis_reports WHERE company_id = ? AND report_type = ? ORDER BY generated_at DESC, created_at DESC LIMIT 1", (db_id(company_id), report_type)).fetchone()
            if row:
                report = report_from_row(row)
                assembled.append({"report_type": report["report_type"], "title": report["title"], "summary": report["summary"], "generated_at": report["generated_at"], "snapshot": report["snapshot"]})
        title = str(payload.get("title") or f"{company['name']}综合风险分析报告")
        summary = f"本次综合风险报告整合了 {len(assembled)} 个维度的最新分析快照，适用于生成管理层汇总版或自定义风险周报。"
        snapshot = {"assembly_mode": "latest_by_report_type", "source_report_types": report_types, "assembled_reports": assembled}
        report_id = uuid.uuid4().hex
        timestamp = now_iso()
        connection.execute("INSERT INTO analysis_reports (id, company_id, report_type, title, summary, snapshot, model_name, generated_at, created_at, updated_at) VALUES (?, ?, 'comprehensive_risk_report', ?, ?, ?, 'd-trust-agent', ?, ?, ?)", (report_id, db_id(company_id), title, summary, json.dumps(snapshot, ensure_ascii=False), timestamp, timestamp, timestamp))
        connection.commit()
        row = connection.execute("SELECT * FROM analysis_reports WHERE id = ?", (report_id,)).fetchone()
        return report_from_row(row)


def run_daily_macro_sync() -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    with connect() as connection:
        company_ids = [api_id(row["id"]) for row in connection.execute("SELECT id FROM companies ORDER BY updated_at DESC").fetchall()]
    for company_id in company_ids:
        with connect() as connection:
            run = create_ingestion_run(connection, company_id, "daily_sync")
        refresh_company_macro_data(db_id(run["id"]), company_id)
        with connect() as connection:
            completed.append(run_from_row(connection.execute("SELECT * FROM ingestion_runs WHERE id=?", (db_id(run["id"]),)).fetchone()))
    return completed


if __name__ == "__main__":
    if "--sync-macro-industry" in sys.argv:
        print(json.dumps(run_daily_macro_sync(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
