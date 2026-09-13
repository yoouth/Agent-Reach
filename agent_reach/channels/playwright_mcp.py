# -*- coding: utf-8 -*-
"""Playwright MCP — check if mcporter + Playwright MCP is available."""

import shutil

from .base import Channel
from .mcporter import McporterConfigError, inspect_mcporter_config


class PlaywrightMcpChannel(Channel):
    name = "playwright_mcp"
    description = "浏览器自动化（JS 重页面兜底）"
    backends = ["Playwright MCP via mcporter"]
    tier = 2

    def can_handle(self, url: str) -> bool:
        return False  # Browser automation channel, not URL-routed

    def check(self, config=None):
        self.active_backend = None
        if not shutil.which("mcporter"):
            return "off", (
                "需要 mcporter + Playwright MCP。安装：\n"
                "  npm install -g mcporter\n"
                "  npx @playwright/mcp 配置为 mcporter 的 stdio server，"
                "启用 --headless --browser=chromium。\n"
                "重要：需运行 `mcporter daemon start` 提供 keep-alive，"
                "因为浏览器会话在调用间保持状态；"
                "首次还需 `npx @playwright/mcp install-browser chrome-for-testing`。"
                "详见 guides/setup-playwright.md。"
            )
        try:
            inspection = inspect_mcporter_config()
        except McporterConfigError as exc:
            return "error", f"mcporter 配置检查失败：{exc}"
        if "playwright" in inspection.server_names:
            return "warn", (
                "Playwright 已写入 mcporter 配置，但 Doctor 未启动远端服务做"
                "连通验证，不能仅凭配置宣称可用。"
            )
        if inspection.imports_unchecked:
            return "warn", (
                "mcporter 本地配置未发现 Playwright；配置还启用了 editor imports，"
                "Doctor 为避免扩大凭据读取范围没有展开，当前未验证。"
            )
        return "off", (
            "mcporter 已装但 Playwright MCP 未配置。运行：\n"
            "  npx @playwright/mcp 并配置为 mcporter 的 stdio server"
        )
