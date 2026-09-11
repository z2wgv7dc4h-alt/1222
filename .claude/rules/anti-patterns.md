# First-attempt failure patterns

- A validator that is not called is not done. Wire it and add a reject test in the same change.
- Tests that name presets by hand miss broken files. Glob the directory.
- No `//` in JSON.
- One class per job. Delete the twin before DONE.
- Two scale names, one interval set: aliases only, documented.
- STATUS.md and CURRENT.md may only claim what grep or pytest just showed.
- One `engine/` folder only — the one with `pyproject.toml`. Source modules go directly inside it. Never `engine/engine/`.
- Do not treat PROGRESS.md or docs/archive as a backlog.
- Do not `/next` past TASKS.md ## Now.
- Labyrinth bank: one song, multi-bar tile. Role-bag bars are the failed demo.
- tools/boo-lab is the FLAC pin UI. Do not build a second one.
