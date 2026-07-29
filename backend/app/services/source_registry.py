from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class SourceSpec:
    code: str
    name: str
    url: str
    authority: str = "official"
    authority_score: int = 100
    categories: tuple[str, ...] = ("finance", "operations", "legal", "brand")
    access_mode: str = "listing"
    frequency: str = "daily"
    query_terms: tuple[str, ...] = ()
    requires_original_verification: bool = True
    notes: str = ""


@dataclass(frozen=True)
class IndustryPlugin:
    code: str
    name: str
    keywords: tuple[str, ...]
    sources: tuple[SourceSpec, ...] = field(default_factory=tuple)
    metric_keys: tuple[str, ...] = field(default_factory=tuple)


UNIVERSAL_SOURCES = (
    SourceSpec(
        "company_official_site",
        "企业官网/投资者关系",
        "",
        categories=("finance", "operations", "legal", "brand"),
        access_mode="company_site",
        query_terms=("公告", "新闻", "投资者关系", "年报", "重大事项"),
    ),
    SourceSpec(
        "cninfo_announcements",
        "巨潮资讯",
        "https://www.cninfo.com.cn/new/index",
        categories=("finance", "operations", "legal"),
        query_terms=("年度报告", "季度报告", "业绩", "诉讼", "处罚", "问询"),
    ),
    SourceSpec(
        "exchange_disclosure",
        "上海证券交易所监管措施",
        "https://www.sse.com.cn/regulation/supervision/measures/",
        categories=("finance", "legal"),
        query_terms=("监管工作函", "监管警示", "通报批评", "公开谴责"),
    ),
    SourceSpec(
        "szse_disclosure",
        "深圳证券交易所监管信息",
        "https://www.szse.cn/disclosure/supervision/measure/index.html",
        categories=("finance", "legal"),
        query_terms=("监管函", "纪律处分", "问询函"),
    ),
    SourceSpec(
        "hkex_disclosure",
        "香港交易所披露易",
        "https://www.hkexnews.hk/index_c.htm",
        categories=("finance", "operations", "legal"),
        query_terms=("年度报告", "中期报告", "公告", "监管"),
    ),
    SourceSpec(
        "bse_disclosure",
        "北京证券交易所监管信息",
        "https://www.bse.cn/disclosure/announcement.html",
        categories=("finance", "operations", "legal"),
        query_terms=("公告", "问询函", "监管措施", "纪律处分"),
    ),
    SourceSpec(
        "csrc_enforcement",
        "中国证券监督管理委员会",
        "https://www.csrc.gov.cn/",
        categories=("finance", "legal"),
        query_terms=("行政处罚", "市场禁入", "监管措施", "立案调查"),
    ),
    SourceSpec(
        "enterprise_credit",
        "国家企业信用信息公示系统",
        "https://www.gsxt.gov.cn/",
        categories=("legal",),
        access_mode="manual_authorized",
        query_terms=("行政处罚", "经营异常", "严重违法失信"),
        notes="存在验证码和访问限制，只允许授权查询或人工原文核验。",
    ),
    SourceSpec(
        "credit_china",
        "信用中国",
        "https://www.creditchina.gov.cn/",
        categories=("legal",),
        access_mode="manual_authorized",
        query_terms=("行政许可", "行政处罚", "失信"),
        notes="优先使用公开查询或授权接口。",
    ),
    SourceSpec(
        "judicial_disclosure",
        "中国裁判文书网",
        "https://wenshu.court.gov.cn/",
        categories=("legal",),
        access_mode="manual_authorized",
        query_terms=("判决", "裁定", "案号", "案由"),
        notes="不绕过登录、验证码或访问频率限制。",
    ),
    SourceSpec(
        "execution_disclosure",
        "中国执行信息公开网",
        "https://zxgk.court.gov.cn/",
        categories=("legal",),
        access_mode="manual_authorized",
        query_terms=("被执行人", "失信被执行人", "限制消费", "终本案件"),
    ),
    SourceSpec(
        "bankruptcy_disclosure",
        "全国企业破产重整案件信息网",
        "https://pccz.court.gov.cn/pcajxxw/index/xxwsy",
        categories=("legal", "finance"),
        access_mode="manual_authorized",
        query_terms=("破产", "重整", "清算", "债权人会议"),
    ),
    SourceSpec(
        "samr_complaints",
        "全国12315消费投诉信息",
        "https://www.12315.cn/",
        categories=("brand", "operations", "legal"),
        access_mode="manual_authorized",
        authority_score=95,
        query_terms=("投诉", "举报", "售后服务", "合同", "质量"),
    ),
    SourceSpec(
        "authoritative_web_search",
        "持证新闻机构与权威媒体检索",
        "",
        authority="licensed",
        authority_score=75,
        categories=("operations", "legal", "brand"),
        access_mode="search_api",
        query_terms=("经营", "处罚", "投诉", "舆情", "回应"),
        notes="仅用于发现线索，结论需回到官方原文。",
    ),
)


BANKING_SOURCES = (
    SourceSpec(
        "nfra_penalties",
        "国家金融监督管理总局行政处罚",
        "https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=4113&itemName=%E6%80%BB%E5%B1%80%E6%9C%BA%E5%85%B3&itemPId=923&itemUrl=ItemListRightList.html&itemsubPId=931",
        categories=("legal", "operations", "brand"),
        query_terms=("行政处罚", "罚款", "监管措施", "整改"),
    ),
    SourceSpec(
        "nfra_statistics",
        "国家金融监督管理总局监管指标",
        "https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=954",
        categories=("finance", "operations"),
        query_terms=("商业银行主要监管指标", "不良贷款率", "拨备覆盖率", "资本充足率", "流动性"),
    ),
    SourceSpec(
        "nfra_branches",
        "金融监管总局地方派出机构",
        "https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=928",
        categories=("legal", "operations", "brand"),
        query_terms=("行政处罚", "监管措施", "许可证", "风险提示"),
        notes="地方处罚往往先由派出机构发布，应与总局同步检查。",
    ),
    SourceSpec(
        "pbc_statistics",
        "中国人民银行统计数据",
        "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html",
        categories=("finance", "operations"),
        query_terms=("社会融资规模", "货币统计", "金融机构贷款", "利率", "LPR"),
    ),
    SourceSpec(
        "pbc_penalties",
        "中国人民银行行政执法与处罚",
        "https://www.pbc.gov.cn/",
        categories=("legal", "operations", "brand"),
        query_terms=("行政处罚", "反洗钱", "征信", "支付结算", "金融消费者权益"),
    ),
    SourceSpec(
        "pbc_branches",
        "中国人民银行分支机构",
        "https://www.pbc.gov.cn/rmyh/105208/index.html",
        categories=("legal", "operations", "brand"),
        query_terms=("行政处罚", "金融消费权益", "支付", "征信"),
    ),
    SourceSpec(
        "interbank_market",
        "中国货币网",
        "https://www.chinamoney.com.cn/chinese/",
        categories=("finance",),
        authority_score=95,
        query_terms=("同业存单", "金融债", "二级资本债", "无固定期限资本债券"),
    ),
    SourceSpec(
        "china_bond",
        "中国债券信息网",
        "https://www.chinabond.com.cn/",
        categories=("finance",),
        authority_score=95,
        query_terms=("债券发行", "信用评级", "付息", "赎回"),
    ),
    SourceSpec(
        "nbs_macro",
        "国家统计局国家数据",
        "https://data.stats.gov.cn/",
        categories=("finance", "operations"),
        query_terms=("GDP", "CPI", "PPI", "PMI", "固定资产投资"),
        frequency="daily_check_monthly_release",
    ),
    SourceSpec(
        "banking_association",
        "中国银行业协会",
        "https://www.china-cba.net/",
        authority="association",
        authority_score=90,
        categories=("operations", "legal", "brand"),
        query_terms=("自律规范", "风险提示", "消费者权益保护", "行业报告"),
        notes="全国性银行业自律组织，用于行业自律信息和交叉验证，不替代监管原文。",
    ),
)


INDUSTRY_PLUGINS = (
    IndustryPlugin(
        "banking",
        "银行业",
        ("银行", "商业银行", "货币金融"),
        BANKING_SOURCES,
        (
            "net_interest_margin", "npl_ratio", "provision_coverage", "cet1_ratio",
            "capital_adequacy", "liquidity_coverage", "cost_income_ratio",
            "loan_growth", "deposit_growth", "complaint_resolution", "system_availability",
        ),
    ),
    IndustryPlugin(
        "automotive",
        "汽车行业",
        ("汽车", "整车", "新能源汽车", "零部件"),
        (
            SourceSpec("miit_auto", "工业和信息化部汽车公告", "https://www.miit.gov.cn/", categories=("operations", "legal"), query_terms=("道路机动车辆生产企业及产品", "新能源汽车")),
            SourceSpec("samr_recall", "市场监管总局缺陷产品召回", "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/zlfzs/", categories=("operations", "legal", "brand"), query_terms=("汽车召回", "缺陷")),
            SourceSpec("mee_auto", "生态环境部机动车环保信息", "https://www.mee.gov.cn/", categories=("operations", "legal"), query_terms=("机动车环保", "排放")),
        ),
        ("sales", "production", "inventory_days", "recall_count", "new_energy_share"),
    ),
    IndustryPlugin(
        "manufacturing",
        "制造业",
        ("制造", "设备", "电子", "化工", "材料", "机械"),
        (
            SourceSpec("miit_industry", "工业和信息化部行业运行", "https://www.miit.gov.cn/gxsj/tjfx/", categories=("operations", "finance"), query_terms=("行业运行", "产量", "收入", "利润")),
            SourceSpec("customs_trade", "海关总署统计", "https://www.customs.gov.cn/", categories=("operations", "finance"), query_terms=("进出口", "贸易统计")),
            SourceSpec("mee_penalties", "生态环境部", "https://www.mee.gov.cn/", categories=("legal", "operations"), query_terms=("行政处罚", "环境违法", "排放")),
            SourceSpec("mem_safety", "应急管理部", "https://www.mem.gov.cn/", categories=("legal", "operations", "brand"), query_terms=("生产安全事故", "行政处罚")),
        ),
        ("revenue_growth", "inventory_days", "inventory_turnover", "receivable_days", "capacity_utilization"),
    ),
    IndustryPlugin(
        "pharma",
        "医药行业",
        ("医药", "制药", "生物", "医疗器械", "疫苗"),
        (
            SourceSpec("nmpa", "国家药品监督管理局", "https://www.nmpa.gov.cn/", categories=("operations", "legal", "brand"), query_terms=("药品注册", "医疗器械", "召回", "飞行检查", "行政处罚")),
            SourceSpec("cde", "国家药监局药品审评中心", "https://www.cde.org.cn/", categories=("operations",), query_terms=("受理", "审评", "批准")),
            SourceSpec("nhsa", "国家医疗保障局", "https://www.nhsa.gov.cn/", categories=("finance", "operations", "legal"), query_terms=("医保目录", "集采", "价格", "信用评价")),
        ),
        ("pipeline_count", "approval_count", "recall_count", "medical_insurance_exposure"),
    ),
    IndustryPlugin(
        "real_estate",
        "房地产行业",
        ("房地产", "地产", "物业", "建筑"),
        (
            SourceSpec("mohurd", "住房和城乡建设部", "https://www.mohurd.gov.cn/", categories=("operations", "legal"), query_terms=("房地产", "建筑市场", "资质", "处罚")),
            SourceSpec("mnr_land", "自然资源部", "https://www.mnr.gov.cn/", categories=("operations", "legal"), query_terms=("土地", "闲置土地", "自然资源处罚")),
        ),
        ("contracted_sales", "land_reserve", "completion", "cash_collection", "debt_maturity"),
    ),
    IndustryPlugin(
        "internet",
        "互联网与软件",
        ("互联网", "软件", "信息技术", "平台", "云计算"),
        (
            SourceSpec("miit_internet", "工业和信息化部", "https://www.miit.gov.cn/", categories=("operations", "legal"), query_terms=("软件业运行", "互联网业务", "电信业务许可")),
            SourceSpec("cac", "国家互联网信息办公室", "https://www.cac.gov.cn/", categories=("legal", "brand", "operations"), query_terms=("行政执法", "网络安全", "数据安全", "算法备案")),
        ),
        ("monthly_active_users", "paying_users", "service_availability", "data_security_events"),
    ),
    IndustryPlugin(
        "energy",
        "能源行业",
        ("能源", "电力", "煤炭", "石油", "天然气", "新能源"),
        (
            SourceSpec("nea", "国家能源局", "https://www.nea.gov.cn/", categories=("operations", "legal"), query_terms=("能源统计", "电力安全", "行政处罚")),
            SourceSpec("mee_energy", "生态环境部", "https://www.mee.gov.cn/", categories=("operations", "legal", "brand"), query_terms=("碳排放", "环境处罚", "环评")),
        ),
        ("output", "utilization_hours", "installed_capacity", "energy_price", "emissions"),
    ),
)


GENERAL_PLUGIN = IndustryPlugin("general", "通用行业", (), (), ())


def detect_industry_plugin(industry: str, name: str = "", profile: dict[str, Any] | None = None) -> IndustryPlugin:
    profile = profile or {}
    text_value = " ".join(
        [
            industry or "",
            name or "",
            str(profile.get("industry") or ""),
            str(profile.get("行业") or ""),
        ]
    )
    matches: list[tuple[int, int, IndustryPlugin]] = []
    for plugin in INDUSTRY_PLUGINS:
        matched_keywords = [
            keyword for keyword in plugin.keywords if keyword in text_value
        ]
        if matched_keywords:
            matches.append(
                (
                    len(matched_keywords),
                    max(len(keyword) for keyword in matched_keywords),
                    plugin,
                )
            )
    if not matches:
        return GENERAL_PLUGIN
    return max(matches, key=lambda item: (item[0], item[1]))[2]


def source_plan_for(
    industry: str,
    name: str = "",
    profile: dict[str, Any] | None = None,
) -> tuple[IndustryPlugin, tuple[SourceSpec, ...]]:
    plugin = detect_industry_plugin(industry, name, profile)
    combined: dict[str, SourceSpec] = {
        source.code: source for source in plugin.sources
    }
    for source in UNIVERSAL_SOURCES:
        combined.setdefault(source.code, source)
    return plugin, tuple(combined.values())


def source_to_dict(source: SourceSpec) -> dict[str, Any]:
    return {
        "code": source.code,
        "name": source.name,
        "url": source.url,
        "authority": source.authority,
        "authority_score": source.authority_score,
        "categories": list(source.categories),
        "access_mode": source.access_mode,
        "frequency": source.frequency,
        "query_terms": list(source.query_terms),
        "requires_original_verification": source.requires_original_verification,
        "notes": source.notes,
    }


def domains_for(sources: Iterable[SourceSpec]) -> set[str]:
    from urllib.parse import urlparse

    domains = set()
    for source in sources:
        host = (urlparse(source.url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return domains
