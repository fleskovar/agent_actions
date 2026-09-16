"""Processes that limit loops and tool use."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any, Final

from agent_actions.model import HookInput, ProcessResult, ToolKind, Verdict, allow, block
from agent_actions.process import ALLOW_OR_BLOCK, PreToolProcess, StopProcess

INNER_STATE_KEY: Final = "inner"
LOOP_ADVICE: Final = (
    "If the problems remain at your next stop, stop anyway and tell the user "
    "that the approach needs a review."
)
BUDGET_REASON: Final = "Stop now and report your progress and the open problems to the user."


class LoopGuard(StopProcess):
    """Wraps a stop process, and allows the stop after `max_blocks` blocks in a row.

    Use it with RequireTests: when the agent cannot make the tests pass in a few
    attempts, the strategy is probably wrong and a person must look at it. The
    last block tells the agent to report this at its next stop.
    """

    def __init__(self, process: StopProcess, max_blocks: int = 3, *, name: str = "") -> None:
        if max_blocks < 1:
            raise ValueError("max_blocks must be 1 or more.")
        self.process = process
        self.max_blocks = max_blocks
        self.on = process.hooks
        self.name = name or f"LoopGuard({process.label})"

    def __state__(self) -> None:
        self.consecutive_blocks = 0

    def load_state(self, saved: Mapping[str, Any]) -> None:
        super().load_state(saved)
        self.process.load_state(saved.get(INNER_STATE_KEY, {}))

    def dump_state(self) -> dict[str, Any]:
        return {**super().dump_state(), INNER_STATE_KEY: self.process.dump_state()}

    def run(self, event: HookInput) -> ProcessResult:
        result = self.process.run(event)
        if result.verdict is not Verdict.BLOCK:
            self.consecutive_blocks = 0
            outcome = result
        elif self.consecutive_blocks >= self.max_blocks:
            self.consecutive_blocks = 0
            outcome = allow(
                f"Allowed the stop after {self.max_blocks} blocked stops in a row.", *result.reasons
            )
        else:
            self.consecutive_blocks += 1
            outcome = replace(result, reasons=(*result.reasons, self._attempt_note()))
        return outcome

    def _attempt_note(self) -> str:
        note = f"Blocked stop {self.consecutive_blocks} of {self.max_blocks}."
        return f"{note} {LOOP_ADVICE}" if self.consecutive_blocks == self.max_blocks else note


class ToolCallBudget(PreToolProcess):
    """Blocks tool calls after `max_calls` calls by the same agent in a session."""

    verdicts = ALLOW_OR_BLOCK

    def __init__(
        self,
        max_calls: int,
        *,
        kinds: Iterable[ToolKind] = tuple(ToolKind),
        reason: str = BUDGET_REASON,
        name: str = "",
    ) -> None:
        self.max_calls = max_calls
        self.kinds = frozenset(kinds)
        self.reason = reason
        self.name = name

    def __state__(self) -> None:
        self.calls = 0

    def run(self, event: HookInput) -> ProcessResult:
        counted = event.tool is not None and event.tool.kind in self.kinds
        if counted and self.calls >= self.max_calls:
            result = block(f"The budget of {self.max_calls} tool calls is used up. {self.reason}")
        else:
            self.calls += int(counted)
            result = allow(f"{self.calls} of {self.max_calls} tool calls used.")
        return result
