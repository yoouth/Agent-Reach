# -*- coding: utf-8 -*-
"""Tests for Firecrawl channel."""

import json
import shutil
import subprocess

import pytest


@pytest.fixture(autouse=True)
def _isolate_sdk(monkeypatch):
    """MCP-only tests must not see a real firecrawl-py or a leftover key."""
    monkeypatch.setattr(
        "agent_reach.channels.firecrawl.import_sdk", lambda: None
    )
    monkeypatch.delenv("FIRECRAWL_AGENT_REACH_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)


class TestFirecrawlChannel:
    def test_mcporter_missing_reports_off(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda _: None)
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "off"
        assert ch.active_backend is None
        assert "firecrawl-py" in msg
        assert "npm install -g mcporter" in msg
        assert "mcporter config add firecrawl --command npx" in msg
        assert "firecrawl-mcp@3.24.0" in msg  # pinned, matching the guide
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

    def _configured_channel(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "firecrawl": {"command": "npx", "args": ["-y", "firecrawl-mcp"]}
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        from agent_reach.channels.firecrawl import FirecrawlChannel

        return FirecrawlChannel()

    def test_probe_success_upgrades_warn_to_ok(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult("ok", output='{"success":true,"data":[]}'),
        )
        status, msg = ch.check()
        assert status == "warn"
        status, msg = ch.probe_check(None, status, msg)
        assert status == "ok"
        assert ch.active_backend == "Firecrawl via mcporter"
        assert "零积分" in msg

    def test_probe_invalid_key_reports_error(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult(
                "error", output="Unauthorized: Invalid token"
            ),
        )
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "FIRECRAWL_API_KEY" in msg
        assert ch.active_backend is None

    def test_probe_inband_failure_with_exit_zero_is_not_ok(
        self, monkeypatch, tmp_path
    ):
        # mcporter 0.9.0 exits 0 on tool-level failure; the error is in-band.
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult(
                "ok",
                output="Tool 'firecrawl_monitor_list' execution failed: "
                "Unauthorized: Invalid token",
            ),
        )
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "FIRECRAWL_API_KEY" in msg
        assert ch.active_backend is None

    def test_probe_exit_zero_without_success_payload_is_error(
        self, monkeypatch, tmp_path
    ):
        # Reviewer-reproduced false positive: exit 0, no "execution failed",
        # no success payload (e.g. DEPRECATED_TOOL JSON, offline hint, empty).
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        shapes = [
            '{"code":"DEPRECATED_TOOL","message":"deprecated and unavailable"}',
            "[mcporter] firecrawl appears offline",
            "",
        ]
        ch = self._configured_channel(monkeypatch, tmp_path)
        for shape in shapes:
            monkeypatch.setattr(
                fc_mod,
                "probe_command",
                lambda *_a, _s=shape, **_k: probe_mod.ProbeResult("ok", output=_s),
            )
            status, msg = ch.check()
            status, msg = ch.probe_check(None, status, msg)
            assert status == "error", shape
            assert ch.active_backend is None

    def test_probe_quota_exhaustion_reports_team_limit(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult(
                "error", output="Payment Required: insufficient credits"
            ),
        )
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "402/429" in msg
        assert "团队" in msg

    def test_probe_generic_failure_scrubs_key_shapes(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult(
                "error", output="unexpected: key fc-abc123SECRET456 rejected"
            ),
        )
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "fc-abc123SECRET456" not in msg
        assert "fc-***" in msg

    def test_probe_timeout_reports_error(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        ch = self._configured_channel(monkeypatch, tmp_path)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult("timeout", hint="`mcporter` 响应超时"),
        )
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "超时" in msg
        assert ch.active_backend is None

    def test_probe_skipped_when_not_configured(self, monkeypatch, tmp_path):
        from agent_reach.channels import firecrawl as fc_mod

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(shutil, "which", lambda _: None)
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: pytest.fail("probe must not run when unconfigured"),
        )
        from agent_reach.channels.firecrawl import FirecrawlChannel

        ch = FirecrawlChannel()
        status, msg = ch.check()
        assert status == "off"
        status2, msg2 = ch.probe_check(None, status, msg)
        assert (status2, msg2) == (status, msg)

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
        assert ch.backends[0] == "Firecrawl Python SDK"
        assert "Firecrawl via mcporter" in ch.backends
        assert ch.tier == 1


class _FakeFirecrawl:
    def __init__(self, api_key=None, **_kwargs):
        self.api_key = api_key
        self.concurrency_calls = 0

    def get_concurrency(self):
        self.concurrency_calls += 1
        return {"concurrency": 0, "max_concurrency": 50}


class TestFirecrawlPythonSdk:
    def test_sdk_with_key_is_preferred_warn(self, monkeypatch, tmp_path):
        from agent_reach.channels import firecrawl as fc_mod

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(fc_mod, "import_sdk", lambda: _FakeFirecrawl)
        monkeypatch.setenv("FIRECRAWL_AGENT_REACH_API_KEY", "fc-sdk-secret-key")
        monkeypatch.setattr(shutil, "which", lambda _: None)
        ch = fc_mod.FirecrawlChannel()
        status, msg = ch.check()
        assert status == "warn"
        assert "Python SDK" in msg
        assert "fc-sdk-secret-key" not in msg
        assert ch.active_backend is None

    def test_sdk_client_prefers_agent_reach_key(self, monkeypatch):
        from agent_reach.channels import firecrawl as fc_mod

        created = {}

        class Tracking(_FakeFirecrawl):
            def __init__(self, api_key=None, **kwargs):
                super().__init__(api_key=api_key, **kwargs)
                created["key"] = api_key

        monkeypatch.setattr(fc_mod, "import_sdk", lambda: Tracking)
        monkeypatch.setenv("FIRECRAWL_AGENT_REACH_API_KEY", "fc-agent-reach-key")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-generic-key")
        client = fc_mod.sdk_client()
        assert created["key"] == "fc-agent-reach-key"
        assert client.api_key == "fc-agent-reach-key"

    def test_sdk_probe_success_sets_sdk_backend(self, monkeypatch, tmp_path):
        from agent_reach.channels import firecrawl as fc_mod

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(fc_mod, "import_sdk", lambda: _FakeFirecrawl)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-probe-key")
        ch = fc_mod.FirecrawlChannel()
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "ok"
        assert ch.active_backend == fc_mod.SDK_BACKEND
        assert "get_concurrency" in msg
        assert "fc-probe-key" not in msg

    def test_sdk_probe_401_scrubs_key(self, monkeypatch, tmp_path):
        from agent_reach.channels import firecrawl as fc_mod

        class Boom(_FakeFirecrawl):
            def get_concurrency(self):
                raise RuntimeError("Unauthorized: Invalid token fc-boomSECRET99")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(fc_mod, "import_sdk", lambda: Boom)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-boomSECRET99")
        monkeypatch.setattr(shutil, "which", lambda _: None)
        ch = fc_mod.FirecrawlChannel()
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "error"
        assert "401" in msg
        assert "fc-boomSECRET99" not in msg
        assert ch.active_backend is None

    def test_sdk_probe_failure_falls_back_to_mcporter(self, monkeypatch, tmp_path):
        from agent_reach import probe as probe_mod
        from agent_reach.channels import firecrawl as fc_mod

        class Boom(_FakeFirecrawl):
            def get_concurrency(self):
                raise RuntimeError("network down")

        config_path = tmp_path / "config" / "mcporter.json"
        config_path.parent.mkdir()
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "firecrawl": {
                            "command": "npx",
                            "args": ["-y", "firecrawl-mcp"],
                        }
                    },
                    "imports": [],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(fc_mod, "import_sdk", lambda: Boom)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-fallback-key")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/mcporter")
        monkeypatch.setattr(
            fc_mod,
            "probe_command",
            lambda *_a, **_k: probe_mod.ProbeResult(
                "ok", output='{"success":true,"data":[]}'
            ),
        )
        ch = fc_mod.FirecrawlChannel()
        status, msg = ch.check()
        status, msg = ch.probe_check(None, status, msg)
        assert status == "ok"
        assert ch.active_backend == fc_mod.MCP_BACKEND

    def test_sdk_methods_are_documented(self):
        from pathlib import Path

        from agent_reach.channels.firecrawl import SDK_METHODS

        docs = (
            Path(__file__).resolve().parents[1]
            / "agent_reach"
            / "skill"
            / "references"
            / "firecrawl.md"
        ).read_text(encoding="utf-8")
        missing = [name for name in SDK_METHODS if name not in docs]
        assert missing == []
