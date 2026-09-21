"""Tests for src/boo_lab/adapt.py -- fake keepers/drafts in a tmp lab.
No FLAC, no torch, no network."""
from __future__ import annotations

import json

import pytest

from boo_lab import adapt


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    return lab


def _keeper(album, track, start, end, role="riff", figure_id="riff-A"):
    return {"album": album, "track": track, "start": start, "end": end,
            "role": role, "figure_id": figure_id, "source": "human", "heard": True}


def _draft(album, track, start, end, role="riff", figure_id="riff-A", source="msa-draft"):
    return {"album": album, "track": track, "start": start, "end": end,
            "role": role, "figure_id": figure_id, "source": source}


def _write(lab, keepers, drafts):
    (lab / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(k) + "\n" for k in keepers), encoding="utf-8")
    (lab / "data" / "drafts.jsonl").write_text(
        "".join(json.dumps(d) + "\n" for d in drafts), encoding="utf-8")


def test_one_pair_shifts_edges(tmp_path):
    lab = _lab(tmp_path)
    _write(lab, [_keeper("A", "T", 10.2, 18.1)], [_draft("A", "T", 10.0, 18.0)])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["n_pairs"] == 1
    assert blob["shift_start"] == pytest.approx(0.2, abs=1e-3)
    assert blob["shift_end"] == pytest.approx(0.1, abs=1e-3)

    out = adapt.apply_adapt([_draft("A", "T", 20.0, 28.0)], blob)
    assert out[0]["start"] == pytest.approx(20.2, abs=1e-3)
    assert out[0]["end"] == pytest.approx(28.1, abs=1e-3)


def test_role_remap_from_pairs(tmp_path):
    lab = _lab(tmp_path)
    _write(lab,
           [_keeper("A", "T", 0.0, 1.0, role="riff"), _keeper("A", "T", 2.0, 3.0, role="riff")],
           [_draft("A", "T", 0.0, 1.0, role="hook"), _draft("A", "T", 2.0, 3.0, role="hook")])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["roles"].get("hook") == "riff"
    out = adapt.apply_adapt([
        {"role": "hook", "start": 0.0, "end": 1.0, "source": "msa-draft"},
        {"role": "breakdown", "start": 5.0, "end": 6.0, "source": "halftime"},
    ], blob)
    assert out[0]["role"] == "riff"
    assert out[1]["role"] == "breakdown"  # not in the map


def test_figure_id_remap(tmp_path):
    lab = _lab(tmp_path)
    _write(lab, [_keeper("A", "T", 0.0, 1.0, figure_id="riff-B")],
           [_draft("A", "T", 0.0, 1.0, figure_id="riff-A")])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["figures"]["riff-A"] == "riff-B"
    out = adapt.apply_adapt([{"figure_id": "riff-A", "start": 0.0, "end": 1.0,
                              "source": "msa-draft"}], blob)
    assert out[0]["figure_id"] == "riff-B"


def test_shift_is_clamped(tmp_path):
    lab = _lab(tmp_path)
    _write(lab, [_keeper("A", "T", 10.9, 18.9)], [_draft("A", "T", 10.0, 18.0)])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["shift_start"] == 0.5 and blob["shift_end"] == 0.5


def test_holdout_track_does_not_teach_a_mixed_album(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "holdout.csv").write_text("album,track\nA,Rebirth\n", encoding="utf-8")
    _write(lab,
           [_keeper("A", "Rebirth", 10.9, 18.9), _keeper("A", "02", 5.0, 9.0)],
           [_draft("A", "Rebirth", 10.0, 18.0), _draft("A", "02", 5.0, 9.0)])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["n_pairs"] == 1                 # only the non-holdout pair
    assert blob["shift_start"] == 0.0
    assert blob["shift_end"] == 0.0


def test_rebirth_only_keeper_does_not_teach_a_13_track_album(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "holdout.csv").write_text("album,track\nA,Rebirth\n", encoding="utf-8")
    keepers = [_keeper("A", "Rebirth", 10.9, 18.9)]
    drafts = [_draft("A", "Rebirth", 10.0, 18.0)] + \
             [_draft("A", "%02d" % (i + 2), 0.0, 1.0) for i in range(12)]

    blob = adapt.rebuild_album(lab, "A")

    assert blob["n_pairs"] == 0  # album has other tracks -> holdout does not teach


def test_holdout_only_album_may_build_for_itself(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "holdout.csv").write_text("album,track\nA,Only\n", encoding="utf-8")
    _write(lab, [_keeper("A", "Only", 10.2, 18.1)], [_draft("A", "Only", 10.0, 18.0)])

    blob = adapt.rebuild_album(lab, "A")

    assert blob["n_pairs"] == 1


# --- corpus-wide cold-start blob (rebuild_global / load_adapt fallback) ----


def test_rebuild_global_pools_pairs_across_albums(tmp_path):
    lab = _lab(tmp_path)
    _write(lab,
           [_keeper("A", "T", 10.2, 18.1, role="hook"),
            _keeper("B", "U", 20.2, 28.1, role="hook")],
           [_draft("A", "T", 10.0, 18.0, role="riff"),
            _draft("B", "U", 20.0, 28.0, role="riff")])

    blob = adapt.rebuild_global(lab)

    assert blob["n_pairs"] == 2
    assert blob["shift_start"] == pytest.approx(0.2, abs=1e-3)
    assert blob["roles"].get("riff") == "hook"


def test_rebuild_global_never_pools_figure_ids(tmp_path):
    lab = _lab(tmp_path)
    _write(lab,
           [_keeper("A", "T", 0.0, 1.0, figure_id="riff-B")],
           [_draft("A", "T", 0.0, 1.0, figure_id="riff-A")])

    blob = adapt.rebuild_global(lab)

    assert blob["figures"] == {}  # per-song identifiers, never pooled globally


def test_rebuild_global_excludes_holdout_tracks(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "holdout.csv").write_text("album,track\nA,Rebirth\n", encoding="utf-8")
    _write(lab,
           [_keeper("A", "Rebirth", 10.9, 18.9), _keeper("B", "U", 5.0, 9.0)],
           [_draft("A", "Rebirth", 10.0, 18.0), _draft("B", "U", 5.0, 9.0)])

    blob = adapt.rebuild_global(lab)

    assert blob["n_pairs"] == 1  # only the non-holdout pair, across the whole corpus


def test_rebuild_global_pools_breakdown_spans_across_albums(tmp_path):
    lab = _lab(tmp_path)
    _write(lab,
           [_keeper("A", "T", 0.0, 8.0, role="breakdown"),
            _keeper("B", "U", 0.0, 10.0, role="breakdown")],
           [])

    blob = adapt.rebuild_global(lab)

    assert blob["breakdowns"]["n"] == 2
    assert blob["breakdowns"]["median_span_sec"] == pytest.approx(9.0, abs=1e-3)


def test_load_adapt_prefers_the_albums_own_armed_blob(tmp_path):
    lab = _lab(tmp_path)
    _write(lab,
           [_keeper("A", "T", 10.2, 18.1), _keeper("B", "U", 50.0, 58.0)],
           [_draft("A", "T", 10.0, 18.0), _draft("B", "U", 40.0, 48.0)])
    adapt.rebuild_album(lab, "A")
    adapt.rebuild_global(lab)

    blob = adapt.load_adapt(lab, "A")

    assert blob["shift_start"] == pytest.approx(0.2, abs=1e-3)  # A's own, not the pooled 5.0


def test_load_adapt_falls_back_to_global_for_a_fresh_album(tmp_path):
    lab = _lab(tmp_path)
    _write(lab, [_keeper("A", "T", 10.2, 18.1)], [_draft("A", "T", 10.0, 18.0)])
    adapt.rebuild_album(lab, "A")
    adapt.rebuild_global(lab)

    blob = adapt.load_adapt(lab, "Brand New Album")  # no keepers/drafts of its own

    assert blob is not None
    assert blob["shift_start"] == pytest.approx(0.2, abs=1e-3)  # inherited from A


def test_load_adapt_returns_none_when_nothing_is_armed(tmp_path):
    lab = _lab(tmp_path)
    _write(lab, [], [])
    adapt.rebuild_global(lab)  # writes a blob with n_pairs == 0

    assert adapt.load_adapt(lab, "Brand New Album") is None


def test_apply_never_sets_heard_and_leaves_sections_file(tmp_path):
    lab = _lab(tmp_path)
    sec = lab / "data" / "sections.jsonl"
    sec.write_text(json.dumps(_keeper("A", "T", 0.0, 1.0)) + "\n", encoding="utf-8")
    before = sec.read_text(encoding="utf-8")

    blob = {"n_pairs": 1, "shift_start": 0.2, "shift_end": 0.1, "roles": {}, "figures": {}}
    out = adapt.apply_adapt([{"start": 10.0, "end": 18.0, "role": "riff",
                              "source": "msa-draft"}], blob)

    assert "heard" not in out[0] and out[0]["source"] == "msa-draft"
    assert sec.read_text(encoding="utf-8") == before


def test_no_pairs_or_no_blob_returns_unchanged():
    sections = [{"start": 1.0, "end": 2.0, "role": "riff", "source": "msa-draft"}]
    assert adapt.apply_adapt(sections, None) is sections
    assert adapt.apply_adapt(sections, {"n_pairs": 0}) is sections


def test_apply_stamps_the_adapt_reason():
    blob = {"n_pairs": 1, "shift_start": 0.2, "shift_end": 0.0,
            "roles": {"hook": "breakdown"}, "figures": {"riff-A": "riff-B"}}
    row = {"role": "hook", "start": 10.0, "end": 18.0, "figure_id": "riff-A",
           "source": "msa-draft"}

    out = adapt.apply_adapt([row], blob)

    assert out[0]["adapt"] == "shift+role+figure"
    assert out[0]["start"] == pytest.approx(10.2, abs=1e-3)
    assert out[0]["source"] == "msa-draft"  # never a keeper source


def test_tiny_shift_does_not_stamp_adapt():
    blob = {"n_pairs": 1, "shift_start": 0.01, "shift_end": 0.0,
            "roles": {}, "figures": {}}

    out = adapt.apply_adapt([{"role": "riff", "start": 1.0, "end": 2.0,
                              "source": "msa-draft"}], blob)

    assert "adapt" not in out[0]


def test_already_adapted_row_is_not_reapplied():
    blob = {"n_pairs": 1, "shift_start": 0.5, "shift_end": 0.5,
            "roles": {"hook": "breakdown"}, "figures": {}}
    row = {"role": "hook", "start": 1.0, "end": 2.0, "source": "msa-draft",
           "_adapted": True}

    out = adapt.apply_adapt([row], blob)

    assert out[0]["role"] == "hook" and out[0]["start"] == 1.0


def test_intern_drafts_are_calibrated_on_load_and_sections_untouched(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from boo_lab import annotator as ann

    lab = _lab(tmp_path)
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "hook", "start": 0.0,
                    "end": 2.0, "source": "msa-draft"}) + "\n", encoding="utf-8")
    (lab / "data" / "adapt.json").write_text(
        json.dumps({"A": {"n_pairs": 1, "shift_start": 0.0, "shift_end": 0.0,
                          "roles": {"hook": "breakdown"}, "figures": {}}}) + "\n",
        encoding="utf-8")
    sec = lab / "data" / "sections.jsonl"
    sec.write_text("", encoding="utf-8")

    client = TestClient(ann.create_app(lab, None, None))
    data = client.get("/api/drafts", params={"album": "A", "track": "T"}).json()

    assert data["drafts"][0]["role"] == "breakdown"
    assert sec.read_text(encoding="utf-8") == ""


def test_structure_applies_adapt_before_writing(tmp_path, monkeypatch):
    from boo_lab import structure

    lab = _lab(tmp_path)
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    (lab / "data" / "adapt.json").write_text(
        json.dumps({"A": {"n_pairs": 1, "shift_start": 0.0, "shift_end": 0.0,
                          "roles": {"hook": "breakdown"}, "figures": {}}}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(structure, "songformer_available", lambda: False)
    monkeypatch.setattr(structure, "run_allin1",
                        lambda fp, cache_dir=None: {"segments": [{"start": 0.0, "label": "chorus"}]})

    structure.build_drafts(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    rows = [json.loads(line) for line in
            (lab / "data" / "drafts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows and rows[0]["role"] == "breakdown"
