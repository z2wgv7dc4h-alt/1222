# STATUS

Wiring only. Listen is not a pytest row.

Active work is the lab: `tools/boo-lab` — see `tools/boo-lab/CURRENT.md` (**342 tests**).

| Area | State | Note |
|---|---|---|
| boo-lab (`tools/boo-lab`) | ACTIVE | keepers/drafts, studio spectrogram, witnesses, agree/compare/JAMS; fail-closed keeper law + atomic writes; `boo-lab interns` runs the whole chain cache-first |
| boo-lab interns pass | WIRED+TESTED | `interns [--album/--steps]` order `stems→beats→structure→drums→vocals→lyrics→sync→extract→figures→compare→learn→status`; resumable, failure-isolated, drafts only |
| boo-lab GPIF reader | WIRED+TESTED | `gpif.py` parses GP7/GP6 `.gp`/`.gpx` `score.gpif` natively (tracks/tuning/instrument, masterbars/time-sig/repeats/sections, beats, notes with computed midi + articulations); flat GP8/alphaTab + nested; `gpif --path` CLI; no conversion |
| boo-lab sync GP7 preference | WIRED+TESTED | `sync` clocks a matching `.gp`/`.gpx` over a sibling `.gp5` (`gpif.note_events`); `.gp5` stays guitarpro; thresholds/rate path unchanged; `gpif_to_gp5` unused |
| boo-lab tab-notes packs | WIRED+TESTED | `tabnotes.py` reads an operator `.zip`/folder (`notes`+`timeline`+`raw`+`video_points`); `ingest` unpacks to `data/tabnotes/<id>/` + `tabnotes_index.jsonl`; `sync` clocks guitar onsets (audio grid) | 
| boo-lab GP matcher | WIRED+TESTED | `_key` strips space-numbered track + band prefixes; `_gp_candidates` scores exact/substring + lead-number + GP7 bonus; one GP → one FLAC; full Discovery/AHP/Eternal Reign GP7 packs win; `map.csv` 52 `match=yes`, `sync` 14/52 |
| Studio beat grid + Snap | WIRED+TESTED | `data/beats.jsonl` ticks; Snap beats snaps a dragged edge to downbeat ≤250 ms else beat ≤120 ms |
| Guess proposals | WIRED+TESTED | tab section letters/repeats (form/figure/unique); gates marker sections on `sync_ok`; snaps audio spans to the beat grid |
| boo-lab interns (allin1/beat_this/torchcrepe) | GPU | `device.py` → CUDA when present; `boo-lab doctor` checks it; allin1 via `_natten_compat` (natten + py2 + numpy + collections) |
| Engine devices Phases 0-7 | WIRED+TESTED | **820 passed, 1 skipped** |
| Labyrinth riff bank + ThemeRegistry.seed | WIRED+TESTED | `1988d22` |
| Labyrinth seed-1 demo | REJECTED | user: sounds like shit — role-bag collage |
| P8.1 `.rpp` | WIRED+TESTED | |
| P8.2-P8.8 NAM/buses/mix | MISSING | |
| P9 editor surface | WIRED+TESTED | buttons work |
| `riff_model.py` | UNUSED | do not import |
| chill/outro bank rows | EMPTY | no chill marker exists in the corpus; `labyrinth` hard-fails, tests encode it (was "silent Markov" — that path is gone) |

Do not add an X.* row. Do not tick BoO.
