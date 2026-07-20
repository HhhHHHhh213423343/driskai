from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from DrissionPage import Chromium, ChromiumOptions

from enterprise_sentinel.config import LISTEN_KEYWORDS, PLATFORM_PROFILES, PlatformProfile


class PacketCaptureError(RuntimeError):
    """监听到了页面，但没有捕获到有效数据包。"""


class LoginRequiredError(RuntimeError):
    """页面已跳转登录，当前登录态不可用。"""


class BrowserStartupError(RuntimeError):
    """浏览器启动或调试连接失败。"""


@dataclass
class BrowserConfig:
    user_data_dir: Path
    profile_directory: str = "Default"
    browser_path: str | None = None
    use_live_profile: bool = False
    load_timeout: int = 25
    packet_timeout: int = 12
    max_pages: int = 3
    max_packets_per_page: int = 8


class CrawlerEngine:
    """负责浏览器启动、页面导航、接口监听与原始数据包采集。"""

    def __init__(self, platform: str, browser_config: BrowserConfig) -> None:
        if platform not in PLATFORM_PROFILES:
            raise ValueError(f"不支持的平台：{platform}")
        self.profile: PlatformProfile = PLATFORM_PROFILES[platform]
        self.browser_config = browser_config
        self.browser = self._build_browser()

    def close(self) -> None:
        try:
            self.browser.quit()
        except Exception:
            pass

    def collect_company_packets(self, company_name: str) -> list[dict[str, Any]]:
        page = self.browser.new_tab()
        try:
            self._prepare_listener(page)
            self._open_company_page(page, company_name)
            packets = self._capture_packets(page)
            if not packets:
                raise PacketCaptureError(f"未抓到 {company_name} 的有效 JSON 数据包。")
            return packets
        finally:
            try:
                page.listen.stop()
            except Exception:
                pass
            try:
                page.close()
            except Exception:
                pass

    def _build_browser(self):
        options = ChromiumOptions()

        # 通过 Chrome 原生用户目录复用登录态，避免脚本内处理验证码和二次登录。
        browser_path = self.browser_config.browser_path or self._detect_browser_path()
        if browser_path:
            options.set_browser_path(browser_path)
        options.set_argument(f"--user-data-dir={self.browser_config.user_data_dir}")
        options.set_argument(f"--profile-directory={self.browser_config.profile_directory}")
        options.set_argument("--disable-blink-features=AutomationControlled")
        options.set_argument("--no-default-browser-check")
        options.set_argument("--disable-features=TranslateUI")
        options.auto_port()
        options.set_load_mode("eager")
        options.ignore_certificate_errors()
        options.set_retry(times=3, interval=2)

        try:
            return Chromium(addr_or_opts=options)
        except Exception as exc:
            message = self._format_startup_error(exc)
            raise BrowserStartupError(message) from exc

    def _prepare_listener(self, page) -> None:
        page.set.load_mode.eager()
        page.set.timeouts(base=self.browser_config.load_timeout)
        page.listen.start(list(LISTEN_KEYWORDS), method=True, res_type=("XHR", "FETCH"))

    def _open_company_page(self, page, company_name: str) -> None:
        if self.profile.search_url_template:
            search_url = self.profile.search_url_template.format(query=quote(company_name))
            page.get(search_url)
            self._raise_if_login_redirect(page)
        else:
            page.get(self.profile.home_url)
            self._raise_if_login_redirect(page)
            self._search_company(page, company_name)

        self._click_first_existing(page, self._render_company_locators(company_name), required=False)
        self._click_by_text(page, self.profile.risk_tab_texts, required=False)
        time.sleep(2)
        self._raise_if_login_redirect(page)

    def _search_company(self, page, company_name: str) -> None:
        for locator in self.profile.search_input_candidates:
            input_box = page.ele(locator, timeout=2)
            if not input_box:
                continue
            input_box.clear(by_js=True)
            input_box.input(company_name, clear=True)
            if not self._click_first_existing(page, self.profile.search_button_candidates, required=False):
                input_box.input("\n")
            time.sleep(2)
            return
        raise RuntimeError(f"未找到 {self.profile.display_name} 的搜索框，请检查页面结构或更新配置。")

    def _capture_packets(self, page) -> list[dict[str, Any]]:
        captured: list[dict[str, Any]] = []

        for page_index in range(self.browser_config.max_pages):
            page_packets = self._drain_packets(page)
            captured.extend(page_packets)
            if page_index + 1 >= self.browser_config.max_pages:
                break
            if not self._click_first_existing(page, self.profile.next_page_candidates, required=False):
                break
            time.sleep(2)

        return captured

    def _drain_packets(self, page) -> list[dict[str, Any]]:
        packets: list[dict[str, Any]] = []
        idle_rounds = 0

        while len(packets) < self.browser_config.max_packets_per_page and idle_rounds < 2:
            packet = page.listen.wait(timeout=self.browser_config.packet_timeout)
            if not packet:
                idle_rounds += 1
                continue
            idle_rounds = 0

            response = getattr(packet, "response", None)
            if not response:
                continue

            body = getattr(response, "body", None)
            if body in (None, "", b""):
                continue

            packets.append(
                {
                    "url": getattr(packet, "url", ""),
                    "method": getattr(packet, "method", ""),
                    "resource_type": getattr(packet, "resourceType", ""),
                    "body": body,
                }
            )
        return packets

    def debug_company_flow(
        self,
        company_name: str,
        capture_all: bool = True,
        packet_limit: int = 40,
    ) -> dict[str, Any]:
        """调试单家公司时，输出页面状态和捕获到的请求摘要。"""

        page = self.browser.new_tab()
        try:
            page.set.load_mode.eager()
            page.set.timeouts(base=self.browser_config.load_timeout)
            if capture_all:
                page.listen.start(True, method=True, res_type=("XHR", "FETCH", "DOCUMENT"))
            else:
                page.listen.start(list(LISTEN_KEYWORDS), method=True, res_type=("XHR", "FETCH"))

            self._open_company_page(page, company_name)
            packets = self._collect_debug_packets(page, packet_limit=packet_limit)
            return {
                "title": page.title,
                "url": page.url,
                "html_snippet": (page.html or "")[:1200],
                "packets": packets,
            }
        finally:
            try:
                page.listen.stop()
            except Exception:
                pass
            try:
                page.close()
            except Exception:
                pass

    def _collect_debug_packets(self, page, packet_limit: int) -> list[dict[str, Any]]:
        packets: list[dict[str, Any]] = []
        idle_rounds = 0
        while len(packets) < packet_limit and idle_rounds < 3:
            packet = page.listen.wait(timeout=3, fit_count=False)
            if not packet:
                idle_rounds += 1
                continue
            idle_rounds = 0
            if isinstance(packet, list):
                for item in packet:
                    packets.append(self._serialize_debug_packet(item))
                    if len(packets) >= packet_limit:
                        break
            else:
                packets.append(self._serialize_debug_packet(packet))
        return packets

    def _serialize_debug_packet(self, packet) -> dict[str, Any]:
        response = getattr(packet, "response", None)
        headers: dict[str, Any] = {}
        status = None
        body_text = ""

        if response and getattr(packet, "is_failed", False) is not True:
            try:
                headers = dict(response.headers or {})
            except Exception:
                headers = {}
            try:
                status = getattr(response, "status", None)
            except Exception:
                status = None
            try:
                body = response.body
            except Exception:
                body = ""
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="ignore")
            body_text = str(body)[:400] if body not in (None, False) else ""

        return {
            "target": getattr(packet, "target", ""),
            "url": getattr(packet, "url", ""),
            "method": getattr(packet, "method", ""),
            "resource_type": getattr(packet, "resourceType", ""),
            "status": status,
            "is_failed": getattr(packet, "is_failed", False),
            "content_type": headers.get("content-type", ""),
            "body_snippet": body_text,
        }

    def _detect_browser_path(self) -> str | None:
        candidate_paths = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        )
        for candidate in candidate_paths:
            if Path(candidate).exists():
                return candidate
        return None

    def _raise_if_login_redirect(self, page) -> None:
        current_url = (page.url or "").lower()
        current_title = (page.title or "").lower()
        login_hints = ("login", "signin", "登录")
        if any(hint in current_url for hint in login_hints) or any(hint in current_title for hint in login_hints):
            raise LoginRequiredError(
                f"{self.profile.display_name} 当前页面已跳转登录页，说明复用的 Chrome 登录态不可用。"
            )

    def _format_startup_error(self, exc: Exception) -> str:
        base = f"浏览器启动失败：{exc}"
        if self.browser_config.use_live_profile:
            return (
                f"{base}\n"
                "当前使用的是原始 Chrome Profile。最常见原因是该 Profile 仍被已打开的 Chrome 占用。\n"
                "请先完全退出所有 Chrome 窗口后重试；如果仍失败，请去掉 --use-live-profile，改用默认克隆模式。"
            )
        return (
            f"{base}\n"
            "当前使用的是克隆后的临时 Profile。可先确认本机 Chrome 可正常打开站点，"
            "再重试；如仍失败，可改用 --use-live-profile 做对照测试。"
        )

    def _click_first_existing(self, page, locators: tuple[str, ...], required: bool) -> bool:
        for locator in locators:
            ele = page.ele(locator, timeout=2)
            if not ele:
                continue
            ele.click(by_js=True)
            time.sleep(1.5)
            return True
        if required:
            raise RuntimeError(f"未找到可点击元素：{locators}")
        return False

    def _click_by_text(self, page, text_candidates: tuple[str, ...], required: bool) -> bool:
        locators = tuple(f'x://*[contains(normalize-space(.), "{text}")]' for text in text_candidates)
        return self._click_first_existing(page, locators, required=required)

    def _render_company_locators(self, company_name: str) -> tuple[str, ...]:
        return tuple(locator.format(company=company_name) for locator in self.profile.result_link_candidates)
