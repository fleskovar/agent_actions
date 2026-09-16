"""Harness adapters and the factory that selects one."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from agent_actions.harnesses.base import HarnessAdapter, ToolCatalog
from agent_actions.harnesses.claude import ClaudeAdapter
from agent_actions.harnesses.copilot_cli import CopilotCliAdapter
from agent_actions.harnesses.vscode import VSCodeAdapter
from agent_actions.model import Harness

_ADAPTERS: Final[Mapping[Harness, HarnessAdapter]] = {
    Harness.CLAUDE: ClaudeAdapter(),
    Harness.VSCODE: VSCodeAdapter(),
    Harness.COPILOT_CLI: CopilotCliAdapter(),
}


def make_adapter(harness: Harness | str) -> HarnessAdapter:
    """The adapter for a harness. To add a harness, register its adapter in `_ADAPTERS`."""
    return _ADAPTERS[Harness(harness)]


def tools_for(harness: Harness | str) -> ToolCatalog:
    """The tool names of a harness, grouped by kind (read, write, search, shell)."""
    return make_adapter(harness).tools


__all__ = ["HarnessAdapter", "ToolCatalog", "make_adapter", "tools_for"]
