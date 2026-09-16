import json
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = """import agent_actions as aa
from agent_actions.processes import BlockWrites

context = aa.get_current_context()
context.add(BlockWrites(["tests/**"]))
aa.run(context)
"""


def run_cli(arguments: list[str], cwd: Path, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_actions", *arguments],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "checks.py").write_text(RUNNER, encoding="utf-8")
    return tmp_path


def payload_for(project: Path, path: str) -> str:
    return json.dumps(
        {
            "session_id": "sess-0001-abcd",
            "cwd": project.as_posix(),
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": "x"},
        }
    )


def test_run_answers_on_stdout_and_records_the_session(project: Path) -> None:
    completed = run_cli(
        ["run", "checks.py", "--harness", "claude", "--hook", "pre-tool"],
        project,
        payload_for(project, "tests/test_a.py"),
    )

    assert completed.returncode == 0, completed.stderr
    decision = json.loads(completed.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    [session] = [path for path in (project / ".hooks").iterdir() if path.is_dir()]
    assert session.name.endswith("_sess-000")
    assert (session / "main-agent" / "io.json").is_file()


def test_run_reads_the_payload_from_a_file_and_allows_other_paths(project: Path) -> None:
    (project / "payload.json").write_text(payload_for(project, "src/app.py"), encoding="utf-8")

    completed = run_cli(
        [
            "run",
            "checks.py",
            "--harness",
            "claude",
            "--hook",
            "pre-tool",
            "--input",
            "payload.json",
        ],
        project,
    )

    assert (completed.returncode, completed.stdout) == (0, "")


def test_runner_file_without_a_run_call_exits_one(project: Path) -> None:
    (project / "broken.py").write_text("import agent_actions as aa\n", encoding="utf-8")

    completed = run_cli(
        ["run", "broken.py", "--harness", "claude", "--hook", "stop"], project, "{}"
    )

    assert completed.returncode == 1
    assert "did not call agent_actions.run" in completed.stderr


def test_install_writes_the_configuration_with_this_interpreter(project: Path) -> None:
    completed = run_cli(["install", "checks.py", "--target", "copilot-cli"], project)

    assert completed.returncode == 0, completed.stderr
    config = json.loads(
        (project / ".github/hooks/agent-actions-copilot-cli.json").read_text(encoding="utf-8")
    )
    [handler] = config["hooks"]["preToolUse"]
    assert Path(sys.executable).as_posix() in handler["bash"]
    assert "checks.py --harness copilot-cli --hook pre-tool" in handler["bash"]


def test_install_without_target_and_without_a_terminal_fails(project: Path) -> None:
    completed = run_cli(["install", "checks.py"], project)

    assert completed.returncode == 1
    assert "Give --target" in completed.stderr


def test_sessions_lists_a_recorded_session(project: Path) -> None:
    run_cli(
        ["run", "checks.py", "--harness", "claude", "--hook", "pre-tool"],
        project,
        payload_for(project, "tests/test_a.py"),
    )

    completed = run_cli(["sessions"], project)

    assert "session=sess-0001-abcd" in completed.stdout


def test_skills_are_copied_into_the_project(project: Path) -> None:
    completed = run_cli(["skills", "--dest", "agent-skills"], project)

    assert completed.returncode == 0, completed.stderr
    assert (project / "agent-skills" / "agent-actions-processes" / "SKILL.md").is_file()
