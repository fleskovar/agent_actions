"""Path guards: block tools that read or change protected paths."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
from fnmatch import fnmatchcase
from typing import Final

from agent_actions.model import HookInput, ProcessResult, ToolCall, ToolKind, allow, block
from agent_actions.process import ALLOW_OR_BLOCK, PreToolProcess

WRITE_REASON: Final = (
    "These files are protected. Do not change them. "
    "If a change is necessary, stop and ask the user."
)
READ_REASON: Final = (
    "These files can contain secrets. Do not read, search or print them, "
    "and do not ask for their content."
)
_WILDCARDS: Final = re.compile(r"[*?\[\]]")


def relative_path(path: str, cwd: str, root: str) -> str:
    """A tool path relative to the project root, with '/' separators.

    A relative path resolves against `cwd`, and a relative `cwd` against `root`.
    A `cwd` that lies outside the root cannot steer patterns that are relative to
    the root, so the root is the base instead. That keeps a guard closed when the
    harness reports a working folder in another path style, for example a POSIX
    path on Windows.

    A path outside the root starts with '..'. A path on another drive stays absolute.
    """
    # os.path, not pathlib: relpath and normpath have no pathlib form.
    full = os.path.normpath(os.path.join(_base_folder(cwd, root), path))  # noqa: PTH118
    return _relative_to(full, root)


def _base_folder(cwd: str, root: str) -> str:
    base = os.path.normpath(os.path.join(root, cwd))  # noqa: PTH118
    return base if not _relative_to(base, root).startswith("..") else root


def _relative_to(path: str, root: str) -> str:
    try:
        relative = os.path.relpath(path, root or os.curdir)
    except ValueError:  # another drive on Windows
        relative = path
    return relative.replace("\\", "/")


def normal_pattern(pattern: str) -> str:
    return pattern.replace("\\", "/").removeprefix("./").rstrip("/").lower()


def matching_pattern(relative: str, patterns: Iterable[str]) -> str | None:
    """The first pattern that covers a root-relative path, or None.

    Matching ignores case. `*` also matches '/'. A pattern also covers everything
    inside the folder that it names: `tests` covers `tests/unit/test_a.py`.
    """
    candidate = relative.lower()
    return next(
        (pattern for pattern in patterns if _covers(normal_pattern(pattern), candidate)), None
    )


def _covers(pattern: str, path: str) -> bool:
    folder = pattern.removesuffix("/**")
    return path == folder or path.startswith(f"{folder}/") or fnmatchcase(path, pattern)


def literal_part(pattern: str) -> str:
    """The longest part of a pattern without wildcards: `secrets/*.json` gives `secrets`."""
    return max(_WILDCARDS.split(normal_pattern(pattern)), key=len).strip("/")


def mentioned_pattern(command: str, patterns: Iterable[str]) -> str | None:
    """The first pattern whose literal part occurs in a shell command.

    ponytail: substring heuristic. It misses paths that a command builds at run time
    and can match unrelated text. Parse the command if that becomes a problem.
    """
    text = command.replace("\\", "/").lower()
    return next(
        (pattern for pattern in patterns if (needle := literal_part(pattern)) and needle in text),
        None,
    )


class PathGuard(PreToolProcess):
    """Blocks tools of the given kinds when one of their paths matches a pattern.

    Patterns are relative to the project root. With `check_shell`, shell commands
    that mention a protected path are blocked too.
    """

    verdicts = ALLOW_OR_BLOCK

    def __init__(
        self,
        patterns: str | Sequence[str],
        *,
        kinds: Iterable[ToolKind],
        reason: str,
        check_shell: bool = False,
        name: str = "",
    ) -> None:
        self.patterns = (patterns,) if isinstance(patterns, str) else tuple(patterns)
        self.kinds = frozenset(kinds)
        self.reason = reason
        self.check_shell = check_shell
        self.name = name

    def run(self, event: HookInput) -> ProcessResult:
        tool = event.tool
        finding = None if tool is None else self._finding(tool, event)
        return allow() if finding is None else block(finding)

    def _finding(self, tool: ToolCall, event: HookInput) -> str | None:
        finding = None
        if tool.kind in self.kinds:
            hits = (
                (path, matching_pattern(relative_path(path, event.cwd, event.root), self.patterns))
                for path in tool.paths
            )
            hit = next(((path, pattern) for path, pattern in hits if pattern is not None), None)
            if hit is not None:
                finding = (
                    f"'{tool.name}' on '{hit[0]}' is blocked: "
                    f"'{hit[1]}' is protected. {self.reason}"
                )
        elif tool.kind is ToolKind.SHELL and self.check_shell and tool.command:
            pattern = mentioned_pattern(tool.command, self.patterns)
            if pattern is not None:
                finding = (
                    f"The shell command is blocked: it mentions '{pattern}', "
                    f"which is protected. {self.reason}"
                )
        return finding


class BlockWrites(PathGuard):
    """Blocks write tools on protected paths, for example tests or generated files."""

    def __init__(
        self,
        patterns: str | Sequence[str],
        *,
        reason: str = WRITE_REASON,
        check_shell: bool = False,
        name: str = "",
    ) -> None:
        super().__init__(
            patterns, kinds={ToolKind.WRITE}, reason=reason, check_shell=check_shell, name=name
        )


class BlockReads(PathGuard):
    """Blocks read, search and write tools on secret paths. Checks shell commands by default."""

    def __init__(
        self,
        patterns: str | Sequence[str],
        *,
        reason: str = READ_REASON,
        check_shell: bool = True,
        name: str = "",
    ) -> None:
        super().__init__(
            patterns,
            kinds={ToolKind.READ, ToolKind.SEARCH, ToolKind.WRITE},
            reason=reason,
            check_shell=check_shell,
            name=name,
        )
