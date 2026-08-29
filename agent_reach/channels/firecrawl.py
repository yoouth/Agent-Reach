# -*- coding: utf-8 -*-
"""Firecrawl — check if mcporter + Firecrawl MCP is available."""

import shutil

from agent_reach.probe import probe_command

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
                "  mcporter config add firecrawl --command npx --arg -y "
                "--arg firecrawl-mcp "
                "--env 'FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}' --scope home\n"
                "注意：需要设置 FIRECRAWL_API_KEY 环境变量。"
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
            "mcporter 已装但 Firecrawl 未配置。运行：\n"
            "  mcporter config add firecrawl --command npx --arg -y "
            "--arg firecrawl-mcp "
            "--env 'FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}' --scope home\n"
            "并设置 FIRECRAWL_API_KEY 环境变量；详见 guides/setup-firecrawl.md。"
        )

    def probe_check(self, config, status, message):
        """doctor --probe 专用：真实调用一次 firecrawl_monitor_list 验证链路。

        选择 firecrawl_monitor_list 是因为它只读、零积分消耗，且能区分
        Key 无效（401）与链路故障。默认 doctor 不会走到这里——探测是
        显式 opt-in，check() 本身仍然不发起任何远端调用。
        """
        if status != "warn":
            return status, message  # 未配置或已出错，无可探测
        result = probe_command(
            "mcporter",
            ["call", "firecrawl.firecrawl_monitor_list"],
            timeout=30,
        )
        output = (result.output or result.hint or "").strip()
        # mcporter 对工具级失败仍以退出码 0 结束（错误在输出文本里），
        # 所以不能只信 result.ok——已实测无效 Key 时 EXIT=0。
        tool_failed = "execution failed" in output
        if result.ok and not tool_failed:
            self.active_backend = "Firecrawl via mcporter"
            return "ok", (
                "Firecrawl 探测通过：firecrawl_monitor_list 真实调用成功"
                "（只读、零积分消耗）。"
            )
        if "401" in output or "Unauthorized" in output or "Invalid token" in output:
            return "error", (
                "Firecrawl 探测失败：API Key 无效或过期（401）。"
                "检查 FIRECRAWL_API_KEY 环境变量；详见 guides/setup-firecrawl.md。"
            )
        if "402" in output or "429" in output or "Payment Required" in output:
            return "error", (
                "Firecrawl 探测失败：配额或并发受限（402/429）。"
                "注意限额按团队计算，多客户端共用同一 Key 会互相挤占。"
            )
        if result.status == "timeout":
            return "error", (
                "Firecrawl 探测超时（>30s）：npx → firecrawl-mcp 启动链路未响应。"
                "手动执行 `mcporter call firecrawl.firecrawl_monitor_list` 排查。"
            )
        return "error", f"Firecrawl 探测失败：{output[:200] or result.status}"
