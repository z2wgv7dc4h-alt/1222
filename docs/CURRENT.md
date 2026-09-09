# CURRENT

task: X.34
phase: cross-cutting
status: DONE
last_pytest: 589 passed, 1 skipped in 13.77s
note: Direct response to the user's follow-up after X.33's pacing fix: "But a song should have insane drums and guitar in all of these genres. Does it? I want fast and heavy." Investigated rather than assuming. Guitar speed checked out (5-7 hits/sec across presets, genre-plausible for the tempos involved). Drums did NOT check out: found `drums.generate_vocabulary_informed_blast_fill` (P4.3/P4.4, real, tested, three genuine alternating-KICK/SNARE blast-beat renderers) was called for every breakdown/solo section and its real output was simply discarded -- `midi_export.py`'s own docstring admitted this outright. The existing "blast" kick style was also found to be misleadingly named -- guitar-locked, capped at ~10.8 hits/sec, not an independent fast device.

User authorized the fix ("Yes wire them in" / "I give authorisation"). X.34: reused the real, valuable alternating-role renderers (traditional/gravity/hammer) applied directly onto a section's own guitar_cells instead of the old independent-skeleton approach (which would have broken the real, load-bearing "kick/snare share guitar's exact cell count" invariant that judge()'s kick-lock scoring and X.24's post-blend re-lock both depend on). New `drums.render_blast_beat`/`render_blast_beat_for_type`/`blast_kick_cells`/`blast_snare_cells`; new `song._BLAST_FILL_ROLES`/`_BLAST_FILL_CHANCE = 0.35` (real, occasional, same precedent as X.33's half-time chance) -- replaces both kick AND snare for the chosen section, with a real, necessary post-blend re-lock interaction (blast sections are guitar-locked, so they need the same re-lock treatment as guitar-locking kick styles, including snare -- a new, deliberate, documented exception to X.24's "snare stays as generated" rule). Removed the now-superseded unused `fill`/`section["fill"]` plumbing.

Verified against real generated output: real blast sections show genuine KICK/SNARE alternation with exact cell-count alignment; combined kick+snare activity now reaches up to 13.3 hits/sec (vs the old ~10.8/sec kick-only ceiling), with real interplay instead of a flat pulse.
updated: 2026-09-09

Real Reaper-driven audio rendering (P8) remains the confirmed next lever for an actual "studio quality" claim -- still deferred per the user's own earlier explicit choice. Audit continuing: `interplay.call_and_response`, `structure.apply_half_time`, `slam.chromatic_creep` all still OPEN.
