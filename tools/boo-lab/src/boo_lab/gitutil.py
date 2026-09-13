from __future__ import annotations

import os
import subprocess
from pathlib import Path


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


def push_lab(lab_root: Path, message: str | None = None) -> dict:
    root = _git_root(lab_root)
    if not root:
        return {"ok": False, "error": "no .git above boo-lab"}
    # 1222 repo root is god-tier-metal; lab-only clone uses "."
    paths = ["tools/boo-lab/src", "tools/boo-lab/data"]
    exist = [p for p in paths if (root / p).exists()]
    if not exist:
        exist = ["src", "data"]
        exist = [p for p in exist if (root / p).exists()] or ["."]
    msg = message or "boo-lab: labels, lyrics, source"
    logs: list[str] = []
    steps = [
        (["git", "-c", "core.safecrlf=false", "add", "-A", "--", *exist], True),
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
