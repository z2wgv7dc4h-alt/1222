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

## Daily loop

1. Pick a track. Clock must show full length before pinning.
2. Draw roles (overlap figure vs function freely; same role may not overlap). Give each box a `figure_id`, then tick **heard** when you have actually listened. Type times, click off the field, **Save**.
3. Confirm table seconds look like music (not `0.00–0.25`). **Unheard boxes are dropped on Save.**
4. **Pack** once labels are good. **Load drafts** pulls machine `msa-draft`/`guess` boxes in unheard for review.
5. `git add` + `commit` + `push` from `god-tier-metal` when you want a backup. The UI button is best-effort.

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
| `hear --album X --track Y` | flip `heard=true` on one song's keepers |
| `agree --album X --track Y [--write\|--diff]` | two-pass keeper agreement |
| `compare [--album X]` | machine drafts vs human keepers |
| `export-jams --out DIR` | JAMS 0.3 (figure/function layers) |

## Outputs (all local-first)

`data/sections.jsonl` is **keepers only** (`human`/`guess-accepted`, `heard=true`). Machines
write `data/drafts.jsonl` (never `sections.jsonl`). Research side-outputs: `data/agree.jsonl`,
`data/compare.json`, `data/beats.jsonl`, `data/holdout.csv`, `data/corpus_health.json`; JAMS
under `--out`. `work/` is gitignored.

Optional extras: `pip install -e ".[intern]"` adds allin1, beat-this, jams, mir_eval;
`.[pitch]` torchcrepe, `.[align]` whisperx. Never default dependencies.

## Do not

Commit FLACs, GP files, `work/stems`, `.venv`, tokens. Treat Guess as a draft. Do not Guess over a finished human Save.
