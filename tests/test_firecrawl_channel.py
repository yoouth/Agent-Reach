# -*- coding: utf-8 -*-
"""Tests for Firecrawl channel."""

import json
import shutil
import subprocess

import pytest


class TestFirecrawlChannel:
    def test_mcporter_missing_reports_off(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda _: None)
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "off"
        assert ch.active_backend is None
        assert "npm install -g mcporter" in msg
        assert "mcporter config add firecrawl --command npx" in msg
        assert "FIRECRAWL_API_KEY" in msg
        assert "https://www.firecrawl.dev" in msg
        assert "guides/setup-firecrawl.md" in msg

    def test_mcporter_is_never_executed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: pytest.fail(
                "Doctor must not execute mcporter"
            ),
        )
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "off"
        assert ch.active_backend is None

    def test_configured_firecrawl_is_not_false_positive_active(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        secret = "sk-should-never-leak-abc123"
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "firecrawl": {
                            "command": "npx",
                            "args": ["-y", "firecrawl-mcp"],
                            "env": {"FIRECRAWL_API_KEY": secret},
                        }
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "warn"
        assert "未启动" in msg or "未启动远端服务" in msg
        assert ch.active_backend is None
        assert secret not in msg

    def test_config_metadata_containing_firecrawl_is_not_a_backend(
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
                            "baseUrl": "https://example.test/firecrawl-project"
                        }
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
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
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
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
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "warn"
        assert ch.active_backend is None
        assert "editor imports" in msg

    def test_can_handle_returns_false(self):
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        assert ch.can_handle("https://example.com") is False
        assert ch.can_handle("https://firecrawl.dev") is False

    def test_channel_properties(self):
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        assert ch.name == "firecrawl"
        assert ch.description == "网页抓取与搜索（JS 渲染、反爬、结构化提取）"
        assert ch.backends == ["Firecrawl via mcporter"]
        assert ch.tier == 1
