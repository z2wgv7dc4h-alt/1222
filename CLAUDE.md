# God Tier Metal

<!-- Compact: keep active task id, files touched, pytest command. Drop reference hunting. -->

Local engine that writes djent / deathcore / metalcore / technical deathcore. No slam. Bar: Infant Annihilator, Born of Osiris, Veil of Maya. Periphery is a major influence -- their level of musicianship (odd-grouping displacement, legato/technical lead lines, extended-chord ambient sections, metric modulation) is a standing goal, not just a tuning reference. Python writes notes. React later. Reaper renders. No cloud writer.

## Law
- Grid is the writer. Audio models are paint after the score.
- Note must be scale-legal and a real `(string, fret)`. Unwired checks do not count.
- Seeded RNG. Same seed = same bytes.
- Guided = sliders on the same params as Pro.
- No vocals. Do not edit `../Ww`. Do not extend `123/` or `reference/claude-code-first-attempt/`.
- Do not bulk-read `/reference`. Open the one path the task names (`PORTS.md`).

## Build
```
cd engine && python -m pytest -q
```
Presets: strict JSON, discover with `*.json` glob, never a name list.

## Session
1. Read `docs/CURRENT.md` then `TASKS.md` `## Next` and `## Scope gaps tracker` — one box. The tracker mirrors the scope doc's own numbered open items so gaps aren't missed without a full re-read (see SCOPE-INDEX.md's reconciliation exception).
2. Plan mode. Implement that box only.
3. Run pytest. Paste output.
4. Stop auto-runs the close skill. You do not have to type `/close`.
5. Type `/clear` only when you want a fresh session. Do not leave auto mode on overnight.

Before a P1+ task: open `SCOPE-INDEX.md`, then only those headings in `god-tier-metal-scope.md`. Never the whole scope file.
Skills: `/close`, `/port`. Ports in `PORTS.md`.
