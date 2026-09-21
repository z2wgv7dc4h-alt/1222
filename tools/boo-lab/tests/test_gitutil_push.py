"""push_lab must never stage private data/map.csv via git add -A data/."""
from __future__ import annotations

import subprocess
from pathlib import Path

from boo_lab.gitutil import _stage_paths, push_lab


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


def test_stage_paths_excludes_map_csv(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    lab = root / "tools" / "boo-lab"
    (lab / "src" / "boo_lab").mkdir(parents=True)
    (lab / "data").mkdir(parents=True)
    (lab / "src" / "boo_lab" / "__init__.py").write_text("", encoding="utf-8")
    (lab / "data" / "sections.jsonl").write_text("{}" + "\n", encoding="utf-8")
    (lab / "data" / "holdout.csv").write_text("album,track\n", encoding="utf-8")
    (lab / "data" / "CATALOG.md").write_text("# catalog\n", encoding="utf-8")
    (lab / "data" / "map.csv").write_text("album,track\nsecret,row\n", encoding="utf-8")

    paths = _stage_paths(lab, root)
    assert "tools/boo-lab/src" in paths
    assert "tools/boo-lab/data/sections.jsonl" in paths
    assert "tools/boo-lab/data/holdout.csv" in paths
    assert "tools/boo-lab/data/CATALOG.md" in paths
    assert all("map.csv" not in p for p in paths)
    assert not any(p == "tools/boo-lab/data" or p.endswith("/data") for p in paths)


def test_push_lab_does_not_stage_dirty_map_csv(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    lab = root / "tools" / "boo-lab"
    (lab / "src" / "boo_lab").mkdir(parents=True)
    (lab / "data").mkdir(parents=True)
    (lab / "src" / "boo_lab" / "__init__.py").write_text("# src\n", encoding="utf-8")
    (lab / "data" / "sections.jsonl").write_text('{"id":"a"}\n', encoding="utf-8")
    (lab / "data" / "map.csv").write_text("album,track\nold\n", encoding="utf-8")

    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    (lab / ".gitignore").write_text("data/map.csv\n", encoding="utf-8")
    _git(root, "add", "tools/boo-lab/src", "tools/boo-lab/data/sections.jsonl", "tools/boo-lab/.gitignore")
    _git(root, "commit", "-m", "seed")

    (lab / "data" / "sections.jsonl").write_text('{"id":"b"}\n', encoding="utf-8")
    (lab / "data" / "map.csv").write_text("album,track\nSECRET_PATH\n", encoding="utf-8")

    push_lab(lab, message="test labels")

    show = _git(root, "show", "--name-only", "--pretty=", "HEAD").stdout
    assert "tools/boo-lab/data/sections.jsonl" in show
    assert "map.csv" not in show

    assert "SECRET_PATH" in (lab / "data" / "map.csv").read_text(encoding="utf-8")
    ls = _git(root, "ls-tree", "-r", "--name-only", "HEAD").stdout
    assert "map.csv" not in ls
