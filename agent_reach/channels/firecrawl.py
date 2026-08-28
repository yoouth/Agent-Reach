# -*- coding: utf-8 -*-
"""Firecrawl — check if mcporter + Firecrawl MCP is available."""

import shutil

from .base import Channel
from .mcporter import McporterConfigError, inspect_mcporter_config


class FirecrawlChannel(Channel):
    name = "firecrawl"
    description = "网页抓取与搜索（JS 渲染、反爬、结构化提取）"
    backends = ["Firecrawl via mcporter"]
    tier = 1

    def can_handle(self, url: str) -> bool:
        return False  # Search/capture channel, not URL-routed

    def check(self, config=None):
        self.active_backend = None
        if not shutil.which("mcporter"):
            return "off", (
                "需要 mcporter + Firecrawl MCP。安装：\n"
                "  npm install -g mcporter\n"
                "  mcporter config add firecrawl --scope home\n"
                "注意：需要设置 FIRECRAWL_API_KEY 环境变量。"
                "免费 Key 可从 https://www.firecrawl.dev 获取。"
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
            "mcporter 已装但 Firecrawl 未配置。运行：\n"
            "  mcporter config add firecrawl --scope home"
        )
