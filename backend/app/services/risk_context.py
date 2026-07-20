from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Company, RiskEvent


def get_company_by_ref(
    db: Session,
    *,
    company_id=None,
    company_name: str | None = None,
) -> Company | None:
    if company_id:
        return db.get(Company, company_id)
    if company_name:
        normalized_name = "".join(company_name.split())

        exact_statement = select(Company).where(Company.name == company_name.strip())
        company = db.execute(exact_statement).scalar_one_or_none()
        if company:
            return company

        fuzzy_statement = (
            select(Company)
            .where(
                func.replace(Company.name, " ", "").ilike(f"%{normalized_name}%")
            )
            .order_by(func.length(Company.name))
            .limit(1)
        )
        return db.execute(fuzzy_statement).scalar_one_or_none()
    return None


def fetch_recent_risk_events(
    db: Session,
    *,
    company_id=None,
    company_name: str | None = None,
    limit: int | None = None,
) -> tuple[Company, list[RiskEvent]]:
    settings = get_settings()
    company = get_company_by_ref(
        db,
        company_id=company_id,
        company_name=company_name,
    )
    if not company:
        raise ValueError("未找到目标公司，请先创建 companies 记录。")

    statement = (
        select(RiskEvent)
        .where(RiskEvent.company_id == company.id)
        .order_by(RiskEvent.occurred_at.desc().nullslast(), RiskEvent.created_at.desc())
        .limit(limit or settings.default_context_limit)
    )
    risk_events = list(db.execute(statement).scalars())
    return company, risk_events


def build_risk_digest(risk_events: list[RiskEvent]) -> list[dict[str, str]]:
    return [
        {
            "category": item.category,
            "severity": item.severity,
            "title": item.title,
            "content": item.content,
            "source_url": item.source_url,
            "occurred_at": item.occurred_at.isoformat() if item.occurred_at else "",
        }
        for item in risk_events
    ]


def build_system_prompt(company: Company, risk_events: list[RiskEvent], question: str = "") -> str:
    severity_counter = Counter(item.severity for item in risk_events)
    category_counter = Counter(item.category for item in risk_events)

    digest_lines = []
    for item in risk_events:
        event_date = item.occurred_at.strftime("%Y-%m-%d") if item.occurred_at else "未知日期"
        digest_lines.append(
            f"- [{item.severity}] {event_date} | {item.category} | {item.title} | {item.content} | 来源: {item.source_url}"
        )

    header = [
        f"企业名称: {company.name}",
        f"所属行业: {company.industry or '未标注'}",
        f"所在区域: {company.region or '未标注'}",
        f"风险严重度分布: {dict(severity_counter)}",
        f"风险类别分布: {dict(category_counter)}",
    ]

    if question:
        header.append(f"用户问题: {question}")

    prompt_body = digest_lines or ["- 暂无已入库风险事件，请基于已有企业画像回答。"]

    return "\n".join(
        [
            "你是一位商业分析智能体，请严格基于给定企业画像和实时风险数据回答问题。",
            "若结论不充分，要明确指出证据不足，不要编造事实。",
            *header,
            "最新风险清单:",
            *prompt_body,
        ]
    )
