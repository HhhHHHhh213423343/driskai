from __future__ import annotations

import argparse
import json
from pathlib import Path

from enterprise_sentinel.engine import BrowserConfig, CrawlerEngine
from enterprise_sentinel.profile_manager import cleanup_prepared_profile, prepare_runtime_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="单家公司抓包调试探针")
    parser.add_argument("--platform", choices=["qyyjt", "tianyancha"], default="tianyancha")
    parser.add_argument("--company", required=True, help="需要调试的公司名称")
    parser.add_argument("--user-data-dir", required=True, help="Chrome 用户数据目录")
    parser.add_argument("--profile-directory", default="Default", help="Chrome 配置名称")
    parser.add_argument("--clone-root-dir", default="/tmp", help="克隆配置的临时根目录")
    parser.add_argument("--browser-path", default="", help="Chrome 可执行文件路径，可选")
    parser.add_argument("--packet-limit", type=int, default=40, help="最多打印多少个请求摘要")
    parser.add_argument("--output-json", default="", help="可选，输出调试 JSON 文件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared_profile = prepare_runtime_profile(
        source_user_data_dir=Path(args.user_data_dir),
        profile_directory=args.profile_directory,
        clone_profile=True,
        clone_root_dir=Path(args.clone_root_dir),
    )

    browser_config = BrowserConfig(
        user_data_dir=prepared_profile.user_data_dir,
        profile_directory=args.profile_directory,
        browser_path=args.browser_path or None,
        load_timeout=20,
        packet_timeout=8,
        max_pages=1,
        max_packets_per_page=args.packet_limit,
    )

    engine = CrawlerEngine(platform=args.platform, browser_config=browser_config)
    try:
        debug_result = engine.debug_company_flow(args.company, capture_all=True, packet_limit=args.packet_limit)
    finally:
        engine.close()
        cleanup_prepared_profile(prepared_profile)

    print("=" * 72)
    print(f"平台：{args.platform}")
    print(f"公司：{args.company}")
    print(f"页面标题：{debug_result['title']}")
    print(f"页面地址：{debug_result['url']}")
    print(f"捕获请求数：{len(debug_result['packets'])}")
    print("-" * 72)
    for index, packet in enumerate(debug_result["packets"], start=1):
        print(
            f"[{index}] {packet['method']} {packet['status']} {packet['resource_type']} "
            f"{packet['content_type']} {packet['url']}"
        )

    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(debug_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"调试结果已写入：{output_path}")


if __name__ == "__main__":
    main()
