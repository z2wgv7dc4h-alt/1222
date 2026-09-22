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

Double-click START.bat. Browser opens. Prep may run in another window; ignore it.

Browser: http://127.0.0.1:8765 — Ctrl+Shift+R after an HTML change.

## Mark

Double-click a box (or its table row) to zoom that part.
The same double-click starts an **A–B loop** over the box.
Click away from the looping box (or Esc / Space / Play box once) to stop the loop.
Drag the box edges to trim it. Play box still plays once without looping.
The right-click edit panel closes on an outside click.
Double-click has ONE meaning: zoom the box and start its A–B loop. **heard** is a
checkbox or the right-click menu. The **How** button in studio is this Mark list —
VAL may be pinned by ear.

1. Click a song on the left.
2. Wait until the clock shows the real song length. Not `0:00 / -`.
3. Press **1** (Riff) or another role button. A box appears.
4. Drag the box to cover that part. Drag does not create a box — the button does.
5. If the same idea comes back, reuse the same **figure** name (`riff-A`).
   A new idea gets a new name (`riff-B`).
6. Tick **heard** only after you listened to that box.
7. Press **Save**. Boxes without heard are deleted.

One album per sitting is enough.

VAL songs do not train and do not vote prefer=. You may pin them by ear. Rebirth is VAL. The old six Rebirth rows were invalid times and were deleted. Re-pin by ear; do not restore the old windows.

**Keys:** Space play · 1 riff · 2 hook · 3 breakdown · **T blast** · 4 solo · I intro · B build · C chill · P pulse · S save · J / K songs · Delete box · Ctrl+Z undo · Esc stops box loop / closes right-click · ? help.

## Lanes and right-click


Each role has its own lane on the wave (Intro at the top, Outro at the bottom).
A box can only sit in its role's lane, so a Riff + Breakdown + Outro stack
shows as three bars at once. Click a bar to select its row; click a row to
light its bar. Right-click a bar to edit role / figure / heard / unique / inst,
Play box, Split at playhead (when the playhead is inside), or Delete.
The All / Figures / Functions buttons only hide bars and rows — they never
edit. synth is an instrument (inst), not a role.

## Ignore until you need them

Guess, Load drafts, Lyrics, Pack, Snap, JSON, Drop, git, Remove album,
More columns.

Guess refuses a song that already has saved boxes.
Do not Guess a song whose list row says tab off-clock. Most tabs in this corpus are off-clock; pin those by ear.
Selected song is highlighted in the left list.

Do not pin the full-album FLAC row (the file sitting next to a `tracks/` folder). Pin the numbered track.
After a scan-rule change, run `python -m boo_lab.cli scan` again so local `map.csv` drops stub/mix `match=yes` rows.

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
Sources: guess, gp-marker, msa-draft, songformer-draft, keeper-model, tabnotes-density, tabnotes-structure, tabnotes-phrase, blast-hint, figure-hash.
It appears on the wave unheard. It dies on Save unless you tick heard.

Tick heard on a Guess box and Save → gold, marked guess-accepted.
That is how you agree with a suggestion. Dragging it first is fine.
Save may also fire a background fine-tune of the structure predictor (see
Learning); it never retrains the frozen interns.

## Roles

Ideas (figures): riff, hook, solo, pulse — a thing you can hum or play.
Jobs (functions): intro, build, breakdown, **blast**, chill, outro — what
that part does in the song.

- **Breakdown** = half-time / pit slam (drums).
- **Blast** = full-speed / blastbeat drums (opposite of breakdown). Pin **T**.
- Both may sit on the same guitar as a riff (two boxes, two roles).
- **on figure** (optional, on a function box) = the figure_id it rides
  (e.g. blast on `B` / `riff-B`). Do not invent names like `riff-blast-A`.

Two boxes of the same role may not overlap. Save will refuse.

figure — name of the idea (`riff-A`, or tab letter `B`). Reuse it when the idea returns.

## The page

Left: songs. Badges: FLAC, GP7/GP5/Tab, no tab, Pack/TN, VAL, off-clock, mix, album.
Middle: waveform (and optional spectrogram). Boxes live here.
Role pins: create a box.
heard: the gate.
Lab: Guess, drafts, lyrics, Pack, Snap.
Corpus: add files, git, delete an album.

## Add music (Corpus → Ingest)

Drop a **file, zip, or folder** on the Corpus → Ingest box (or use
**Add file(s)** / **Add folder**). A lone `.flac` / `.wav`, GP tab, tab-notes
`.zip`, `notes.json`, or a folder that is a pack all work — not only an
archive of mixed stuff.

Band is optional. Leave it blank and it is inferred from the file or pack name
(`Born_Of_Osiris-Elimination`, `Born Of Osiris - Song`,
`born_of_osiris__the_new_reign__s32187`). Type a band only to force one.

Ingest then preps what landed — scan, hash, and `beats,sync` (scoped to the
album when one is known) — and refreshes the song list. No studio restart. A
prep error is shown in the status line; the copied files still stay.

## Guess, drafts, interns

START will not open a **second** `boo-lab interns` window if one is already running. Beats merge into `beats.jsonl` and cache under `work/beats/`; structure can print `CACHE structure (drafts unchanged)` when prep is already done.


An intern is an optional helper that proposes structure or extra analysis.

Guess — tab section markers if the clock matched, plus drum breakdowns.
allin1 — mix cut into parts (msa-draft).
SongFormer — newer mix cutter (songformer-draft).
structure predictor — your own keeper-trained boxes (keeper-model); learns from Save.
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

When the tab has real section markers (A, B, C, B-Solo, …) and the clock matched,
those markers are the structure. Guess gives one box per marker and will not bury
them under a pile of short 2-bar figure hashes — a `B-Solo` marker becomes a solo
box named `solo-B`, repeats share the same figure. Only unmarked gaps may get a
figure draft. Audio still adds breakdown/blast overlays on top.

When there is **no GP at all** (a FLAC + a tab-notes pack, like Mindful), a
matched pack is the spine instead. Guess reads the pack's own guitar phrases and
proposes real `riff` boxes with simple `riff-A` / `riff-B` / `riff-C` ids by
order (`source=tabnotes-structure`), plus the drum breakdown/blast overlays. It
does **not** invent GP-style A1/B letters the pack never had, and it still caps
the figure-hash flood against that spine. A GP marker tab always wins when it
exists.

scan only rebuilds the list of files after you add FLACs or GP tabs.
It does not label and does not align clocks.

The lab reads GP7 `.gp` / `.gpx` directly (parsed score, no conversion) and
still reads `.gp5`. When a song has both, sync clocks the GP7. Drop the GP7
beside the GP5 or under `gp-tabs/gp7/` — no TuxGuitar, no export step.
Inspect one with `boo-lab gpif --path FILE` (duration, bars, notes, midi).

A local tab-notes pack (`data/tabnotes/`) adds three helpers, all only when
`sync` matched: `tabnotes-drafts` turns busy guitar passages into unheard
`riff` drafts and half-time drums into `breakdown` drafts (`source=
tabnotes-density`, in `data/drafts.jsonl`); Guess notes the song's
`tempo/meter cuts` and aligns its box edges to them; and the structure
predictor reads palm-mute / hammer density from the pack, so `predict` gets
better with it. Re-run `boo-lab interns` after a sync to pick these up.

## Learning (optional predictor)

**Structure predictor (v1 scaffold):** optional draft source `keeper-model`. Needs non-holdout keepers before it is useful. Rebirth-only labs skip train unless `holdout_fallback` is explicit. After heard+Save it may fine-tune in the background; drafts only, never keepers. Frozen interns do not retrain.


**adapt / learn (calibration):** timing/role/breakdown nudges; after 5 songs, which
stencil to trust. Not musical IQ. Compare scores on VAL songs are diagnostics, not
votes. Live Rebirth pins were wiped; re-pinning is human-only.

**Frozen interns never retrain** from your marks (Demucs, WhisperX, allin1, beat_this, …).

Detail: CURRENT.md → Structure predictor.

## Figures and cells

figures — from a GP5 or GP7 tab, suggest repeating-idea names. Dropdown only.
cells — one short 2-4 bar example per figure name you kept, not a 40-second box.

## VAL / holdout

VAL songs do not train and do not vote prefer=. You may pin them by ear. Rebirth is VAL. The old six Rebirth rows were invalid times and were deleted. Re-pin by ear; do not restore the old windows.

## Pack, stems, lyrics

**Pack badge** — song list shows Pack/TN when a local tab-notes pack matches (filter: Pack).


Stem chips (drums / bass / guitar / piano / other / vocals) are now a real
multi-toggle **listen**. Turn one or more on and the main Play / Play box / A–B
loop plays the sum of exactly those stems — the full mix is muted for real. Turn
all off and you hear the full mix again. Chips for stems this song has not
cached are greyed out. The lower lane still shows one stem's waveform; toggling
a chip on shows that stem there.

The song list badges a local tab-notes pack: **Pack** when the pack is the only
tab (a FLAC + pack, like Mindful), **TN** when it supplements a GP tab. The
**Pack** filter shows only those songs. Nothing is committed; the pack itself
stays under `data/tabnotes/`.


Pack cuts each saved box to disk (mix + stems) so you can listen later.
**JAMS** (Lab → JAMS) writes your saved boxes as one `.jams` per song under `work/jams/` — an
interchange format for MIR tools. Keepers only; refuses when there are no keepers or the song is VAL.
Lyrics are optional timed lines. They are not structure gold.
When a vocals stem is cached, WhisperX force-aligns the LRCLIB words onto that
stem and its real times win over LRCLIB's; without a stem, LRCLIB times stand.

## Commands

    python -m boo_lab.cli init-map
    python -m boo_lab.cli scan
    python -m boo_lab.cli hash
    python -m boo_lab.cli ingest
    python -m boo_lab.cli studio
    python -m boo_lab.cli annotate
    python -m boo_lab.cli stems
    python -m boo_lab.cli pack
    python -m boo_lab.cli drums
    python -m boo_lab.cli vocals
    python -m boo_lab.cli lyrics
    python -m boo_lab.cli structure
    python -m boo_lab.cli beats
    python -m boo_lab.cli interns
    python -m boo_lab.cli gpif
    python -m boo_lab.cli tabnotes
    python -m boo_lab.cli tabnotes-drafts
    python -m boo_lab.cli tempo-hints
    python -m boo_lab.cli figures
    python -m boo_lab.cli gp-export
    python -m boo_lab.cli extract
    python -m boo_lab.cli gate
    python -m boo_lab.cli export-bank
    python -m boo_lab.cli pack-notes
    python -m boo_lab.cli compare
    python -m boo_lab.cli agree
    python -m boo_lab.cli learn
    python -m boo_lab.cli adapt
    python -m boo_lab.cli predict-train
    python -m boo_lab.cli predict
    python -m boo_lab.cli sync
    python -m boo_lab.cli hear
    python -m boo_lab.cli holdout
    python -m boo_lab.cli export-jams
    python -m boo_lab.cli report
    python -m boo_lab.cli status
    python -m boo_lab.cli audit
    python -m boo_lab.cli doctor

Short studio titles are fine; the lab maps year-prefixed folder names.

## Do not

Guess a finished song.
Trust Guess on tab off-clock.
Expect unheard boxes to survive Save.
Let a helper write sections.jsonl.
Train a song model on raw mixed FLACs.
Scrape tabs or commit audio / Guitar Pro files.
Convert GP7 to GP5 — the lab reads GP7 directly.

## Four lines

Clock must show the length.
Buttons create boxes; drag only fits them.
heard + Save is truth.
Guess is a stencil.

