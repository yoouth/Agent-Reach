# -*- coding: utf-8 -*-
"""Hermes edition — typed, cookie-free public read operations.

The Hermes research plugin calls `agent-reach read <op> --json` and consumes
one JSON envelope per call. This package holds the read surface only:
it never installs, upgrades, logs in, or acquires cookies.
"""

from agent_reach.hermes.reads import DEFAULT_TIMEOUT, OPERATIONS, run

__all__ = ["DEFAULT_TIMEOUT", "OPERATIONS", "run"]
