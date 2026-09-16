"""Agent Actions: Python processes on AI agent lifecycle hooks, with tracked session state.

A runner file:

    import agent_actions as aa
    from agent_actions.processes import BlockWrites

    context = aa.get_current_context()
    context.add(BlockWrites(["tests/**"]))
    aa.run(context)
"""

from agent_actions.harnesses import make_adapter, tools_for
from agent_actions.harnesses.base import ToolCatalog
from agent_actions.model import (
    Harness,
    Hook,
    HookInput,
    ProcessResult,
    ToolCall,
    ToolKind,
    Verdict,
    allow,
    ask,
    block,
)
from agent_actions.process import (
    EventProcess,
    PostToolProcess,
    PreToolProcess,
    Process,
    PromptProcess,
    StartProcess,
    StopProcess,
)
from agent_actions.runtime import Context, get_current_context, log, run

getCurrentContext = get_current_context  # the spelling of the original specification

__all__ = [
    "Context",
    "EventProcess",
    "Harness",
    "Hook",
    "HookInput",
    "PostToolProcess",
    "PreToolProcess",
    "Process",
    "ProcessResult",
    "PromptProcess",
    "StartProcess",
    "StopProcess",
    "ToolCall",
    "ToolCatalog",
    "ToolKind",
    "Verdict",
    "allow",
    "ask",
    "block",
    "getCurrentContext",
    "get_current_context",
    "log",
    "make_adapter",
    "run",
    "tools_for",
]
