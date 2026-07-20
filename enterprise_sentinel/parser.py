from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

import pandas as pd

from enterprise_sentinel.config import (
    AMOUNT_FIELDS,
    BASE_EVENT_COLUMNS,
    CATEGORY_FIELDS,
    CONTENT_FIELDS,
    COLOR_SENTIMENT_MAP,
    DATE_FIELDS,
    IMPORTANCE_FIELDS,
    IMPORTANCE_MAP,
    LIKELY_LIST_KEYS,
    LIKELY_RECORD_KEYS,
    SENTIMENT_FIELDS,
    SENTIMENT_MAP,
    SOURCE_FIELDS,
    TITLE_FIELDS,
)


class RiskDataParser:
    """负责把监听到的原始 JSON 包转换成标准报表结构。"""

    def parse_packets(self, packets: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
        normalized_rows: list[dict[str, str]] = []
        for packet in packets:
            body = packet.get("body")
            for raw_record in self._extract_records(body):
                row = self._normalize_record(raw_record)
                if row["标题及主要内容"]:
                    normalized_rows.append(row)
        return self._deduplicate(normalized_rows)

    def to_dataframe(self, rows: list[dict[str, str]]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=BASE_EVENT_COLUMNS)
        frame = pd.DataFrame(rows)
        frame = frame.reindex(columns=BASE_EVENT_COLUMNS)
        frame.sort_values(by=["事件发生日期", "标题及主要内容"], ascending=[False, True], inplace=True, kind="stable")
        frame.reset_index(drop=True, inplace=True)
        return frame

    def _extract_records(self, body: Any) -> list[dict[str, Any]]:
        parsed = self._ensure_json(body)
        records: list[dict[str, Any]] = []
        self._walk_node(parsed, records)
        return records

    def _walk_node(self, node: Any, records: list[dict[str, Any]]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, list):
                    normalized_key = str(key).lower()
                    if normalized_key in LIKELY_LIST_KEYS or self._looks_like_record_list(value):
                        records.extend([item for item in value if isinstance(item, dict)])
                    for item in value:
                        self._walk_node(item, records)
                elif isinstance(value, dict):
                    self._walk_node(value, records)
        elif isinstance(node, list):
            if self._looks_like_record_list(node):
                records.extend([item for item in node if isinstance(item, dict)])
            for item in node:
                self._walk_node(item, records)

    def _looks_like_record_list(self, items: list[Any]) -> bool:
        dict_items = [item for item in items if isinstance(item, dict)]
        if not dict_items:
            return False
        score = 0
        for item in dict_items[:5]:
            keys = {str(key).lower() for key in item.keys()}
            if keys & {key.lower() for key in LIKELY_RECORD_KEYS}:
                score += 1
        return score >= 1

    def _normalize_record(self, raw: dict[str, Any]) -> dict[str, str]:
        return {
            "事件发生日期": self._format_date(self._pick_first(raw, DATE_FIELDS)),
            "标题及主要内容": self._build_title_and_content(raw),
            "分类": self._clean_text(self._pick_first(raw, CATEGORY_FIELDS)) or "未分类",
            "重要性": self._map_importance(raw),
            "正负面": self._map_sentiment(raw),
            "来源": self._clean_text(self._pick_first(raw, SOURCE_FIELDS)) or "未知来源",
            "执行标的金额": self._format_amount(self._pick_first(raw, AMOUNT_FIELDS)),
        }

    def _build_title_and_content(self, raw: dict[str, Any]) -> str:
        title = self._clean_text(self._pick_first(raw, TITLE_FIELDS))
        content = self._clean_text(self._pick_first(raw, CONTENT_FIELDS))
        if title and content and content not in title:
            return f"{title} {content}"
        return title or content

    def _pick_first(self, raw: dict[str, Any], candidates: tuple[str, ...]) -> Any:
        for field in candidates:
            if field in raw and raw[field] not in (None, "", [], {}):
                return raw[field]
        lower_key_map = {str(key).lower(): key for key in raw.keys()}
        for field in candidates:
            if field.lower() in lower_key_map:
                key = lower_key_map[field.lower()]
                value = raw.get(key)
                if value not in (None, "", [], {}):
                    return value
        return ""

    def _map_importance(self, raw: dict[str, Any]) -> str:
        for field in IMPORTANCE_FIELDS:
            value = self._pick_first(raw, (field,))
            mapped = self._convert_with_map(value, IMPORTANCE_MAP)
            if mapped:
                return mapped
        title = self._clean_text(self._pick_first(raw, TITLE_FIELDS))
        if any(keyword in title for keyword in ("被执行", "失信", "强制执行", "限制高消费", "行政处罚", "立案")):
            return "重要"
        return "一般"

    def _map_sentiment(self, raw: dict[str, Any]) -> str:
        for field in SENTIMENT_FIELDS:
            value = self._pick_first(raw, (field,))
            mapped = self._convert_with_map(value, SENTIMENT_MAP)
            if mapped:
                return mapped

        color_hint = self._collect_color_hint(raw)
        if color_hint:
            return color_hint

        title = self._clean_text(self._pick_first(raw, TITLE_FIELDS))
        negative_keywords = ("被执行", "失信", "处罚", "冻结", "终本", "欠税", "违法", "立案", "风险")
        positive_keywords = ("中标", "融资", "合作", "获批", "增长", "签约")
        if any(keyword in title for keyword in negative_keywords):
            return "负面"
        if any(keyword in title for keyword in positive_keywords):
            return "正面"
        return "中性"

    def _collect_color_hint(self, raw: dict[str, Any]) -> str:
        for value in raw.values():
            if isinstance(value, str):
                lower_value = value.lower()
                for color_key, sentiment in COLOR_SENTIMENT_MAP.items():
                    if color_key in lower_value:
                        return sentiment
        return ""

    def _convert_with_map(self, value: Any, mapping: dict[str, str]) -> str:
        if value in (None, ""):
            return ""

        normalized = self._clean_text(value).lower()
        if normalized in mapping:
            return mapping[normalized]

        if normalized in {"true", "yes"} and mapping is IMPORTANCE_MAP:
            return "重要"
        if normalized in {"false", "no"} and mapping is IMPORTANCE_MAP:
            return "一般"
        return ""

    def _format_date(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            date_value = pd.to_datetime(value)
            if pd.isna(date_value):
                return ""
            return date_value.strftime("%Y-%m-%d")
        except Exception:
            text = self._clean_text(value)
            match = re.search(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}", text)
            if match:
                normalized = (
                    match.group(0)
                    .replace("年", "-")
                    .replace("月", "-")
                    .replace("日", "")
                    .replace("/", "-")
                    .replace(".", "-")
                )
                try:
                    return pd.to_datetime(normalized).strftime("%Y-%m-%d")
                except Exception:
                    return normalized
            return text

    def _format_amount(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, (int, float)):
            return f"{value:,.2f}".rstrip("0").rstrip(".")
        text = self._clean_text(value)
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return f"{float(text):,.2f}".rstrip("0").rstrip(".")
        return text

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        text = str(value).replace("\u3000", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _ensure_json(self, body: Any) -> Any:
        if isinstance(body, (dict, list)):
            return body
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw_text": body}
        return {}

    def _deduplicate(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        deduplicated: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            fingerprint = (row["事件发生日期"], row["标题及主要内容"], row["来源"])
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            deduplicated.append(row)
        return deduplicated
