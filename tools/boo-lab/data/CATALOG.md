# BoO corpus note — 2026-09-12

Tabs: uploaded zip (91 Guitar Pro files after ignoring songsterr-downloader source).
FLACs: `C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus\born_of_osiris`

Do not trust folder titles on the FLAC disk. Two folders are misnamed.

## Folder labels vs real albums

| Disk folder | Actual album |
|---|---|
| 2009 - A Higher Place | A Higher Place (2009) — correct |
| 2013 - Tomorrow We Die ∆live | Tomorrow We Die Alive (2013) — correct |
| Born Of Osiris - The Eternal Reign - 2017 | The Eternal Reign (2017) remake of The New Reign — correct |
| **Born of Osiris - Soul Sphere (2015)** | **The Discovery (2011)** including FYE Misha mixes. Not Soul Sphere. |
| **Born of Osiris - The Discovery (Fye Edition) (FLAC)** | **The Simulation (2019)** 8 tracks. Not The Discovery. |
| Born of Osiris - The Simulation (2019) | The Simulation (2019) — same 8 files as the FYE-misnamed folder |

Soul Sphere (2015) FLACs are **not in this tree**. Tabs exist for some of those songs (Illuminate, Resilience, Goddess of the Dawn, Free Fall).

## FLACs present (use `tracks/` when it exists)

A Higher Place 2009: Rebirth, Elimination, The Accountable, Now Arise, Live Like I'm Real, Starved, Exist, Put To Rest, A Descent, A Higher Place, An Ascent, Thrive, Faces Of Death.

TWDA 2013: Machine, Divergency, Mindful, Exhilarate, Absolution, The Origin, Aeon III, Imaginary Condition, Illusionist, Source Field, Vengeance.

Eternal Reign 2017: Rosecrance, Empires Erased, Open Arms To Damnation, Abstract Art, The New Reign, Brace Legs, Bow Down, The Takeover, Glorious Day.

The Discovery 2011 (in the “Soul Sphere” folder): Follow the Signs … Behold + 3 Misha mixes. Skip mixes for the bank.

The Simulation 2019: The Accursed … One Without the Other. Two copies on disk; pick one folder.

## Tab sources in the zip (duplicates)

- `gprotab/` 10
- `gtptabs/extracted/born_of_osiris/` 16
- `musicnoteslib/` 11
- zip root `Born_Of_Osiris-*-sNNNN.gp` 54 (Songsterr-style ids)

Same song often appears 2–4 times. Prefer the **largest** full-song file. Skip `*_solo*`, `*_intro*`, `*bass*`, `*cover*`, files under ~10 KB (stubs).

## Coverage vs FLACs

Has FLAC + at least one usable-looking tab: Machine, Divergency, Exhilarate, Absolution, The Origin, Aeon III, Illusionist, Vengeance, Bow Down, Brace Legs, Empires Erased, Abstract Art, Rosecrance, Follow the Signs, Singularity, Ascension, Devastate, Recreate, Two Worlds of Design, Dissimulation, Automatic Motion, Last Straw, Regenerate, XIV, Behold, Exist, Now Arise, A Descent, The Takeover, Live Like I'm Real, Under the Gun, Analogs in a Cell.

FLAC, **no tab in this zip**: Rebirth, Elimination, The Accountable, Starved, Put To Rest, A Higher Place, An Ascent, Thrive, Faces Of Death, Mindful, Imaginary Condition, Source Field, Open Arms To Damnation, The New Reign, Glorious Day, A Solution, Shaping the Masterpiece, The Omniscient, The Accursed, Disconnectome, Cycles of Tragedy, Recursion, Silence the Echo, One Without the Other.

Tab, **no FLAC here** (later / other albums): Illuminate, Resilience, Goddess of the Dawn, Free Fall, White Nile, Shadowmourne, Poster Child, Through Shadows, Elevate, Threat of Your Presence, The Other Half of Me.

Tiny / fragment tabs (do not bank as a song): Behold outro solo, Illusionist.gp4 (4 KB), Exhilarate.gp5 (3 KB — use exhilarate_2), Brace_Legs.gp5 1.5 KB, Follow the sings solo cover, Devastate Solo, Behold Sweep, Threat intro, Outro-s69180.

## Preferred GP when several exist

Use these as `map.csv` gp when you copy the zip onto the rig:

| Track | Pick |
|---|---|
| Machine | largest of machine_2.gpx / Machine-s383457 / 7-string version |
| Divergency | gprotab or gtptabs divergency.gp5 (145 KB) |
| Exhilarate | exhilarate_2.gp5 (132 KB), not the 3 KB file |
| Aeon III | aeon_iii.gp5 |
| The Origin | the_origin.gp5 |
| Follow the Signs | gtptabs follow_the_signs.gp5 (168 KB), not solo/bass variants |
| Bow Down | bow_down.gp5 |
| Empires Erased | musicnoteslib Empires_Erased.gpx or gtptabs jerome cover — mark match=unknown until you listen |
| Behold | full song tab if any; behold_outro_solo is not the song |

## Zip junk (ignore)

`songsterr-downloader/` (~4700 files, app + test json). `New folder/CLAUDE.md`. Nested `gtptabs/born_of_osiris.zip` if already extracted.
