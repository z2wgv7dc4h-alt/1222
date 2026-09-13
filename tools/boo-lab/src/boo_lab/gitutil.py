from __future__ import annotations

import subprocess
from pathlib import Path


def _git_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return None


def push_lab(lab_root: Path, message: str | None = None) -> dict:
    root = _git_root(lab_root)
    if not root:
        return {"ok": False, "error": "no .git above boo-lab — init the god-tier-metal repo first"}
    paths = [
        "tools/boo-lab/src",
        "tools/boo-lab/data",
        "tools/boo-lab/work/lyrics",
    ]
    exist = [p for p in paths if (root / p).exists()]
    if not exist:
        exist = ["."]
    msg = message or "boo-lab: labels, lyrics, source"
    cmds = [
        ["git", "-c", "core.safecrlf=false", "add", "--", *exist],
        ["git", "status", "--short"],
        ["git", "commit", "-m", msg],
        ["git", "push"],
    ]
    logs = []
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
        except Exception as e:
            return {"ok": False, "error": str(e), "root": str(root), "log": "\n".join(logs)}
        out = (r.stdout or "") + (r.stderr or "")
        logs.append("$ " + " ".join(cmd) + "\n" + out.strip())
        low = out.lower()
        warn_only = ("warning:" in low) and ("fatal:" not in low) and ("error:" not in low)
        if r.returncode != 0 and cmd[1] == "commit" and "nothing to commit" in low:
            logs.append("(nothing new to commit, still pushing)")
            continue
        if r.returncode != 0 and warn_only:
            continue
        if r.returncode != 0:
            return {
                "ok": False,
                "error": out.strip()[-500:] or "git failed",
                "root": str(root),
                "log": "\n".join(logs),
            }
    return {"ok": True, "root": str(root), "log": "\n".join(logs)}
