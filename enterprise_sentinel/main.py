from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from enterprise_sentinel.config import DEFAULT_TARGET_FILE, OUTPUT_COLUMNS
from enterprise_sentinel.engine import BrowserConfig, CrawlerEngine, PacketCaptureError
from enterprise_sentinel.excel_writer import ExcelReportWriter
from enterprise_sentinel.parser import RiskDataParser
from enterprise_sentinel.profile_manager import cleanup_prepared_profile, prepare_runtime_profile


@dataclass(frozen=True)
class TargetCompany:
    """目标主体及其外部提供的静态关联信息。"""

    name: str
    holding_ratio: str = ""
    related_entity: str = ""
    relation: str = ""


def load_target_companies(target_file: Path) -> list[TargetCompany]:
    """从同目录文本读取目标公司名单及关联元数据。"""

    if not target_file.exists():
        raise FileNotFoundError(f"未找到目标公司清单：{target_file}")

    companies: list[TargetCompany] = []
    for line in target_file.read_text(encoding="utf-8").splitlines():
        raw_line = line.strip()
        if not raw_line or raw_line.startswith("#"):
            continue
        company = _parse_target_line(raw_line)
        companies.append(company)

    if not companies:
        raise ValueError(f"{target_file} 中没有可用公司名称。")
    return companies


def _parse_target_line(line: str) -> TargetCompany:
    """兼容制表符、竖线和 CSV 三种常见录入格式。"""

    if "\t" in line:
        parts = [item.strip() for item in line.split("\t")]
    elif "|" in line:
        parts = [item.strip() for item in line.split("|")]
    else:
        parts = next(csv.reader([line], skipinitialspace=True))
        parts = [item.strip() for item in parts]

    if len(parts) == 1:
        return TargetCompany(name=parts[0])
    if len(parts) >= 4:
        return TargetCompany(
            name=parts[0],
            holding_ratio=parts[1],
            related_entity=parts[2],
            relation=parts[3],
        )
    raise ValueError(f"目标公司配置格式错误：{line}")


def collect_all_companies(
    platform: str,
    companies: list[TargetCompany],
    browser_config: BrowserConfig,
    retry_times: int,
) -> dict[str, list[dict[str, str]]]:
    """抓取引擎入口：逐家公司监听接口并执行超时重试。"""

    parser = RiskDataParser()
    company_rows: dict[str, list[dict[str, str]]] = {}
    engine = CrawlerEngine(platform=platform, browser_config=browser_config)

    try:
        for company in tqdm(companies, desc="抓取进度", ncols=88):
            last_error: Exception | None = None
            for attempt in range(1, retry_times + 1):
                try:
                    monitored_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    packets = engine.collect_company_packets(company.name)
                    rows = parser.parse_packets(packets)
                    if not rows:
                        raise PacketCaptureError(f"{company.name} 没有提取到任何标准记录。")
                    company_rows[company.name] = [
                        {
                            "监测日期": monitored_at,
                            "主体名称": company.name,
                            "当前持股比例": company.holding_ratio,
                            "关联实体": company.related_entity,
                            "关联关系": company.relation,
                            **row,
                        }
                        for row in rows
                    ]
                    print(
                        f"[成功] {company.name} | 数据包 {len(packets)} 个 | 标准记录 {len(rows)} 条 | 第 {attempt} 次尝试"
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"[重试] {company.name} | 第 {attempt}/{retry_times} 次失败：{exc}")
            else:
                company_rows[company.name] = []
                print(f"[失败] {company.name} | 已放弃抓取 | 原因：{last_error}")
    finally:
        engine.close()

    return company_rows


def generate_excel_report(company_rows: dict[str, list[dict[str, str]]], output_path: Path) -> None:
    """Excel 入口：汇总所有主体并生成单个累计总表。"""

    writer = ExcelReportWriter()
    all_rows = [row for rows in company_rows.values() for row in rows]
    new_frame = pd.DataFrame(all_rows)

    history_frame = load_existing_report(output_path)
    frame = merge_history_and_new(history_frame=history_frame, new_frame=new_frame)

    writer.write(output_path=output_path, frame=frame)


def build_output_path(output_dir: Path, platform: str) -> Path:
    return output_dir / f"Enterprise_Sentinel_{platform}_累计台账.xlsx"


def load_existing_report(output_path: Path) -> pd.DataFrame:
    """如果历史总表已存在，则先读入用于累计合并。"""

    if not output_path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    try:
        history_frame = pd.read_excel(output_path, sheet_name="监测结果")
    except Exception:
        history_frame = pd.read_excel(output_path)

    return history_frame.reindex(columns=OUTPUT_COLUMNS)


def merge_history_and_new(history_frame: pd.DataFrame, new_frame: pd.DataFrame) -> pd.DataFrame:
    """按核心业务字段去重，保留累计历史。"""

    base_columns = [column for column in OUTPUT_COLUMNS if column != "序号"]
    history_frame = history_frame.reindex(columns=base_columns)
    new_frame = new_frame.reindex(columns=base_columns)

    merged = pd.concat([history_frame, new_frame], ignore_index=True)
    if merged.empty:
        merged = pd.DataFrame(columns=OUTPUT_COLUMNS)
        return merged

    merged.fillna("", inplace=True)
    merged.drop_duplicates(
        subset=["主体名称", "事件发生日期", "标题及主要内容", "来源"],
        keep="first",
        inplace=True,
    )
    merged.sort_values(
        by=["监测日期", "事件发生日期", "主体名称", "标题及主要内容"],
        ascending=[False, False, True, True],
        inplace=True,
        kind="stable",
    )
    merged.reset_index(drop=True, inplace=True)
    merged.insert(0, "序号", range(1, len(merged) + 1))
    return merged.reindex(columns=OUTPUT_COLUMNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enterprise_Sentinel 风险舆情采集工具")
    parser.add_argument(
        "--platform",
        choices=["qyyjt", "tianyancha"],
        default="tianyancha",
        help="选择抓取平台，默认 tianyancha。",
    )
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Chrome 用户数据目录，例如 ~/Library/Application Support/Google/Chrome",
    )
    parser.add_argument(
        "--profile-directory",
        default="Default",
        help="Chrome 配置名称，默认 Default。",
    )
    parser.add_argument(
        "--browser-path",
        default="",
        help="Chrome 可执行文件路径，可选。macOS 默认会自动尝试 /Applications/Google Chrome.app。",
    )
    parser.add_argument("--target-file", default=str(DEFAULT_TARGET_FILE), help="目标公司清单，默认读取当前目录 target_list.txt。")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Excel 输出目录，默认 output。",
    )
    parser.add_argument(
        "--retry-times",
        type=int,
        default=3,
        help="单家公司抓取失败时的重试次数，默认 3。",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="每家公司最多翻页数，默认 3。",
    )
    parser.add_argument(
        "--packet-timeout",
        type=int,
        default=12,
        help="监听单个数据包的超时时间（秒），默认 12。",
    )
    parser.add_argument(
        "--use-live-profile",
        action="store_true",
        help="默认会复制一份临时 Chrome 配置避免和正在使用的浏览器冲突；传入本参数时改为直接使用原始目录。",
    )
    parser.add_argument(
        "--clone-root-dir",
        default="/tmp",
        help="克隆 Chrome 配置时的临时根目录，默认 /tmp。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    target_file = Path(args.target_file).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    source_user_data_dir = Path(args.user_data_dir).expanduser().resolve()

    companies = load_target_companies(target_file)
    prepared_profile = prepare_runtime_profile(
        source_user_data_dir=source_user_data_dir,
        profile_directory=args.profile_directory,
        clone_profile=not args.use_live_profile,
        clone_root_dir=Path(args.clone_root_dir),
    )

    try:
        print(f"运行配置目录：{prepared_profile.user_data_dir}")
        browser_config = BrowserConfig(
            user_data_dir=prepared_profile.user_data_dir,
            profile_directory=args.profile_directory,
            browser_path=args.browser_path or None,
            use_live_profile=args.use_live_profile,
            packet_timeout=args.packet_timeout,
            max_pages=args.max_pages,
        )

        company_rows = collect_all_companies(
            platform=args.platform,
            companies=companies,
            browser_config=browser_config,
            retry_times=args.retry_times,
        )

        output_path = build_output_path(output_dir=output_dir, platform=args.platform)
        generate_excel_report(company_rows=company_rows, output_path=output_path)

        total_records = sum(len(rows) for rows in company_rows.values())
        success_companies = sum(1 for rows in company_rows.values() if rows)
        print("-" * 72)
        print(f"输出文件：{output_path}")
        print(f"抓取公司数：{len(company_rows)} | 成功公司数：{success_companies} | 总记录数：{total_records}")
        print(f"固定表头：{'、'.join(OUTPUT_COLUMNS)}")
    finally:
        cleanup_prepared_profile(prepared_profile)


if __name__ == "__main__":
    main()
