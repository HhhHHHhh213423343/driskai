from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


OUTPUT_COLUMNS = [
    "序号",
    "监测日期",
    "事件发生日期",
    "主体名称",
    "当前持股比例",
    "关联实体",
    "关联关系",
    "标题及主要内容",
    "分类",
    "执行标的金额",
    "重要性",
    "正负面",
    "来源",
]


BASE_EVENT_COLUMNS = [
    "事件发生日期",
    "标题及主要内容",
    "分类",
    "执行标的金额",
    "重要性",
    "正负面",
    "来源",
]


LISTEN_KEYWORDS = (
    "news/list",
    "risk",
    "warning",
    "opinion",
    "monitor",
    "dynamic",
)


LIKELY_LIST_KEYS = {
    "list",
    "rows",
    "items",
    "records",
    "result",
    "data",
    "newslist",
    "risklist",
    "datalist",
}


LIKELY_RECORD_KEYS = {
    "title",
    "name",
    "news_title",
    "event_title",
    "content",
    "main_content",
    "publish_time",
    "publishdate",
    "pubtime",
    "date",
    "category",
    "category_name",
    "risk_type",
    "sentiment_type",
    "sentiment",
    "emotion",
    "source",
    "source_name",
    "media",
    "amount",
    "exec_money",
    "execution_amount",
}


DATE_FIELDS = (
    "publish_time",
    "publishTime",
    "publish_date",
    "publishDate",
    "pub_time",
    "pubTime",
    "date",
    "event_time",
    "eventTime",
    "create_time",
    "createTime",
    "notice_date",
    "noticeDate",
    "time",
)


TITLE_FIELDS = (
    "title",
    "name",
    "news_title",
    "newsTitle",
    "event_title",
    "eventTitle",
    "case_title",
    "caseTitle",
)


CONTENT_FIELDS = (
    "content",
    "main_content",
    "mainContent",
    "summary",
    "brief",
    "abstract",
    "desc",
    "description",
    "event_content",
    "eventContent",
    "news_content",
    "newsContent",
)


CATEGORY_FIELDS = (
    "category",
    "category_name",
    "categoryName",
    "news_type",
    "newsType",
    "risk_type",
    "riskType",
    "label",
    "tag",
)


IMPORTANCE_FIELDS = (
    "importance",
    "important",
    "is_important",
    "isImportant",
    "level",
    "risk_level",
    "riskLevel",
    "alert_level",
    "alertLevel",
)


SENTIMENT_FIELDS = (
    "sentiment_type",
    "sentimentType",
    "sentiment",
    "polarity",
    "emotion",
    "tone",
    "orientation",
)


SOURCE_FIELDS = (
    "source",
    "source_name",
    "sourceName",
    "media",
    "media_name",
    "publisher",
    "website",
)


AMOUNT_FIELDS = (
    "exec_money",
    "execMoney",
    "execution_amount",
    "executionAmount",
    "target_amount",
    "targetAmount",
    "amount",
    "money",
)


IMPORTANCE_MAP = {
    "1": "重要",
    "2": "重要",
    "3": "重要",
    "4": "重要",
    "5": "重要",
    "high": "重要",
    "medium": "重要",
    "important": "重要",
    "major": "重要",
    "critical": "重要",
    "严重": "重要",
    "高": "重要",
    "高风险": "重要",
    "重要": "重要",
    "一般": "一般",
    "普通": "一般",
    "low": "一般",
    "normal": "一般",
    "minor": "一般",
    "info": "一般",
    "0": "一般",
}


SENTIMENT_MAP = {
    "positive": "正面",
    "neutral": "中性",
    "negative": "负面",
    "pos": "正面",
    "neu": "中性",
    "neg": "负面",
    "1": "正面",
    "0": "中性",
    "-1": "负面",
    "正面": "正面",
    "中性": "中性",
    "负面": "负面",
    "利好": "正面",
    "一般": "中性",
    "利空": "负面",
}


COLOR_SENTIMENT_MAP = {
    "green": "正面",
    "blue": "中性",
    "gray": "中性",
    "grey": "中性",
    "orange": "负面",
    "yellow": "负面",
    "red": "负面",
}


@dataclass(frozen=True)
class PlatformProfile:
    """站点配置。"""

    code: str
    display_name: str
    home_url: str
    search_url_template: str | None
    search_input_candidates: tuple[str, ...]
    search_button_candidates: tuple[str, ...]
    result_link_candidates: tuple[str, ...]
    risk_tab_texts: tuple[str, ...]
    next_page_candidates: tuple[str, ...]


PLATFORM_PROFILES = {
    "qyyjt": PlatformProfile(
        code="qyyjt",
        display_name="企业预警通",
        home_url="https://www.qyyjt.cn/",
        search_url_template=None,
        search_input_candidates=(
            'x://input[contains(@placeholder, "企业")]',
            'x://input[contains(@placeholder, "公司")]',
            'x://input[@type="search"]',
        ),
        search_button_candidates=(
            'x://button[contains(., "搜索")]',
            'x://span[contains(., "搜索")]',
        ),
        result_link_candidates=(
            'x://a[contains(., "{company}")]',
            'x://span[contains(., "{company}")]',
        ),
        risk_tab_texts=("风险", "舆情", "动态", "预警"),
        next_page_candidates=(
            'x://button[contains(., "下一页")]',
            'x://li[contains(@class, "next")]',
            'x://a[contains(., "下一页")]',
        ),
    ),
    "tianyancha": PlatformProfile(
        code="tianyancha",
        display_name="天眼查",
        home_url="https://www.tianyancha.com/",
        search_url_template="https://www.tianyancha.com/search?key={query}",
        search_input_candidates=(
            'x://input[contains(@placeholder, "请输入公司名称")]',
            'x://input[contains(@placeholder, "公司名称")]',
            'x://input[@type="search"]',
        ),
        search_button_candidates=(
            'x://button[contains(., "天眼一下")]',
            'x://div[contains(., "天眼一下")]',
        ),
        result_link_candidates=(
            'x://a[contains(., "{company}")]',
            'x://span[contains(., "{company}")]',
        ),
        risk_tab_texts=("风险", "舆情", "司法风险", "经营风险"),
        next_page_candidates=(
            'x://button[contains(., "下一页")]',
            'x://li[contains(@class, "next")]',
            'x://a[contains(., "下一页")]',
        ),
    ),
}


DEFAULT_TARGET_FILE = Path("target_list.txt")
