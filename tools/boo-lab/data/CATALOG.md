# Corpus note

Multi-band tree. Put a new band under `audio-corpus/<band>/`, never inside
`born_of_osiris/`. BoO remains the first band.

# BoO disk identity

FLACs live under `<CORPUS>/born_of_osiris`. Some folder titles are wrong — the
file contents are the truth, not the folder name. This page tracks the real
FLACs on disk (grounded in `data/flacs.csv` at scan time).

## Folder labels vs real albums

| Disk folder | Actual album |
|---|---|
| 2009 - A Higher Place | A Higher Place (2009) — correct |
| 2013 - Tomorrow We Die ∆live | Tomorrow We Die Alive (2013) — correct |
| Born Of Osiris - The Eternal Reign - 2017 | The Eternal Reign (2017) remake of The New Reign — correct |
| Born of Osiris - Soul Sphere (2015) | Soul Sphere (2015) — correct title, 12 real Soul Sphere tracks (The Other Half of Me … The Composer) |
| Born of Osiris - The Discovery (Fye Edition) (FLAC) | The Discovery (2011) — bad folder title, real Discovery 15 tracks + 3 Misha Mansoor demo mixes |
| Born of Osiris - The Simulation (2019) | The Simulation (2019) — correct, 8 tracks |

A **2026-09-12** version of this table said the Soul Sphere folder was The
Discovery and the FYE folder was The Simulation. That was **wrong** — the two
rows were swapped. The table above is the corrected one; do not restore the old
story. Soul Sphere (2015) FLACs **are** in this tree (under the Soul Sphere
folder), not missing.

## FLACs present

`<CORPUS>/born_of_osiris/<folder>` track files:

- **A Higher Place (2009)** — 13 tracks: Rebirth, Elimination, The Accountable,
  Now Arise, Live Like I'm Real, Starved, Exist, Put To Rest, A Descent,
  A Higher Place, An Ascent, Thrive, Faces Of Death (+ a full-album file).
- **Tomorrow We Die Alive (2013)** — 11 tracks: M∆chine, Divergency, Mindful,
  Exhil∆r∆te, ∆bsolution, The Origin, ∆eon III, Im∆gin∆ry Condition,
  Illusionist, Source Field, Venge∆nce (+ a full-album file).
- **Soul Sphere (2015)** — 12 tracks: The Other Half of Me, Throw Me in the
  Jungle, Free Fall, Illuminate, The Sleeping and the Dead, Tidebinder,
  Resilience, Goddess of the Dawn, The Louder the Sound the More We All Believe,
  Warlords, River of Time, The Composer.
- **The Discovery (2011)** — 15 tracks: Follow the Signs, Singularity, Ascension,
  Devastate, Recreate, Two Worlds of Design, A Solution, Shaping the Masterpiece,
  Dissimulation, Automatic Motion, The Omniscient, Last Straw, Regenerate, XIV,
  Behold; plus 3 Misha Mansoor demo mixes (Follow the Signs, Singularity,
  Recreate) at the end.
- **The Eternal Reign (2017)** — 9 tracks: Rosecrance, Empires Erased,
  Open Arms To Damnation, Abstract Art, The New Reign, Brace Legs, Bow Down,
  The Takeover, Glorious Day.
- **The Simulation (2019)** — 8 tracks: The Accursed, Disconnectome,
  Cycles of Tragedy, Under the Gun, Recursion, Analogs in a Cell,
  Silence the Echo, One Without the Other.

## Operator rules

- Do not trust folder titles blindly — check the file contents/album.
- Skip `*_solo*`, tiny stubs, cover/bass-only tabs, and Misha mixes when banking
  a song.
- Prefer the largest full-song GP when duplicates exist.
- New bands sit under `audio-corpus/<band>/`, never inside `born_of_osiris/`.
