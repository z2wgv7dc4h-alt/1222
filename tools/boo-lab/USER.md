# boo-lab

This is the operator guide. LAW.md = rules. CURRENT.md = internals. README.md = install.

A bench for marking parts of songs you already own.

You listen, you draw boxes on the waveform, you tick **heard**, you **Save**.
Those saved boxes are the product.

This program does not write music. It does not train a new AI each time you
click. Computer boxes are suggestions. Only heard + Save is truth.

Read **Part A** to work. Read **Part B** when you need to know what a button
or file is for.

Audio and Guitar Pro files stay on this PC. Git only stores code and labels.

---

# Part A — work

## Open

Double-click `START.bat` in the `boo-lab` folder.
It rescans, hashes new FLACs, and runs the beat/sync pass before opening the
studio. That pass is resumable and safe to re-run; it only fills what is missing.

Browser: http://127.0.0.1:8765
Old page: Ctrl+Shift+R.

From a terminal:

    cd tools/boo-lab
    .venv/Scripts/activate
    python -m boo_lab.cli scan
    python -m boo_lab.cli studio

## Mark

1. Click a song on the left. Skip anything tagged **VAL**.
2. Wait until the clock shows the real song length. Not `0:00 / —`.
3. Press **1** (Riff) or another role button. A box appears.
4. Drag the box to cover that part. Drag does not create a box — the button does.
5. If the same idea comes back, reuse the same **figure** name (`riff-A`).
   A new idea gets a new name (`riff-B`).
6. Tick **heard** only after you listened to that box.
7. Press **Save**. Boxes without heard are deleted.

One album per sitting is enough.

**Keys:** Space play · 1 riff · 2 hook · 3 breakdown · 4 solo · I intro ·
B build · C chill · P pulse · S save · J / K songs · Delete box · Ctrl+Z undo ·
? help.

## Lanes and right-click

Each role has its own lane on the wave (Intro at the top, Outro at the bottom).
A box can only sit in its role's lane, so a Riff + Breakdown + Outro stack
shows as three bars at once. Click a bar to select its row; click a row to
light its bar. Right-click a bar to edit role / figure / heard / unique / inst,
Play box, Split at playhead (when the playhead is inside), or Delete.
Double-click a bar to toggle heard. The All / Figures / Functions buttons only
hide bars and rows — they never edit. synth is an instrument (inst), not a role.

## Ignore until you need them

Guess, Load drafts, Lyrics, Pack, Snap, JSON, Drop, git, Remove album,
More columns.

**VAL** = exam song. Do not mark it.

Guess refuses a song that already has saved boxes.
Selected song is highlighted in the left list.

## Stuck

Clock 0:00 / — means wait. Do not draw yet.
Empty song list: run scan. Check .env roots in README.
Save refused: read the status line (overlap, unheard, tiny box).
Last Save was wrong: Undo / Ctrl+Z. Save also left data/sections.jsonl.bak.

---

# Part B — the lab

## The rule

Machines may propose boxes. They may not write the gold file.
heard + Save is the only way a box becomes official.

## Two kinds of box

Gold (keeper) — you heard it, you saved it. Lives in data/sections.jsonl.
Source is human or guess-accepted.

Stencil (draft) — Guess or an intern drew it. Lives in data/drafts.jsonl.
It appears on the wave unheard. It dies on Save unless you tick heard.

Tick heard on a Guess box and Save → gold, marked guess-accepted.
That is how you agree with a suggestion. Dragging it first is fine.
Nothing trains a neural net when you do that.

## Roles

Ideas (figures): riff, hook, solo, pulse — a thing you can hum or play.
Jobs (functions): intro, build, breakdown, chill, outro — what that
stretch is doing in the song.

A breakdown may sit on the same guitar as a riff (two boxes, two roles).
Two boxes of the same role may not overlap. Save will refuse.

figure — name of the idea (riff-A). Reuse it when the idea returns.
form — optional A/B/C for the large shape of the song. Under More columns.

## The page

Left: songs. Tags: FLAC, GP5, no tab, tab off-clock, VAL.
Middle: waveform (and optional spectrogram). Boxes live here.
Role pins: create a box.
heard: the gate.
Lab: Guess, drafts, lyrics, Pack, Snap.
Corpus: add files, git, delete an album.

## Guess, drafts, interns

An intern is an optional helper that proposes structure or extra analysis.

Guess — tab section markers if the clock matched, plus drum breakdowns.
allin1 — mix cut into parts (msa-draft).
SongFormer — newer mix cutter (songformer-draft).
beat_this — beat grid for Snap.
Demucs — split stems for Pack and some analysis.
torchcrepe / whisperx — melody / lyrics.

None of these are required to mark by ear.

You can run one intern at a time, or all of them in order with one command
(`boo-lab interns`). That command skips work already done, so it is safe to
run again. It only ever writes drafts.

Do not press Guess on a song you already finished.
Do not trust Guess when the list says tab off-clock.
Load drafts pulls intern boxes for this song. Still unheard.

## When the tab matches the recording

sync checks whether the Guitar Pro timeline lines up with the FLAC.
Match (sync_ok) → Guess may use tab markers.
No match → those markers are dropped. You can still mark by ear.
A small stretch (tempo a bit fast/slow) may be corrected.
A missing intro or extra repeat will not be fixed. That is a tab problem.

scan only rebuilds the list of files after you add FLACs or .gp5 tabs.
It does not label and does not align clocks.

The code reads GP5. GP7 / .gpx must be saved as GP5 first
(TuxGuitar is free), then scan.
If the song already shows GP5, you can ignore GP7.

## Learn and adapt (not training)

learn is a scoreboard. After five non-VAL songs that have both your
pins and some drafts, it may set prefer= to the helper that matched you
best. VAL songs do not vote. No weights are trained.

adapt (when data/adapt.json exists) remembers how you changed Guess
boxes on that album and nudges the next Guess on the same album.
Still a draft. Still needs heard + Save.
One album cannot teach another. VAL must not train other albums.

A later model would train on short tab cells, not on mixed FLACs.

## Figures and cells

figures — from a GP5, suggest repeating-idea names. Dropdown only.
cells — one short 2-4 bar example per figure name you kept, not a 40-second box.

## VAL / holdout

Some songs are reserved to test helpers later. The UI marks them VAL.
Do not mark them. They do not vote for prefer=.

## Pack, stems, lyrics

Pack cuts each saved box to disk (mix + stems) so you can listen later.
**JAMS** (Lab → JAMS) writes your saved boxes as one `.jams` per song under `work/jams/` — an
interchange format for MIR tools. Keepers only; refuses when there are no keepers or the song is VAL.
Lyrics are optional timed lines. They are not structure gold.

## Commands

    python -m boo_lab.cli doctor
    python -m boo_lab.cli scan
    python -m boo_lab.cli studio
    python -m boo_lab.cli interns
    python -m boo_lab.cli interns --album ALBUM
    python -m boo_lab.cli learn
    python -m boo_lab.cli sync --album ALBUM --track TRACK
    python -m boo_lab.cli figures --album ALBUM --track TRACK
    python -m boo_lab.cli compare

Short studio titles are fine; the lab maps year-prefixed folder names.

## Do not

Mark VAL songs.
Guess a finished song.
Trust Guess on tab off-clock.
Expect unheard boxes to survive Save.
Let a helper write sections.jsonl.
Train a song model on raw mixed FLACs.
Scrape tabs or commit audio / Guitar Pro files.

## Four lines

Clock must show the length.
Buttons create boxes; drag only fits them.
heard + Save is truth.
Guess is a stencil.
