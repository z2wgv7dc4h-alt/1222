# First-attempt failure patterns

- A validator that is not called is not done. Wire it and add a reject test in the same change.
- Tests that name presets by hand miss broken files. Glob the directory.
- No `//` in JSON.
- One class per job. Delete the twin before DONE.
- Two scale names, one interval set: aliases only, documented.
- STATUS.md and CURRENT.md may only claim what grep or pytest just showed.
