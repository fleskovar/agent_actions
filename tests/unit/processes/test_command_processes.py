import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from builders import a_tool_event, an_event

from agent_actions.model import Hook, ToolKind, allow, block
from agent_actions.processes import (
    CheckAfterEdit,
    CommandOutcome,
    RequireCommand,
    RequireTests,
    run_subprocess,
)
from agent_actions.processes.commands import (
    NOT_FOUND_EXIT_CODE,
    PYTEST_COMMAND,
    STOP_REASON,
    TESTS_REASON,
    Command,
    with_paths,
)

STOP = an_event(Hook.STOP, cwd="/repo/src", root="/repo")


class FakeCommandRunner:
    """Returns prepared outcomes in order, and records each call."""

    def __init__(self, *outcomes: CommandOutcome) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[Command, Path, float]] = []

    def __call__(self, command: Command, cwd: Path, timeout: float) -> CommandOutcome:
        self.calls.append((command, cwd, timeout))
        return self.outcomes.pop(0)


def test_passing_command_allows_the_stop_and_runs_in_the_project_root() -> None:
    runner = FakeCommandRunner(CommandOutcome(0, "ok"))

    result = RequireCommand("ruff check .", command_runner=runner).run(STOP)

    assert result == allow("`ruff check .` passed.")
    assert runner.calls == [("ruff check .", Path("/repo"), 240.0)]


def test_failing_command_blocks_with_the_output_tail() -> None:
    runner = FakeCommandRunner(CommandOutcome(1, "xxxxxxxxxx2 errors"))

    result = RequireCommand(["ruff", "check"], max_output_chars=8, command_runner=runner).run(STOP)

    assert result == block(
        f"`ruff check` failed with exit code 1. {STOP_REASON}", "Output:\n...2 errors"
    )


def test_require_tests_runs_pytest_with_its_own_reason() -> None:
    runner = FakeCommandRunner(CommandOutcome(1, "1 failed"))
    process = RequireTests(command_runner=runner)

    result = process.run(STOP)

    assert runner.calls[0][0] == PYTEST_COMMAND
    assert TESTS_REASON in result.reasons[0]
    assert process.label == "RequireTests"


@pytest.mark.parametrize(
    ("command", "paths", "expected"),
    [
        ("ruff check {paths}", ["a b.py", "c.py"], "ruff check 'a b.py' c.py"),
        (["ruff", "check", "{paths}"], ["a.py", "c.py"], ["ruff", "check", "a.py", "c.py"]),
    ],
    ids=["string_is_quoted", "sequence_is_expanded"],
)
def test_paths_placeholder_is_replaced(
    command: Command, paths: Sequence[str], expected: Command
) -> None:
    assert with_paths(command, paths) == expected


def test_failed_check_after_an_edit_becomes_context() -> None:
    runner = FakeCommandRunner(CommandOutcome(1, "E501 line too long"))
    event = a_tool_event("Write", ToolKind.WRITE, paths=["src/a.py"], hook=Hook.POST_TOOL)

    result = CheckAfterEdit("ruff check {paths}", command_runner=runner).run(event)

    assert result == allow(
        context="`ruff check src/a.py` failed with exit code 1 after your edit. Fix these problems.\nE501 line too long"
    )


def test_edit_outside_the_patterns_runs_no_command() -> None:
    runner = FakeCommandRunner()
    event = a_tool_event("Write", ToolKind.WRITE, paths=["README.md"], hook=Hook.POST_TOOL)

    CheckAfterEdit("ruff check {paths}", patterns=["*.py"], command_runner=runner).run(event)

    assert runner.calls == []


def test_read_tool_runs_no_check() -> None:
    runner = FakeCommandRunner()
    event = a_tool_event("Read", ToolKind.READ, paths=["src/a.py"], hook=Hook.POST_TOOL)

    assert CheckAfterEdit("ruff check .", command_runner=runner).run(event) == allow()
    assert runner.calls == []


def test_real_subprocess_reports_exit_code_and_output(tmp_path: Path) -> None:
    outcome = run_subprocess(
        [sys.executable, "-c", "print('hi'); raise SystemExit(3)"], tmp_path, 60
    )

    assert outcome == CommandOutcome(3, "hi\n")


def test_missing_program_reports_not_found(tmp_path: Path) -> None:
    outcome = run_subprocess(["agent-actions-no-such-program"], tmp_path, 60)

    assert outcome.exit_code == NOT_FOUND_EXIT_CODE
