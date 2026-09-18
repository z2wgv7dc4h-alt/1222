"""Guard the lab -> engine role map stays complete and fail-closed.

`pulse` has no real engine equivalent (engine/riff_bank has no synth-loop
role), so its entry exists with value `None` -- callers can still tell a known
lab role from an unknown one. Unknown roles are absent, i.e. fail closed."""
from __future__ import annotations

from boo_lab import extract
from boo_lab.schema import ROLES

_EXPECTED = {
    "intro": "intro",
    "build": "build",
    "riff": "verse",
    "hook": "chorus",
    "breakdown": "breakdown",
    "solo": "solo",
    "chill": "chill",
    "pulse": None,
    "outro": "outro",
}


def test_role_map_is_exactly_the_lab_vocabulary():
    assert set(extract._BOO_LAB_TO_ENGINE_ROLE) == set(ROLES)
    assert extract._BOO_LAB_TO_ENGINE_ROLE == _EXPECTED


def test_every_mapped_engine_role_is_a_string_and_pulse_is_deliberate_none():
    for lab, engine in extract._BOO_LAB_TO_ENGINE_ROLE.items():
        if lab == "pulse":
            assert engine is None
        else:
            assert isinstance(engine, str) and engine


def test_unknown_role_fails_closed():
    assert "bogus" not in extract._BOO_LAB_TO_ENGINE_ROLE
    assert extract._BOO_LAB_TO_ENGINE_ROLE.get("bogus") is None
