# -*- coding: utf-8 -*-
"""Firecrawl — Python SDK preferred, mcporter MCP as fallback."""

from __future__ import annotations

import json
import os
import re
import shutil
from typing import Any, Optional, Tuple

from agent_reach.probe import probe_command

from .base import Channel
from .mcporter import McporterConfigError, inspect_mcporter_config

#: Pinned alongside guides/setup-firecrawl.md — upgrades are deliberate.
_MCP_PACKAGE = "firecrawl-mcp@3.24.0"
_SDK_EXTRA = "firecrawl-py>=4.42.0,<5"

SDK_BACKEND = "Firecrawl Python SDK"
MCP_BACKEND = "Firecrawl via mcporter"

#: Env names only — never log values. Agent Reach key wins over the generic one.
_KEY_ENVS = ("FIRECRAWL_AGENT_REACH_API_KEY", "FIRECRAWL_API_KEY")

# Official firecrawl-py v2 public surface (4.42+). Aliases omitted.
SDK_METHODS = (
    "scrape",
    "parse",
    "search",
    "developer_search",
    "map",
    "crawl",
    "start_crawl",
    "get_crawl_status",
    "cancel_crawl",
    "batch_scrape",
    "start_batch_scrape",
    "get_batch_scrape_status",
    "cancel_batch_scrape",
    "extract",
    "start_extract",
    "get_extract_status",
    "agent",
    "start_agent",
    "get_agent_status",
    "cancel_agent",
    "interact",
    "stop_interaction",
    "browser",
    "browser_execute",
    "list_browsers",
    "delete_browser",
    "list_monitors",
    "create_monitor",
    "get_concurrency",
    "get_credit_usage",
    "get_queue_status",
    "search_papers",
    "inspect_paper",
    "read_paper",
    "related_papers",
    "search_github",
)

_ADD_COMMAND = (
    "  mcporter config add firecrawl --command npx --arg -y "
    f"--arg {_MCP_PACKAGE} "
    "--env 'FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}' --scope home\n"
)

_SDK_INSTALL = f"  pip install '{_SDK_EXTRA}'\n"


def _scrub_key_shapes(text: str) -> str:
    """Drop Firecrawl key shapes (fc-…) before echoing upstream output."""
    return re.sub(r"fc-[A-Za-z0-9_-]{4,}", "fc-***", text)


def resolved_api_key() -> Optional[str]:
    """Return the first configured Firecrawl key, or None. Never log the value."""
    for name in _KEY_ENVS:
        value = os.environ.get(name)
        if value:
            return value
    return None


def import_sdk() -> Any:
    """Return the Firecrawl class, or None if firecrawl-py is not installed."""
    try:
        from firecrawl import Firecrawl
    except ImportError:
        return None
    return Firecrawl


def sdk_client() -> Any:
    """Construct the official Firecrawl client with the Agent Reach key.

    Prefers FIRECRAWL_AGENT_REACH_API_KEY so this process does not steal the
    generic FIRECRAWL_API_KEY used by other harnesses. The SDK itself only
    auto-reads FIRECRAWL_API_KEY, so the Agent Reach key is passed explicitly.
    """
    cls = import_sdk()
    if cls is None:
        raise RuntimeError(
            "firecrawl-py is not installed. Run: pip install "
            f"'{_SDK_EXTRA}'"
        )
    key = resolved_api_key()
    if key:
        return cls(api_key=key)
    return cls()


class FirecrawlChannel(Channel):
    name = "firecrawl"
    description = "网页抓取与搜索（JS 渲染、反爬、结构化提取）"
    backends = [SDK_BACKEND, MCP_BACKEND]
    tier = 1

    def can_handle(self, url: str) -> bool:
        return False  # Search/capture channel, not URL-routed

    def check(self, config=None):
        self.active_backend = None
        sdk_ready = import_sdk() is not None and bool(resolved_api_key())
        if sdk_ready:
            return "warn", (
                "Firecrawl Python SDK 已安装且检测到 API Key，但 Doctor 未做"
                "连通验证，不能仅凭 import 宣称可用。"
            )

        mcp_status, mcp_msg = self._check_mcporter()
        if mcp_status in ("warn", "error"):
            return mcp_status, mcp_msg

        if import_sdk() is not None:
            return "warn", (
                "firecrawl-py 已安装，但未设置 FIRECRAWL_AGENT_REACH_API_KEY "
                "或 FIRECRAWL_API_KEY。详见 guides/setup-firecrawl.md。"
            )
        return mcp_status, mcp_msg

    def _check_mcporter(self) -> Tuple[str, str]:
        if not shutil.which("mcporter"):
            return "off", (
                "需要 Firecrawl Python SDK（首选）或 mcporter MCP（兜底）。安装 SDK：\n"
                + _SDK_INSTALL
                + "或安装 MCP：\n"
                "  npm install -g mcporter\n"
                + _ADD_COMMAND
                + "并设置 FIRECRAWL_AGENT_REACH_API_KEY 或 FIRECRAWL_API_KEY。"
                "免费 Key 可从 https://www.firecrawl.dev 获取。"
                "详见 guides/setup-firecrawl.md。"
            )
        try:
            inspection = inspect_mcporter_config()
        except McporterConfigError as exc:
            return "error", f"mcporter 配置检查失败：{exc}"
        if "firecrawl" in inspection.server_names:
            return "warn", (
                "Firecrawl 已写入 mcporter 配置，但 Doctor 未启动远端服务做"
                "连通验证，不能仅凭配置宣称可用。"
            )
        if inspection.imports_unchecked:
            return "warn", (
                "mcporter 本地配置未发现 Firecrawl；配置还启用了 editor imports，"
                "Doctor 为避免扩大凭据读取范围没有展开，当前未验证。"
            )
        return "off", (
            "mcporter 已装但 Firecrawl 未配置。首选安装 Python SDK：\n"
            + _SDK_INSTALL
            + "或配置 MCP：\n"
            + _ADD_COMMAND
            + "并设置 FIRECRAWL_AGENT_REACH_API_KEY 或 FIRECRAWL_API_KEY；"
            "详见 guides/setup-firecrawl.md。"
        )

    def probe_check(
        self, config: Optional[object], status: str, message: str
    ) -> Tuple[str, str]:
        """doctor --probe：SDK 走 get_concurrency，MCP 走 firecrawl_monitor_list。

        两者都是只读、零积分。默认 doctor 不会走到这里——探测是显式 opt-in，
        check() 本身仍然不发起任何远端调用。
        """
        if status != "warn":
            return status, message
        if import_sdk() is not None and resolved_api_key():
            sdk_status, sdk_msg = self._probe_sdk()
            if sdk_status == "ok":
                return sdk_status, sdk_msg
            mcp_status, _mcp_msg = self._check_mcporter()
            if mcp_status == "warn":
                mcp_probe = self._probe_mcporter()
                if mcp_probe[0] == "ok":
                    return mcp_probe
            return sdk_status, sdk_msg
        return self._probe_mcporter()

    def _probe_sdk(self) -> Tuple[str, str]:
        try:
            client = sdk_client()
            client.get_concurrency()
        except Exception as exc:
            output = _scrub_key_shapes(str(exc))
            return self._classify_probe_failure(output, via="Python SDK get_concurrency")
        self.active_backend = SDK_BACKEND
        return "ok", (
            "Firecrawl 探测通过：Python SDK get_concurrency 真实调用成功"
            "（只读、零积分消耗）。"
        )

    def _probe_mcporter(self) -> Tuple[str, str]:
        result = probe_command(
            "mcporter",
            ["call", "firecrawl.firecrawl_monitor_list"],
            timeout=60,
        )
        output = (result.output or result.hint or "").strip()
        if result.ok and self._payload_success(output):
            self.active_backend = MCP_BACKEND
            return "ok", (
                "Firecrawl 探测通过：firecrawl_monitor_list 真实调用成功"
                "（只读、零积分消耗）。"
            )
        if result.status == "timeout":
            return "error", (
                "Firecrawl 探测超时（>60s）：npx → firecrawl-mcp 启动链路未响应。"
                "手动执行 `mcporter call firecrawl.firecrawl_monitor_list` 排查。"
            )
        return self._classify_probe_failure(output or result.status, via="mcporter")

    def _classify_probe_failure(self, output: str, via: str) -> Tuple[str, str]:
        if "Unauthorized" in output or "Invalid token" in output or " 401" in output:
            return "error", (
                "Firecrawl 探测失败：API Key 无效或过期（401）。"
                "检查 FIRECRAWL_AGENT_REACH_API_KEY 或 FIRECRAWL_API_KEY；"
                "详见 guides/setup-firecrawl.md。"
            )
        if (
            "Payment Required" in output
            or "Too Many Requests" in output
            or "insufficient credits" in output
            or " 402" in output
            or " 429" in output
        ):
            return "error", (
                "Firecrawl 探测失败：配额或并发受限（402/429）。"
                "注意限额按团队计算，多客户端共用同一 Key 会互相挤占。"
            )
        detail = _scrub_key_shapes(output[:200]) or via
        return "error", f"Firecrawl 探测失败（{via}）：{detail}"

    @staticmethod
    def _payload_success(output: str) -> bool:
        """True only if the output contains a JSON object with success=true."""
        start = output.find("{")
        if start == -1:
            return False
        try:
            payload = json.loads(output[start:])
        except (ValueError, TypeError):
            return False
        return isinstance(payload, dict) and payload.get("success") is True
