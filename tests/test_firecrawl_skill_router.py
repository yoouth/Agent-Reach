# -*- coding: utf-8 -*-
"""Always-loaded skill must route Firecrawl jobs, not only search/scrape."""

import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_reach.cli import _install_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_ZH = (ROOT / "agent_reach" / "skill" / "SKILL.md").read_text(encoding="utf-8")
SKILL_EN = (ROOT / "agent_reach" / "skill" / "SKILL_en.md").read_text(encoding="utf-8")
FC_MD = (
    ROOT / "agent_reach" / "skill" / "references" / "firecrawl.md"
).read_text(encoding="utf-8")

# Narrowest-row order encoded in SKILL.md (first app.* token per table row).
_TABLE_ORDER = (
    "app.search",
    "app.scrape",
    "app.batch_scrape",
    "app.map",
    "app.crawl",
    "app.agent",
    "app.search_papers",
    "app.interact",
    "app.create_monitor",
    "app.parse",
)


def _firecrawl_section(skill: str) -> str:
    for marker in ("## Firecrawl（", "## Firecrawl ("):
        idx = skill.find(marker)
        if idx != -1:
            rest = skill[idx:]
            nxt = rest.find("\n## ", 1)
            return rest if nxt == -1 else rest[:nxt]
    raise AssertionError("Firecrawl section missing")


def _table_methods(section: str) -> list[str]:
    methods = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        methods.extend(re.findall(r"`(app\.[a-z_]+)`", line))
    return methods


@pytest.mark.parametrize("skill", [SKILL_ZH, SKILL_EN], ids=["zh", "en"])
def test_skill_live_example_is_sdk_client(skill):
    section = _firecrawl_section(skill)
    assert "from agent_reach.channels.firecrawl import sdk_client" in section
    assert "app = sdk_client()" in section
    sdk_idx = section.index("sdk_client()")
    mcp_idx = section.find("mcporter call firecrawl")
    assert mcp_idx == -1 or sdk_idx < mcp_idx


@pytest.mark.parametrize("skill", [SKILL_ZH, SKILL_EN], ids=["zh", "en"])
def test_skill_intent_table_order_and_mcp_fallback(skill):
    section = _firecrawl_section(skill)
    in_table = _table_methods(section)
    for method in _TABLE_ORDER:
        assert method in in_table, method
    positions = [section.index(f"`{method}`") for method in _TABLE_ORDER]
    assert positions == sorted(positions)
    assert "/tmp/agent-reach/" in section
    assert "mcporter call firecrawl.firecrawl_search" in section
    assert "mcporter call firecrawl.firecrawl_scrape" in section
    assert "/ `firecrawl_scrape`" not in section


def test_firecrawl_md_agent_contract():
    for token in (
        "spark-2",
        "max_credits",
        "schema",
        "stop_interaction",
        "/tmp/agent-reach/",
    ):
        assert token in FC_MD, token


def test_install_skill_copy_keeps_firecrawl_table(tmp_path):
    agents = tmp_path / ".agents" / "skills"
    agents.mkdir(parents=True)
    env = os.environ.copy()
    env.pop("OPENCLAW_HOME", None)
    env.pop("AGENT_REACH_LANG", None)
    env["LANG"] = "zh_CN.UTF-8"
    with patch(
        "agent_reach.cli.os.path.expanduser",
        side_effect=lambda p: p.replace("~", str(tmp_path)),
    ), patch.dict(os.environ, env, clear=True):
        _install_skill(force=True)
    installed = (agents / "agent-reach" / "SKILL.md").read_text(encoding="utf-8")
    section = _firecrawl_section(installed)
    in_table = _table_methods(section)
    for method in _TABLE_ORDER:
        assert method in in_table, method
    assert "mcporter call firecrawl.firecrawl_scrape" in installed
