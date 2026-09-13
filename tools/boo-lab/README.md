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
2. Draw roles (overlap different roles only). Type times, click off the field, **Save**.
3. Confirm table seconds look like music (not `0.00–0.25`).
4. **Pack** once labels are good.
5. `git add` + `commit` + `push` from `god-tier-metal` when you want a backup. The UI button is best-effort.

## Ingest a new band

Type the band name. Drop a **zip or folder** (not RAR). FLACs + `cover.jpg` + `.gp5` can arrive together or tabs-only.

Then `python -m boo_lab.cli scan` and reload. Green GP5 = matched tab.

## Commands

| cmd | what |
|---|---|
| `scan` | rebuild `data/map.csv` (fuzzy FLAC↔tab) |
| `studio` | UI |
| `ingest DROP --band NAME` | copy drop into corpus |
| `pack` | slice mix/stems per human box |
| `lyrics` | LRC fetch |

## Do not

Commit FLACs, GP files, `work/stems`, `.venv`, tokens. Treat Guess as a draft. Do not Guess over a finished human Save.
