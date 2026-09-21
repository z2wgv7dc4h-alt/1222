"""Tests for src/boo_lab/predict.py -- the keeper-trained structure predictor.

Synthetic two-tone wavs + fake keepers; no real corpus. Proves: training writes
a checkpoint even with one track, inference writes `keeper-model` drafts (never
`sections.jsonl`), holdout songs are excluded from train features, and an empty
lab exits cleanly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
soundfile = pytest.importorskip("soundfile")
torch = pytest.importorskip("torch")

from boo_lab import predict  # noqa: E402
from boo_lab.catalogue import save_map  # noqa: E402
from boo_lab.holdout import write_holdout  # noqa: E402

SR = 22050


def _wav(path: Path, segments=((110.0, 2.0), (440.0, 2.0))) -> None:
    parts = []
    for freq, dur in segments:
        t = np.arange(int(SR * dur)) / SR
        parts.append(0.2 * np.sin(2 * np.pi * freq * t))
    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(path), np.concatenate(parts).astype("float32"), SR)


def _lab(tmp_path, *, songs, spans=(("intro", 0.0, 2.0), ("riff", 2.0, 3.5))):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    rows = []
    recs = []
    for album, track in songs:
        wav = tmp_path / "audio" / (album + "_" + track + ".wav")
        _wav(wav)
        rows.append({"album": album, "track": track, "year": "", "flac": str(wav),
                     "gp": "", "tuning": "drop_g_7", "match": "unknown", "notes": ""})
        for role, start, end in spans:
            recs.append({"album": album, "track": track, "start": start, "end": end,
                         "role": role, "source": "human", "heard": True})
    save_map(lab / "data" / "map.csv", rows)
    (lab / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return lab, rows


def _drafts(lab):
    path = lab / "data" / "drafts.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_train_produces_a_checkpoint_with_one_track(tmp_path):
    torch.manual_seed(0)
    lab, rows = _lab(tmp_path, songs=[("A", "TA")])

    report = predict.train(lab, epochs=10, rows=rows)

    assert report["trained"] is True and report["n_tracks"] == 1
    md = predict.model_dir(lab)
    assert (md / "weights.pt").exists()
    assert (md / "config.json").exists()
    assert (md / "label_map.json").exists()
    assert (md / "metrics.json").exists()
    metrics = json.loads((md / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["source"] == "keeper-model"


def test_predict_writes_keeper_model_drafts_and_never_sections(tmp_path):
    torch.manual_seed(0)
    lab, rows = _lab(tmp_path, songs=[("A", "TA")])
    predict.train(lab, epochs=40, rows=rows)
    sec = lab / "data" / "sections.jsonl"
    before = sec.read_text(encoding="utf-8")

    report = predict.build_drafts(lab, rows, album="A", track="TA")

    assert report["written"] >= 1
    km = [d for d in _drafts(lab) if d["source"] == "keeper-model"]
    assert km and all(d["heard"] is False for d in km)
    assert sec.read_text(encoding="utf-8") == before  # sections.jsonl untouched


def test_holdout_track_excluded_from_train_features(tmp_path):
    torch.manual_seed(0)
    lab, rows = _lab(tmp_path, songs=[("A", "TA"), ("B", "TB")])
    write_holdout(lab, {("B", "TB")})

    samples, info = predict.build_dataset(lab, rows)

    train_keys = {tuple(k) for k in info["train_tracks"]}
    assert ("A", "TA") in train_keys
    assert ("B", "TB") not in train_keys
    assert info["holdout_fallback"] is False
    assert {tuple(k) for k in info["eval_tracks"]} == {("B", "TB")}
    assert samples and all(s["track"] != "TB" for s in samples)


def test_holdout_only_lab_falls_back_and_flags(tmp_path):
    torch.manual_seed(0)
    lab, rows = _lab(tmp_path, songs=[("A", "TA")])
    write_holdout(lab, {("A", "TA")})

    report = predict.train(lab, epochs=2, rows=rows)

    assert report["trained"] is True and report["holdout_fallback"] is True


def test_empty_keepers_exits_clean_without_crashing(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sections.jsonl").write_text("", encoding="utf-8")

    report = predict.train(lab, epochs=1, rows=[])

    assert report["trained"] is False
    assert "no usable keepers" in report["reason"]
    assert not predict.model_exists(lab)


def test_predict_without_a_model_is_a_noop(tmp_path):
    lab, rows = _lab(tmp_path, songs=[("A", "TA")])
    draft = lab / "data" / "drafts.jsonl"
    draft.write_text(
        json.dumps({"album": "A", "track": "TA", "start": 0.0, "end": 1.0,
                    "role": "riff", "source": "msa-draft"}) + "\n",
        encoding="utf-8")
    before = draft.read_text(encoding="utf-8")

    report = predict.build_drafts(lab, rows, album="A", track="TA")

    assert report["written"] == 0 and report["reason"] == "no model"
    assert draft.read_text(encoding="utf-8") == before


def _synthetic_pack():
    from boo_lab import tabnotes as tn

    measures = [tn.TabMeasure(measure=0, start_ms=0.0, start_sec_audio=0.0,
                              duration_ms=4000.0)]
    events = [
        tn.TabEvent(track=0, category="guitar", measure=0, onset_ms=i * 100.0,
                    pitch=40, palm_mute=(i % 2 == 0), hammer=(i % 3 == 0))
        for i in range(20)
    ]
    return tn.TabNotesPack(id="p", tracks=[tn.TabTrack(index=0, category="guitar")],
                           events=events, measures=measures)


def test_tab_articulations_add_feature_columns(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "TA", "sync_ok": True}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake")
    monkeypatch.setattr(tn, "load_pack", lambda path: _synthetic_pack())

    row = {"album": "A", "track": "TA"}
    sig = predict._tab_signals(lab, row, 40)
    assert sig is not None
    onset, palm, hammer, count = sig
    assert onset.shape == palm.shape == hammer.shape == count.shape == (40,)
    assert float(palm.max()) > 0 and float(hammer.max()) > 0
    assert int(count.sum()) == 20

    monkeypatch.setattr(predict, "_audio_for", lambda row, cache: (Path("x"), "mix"))
    monkeypatch.setattr(
        predict, "extract_frames",
        lambda audio: (np.zeros((40, predict.N_MELS + 2), "float32"),
                       np.arange(40, dtype="float32")))
    tf = predict.track_features(lab, row)
    assert tf is not None and tf["features"].shape == (40, predict.N_MELS + 6)


def test_tab_articulations_soft_fail_without_sync(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    monkeypatch.setattr(predict, "_audio_for", lambda row, cache: (Path("x"), "mix"))
    monkeypatch.setattr(
        predict, "extract_frames",
        lambda audio: (np.zeros((40, predict.N_MELS + 2), "float32"),
                       np.arange(40, dtype="float32")))

    tf = predict.track_features(lab, {"album": "A", "track": "TA"})

    assert tf is not None and tf["features"].shape == (40, predict.N_MELS + 6)
    assert float(tf["features"][:, predict.N_MELS + 3:].max()) == 0.0


def test_predict_replaces_only_its_own_rows(tmp_path):
    torch.manual_seed(0)
    lab, rows = _lab(tmp_path, songs=[("A", "TA"), ("B", "TB")])
    draft = lab / "data" / "drafts.jsonl"
    draft.write_text(
        json.dumps({"album": "A", "track": "TA", "start": 0.0, "end": 1.0,
                    "role": "riff", "source": "msa-draft"}) + "\n"
        + json.dumps({"album": "A", "track": "TA", "start": 0.0, "end": 1.0,
                      "role": "riff", "source": "keeper-model"}) + "\n"
        + json.dumps({"album": "B", "track": "TB", "start": 0.0, "end": 1.0,
                      "role": "riff", "source": "keeper-model"}) + "\n",
        encoding="utf-8")
    predict.train(lab, epochs=20, rows=rows)

    predict.build_drafts(lab, rows, album="A", track="TA")

    out = _drafts(lab)
    assert any(d["source"] == "msa-draft" for d in out)       # sibling source kept
    assert any(d["source"] == "keeper-model" and d["track"] == "TB" for d in out)
    a_km = [d for d in out if d["source"] == "keeper-model" and d["track"] == "TA"]
    assert a_km and all(float(d["end"]) > 1.0 for d in a_km)  # old 0-1 row replaced
