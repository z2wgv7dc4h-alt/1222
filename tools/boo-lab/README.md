**Read CURRENT.md first.** Then LAW.md.

# boo-lab

Local studio: listen to FLACs, mark structure, pack clips for later learning. Nothing leaves this PC except git of **code + `data/` labels**.

Using it: [USER.md](USER.md) first (Part A to work, Part B for every button and file). This README is the developer/operator reference.

Repo on GitHub: `z2wgv7dc4h-alt/1222` under `tools/boo-lab`.

## This machine

Absolute Windows paths below are **this machine** only.

```
LAB    C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab
FLAC   C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus
GP     C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs
```

`BOO_FLAC_ROOT` must be **`audio-corpus`**, not `born_of_osiris`. New bands sit beside BoO, not inside it.

## Start

New here? Read **USER.md** first. Easiest (scans, hashes, runs the resumable beat/sync pass, then serves): run `START.bat`.

Manual equivalent (use the lab root under **This machine** above):

```
cd <lab root from "This machine">
.venv\Scripts\activate
python -m boo_lab.cli scan
python -m boo_lab.cli studio --port 8765
```

Corpus roots come from `.env` (`BOO_FLAC_ROOT` = the **corpus** root, e.g.
`...\reference\audio-corpus`, not a band folder; `BOO_GP_ROOT` = `...\reference\gp-tabs`).
Open http://127.0.0.1:8765 — Ctrl+Shift+R after HTML changes. One server only.

## Install

New machine: one shot (creates `.venv`, picks GPU-vs-CPU torch, installs core +
interns + pitch + align, then verifies).

```
cd tools\boo-lab
setup.bat --flac <FLAC_ROOT> --gp <GP_ROOT>
```

Manual equivalent, thin by default (librosa + soundfile):

```
cd tools\boo-lab
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

Optional extras (never default): `-e ".[dev]"` pytest; `-e ".[pitch]"` torchcrepe;
`-e ".[align]"` whisperx; `-e ".[intern]"` allin1 + beat-this + natten + jams + mir_eval + madmom.
None is required to pin and Save; missing interns just print a skip. (`madmom` is listed explicitly
because allin1 imports it but its package metadata omits it.)

## GPU

The interns (allin1 structure, beat_this, torchcrepe, whisperx) run on CUDA when it
is available and fall back to CPU otherwise -- `boo_lab.device.torch_device()` is the
single switch. A fresh `pip install torch` on Windows is CPU-only, which is the usual
reason a run crawls; install the CUDA wheel explicitly (cu128 covers RTX 50xx):

```
.venv\Scripts\python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Then confirm with `boo-lab doctor` (prints the torch build, `cuda=True`, GPU name, and
the exact fix for anything missing).

## Durability (why this cannot silently break again)

The intern stack is a minefield; each fix is now code or a hard pin, not a session note:

| failure | permanent fix |
|---|---|
| GPU present but everything on CPU | `boo_lab/device.py` `torch_device()`; allin1/beat_this/torchcrepe read it |
| allin1 needs NATTEN API removed in 0.17 | `boo_lab/_natten_compat.py` reimplements `natten1dqkrpb/1dav/2dqkrpb/2dav` (exact `get_window_start`/`get_pb_start` ports) and registers them |
| madmom py2 builtins + `np.int` + NumPy-2 ragged `asarray` + `collections` ABCs | `_natten_compat.install()`, now run at `import boo_lab` so `doctor`/CLI get it first |
| a fresh machine drifts to incompatible versions | `constraints.txt` + `setup.bat` |
| "is my box set up?" guessing | `boo-lab doctor` |
| a failed/zero-row run blanking a derived file | `beats`/`structure`/`sync`/`agree`/`drums`/`vocals` write atomically and only replace on a real result |
| re-running the whole analysis chain by hand (and re-paying for finished work) | `boo-lab interns` runs every step cache-first; each step is isolated so one failure never aborts the rest (`structure` reuses `work/msa/*.json`) |
| a GP7 tab ignored because `map.csv` points at a `.gp5` | sync prefers a matching `.gp`/`.gpx` (parsed natively via `gpif.py`, no conversion) and records the clocked path |
| a crash mid-Save destroying every label | every `sections.jsonl` write is atomic (`schema.write_jsonl_atomic`); Save keeps `data/sections.jsonl.bak` |
| a machine draft / unknown role-sourced as human | fail-closed schema: `is_keeper`, `canonical_role`, `stamp_box`, and the one `load_section_rows` reader |

Behavior is pinned by `tests/test_natten_compat.py`, `test_device.py`, `test_doctor.py`, plus bad-input
tests for the keeper law and Save path. Lab: **342 tests**; engine: **820 passed, 1 skipped**. Generated
outputs (`data/{drafts,beats,compare,sync,agree}.*`, `data/sections.jsonl.bak`, `*.tmp`) and
`*.egg-info/` are gitignored; the tracked asset stays `data/sections.jsonl` (human pins).

## Daily loop

One album side per session.

Primary bar: **Play · clock · Play box · Save · Undo · How**. Guess / Load drafts / Lyrics / Pack /
Snap beats / JSON / Next GP live under **Lab**; Drop / Push git / Remove album live under **Corpus**.

1. Pick a track. Clock must show full length before pinning. Use the waveform **and** the mel
   spectrogram (Wave / Spec / Both) to find edges. An empty wave shows a ghost hint
   ("Press 1 for Riff"); it disappears after the first box. New boxes come from the role pins /
   keys (1–4, I B C P) or Guess — drag only moves and resizes a box, it does not create one.
   Pins are refused until the clock shows full length, and the status bar coaches the next step.
   The How drawer opens once on first run.
2. Daily pinning needs four things per box: **role**, **figure** (`figure_id`, e.g. `riff-A`), the
   **start/end** seconds, and **heard** once you have actually listened. `form` / `uniq` /
   `inst` / `bar0` / `bar1` are optional and sit behind **More columns**. With **Snap beats** on,
   a dragged edge snaps to the nearest downbeat/beat (from `data/beats.jsonl`; run `boo-lab beats`
   once).
3. **Save.** Unheard boxes are dropped — the status line says how many, and the previous file is kept
   as `data/sections.jsonl.bak`. In-app **Undo** (button or Ctrl+Z) steps back through this
   session's edits. A box with `end <= start` is refused, never repaired. Confirm table seconds look
   like music (not `0.00–0.25`).
4. **Pack** once labels are good.
5. Old pins without `heard`: `boo-lab hear --album X --track Y` (that track only).
6. If the interns are installed: `boo-lab interns --album X` runs the whole chain in order
   (structure, beats, drums, vocals, lyrics, sync, extract, figures, tempo_hints, compare, learn,
   status), skipping what is already on disk. `sync` clocks a GP7 `.gp`/`.gpx` when one is present
   (parsed natively, no conversion), else the `.gp5`. Or run one step: `boo-lab structure
   --album X`, then `boo-lab compare --album X`.

Rules: skip **VAL** songs; never Guess a finished song; the interns (Guess / allin1 / SongFormer /
beat_this / Demucs) are optional **stencils**, not truth; `learn` does not train anything.

## The table columns

Header: `role figure form uniq inst bar0 bar1 start end source heard` (hover any header in the UI).
The secondary columns (`form` / `uniq` / `inst` / `bar0` / `bar1` / `source`) start hidden — click **More columns** above the table to reveal them. Every column still harvests on Save.

- **role** — what the section is (`intro riff hook breakdown solo chill pulse build outro`). The only required label.
- **figure** — a name for the musical idea (`riff-A`); the same idea returning keeps the same name.
- **form** — big-picture song-part letter (A/B/C…; usually `A`).
- **uniq** — tick if the idea happens only once.
- **inst** — which instrument leads (`rhythm`/`lead`/`bass`/`drums`/`synth`/`vocal`/`mix`); blank is fine.
- **bar0 / bar1** — the tab's measures (1-based); auto-filled on Save **only** when a GP tab matches, else blank.
- **start / end** — seconds in the audio.
- **source** — `human`, or a draft (`guess` / `msa-draft` / `songformer-draft`).
- **heard** — the save gate; unticked boxes are dropped.

Figure roles (`riff`/`hook`/`solo`/`pulse`) may overlap function roles (`intro`/`build`/`breakdown`/`chill`/`outro`);
two boxes of the *same* role overlapping >50 ms refuses the whole Save.

## Ingest a new band

Type the band name. Drop a **zip or folder** (not RAR). FLACs + `cover.jpg` + `.gp5` can arrive together or tabs-only.

A local **tab-notes pack** (`.zip` or folder with `notes.json` `format: tab-notes/1`) may be in the same drop: it is detected and unpacked into `data/tabnotes/<id>/`, indexed in `data/tabnotes_index.jsonl`, and never copied into the FLAC/GP roots. Put packs in the ingest drop folder or directly in `data/tabnotes/`.

Then `python -m boo_lab.cli scan` and reload. Green GP5/GP7 = matched tab.

## Commands

| cmd | what |
|---|---|
| `scan` | rebuild `data/map.csv` (fuzzy FLAC↔tab) |
| `studio` / `annotate` | UI |
| `ingest DROP --band NAME` | copy drop into corpus |
| `stems` | Demucs 6-stem separation into `work/stems` |
| `pack` | slice mix/drums/bass/other/guitar/piano/vocals/no-vox per keeper box |
| `drums [--per-track]` | drum onsets + measured `low_confidence` per keeper section, or one whole-track row per song |
| `vocals [--per-track]` | vocal melody (CREPE) per keeper section, or one whole-track row per song |
| `lyrics` | LRCLIB + WhisperX force-aligned plain lyrics |
| `interns [--album X] [--steps a,b,c]` | run the whole analysis chain in order, cache-first and failure-isolated |
| `structure` | MSA/SongFormer drafts → `data/drafts.jsonl` (allin1 optional; cache-first) |
| `beats` | beat/downbeat grid → `data/beats.jsonl` (beat_this → allin1) |
| `gpif --path FILE` | read a GP7/GP6 `.gp`/`.gpx` score (duration, bars, notes, markers, `n_with_midi`); GP7 is read natively, never converted |
| `tabnotes --path F [--json] [--index]` | read a local tab-notes pack (`.zip`/folder): tracks, both clocks, raw tuplets/bends; `--index` → `data/tabnotes_index.jsonl` |
| `gp-export` | probe `.gp`/`.gpx`: already parse (run `scan`) or record `gpx-unsupported`/`gp7-unsupported` (+ GPIF `converted`/`drops`) |
| `learn` | rebuild `data/intern_rank.json`: rank draft sources from keepers (5-song vote, F@0.5) |
| `status` | refresh the `STATUS.md` counts block from data files |
| `adapt` | rebuild `data/adapt.json`: per-album edge/role/figure calibration from heard pairs |
| `doctor` | torch/GPU + optional-intern check with install hints |
| `audit` | pin hygiene (sources, overlaps, heard, short boxes) |
| `extract` | riff bank from GP (tab) or audio fallback → `data/riffs.jsonl` |
| `gate` / `export-bank` | gated riff export |
| `report` | pipeline state → `data/corpus_health.json` |
| `holdout` | fixed whole-song train/val split → `data/holdout.csv` |
| `hear --album X --track Y` | flip `heard=true` on one song's keepers (needs both flags) |
| `sync --album X --track Y` | tab-vs-audio witness → `data/sync.jsonl` (needs both flags) |
| `hash [--album X]` | fill empty `flac_sha256` cells in `map.csv` |
| `agree --album X --track Y [--write\|--diff]` | two-pass keeper agreement |
| `compare [--album X]` | machine drafts vs human keepers |
| `export-jams --out DIR` | JAMS 0.3 (figure/function layers) |

## Outputs (all local-first)

`data/sections.jsonl` is **keepers only** (`human`/`guess-accepted`, `heard=true`). Machines
write `data/drafts.jsonl` (never `sections.jsonl`). Research side-outputs: `data/agree.jsonl`,
`data/compare.json`, `data/beats.jsonl`, `data/sync.jsonl`, `data/holdout.csv`,
`data/corpus_health.json`; JAMS under `--out`. `work/` is gitignored.

`structure` writes drafts only. `hear` and `sync` require `--album` **and** `--track`.
Optional extras: `pip install -e ".[intern]"` adds allin1, beat-this, jams, mir_eval;
`.[pitch]` torchcrepe, `.[align]` whisperx. Never default dependencies.

## Do not

Commit FLACs, GP files, `work/stems`, `.venv`, tokens. Treat Guess as a draft. Do not Guess over a finished human Save.
