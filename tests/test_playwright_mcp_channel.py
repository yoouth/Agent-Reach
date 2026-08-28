# -*- coding: utf-8 -*-
"""Tests for Playwright MCP channel."""

import json
import shutil

import pytest


class TestPlaywrightMcpChannel:
    def test_mcporter_missing_reports_off(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda _: None)
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        status, msg = ch.check()
        assert status == "off"
        assert ch.active_backend is None
        assert "npm install -g mcporter" in msg
        assert "npx @playwright/mcp" in msg
        assert "mcporter daemon start" in msg
        assert "install-browser chrome-for-testing" in msg

    def test_configured_playwright_is_not_false_positive_active(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "playwright": {"command": "npx @playwright/mcp"}
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        status, msg = ch.check()
        assert status == "warn"
        assert "未启动" in msg or "未启动远端服务" in msg
        assert ch.active_backend is None

    def test_config_metadata_containing_playwright_is_not_a_backend(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "unrelated": {
                            "baseUrl": "https://example.test/playwright-project"
                        }
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        status, _ = ch.check()
        assert status == "off"
        assert ch.active_backend is None

    def test_invalid_mcporter_json_is_reported_as_error(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text("not-json", encoding="utf-8")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        status, msg = ch.check()
        assert status == "error"
        assert ch.active_backend is None
        assert "配置检查失败" in msg

    def test_imports_unchecked_is_reported_as_warn(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "unrelated": {"command": "some-mcp"}
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        status, msg = ch.check()
        assert status == "warn"
        assert ch.active_backend is None
        assert "editor imports" in msg

    def test_can_handle_returns_false(self):
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        assert ch.can_handle("https://example.com") is False
        assert ch.can_handle("https://playwright.dev") is False

    def test_channel_properties(self):
        from agent_reach.channels.playwright_mcp import PlaywrightMcpChannel

        ch = PlaywrightMcpChannel()
        assert ch.name == "playwright_mcp"
        assert ch.description == "浏览器自动化（JS 重页面兜底）"
        assert ch.backends == ["Playwright MCP via mcporter"]
        assert ch.tier == 2
