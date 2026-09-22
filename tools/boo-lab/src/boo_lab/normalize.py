"""Comparable song keys for the inconsistent on-disk tokens.

These produce keys for MATCHING only -- they are never new filenames and never
rewrite `holdout.csv` / `identity.csv`. `identity.album_id_for` still wins when
a pair is present; these are the fallback when only a loose title (or a
different separator/delta spelling) is available.

Disk tokens seen in this corpus:
    "01 - Rebirth"   "04 Devastate"   "01 Follow the Signs"
    "05 - ∆bsolution"   "01 - M∆chine"
"""
from __future__ import annotations

import os
import re

# The TWDA display deltas (INCREMENT / GREEK delta, upper / lower) read as "a":
# "M∆chine" -> "machine", "∆bsolution" -> "absolution", "∆eon" -> "aeon".
_DELTAS = str.maketrans({"∆": "a", "Δ": "a", "δ": "a"})

# Leading track number: "01 - ", "04 ", "01 ", "04. ", "04_ ".
_LEAD_NUM = re.compile(r"^\s*\d{1,3}\s*[-._]?\s*")
_YEAR_PREFIX = re.compile(r"^\s*\d{4}\s*[-._]?\s*")
_BAND_PREFIX = re.compile(r"^\s*born[\s._-]*of[\s._-]*osiris\b[\s._-]*")
_PAREN = re.compile(r"\([^)]*\)")
_NON_KEY = re.compile(r"[^0-9a-z]+")
_SPACES = re.compile(r"\s+")


def _compact(text: str) -> str:
    text = _NON_KEY.sub(" ", text).strip()
    return _SPACES.sub(" ", text)


def track_key(s) -> str:
    """Comparable track key: no extension, no leading number, casefolded,
    TWDA `∆` read as `a`, punctuation collapsed. Not a filename."""
    if not s:
        return ""
    name = os.path.splitext(str(s))[0]
    name = _LEAD_NUM.sub("", name)
    name = name.translate(_DELTAS).casefold()
    return _compact(name)


def album_key(s) -> str:
    """Loose album key: casefolded, year prefix and `Born Of Osiris -` band
    prefix stripped, trailing `(FLAC)` / `(Fye Edition)` / `(2015)` style
    parentheticals dropped. `identity.album_id` still wins when present."""
    if not s:
        return ""
    name = str(s).translate(_DELTAS).casefold()
    name = _YEAR_PREFIX.sub("", name)
    name = _BAND_PREFIX.sub("", name)
    name = _PAREN.sub(" ", name)
    return _compact(name)
