**Read CURRENT.md first.** Then LAW.md.

# boo-lab

Local studio: listen to FLACs, mark structure, pack clips for later learning. Nothing leaves this PC except git of **code + `data/` labels**.

Repo on GitHub: `z2wgv7dc4h-alt/1222` under `tools/boo-lab`.

## Paths

```
LAB    C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab
FLAC   C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus
GP     C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs
```

`BOO_FLAC_ROOT` must be **`audio-corpus`**, not `born_of_osiris`. New bands sit beside BoO, not inside it.

## Start

```
cd C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab
.venv\Scripts\activate
set BOO_FLAC_ROOT=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus
set BOO_GP_ROOT=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs
python -m boo_lab.cli scan
python -m boo_lab.cli studio --port 8765
```

Open http://127.0.0.1:8765 — Ctrl+Shift+R after HTML changes. One server only.

## Install

Thin by default (librosa + soundfile).

```
cd tools\boo-lab
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

Optional extras (never default): `-e ".[dev]"` pytest; `-e ".[pitch]"` torchcrepe;
`-e ".[align]"` whisperx; `-e ".[intern]"` allin1 + beat-this + jams + mir_eval. None is
required to pin and Save; missing interns just print a skip.

## Daily loop

One album side per session.

1. Pick a track. Clock must show full length before pinning. Use the waveform **and** the mel
   spectrogram (Wave / Spec / Both) to find edges.
2. Give each box a `form` (large letter), a `figure_id` (small, e.g. `riff-A`), and a `role`;
   mark `unique` for single-use figures, `instrument` when two guitars differ. Tick **heard**
   when you have actually listened.
3. **Save** (unheard boxes are dropped). Confirm table seconds look like music (not `0.00–0.25`).
4. **Pack** once labels are good.
5. Old pins without `heard`: `boo-lab hear --album X --track Y` (that track only).
6. If the interns are installed: `boo-lab structure --album X`, then `boo-lab compare --album X`.

## Ingest a new band

Type the band name. Drop a **zip or folder** (not RAR). FLACs + `cover.jpg` + `.gp5` can arrive together or tabs-only.

Then `python -m boo_lab.cli scan` and reload. Green GP5 = matched tab.

## Commands

| cmd | what |
|---|---|
| `scan` | rebuild `data/map.csv` (fuzzy FLAC↔tab) |
| `studio` / `annotate` | UI |
| `ingest DROP --band NAME` | copy drop into corpus |
| `stems` | Demucs 6-stem separation into `work/stems` |
| `pack` | slice mix/drums/bass/other/guitar/piano/vocals/no-vox per keeper box |
| `drums` | per-section drum onsets + measured `low_confidence` |
| `vocals` | per-section vocal melody (CREPE) |
| `lyrics` | LRCLIB + WhisperX force-aligned plain lyrics |
| `structure` | MSA/SongFormer drafts → `data/drafts.jsonl` (allin1 optional) |
| `beats` | beat/downbeat grid → `data/beats.jsonl` (beat_this → allin1) |
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
