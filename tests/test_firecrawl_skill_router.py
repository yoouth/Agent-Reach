# -*- coding: utf-8 -*-
"""Always-loaded skill must route Firecrawl jobs, not only search/scrape."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ZH = (ROOT / "agent_reach" / "skill" / "SKILL.md").read_text(encoding="utf-8")
SKILL_EN = (ROOT / "agent_reach" / "skill" / "SKILL_en.md").read_text(encoding="utf-8")
FC_MD = (
    ROOT / "agent_reach" / "skill" / "references" / "firecrawl.md"
).read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", [SKILL_ZH, SKILL_EN], ids=["zh", "en"])
def test_skill_live_example_is_sdk_client(skill):
    assert "from agent_reach.channels.firecrawl import sdk_client" in skill
    assert "app = sdk_client()" in skill
    # MCP is fallback, not the only runnable Firecrawl example.
    sdk_idx = skill.index("sdk_client()")
    mcp_idx = skill.find("mcporter call firecrawl")
    assert mcp_idx == -1 or sdk_idx < mcp_idx


@pytest.mark.parametrize("skill", [SKILL_ZH, SKILL_EN], ids=["zh", "en"])
def test_skill_intent_table_names_full_surface(skill):
    for method in (
        "app.search",
        "app.scrape",
        "app.batch_scrape",
        "app.map",
        "app.crawl",
        "app.agent",
        "app.search_papers",
        "app.interact",
        "app.parse",
        "app.create_monitor",
    ):
        assert method in skill, method
    assert "/tmp/agent-reach/" in skill


def test_firecrawl_md_agent_contract():
    for token in (
        "spark-2",
        "max_credits",
        "schema",
        "stop_interaction",
        "/tmp/agent-reach/",
    ):
        assert token in FC_MD, token
