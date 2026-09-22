"""README.md and USER.md command docs must list exactly the cli subparsers.

Parses the real argparse parser so adding a command without documenting it
(or documenting a ghost) fails here.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from boo_lab import cli

LAB = Path(__file__).resolve().parents[1]


def _subparser_names() -> set[str]:
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


def _readme_command_names() -> set[str]:
    text = (LAB / "README.md").read_text(encoding="utf-8")
    names: set[str] = set()
    in_commands = False
    for line in text.splitlines():
        if line.strip() == "## Commands":
            in_commands = True
            continue
        if in_commands and line.startswith("## "):
            break
        if not in_commands or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "cmd":
            continue
        cmd = cells[0].strip("`").split()
        if cmd:
            names.add(cmd[0])
    return names


def _user_command_names() -> set[str]:
    text = (LAB / "USER.md").read_text(encoding="utf-8")
    return set(re.findall(r"python -m boo_lab\.cli\s+([a-z0-9][a-z0-9-]*)", text))


def test_readme_commands_match_cli_subparsers():
    assert _readme_command_names() == _subparser_names()


def test_user_commands_match_cli_subparsers():
    assert _user_command_names() == _subparser_names()


def test_no_ghost_commands_in_readme():
    assert _readme_command_names() <= _subparser_names()
