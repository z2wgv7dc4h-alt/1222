# boo-lab

Local lab: play your FLACs, pin Riff / Hook / Breakdown / Solo, pull riffs from Guitar Pro you already own. Feeds God Tier Metal. Not a writer. Nothing leaves this PC.

## Windows

1. Clone this repo.
2. Double-click `START.bat`.
3. First run opens `.env` — set:

```
BOO_FLAC_ROOT=C:\path\to\your\flacs
BOO_GP_ROOT=C:\path\to\your\gp
```

4. Save. Run `START.bat` again. Browser opens http://127.0.0.1:8765

Optional Guess button: `INSTALL-GUESS.bat` (allin1, heavy).

## Keys

Space play. 1 riff. 2 hook. 3 breakdown. 4 solo. G guess. S save. N next. Click the wave to seek.

Green dots in the list = file found. Pins fill the song until the next pin.

## After an album

```
.venv\Scripts\activate
boo-lab extract --album "The Discovery"
boo-lab export-bank --out ..\god-tier-metal\engine\data\riff_bank.json
```

Copy any existing bank first. Do not train models. Do not add FLACs or GP files to git.

## Layout

```
data/map.csv         drafted by scan
data/sections.jsonl  your pins
data/riffs.jsonl     extract
.env                 your disk paths (gitignored)
```
