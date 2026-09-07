---
name: close
description: End-of-task bookkeeping. Use when a task is finished, before /clear, or when the user says wrap up / close / update docs.
---

Do not write more product code.

1. Identify the TASKS.md box you worked.
2. If pytest was not run this session, run `cd engine && python -m pytest -q` (skip if engine/ still missing and the task was folders-only).
3. Tick the box only if evidence exists. Otherwise leave it and write BLOCKED + why.
4. Rewrite `docs/CURRENT.md` (task id, status, last pytest line, one-line note, date).
5. Append 3–8 lines to `PROGRESS.md`: what changed, files, decision, next id.
6. Update only the matching row in `docs/STATUS.md`. State = WIRED+TESTED only with evidence.
7. Replace `HANDOFF.md` with the next box from `## Next` and the first sentence of what to read.
8. Git (this repo only):
   - If `.git` is missing: `git init` here. Do not init inside Ww or 123.
   - `git add` docs, engine, CLAUDE.md, TASKS.md, PLAN.md, PORTS.md, HANDOFF.md, SCOPE-INDEX.md, MAP.md, `.claude` (not `assets/`, not `reference/`, not `.claude/logs/`). Add `god-tier-metal-scope.md` if it exists.
   - `git commit -m "Pxx.x: <one line from CURRENT>"` only if there is a real diff.
   - `git push` only if `origin` already exists. Never create a GitHub repo or invent a remote.
9. Stop. Do not start the next task.
