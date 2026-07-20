from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisReport, RiskEvent
from app.services.risk_context import get_company_by_ref


CATEGORY_LABELS = {
    "macro": "宏观环境及行业分析",
    "operations": "企业业务运营分析",
    "finance": "企业财务状况分析",
    "legal": "法律诉讼风险分析",
    "brand": "品牌舆情分析",
}

REPORT_TYPES = {
    "macro": "macro_environment_report",
    "operations": "business_operations_report",
    "finance": "financial_health_report",
    "legal": "legal_risk_report",
    "brand": "brand_sentiment_report",
}

DEFAULT_NEXT_ACTIONS = {
    "macro": [
        "补充政策原文、市场规模与主要竞争者份额，形成可量化的行业雷达。",
        "将跨境政策节点与海外产能、区域销量和单车利润联动跟踪。",
    ],
    "operations": [
        "接入订单、交付、库存和风险工单系统，替换当前缺失的经营漏斗指标。",
        "按工厂拆解设备、认证、供应链和投产节点，并加入同业对标。",
    ],
    "finance": [
        "对年度与季度累计口径分别分析，避免直接比较不同报告期。",
        "补充现金流量表、研发投入与资本开支，完成情景压力测试。",
    ],
    "legal": [
        "补充案件编号、阶段、涉案金额与裁判文书原文，完善风险敞口。",
        "按业务链路建立法规变化、处罚与诉讼的传导和处置矩阵。",
    ],
    "brand": [
        "接入新闻、社交平台和行业自媒体的实时流，校准情绪样本覆盖。",
        "按话题热度、扩散速度和媒体/KOL 权重设置分级预警阈值。",
    ],
}

SEVERITY_HIGH = {"important", "high", "critical", "重要", "高", "严重"}
SENTIMENT_NEGATIVE = {"negative", "负面", "消极"}
SENTIMENT_POSITIVE = {"positive", "正面", "积极"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _period_label(period: str) -> str:
    if len(period) == 8 and period.isdigit():
        month = period[4:6]
        quarter = {"03": "Q1", "06": "Q2", "09": "Q3", "12": "Q4"}.get(month)
        if quarter:
            return f"{period[:4]}{quarter}"
    return period


def _metric_row(rows: list[dict[str, Any]], *names: str) -> dict[str, Any]:
    for row in rows:
        metric_name = str(row.get("指标") or row.get("项目") or "")
        if any(name == metric_name or name in metric_name for name in names):
            return row
    return {}


def _period_values(row: dict[str, Any], limit: int = 8) -> list[tuple[str, float]]:
    values = [
        (str(key), number)
        for key, value in row.items()
        if len(str(key)) == 8
        and str(key).isdigit()
        and (number := _number(value)) is not None
    ]
    return sorted(values, key=lambda item: item[0])[-limit:]


def _growth_for_latest(row: dict[str, Any]) -> float | None:
    values = _period_values(row, limit=100)
    if not values:
        return None
    latest_period, latest_value = values[-1]
    previous_period = f"{int(latest_period[:4]) - 1}{latest_period[4:]}"
    previous_value = _number(row.get(previous_period))
    if previous_value in (None, 0):
        return None
    return round((latest_value / previous_value - 1) * 100, 1)


def _latest_indicator(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: str(row.get("日期") or ""), default={})


def _metric(
    key: str,
    label: str,
    value: Any,
    *,
    unit: str = "",
    delta: str = "",
    tone: str = "neutral",
    description: str = "",
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    display = "待接入" if value is None else str(value)
    return {
        "key": key,
        "label": label,
        "value": display,
        "unit": unit,
        "delta": delta,
        "tone": tone,
        "description": description,
        "source_ids": source_ids or [],
    }


def _event_source(event: RiskEvent, index: int) -> dict[str, Any]:
    extra = event.extra_payload or {}
    return {
        "id": f"event-{index + 1}",
        "title": event.title,
        "source_name": event.source_name,
        "source_url": event.source_url,
        "source_tag": "结构化事件",
        "page_hint": str(
            extra.get("page_hint")
            or extra.get("pdf_page")
            or extra.get("report_page")
            or ""
        ),
        "published_at": event.occurred_at or event.created_at,
        "severity": event.severity,
        "sentiment": event.sentiment,
    }


def _timeline_items(events: list[RiskEvent]) -> list[dict[str, Any]]:
    return [
        {
            "date": (event.occurred_at or event.created_at).date().isoformat(),
            "title": event.title,
            "detail": event.content,
            "severity": event.severity,
            "sentiment": event.sentiment,
            "source_id": f"event-{index + 1}",
        }
        for index, event in enumerate(events)
    ]


def _event_metrics(events: list[RiskEvent]) -> tuple[int, int, float]:
    total = len(events)
    high = sum(event.severity in SEVERITY_HIGH for event in events)
    negative = sum(event.sentiment in SENTIMENT_NEGATIVE for event in events)
    negative_share = round(negative / total * 100, 1) if total else 0.0
    return total, high, negative_share


def _akshare_context(company: Any) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    profile = (company.company_profile or {}).get("akshare_profile") or {}
    abstract = profile.get("financial_abstract") or []
    indicators = profile.get("financial_indicators") or []
    return profile, abstract, _latest_indicator(indicators)


def _finance_analysis(company: Any, events: list[RiskEvent]) -> dict[str, Any]:
    profile, abstract, indicator = _akshare_context(company)
    revenue_row = _metric_row(abstract, "营业总收入", "营业收入")
    profit_row = _metric_row(abstract, "归母净利润", "净利润")
    revenue_values = _period_values(revenue_row)
    profit_values = _period_values(profit_row)
    latest_revenue = revenue_values[-1][1] if revenue_values else None
    latest_profit = profit_values[-1][1] if profit_values else None
    revenue_growth = _growth_for_latest(revenue_row)
    profit_growth = _growth_for_latest(profit_row)
    debt_ratio = _number(indicator.get("资产负债率(%)"))
    cash_elasticity = _number(indicator.get("经营现金净流量与净利润的比率(%)"))
    source_ids = ["akshare-financial"] if abstract else []

    sources = [_event_source(event, index) for index, event in enumerate(events)]
    if abstract:
        sources.insert(
            0,
            {
                "id": "akshare-financial",
                "title": f"{company.name} 财务摘要与财务指标",
                "source_name": "AkShare（公开财务数据聚合）",
                "source_url": "https://www.cninfo.com.cn/new/index",
                "source_tag": "财务数据",
                "page_hint": "financial_abstract / financial_indicators",
                "published_at": None,
                "severity": "",
                "sentiment": "",
            },
        )

    latest_period = _period_label(revenue_values[-1][0]) if revenue_values else "最新报告期"
    if latest_revenue is not None and latest_profit is not None:
        summary = (
            f"{company.name} {latest_period}累计营收{latest_revenue / 1e8:,.2f}亿元、"
            f"归母净利润{latest_profit / 1e8:,.2f}亿元；"
            f"同口径营收同比{revenue_growth:.1f}%" if revenue_growth is not None else
            f"{company.name} {latest_period}已取得营收和净利润数据，但缺少可比报告期。"
        )
    else:
        summary = f"{company.name} 尚未取得可计算的营收与归母净利润序列。"

    metrics = [
        _metric(
            "revenue",
            f"{latest_period}营收",
            f"{latest_revenue / 1e8:,.2f}" if latest_revenue is not None else None,
            unit="亿元",
            source_ids=source_ids,
        ),
        _metric(
            "net_profit",
            f"{latest_period}归母净利润",
            f"{latest_profit / 1e8:,.2f}" if latest_profit is not None else None,
            unit="亿元",
            source_ids=source_ids,
        ),
        _metric(
            "revenue_growth",
            "营收同比增长",
            f"{revenue_growth:.1f}" if revenue_growth is not None else None,
            unit="%",
            tone="positive" if revenue_growth is not None and revenue_growth >= 0 else "warning",
            description="与上年同一报告期比较",
            source_ids=source_ids,
        ),
        _metric(
            "profit_growth",
            "净利润同比增长",
            f"{profit_growth:.1f}" if profit_growth is not None else None,
            unit="%",
            tone="positive" if profit_growth is not None and profit_growth >= 0 else "warning",
            source_ids=source_ids,
        ),
        _metric(
            "cash_flow_elasticity",
            "现金流弹性",
            f"{cash_elasticity:.2f}" if cash_elasticity is not None else None,
            unit="倍",
            description="经营现金净流量与净利润比率",
            source_ids=source_ids,
        ),
        _metric(
            "debt_safety_margin",
            "债务安全边际",
            f"{100 - debt_ratio:.1f}" if debt_ratio is not None else None,
            unit="%",
            tone="warning" if debt_ratio is not None and debt_ratio > 70 else "neutral",
            description="100% - 资产负债率，仅作偿债结构观察指标",
            source_ids=source_ids,
        ),
    ]
    series = [
        {
            "key": "revenue",
            "label": "营业总收入",
            "unit": "亿元",
            "points": [
                {"period": _period_label(period), "value": round(value / 1e8, 2)}
                for period, value in revenue_values
            ],
            "source_ids": source_ids,
        },
        {
            "key": "net_profit",
            "label": "归母净利润",
            "unit": "亿元",
            "points": [
                {"period": _period_label(period), "value": round(value / 1e8, 2)}
                for period, value in profit_values
            ],
            "source_ids": source_ids,
        },
    ]
    period_table = []
    profit_by_period = dict(profit_values)
    for period, revenue in revenue_values[-6:]:
        profit = profit_by_period.get(period)
        period_table.append(
            {
                "period": _period_label(period),
                "revenue": round(revenue / 1e8, 2),
                "net_profit": round(profit / 1e8, 2) if profit is not None else None,
                "net_margin": round(profit / revenue * 100, 2) if profit is not None and revenue else None,
            }
        )
    scenario_items = []
    if latest_revenue is not None and latest_profit is not None and latest_revenue:
        margin = latest_profit / latest_revenue
        for label, rate in (("压力", -0.10), ("基准", 0.0), ("增长", 0.10)):
            scenario_revenue = latest_revenue * (1 + rate)
            scenario_items.append(
                {
                    "scenario": label,
                    "revenue": round(scenario_revenue / 1e8, 2),
                    "net_profit": round(scenario_revenue * margin / 1e8, 2),
                    "assumption": f"营收较当前报告期{rate:+.0%}，净利率保持{margin:.2%}",
                }
            )
    sections = [
        {
            "key": "period_analysis",
            "title": "年度 / 季度财务分析",
            "kind": "table",
            "summary": "AkShare 报告期累计口径；同比计算仅使用上年同一报告期。",
            "items": period_table,
            "source_ids": source_ids,
        },
        {
            "key": "scenario_simulation",
            "title": "财务情景模拟",
            "kind": "scenario",
            "summary": "保持当前净利率不变的简化敏感性分析，不构成盈利预测。",
            "items": scenario_items,
            "source_ids": source_ids,
        },
        {
            "key": "announcement_timeline",
            "title": "财务公告时间线",
            "kind": "timeline",
            "summary": "展示已入库公告和财务事件。",
            "items": _timeline_items(events),
            "source_ids": [f"event-{index + 1}" for index in range(len(events))],
        },
    ]
    warnings = []
    if not abstract:
        warnings.append("未取得 AkShare 财务摘要，营收、利润和趋势暂不可计算。")
    if cash_elasticity is None:
        warnings.append("缺少经营现金流与净利润比率，现金流弹性暂不可计算。")
    if not events:
        warnings.append("尚无财务公告或风险事件，证据链仅包含结构化财务数据。")
    status = "complete" if abstract and revenue_values and profit_values else "partial"
    return {
        "summary": summary,
        "metrics": metrics,
        "series": series,
        "sections": sections,
        "sources": sources,
        "warnings": warnings,
        "status": status,
        "coverage": 90 if status == "complete" else 55,
        "retrieval_stage": "financial_data_first" if abstract else "knowledge_base_fallback",
    }


def _operations_analysis(company: Any, events: list[RiskEvent]) -> dict[str, Any]:
    profile, abstract, indicator = _akshare_context(company)
    inventory_days = _number(indicator.get("存货周转天数(天)"))
    receivable_days = _number(indicator.get("应收账款周转天数(天)"))
    inventory_turnover = _number(indicator.get("存货周转率(次)"))
    financial_source = ["akshare-financial"] if profile.get("status") == "available" else []
    sources = [_event_source(event, index) for index, event in enumerate(events)]
    if financial_source:
        sources.insert(
            0,
            {
                "id": "akshare-financial",
                "title": f"{company.name} 营运效率财务指标",
                "source_name": "AkShare（公开财务数据聚合）",
                "source_url": "https://www.cninfo.com.cn/new/index",
                "source_tag": "营运指标",
                "page_hint": "financial_indicators",
                "published_at": None,
                "severity": "",
                "sentiment": "",
            },
        )
    milestone_count = len(events)
    summary = (
        f"{company.name} 当前入库 {milestone_count} 条运营节点；"
        f"最新财务口径存货周转天数为{inventory_days:.1f}天。"
        if inventory_days is not None
        else f"{company.name} 当前入库 {milestone_count} 条运营节点，尚缺订单、交付与库存系统数据。"
    )
    metrics = [
        _metric("milestone_count", "运营节点", milestone_count, unit="条", source_ids=[f"event-{i + 1}" for i in range(len(events))]),
        _metric("inventory_days", "存货周转天数", f"{inventory_days:.1f}" if inventory_days is not None else None, unit="天", source_ids=financial_source),
        _metric("inventory_turnover", "存货周转率", f"{inventory_turnover:.2f}" if inventory_turnover is not None else None, unit="次", source_ids=financial_source),
        _metric("receivable_days", "应收账款周转天数", f"{receivable_days:.1f}" if receivable_days is not None else None, unit="天", source_ids=financial_source),
        _metric("order_fulfillment", "订单履约率", None, unit="%", description="需接入订单与交付系统"),
        _metric("ticket_closure", "风险工单闭环率", None, unit="%", description="需接入风险工单系统"),
    ]
    sections = [
        {
            "key": "operations_funnel",
            "title": "经营转化漏斗",
            "kind": "funnel",
            "summary": "未接入订单系统前仅展示数据准备状态，不填充演示数量。",
            "items": [
                {"label": "线索 / 订单", "value": "待接入"},
                {"label": "排产", "value": "待接入"},
                {"label": "交付", "value": "待接入"},
                {"label": "回款", "value": "待接入"},
            ],
            "source_ids": [],
        },
        {
            "key": "factory_milestones",
            "title": "工厂与运营节点",
            "kind": "timeline",
            "summary": "按已入库运营事件展示海外工厂、认证和交付相关节点。",
            "items": _timeline_items(events),
            "source_ids": [f"event-{index + 1}" for index in range(len(events))],
        },
        {
            "key": "peer_benchmark",
            "title": "同行对标与瓶颈定位",
            "kind": "comparison",
            "summary": "当前没有同口径同行数据，先列出本公司可验证的营运效率指标。",
            "items": [
                {"label": "存货周转天数", "company": inventory_days, "peer": None},
                {"label": "应收账款周转天数", "company": receivable_days, "peer": None},
            ],
            "source_ids": financial_source,
        },
    ]
    warnings = [
        "订单、排产、交付和回款数据尚未接入，经营漏斗不展示推测值。",
        "缺少同口径同行数据，暂不能形成真实行业排名。",
        "风险工单系统尚未接入，闭环率暂不可计算。",
    ]
    status = "partial" if events or indicator else "insufficient"
    return {
        "summary": summary,
        "metrics": metrics,
        "series": [],
        "sections": sections,
        "sources": sources,
        "warnings": warnings,
        "status": status,
        "coverage": 60 if status == "partial" else 20,
        "retrieval_stage": "risk_events_first" if events else "knowledge_base_fallback",
    }


def _event_analysis(company: Any, category: str, events: list[RiskEvent]) -> dict[str, Any]:
    total, high, negative_share = _event_metrics(events)
    sources = [_event_source(event, index) for index, event in enumerate(events)]
    source_ids = [f"event-{index + 1}" for index in range(len(events))]
    sentiment_counts = Counter(
        "负面" if event.sentiment in SENTIMENT_NEGATIVE else
        "正面" if event.sentiment in SENTIMENT_POSITIVE else "中性"
        for event in events
    )
    severity_counts = Counter("高优先级" if event.severity in SEVERITY_HIGH else "一般" for event in events)

    if category == "macro":
        summary = (
            f"{company.name} 宏观与行业维度命中 {total} 条可追溯事件，其中"
            f"高优先级 {high} 条、负面事件占比 {negative_share:.1f}%。"
        )
        metrics = [
            _metric("event_count", "宏观/行业事件", total, unit="条", source_ids=source_ids),
            _metric("high_priority", "高优先级事件", high, unit="条", tone="warning" if high else "neutral", source_ids=source_ids),
            _metric("negative_share", "负面事件占比", f"{negative_share:.1f}", unit="%", tone="warning" if negative_share >= 50 else "neutral", source_ids=source_ids),
            _metric("industry_market_size", "行业市场规模", None, description="需接入权威行业数据库或研报"),
        ]
        monthly = Counter(
            (event.occurred_at or event.created_at).strftime("%Y-%m") for event in events
        )
        series = [{
            "key": "macro_event_trend",
            "label": "宏观风险事件趋势",
            "unit": "条",
            "points": [{"period": period, "value": float(value)} for period, value in sorted(monthly.items())],
            "source_ids": source_ids,
        }]
        sections = [
            {"key": "macro_radar", "title": "宏观风险雷达", "kind": "distribution", "summary": "基于已入库事件的严重度与情绪分布，不代表整体行业景气指数。", "items": [{"label": label, "value": value} for label, value in severity_counts.items()] + [{"label": label, "value": value} for label, value in sentiment_counts.items()], "source_ids": source_ids},
            {"key": "policy_timeline", "title": "政策与行业事件时间线", "kind": "timeline", "summary": "政策、经济与行业事件的可追溯节点。", "items": _timeline_items(events), "source_ids": source_ids},
            {"key": "industry_insight", "title": "行业洞察与影响路径", "kind": "insight", "summary": "优先关注高优先级、负面事件对区域经营、成本和产能调度的影响。", "items": [{"title": event.title, "impact": event.content, "source_id": f"event-{index + 1}"} for index, event in enumerate(events[:5])], "source_ids": source_ids[:5]},
        ]
        warnings = ["行业市场规模、竞争份额和技术趋势数据尚未接入，当前雷达只反映事件样本。"]
    elif category == "legal":
        summary = (
            f"{company.name} 法律维度命中 {total} 条事件，其中高优先级 {high} 条；"
            "当前结论聚焦案件阶段和业务传导，涉案金额缺失时不作估算。"
        )
        metrics = [
            _metric("case_count", "法律/监管事件", total, unit="条", source_ids=source_ids),
            _metric("high_priority", "高优先级", high, unit="条", tone="warning" if high else "neutral", source_ids=source_ids),
            _metric("negative_share", "负面事件占比", f"{negative_share:.1f}", unit="%", tone="warning" if negative_share else "neutral", source_ids=source_ids),
            _metric("exposure_amount", "已披露涉案金额", None, unit="万元", description="当前事件未提供可汇总金额"),
        ]
        series = []
        sections = [
            {"key": "legal_timeline", "title": "法律事件时间轴", "kind": "timeline", "summary": "按发生时间展示诉讼、调查、处罚和合规事件。", "items": _timeline_items(events), "source_ids": source_ids},
            {"key": "risk_summary", "title": "风险分级汇总", "kind": "distribution", "summary": "按事件严重度统计。", "items": [{"label": label, "value": value} for label, value in severity_counts.items()], "source_ids": source_ids},
            {"key": "risk_transmission", "title": "风险传导与联动建议", "kind": "recommendation", "summary": "从法律事件向经营、财务和品牌维度映射潜在影响。", "items": [{"title": event.title, "path": "法律/监管 → 产品或区域经营 → 成本与交付 → 品牌舆情", "action": "核验案件阶段、影响区域和可执行处置动作", "source_id": f"event-{index + 1}"} for index, event in enumerate(events[:5])], "source_ids": source_ids[:5]},
        ]
        warnings = ["案件编号、阶段、涉案金额和裁判文书结构化字段尚不完整。"]
    else:
        summary = (
            f"{company.name} 品牌舆情维度命中 {total} 条事件，"
            f"负面占比 {negative_share:.1f}%；该占比仅代表当前入库样本。"
        )
        positive = sentiment_counts.get("正面", 0)
        neutral = sentiment_counts.get("中性", 0)
        negative = sentiment_counts.get("负面", 0)
        denominator = total or 1
        positive_share = round(positive / denominator * 100, 1)
        neutral_share = round(neutral / denominator * 100, 1)
        sentiment_items = [
            {"label": "正面", "value": positive_share},
            {"label": "中性", "value": neutral_share},
            {"label": "负面", "value": round(100 - positive_share - neutral_share, 1)},
        ]
        source_counts = Counter(event.source_name or "未知来源" for event in events)
        metrics = [
            _metric("mention_count", "舆情样本", total, unit="条", source_ids=source_ids),
            _metric("positive_share", "正面占比", f"{positive / denominator * 100:.1f}", unit="%", tone="positive", source_ids=source_ids),
            _metric("negative_share", "负面占比", f"{negative_share:.1f}", unit="%", tone="warning" if negative else "neutral", source_ids=source_ids),
            _metric("source_count", "覆盖来源", len(source_counts), unit="个", source_ids=source_ids),
        ]
        series = []
        sections = [
            {"key": "sentiment_distribution", "title": "舆情情绪分布", "kind": "distribution", "summary": "根据 risk_events.sentiment 标签计算。", "items": sentiment_items, "source_ids": source_ids},
            {"key": "source_distribution", "title": "媒体与平台分布", "kind": "distribution", "summary": "按当前入库来源统计，后续可扩展媒体/KOL 权重。", "items": [{"label": label, "value": value} for label, value in source_counts.most_common()], "source_ids": source_ids},
            {"key": "topic_heat", "title": "议题热度与事件时间线", "kind": "timeline", "summary": "以当前事件标题作为议题，不伪造外部平台阅读量。", "items": _timeline_items(events), "source_ids": source_ids},
            {"key": "handling_advice", "title": "舆情处置建议", "kind": "recommendation", "summary": "优先处置高优先级负面事件，并持续校验信息源。", "items": [{"title": event.title, "action": "核实原始来源、评估扩散范围并制定回应口径", "source_id": f"event-{index + 1}"} for index, event in enumerate(events) if event.sentiment in SENTIMENT_NEGATIVE], "source_ids": source_ids},
        ]
        warnings = ["当前样本量较小，尚未接入全量新闻、社交平台与行业自媒体实时流。"]

    status = "partial" if events else "insufficient"
    if not events:
        warnings.append("该维度暂无结构化事件，需要回退知识库或外部数据源补充证据。")
    return {
        "summary": summary,
        "metrics": metrics,
        "series": series,
        "sections": sections,
        "sources": sources,
        "warnings": warnings,
        "status": status,
        "coverage": min(80, 25 + total * 10) if events else 10,
        "retrieval_stage": "risk_events_first" if events else "knowledge_base_fallback",
    }


def fetch_agent_risk_events(
    db: Session,
    *,
    company_id=None,
    company_name: str | None = None,
    category: str,
    limit: int = 12,
):
    company = get_company_by_ref(db, company_id=company_id, company_name=company_name)
    if not company:
        raise ValueError("未找到目标公司，请先创建 companies 记录。")

    statement = (
        select(RiskEvent)
        .where(RiskEvent.company_id == company.id)
        .where(RiskEvent.category == category)
        .order_by(RiskEvent.occurred_at.desc().nullslast(), RiskEvent.created_at.desc())
        .limit(limit)
    )
    return company, list(db.execute(statement).scalars())


def build_agent_preview(
    *,
    company: Any | None = None,
    company_name: str | None = None,
    category: str,
    risk_events: list[RiskEvent],
) -> dict[str, Any]:
    if company is None:
        company = type(
            "CompanySnapshot",
            (),
            {"name": company_name or "目标公司", "company_profile": {}, "industry": ""},
        )()
    label = CATEGORY_LABELS.get(category, category)
    if category == "finance":
        analysis = _finance_analysis(company, risk_events)
    elif category == "operations":
        analysis = _operations_analysis(company, risk_events)
    else:
        analysis = _event_analysis(company, category, risk_events)

    key_points = [
        f"{event.title}：{event.content}" for event in risk_events[:3]
    ]
    if not key_points:
        key_points = [
            f"{label}当前证据覆盖不足，页面已保留数据缺口而非填充演示结论。",
            "需要通过知识库、公告或业务系统补充原始证据后再形成正式判断。",
        ]
    updated_at = None
    profile = (company.company_profile or {}).get("akshare_profile") or {}
    profile_updated_at = profile.get("updated_at")
    if isinstance(profile_updated_at, str):
        try:
            updated_at = datetime.fromisoformat(profile_updated_at.replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    if updated_at is None and risk_events:
        updated_at = risk_events[0].occurred_at or risk_events[0].created_at

    return {
        "company_name": company.name,
        "category": category,
        "report_type": REPORT_TYPES.get(category, f"{category}_report"),
        "retrieval_stage": analysis["retrieval_stage"],
        "summary": analysis["summary"],
        "key_points": key_points,
        "next_actions": DEFAULT_NEXT_ACTIONS.get(category, []),
        "sources": [
            {key: value for key, value in source.items() if key != "id"}
            for source in analysis["sources"]
        ],
        "metrics": analysis["metrics"],
        "series": analysis["series"],
        "sections": analysis["sections"],
        "data_quality": {
            "status": analysis["status"],
            "coverage_percent": analysis["coverage"],
            "evidence_count": len(analysis["sources"]),
            "warnings": analysis["warnings"],
            "updated_at": updated_at,
        },
        "generated_at": datetime.now(timezone.utc),
    }


def compose_comprehensive_report(
    db: Session,
    *,
    company_id,
    report_types: list[str],
    title: str = "",
) -> AnalysisReport:
    reports: list[AnalysisReport] = []
    for report_type in report_types:
        statement = (
            select(AnalysisReport)
            .where(AnalysisReport.company_id == company_id)
            .where(AnalysisReport.report_type == report_type)
            .order_by(AnalysisReport.generated_at.desc())
            .limit(1)
        )
        report = db.execute(statement).scalar_one_or_none()
        if report:
            reports.append(report)

    if not reports:
        raise ValueError("没有找到可组装的单项报告。")

    company_name = reports[0].company.name if reports[0].company else "目标公司"
    summary = (
        f"本次综合风险报告整合了 {len(reports)} 个维度的最新分析快照，"
        "适用于生成管理层汇总版或自定义风险周报。"
    )
    snapshot = {
        "assembly_mode": "latest_by_report_type",
        "source_report_types": report_types,
        "assembled_reports": [
            {
                "report_type": report.report_type,
                "title": report.title,
                "summary": report.summary,
                "generated_at": report.generated_at.isoformat(),
                "snapshot": report.snapshot,
            }
            for report in reports
        ],
    }
    composed = AnalysisReport(
        company_id=company_id,
        report_type="comprehensive_risk_report",
        title=title or f"{company_name} 综合风险报告",
        summary=summary,
        snapshot=snapshot,
        model_name="d-trust-agent",
    )
    db.add(composed)
    db.commit()
    db.refresh(composed)
    return composed
