from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Label files that may be pushed. Never stage the whole data/ tree.
_LABEL_FILES = (
    "data/sections.jsonl",
    "data/holdout.csv",
    "data/CATALOG.md",
)


def _git_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return None


def _run(cmd: list[str], cwd: Path, capture: bool, timeout: int = 180) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GCM_INTERACTIVE", "auto")
    kw: dict = {"cwd": str(cwd), "timeout": timeout, "env": env}
    if capture:
        kw.update(capture_output=True, text=True)
    else:
        kw.update(text=True)
    return subprocess.run(cmd, **kw)


def _stage_paths(lab_root: Path, root: Path) -> list[str]:
    """Paths relative to git root to stage (never git add -A data/)."""
    lab_root = lab_root.resolve()
    root = root.resolve()
    if (root / "tools" / "boo-lab").exists() and lab_root == (root / "tools" / "boo-lab").resolve():
        prefix = "tools/boo-lab/"
    elif lab_root == root:
        prefix = ""
    else:
        try:
            prefix = lab_root.relative_to(root).as_posix().rstrip("/") + "/"
        except ValueError:
            prefix = ""

    candidates = [f"{prefix}src"]
    candidates.extend(f"{prefix}{rel}" for rel in _LABEL_FILES)
    return [p for p in candidates if (root / p).exists()]


def push_lab(lab_root: Path, message: str | None = None) -> dict:
    root = _git_root(lab_root)
    if not root:
        return {"ok": False, "error": "no .git above boo-lab"}
    exist = _stage_paths(Path(lab_root), root)
    if not exist:
        return {"ok": False, "error": "nothing to stage under boo-lab", "root": str(root)}
    msg = message or "boo-lab: labels, lyrics, source"
    logs: list[str] = []
    steps = [
        (["git", "-c", "core.safecrlf=false", "add", "--", *exist], True),
        (["git", "status", "--short"], True),
        (["git", "commit", "-m", msg], True),
        (["git", "push"], False),
    ]
    for cmd, capture in steps:
        try:
            r = _run(cmd, root, capture=capture)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "git timed out (push waiting for GitHub login?)", "root": str(root), "log": "\n".join(logs)}
        except Exception as e:
            return {"ok": False, "error": str(e), "root": str(root), "log": "\n".join(logs)}
        out = ((r.stdout or "") + (r.stderr or "")).strip() if capture else ("exit %s" % r.returncode)
        logs.append("$ " + " ".join(cmd) + "\n" + out)
        low = out.lower()
        is_commit = "commit" in cmd
        if r.returncode != 0 and is_commit and "nothing to commit" in low:
            logs.append("(nothing new, still pushing)")
            continue
        warn_only = (
            ("warning:" in low or "ignored by one of your .gitignore" in low or "hint:" in low)
            and "fatal:" not in low
        )
        if r.returncode != 0 and warn_only:
            continue
        if r.returncode != 0:
            return {"ok": False, "error": out[-500:] or "git failed", "root": str(root), "log": "\n".join(logs)}
    return {"ok": True, "root": str(root), "log": "\n".join(logs)}
