"""Keeper-trained structure predictor -- thin v1 scaffold.

Optional draft source `keeper-model`. Needs non-holdout keepers before it is
useful. Rebirth-only labs skip train unless `holdout_fallback` is explicit.

Law (unchanged):
  * Trains on keepers only (`schema.is_keeper` + `heard is True`).
  * Holdout / VAL songs never train by default. A cold-start lab whose *only*
    keepers sit on holdout songs does not fine-tune unless `holdout_fallback`
    is explicitly enabled; a mixed lab excludes holdout keepers, always.
  * Writes drafts only (`source="keeper-model"`), never `sections.jsonl`.
  * Incremental: an existing `weights.pt` is loaded and fine-tuned.
  * Frozen interns are never retrained here.

Features are fixed-hop librosa log-mel + RMS + onset-strength frames (0.25 s),
optionally tab columns when the song's `sync.jsonl` is `sync_ok`: onset
density, palm-mute density, hammer density and a raw onset count from a
tab-notes pack (guitar category) or a GP7 GPIF score. Labels are per-frame
role (canonical role or `none`) + a boundary
flag near any keeper start/end. The model is a small 2-layer Conv1d with a
role head and a boundary head. CPU works; `device.py` wins when CUDA exists.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from .schema import (
    ROLES,
    canonical_role,
    load_section_rows,
    stamp_box,
    write_jsonl_atomic,
)

SOURCE = "keeper-model"
MODEL_NAME = "structure-v1"
HOP_SEC = 0.25
SAMPLE_RATE = 22050
N_FFT = 2048
N_MELS = 40
HIDDEN = 64
NONE_ROLE = "none"
MIN_BOX_SEC = 0.5
DEFAULT_EPOCHS = 40
SAVE_EPOCHS = 3

# Guards concurrent training (a Save hook and an explicit `predict-train` can
# race). Held by a background Save-train thread only; explicit CLI training is
# not expected to overlap itself.
_TRAIN_LOCK = threading.Lock()

_NET_CLASS = None


# --- role vocabulary / paths -------------------------------------------------


def role_classes() -> list[str]:
    return list(ROLES) + [NONE_ROLE]


def model_dir(lab_root) -> Path:
    return Path(lab_root) / "work" / "models" / MODEL_NAME


def model_exists(lab_root) -> bool:
    md = model_dir(lab_root)
    return (md / "weights.pt").exists() and (md / "config.json").exists()


# --- audio / features --------------------------------------------------------


def _sync_record(lab_root, album: str, track: str) -> dict | None:
    path = Path(lab_root) / "data" / "sync.jsonl"
    if not path.exists():
        return None
    for rec in _read_jsonl(path):
        if (rec.get("track") or "") != track:
            continue
        if album and (rec.get("album") or "") != album:
            continue
        return rec
    return None


def _audio_for(row: dict, cache: Path | None) -> tuple[Path | None, str]:
    """The guitar stem when cached, else the FLAC/mix. `(path, kind)`."""
    val = row.get("flac_path") or row.get("flac") or ""
    flac = Path(val) if val else None
    if flac is None or not flac.exists():
        return None, "no flac"
    if cache is not None:
        try:
            from .stems import find_stem

            stem = find_stem(flac, Path(cache), "guitar")
            if stem is not None:
                return stem, "guitar stem"
        except Exception:
            pass
    return flac, "mix"


def extract_frames(audio: Path):
    """`(features (T, N_MELS+2), times (T,))` at a fixed `HOP_SEC`; `None`
    when the file will not load."""
    import librosa

    y, sr = librosa.load(str(audio), sr=SAMPLE_RATE, mono=True)
    if y is None or len(y) == 0:
        return None
    hop = max(1, int(round(sr * HOP_SEC)))
    mel = librosa.feature.melspectrogram(
        y=y, sr=sr, n_fft=N_FFT, hop_length=hop, n_mels=N_MELS)
    logmel = librosa.power_to_db(mel, ref=np.max).T  # (T, N_MELS)
    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    n = min(logmel.shape[0], rms.shape[0], onset.shape[0])
    if n <= 0:
        return None
    feats = np.concatenate(
        [logmel[:n], rms[:n, None], onset[:n, None]], axis=1).astype("float32")
    times = librosa.frames_to_time(
        np.arange(n), sr=sr, hop_length=hop).astype("float32")
    return feats, times


def _norm_env(env) -> "np.ndarray":
    env = np.asarray(env, dtype="float32")
    top = float(env.max()) if env.size else 0.0
    return (env / top).astype("float32") if top > 0 else env


def _tab_signals(lab_root, row: dict, n_frames: int):
    """Per-frame tab columns `(onset, palm_mute, hammer, onset_count)` when this
    song's clock is trusted and a tab-notes pack / GP7 GPIF supplies them; else
    `None` (soft-fail -- the predictor never needs a tab). A pack wins (guitar
    category, on the audio clock); a GP7 GPIF contributes onset + `palm_mute`
    only (hammer stays zero). The first three are normalized 0..1; the count is
    a raw onset count (the model's own standardizer handles the scale)."""
    album = row.get("album") or ""
    track = row.get("track") or ""
    rec = _sync_record(lab_root, album, track)
    if not rec or rec.get("sync_ok") is not True:
        return None
    onset_times: list[float] = []
    palm_times: list[float] = []
    hammer_times: list[float] = []
    try:
        from . import tabnotes as tn

        pack_path = tn.discover_pack(lab_root, album, track)
        if pack_path is not None:
            pack = tn.load_pack(pack_path)
            events = tn.events_for(pack, category="guitar")
            if not events:
                events = [e for e in pack.events
                          if not getattr(e, "is_percussion", False)]
            for e in events:
                t = pack.audio_sec(e)
                onset_times.append(t)
                if getattr(e, "palm_mute", False):
                    palm_times.append(t)
                if getattr(e, "hammer", False):
                    hammer_times.append(t)
    except Exception:
        onset_times = []
    if not onset_times:
        gp_val = row.get("gp_path") or row.get("gp") or ""
        gp = Path(gp_val) if gp_val else None
        if gp is not None and gp.exists() and gp.suffix.lower() in (".gp", ".gpx"):
            try:
                from .gpif import load_score, note_events

                for ev in note_events(load_score(gp)):
                    onset_times.append(float(ev[0]))
                    if ev[3]:
                        palm_times.append(float(ev[0]))
            except Exception:
                onset_times = []
    if not onset_times:
        return None
    from .sync import envelope_from_times

    onset_env = envelope_from_times(onset_times, n_frames, HOP_SEC)
    return (
        _norm_env(onset_env),
        _norm_env(envelope_from_times(palm_times, n_frames, HOP_SEC)),
        _norm_env(envelope_from_times(hammer_times, n_frames, HOP_SEC)),
        np.asarray(onset_env, dtype="float32"),
    )


def track_features(lab_root, row: dict, cache: Path | None = None) -> dict | None:
    """Frame features + times for one song, or `None` when no real audio / a
    librosa failure. Always one fixed feature width (N_MELS + 6): log-mel +
    RMS + onset, then tab onset-density, palm-mute density, hammer density and
    a raw tab onset count (all zeros without a trusted tab)."""
    audio, kind = _audio_for(row, cache)
    if audio is None:
        return None
    try:
        frames = extract_frames(audio)
    except Exception:
        return None
    if frames is None:
        return None
    feats, times = frames
    sig = _tab_signals(lab_root, row, len(times))
    if sig is None:
        z = np.zeros(len(times), dtype="float32")
        sig = (z, z, z, z)
    feats = np.concatenate(
        [feats] + [col[:, None] for col in sig], axis=1).astype("float32")
    return {"features": feats, "times": times, "audio": str(audio), "audio_kind": kind}


# --- labels ------------------------------------------------------------------


def build_labels(boxes: list[dict], times) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame role index + boundary flag from keeper boxes."""
    classes = role_classes()
    index = {r: i for i, r in enumerate(classes)}
    none_i = index[NONE_ROLE]
    y = np.full(len(times), none_i, dtype="int64")
    b = np.zeros(len(times), dtype="float32")
    spans: list[tuple[float, float, int]] = []
    for box in boxes:
        role = canonical_role(box.get("role"))
        try:
            start, end = float(box.get("start")), float(box.get("end"))
        except (TypeError, ValueError):
            continue
        if role is None or end <= start:
            continue
        spans.append((start, end, index[role]))
    if not spans:
        return y, b
    tol = HOP_SEC
    for i, t in enumerate(times):
        t = float(t)
        for start, end, ri in spans:
            if start <= t < end:
                y[i] = ri
                break
        for start, end, _ri in spans:
            if abs(t - start) <= tol or abs(t - end) <= tol:
                b[i] = 1.0
                break
    return y, b


# --- dataset -----------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _map_rows(lab_root) -> list[dict]:
    from .catalogue import load_map, resolve

    path = Path(lab_root) / "data" / "map.csv"
    rows = load_map(path) if path.exists() else []
    fr = os.environ.get("BOO_FLAC_ROOT")
    gr = os.environ.get("BOO_GP_ROOT")
    return [resolve(r, Path(fr) if fr else None, Path(gr) if gr else None) for r in rows]


def _album_ok(rec: dict, album: str | None) -> bool:
    if not album:
        return True
    from .catalogue import _album_core

    return ((rec.get("album") or "").casefold() == album.casefold()
            or _album_core(rec.get("album")) == _album_core(album))


def _row_for(rows: list[dict], key: tuple[str, str]) -> dict | None:
    album, track = key
    for r in rows:
        if (r.get("album") or "") == album and (r.get("track") or "") == track:
            return r
    from .catalogue import _track_key

    tk = _track_key(track)
    for r in rows:
        if _track_key(r.get("track")) == tk and _album_ok(r, album):
            return r
    return None


def _group_keepers(lab_root, album: str | None) -> dict:
    keepers = load_section_rows(Path(lab_root) / "data" / "sections.jsonl")
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rec in keepers:
        if not _album_ok(rec, album):
            continue
        groups[((rec.get("album") or ""), (rec.get("track") or ""))].append(rec)
    return groups



def holdout_fallback_enabled() -> bool:
    """Opt-in: train on holdout-only gold. Env `BOO_PREDICT_HOLDOUT_FALLBACK=1`."""
    return os.environ.get("BOO_PREDICT_HOLDOUT_FALLBACK", "0") == "1"


def build_dataset(lab_root, rows, *, album=None, cache=None, holdout=None,
                  allow_holdout_fallback: bool = False) -> tuple[list[dict], dict]:
    """`(train_samples, info)`. Holdout keeper songs are excluded unless that
    leaves zero training songs and `allow_holdout_fallback` is on (cold start,
    recorded in `info["holdout_fallback"]`)."""
    from .holdout import ensure_holdout

    lab_root = Path(lab_root)
    rows = list(rows) if rows is not None else _map_rows(lab_root)
    holdout = ensure_holdout(lab_root, rows) if holdout is None else set(holdout)
    groups = _group_keepers(lab_root, album)

    train_keys = [k for k in groups if k not in holdout]
    fallback = False
    if not train_keys and groups and allow_holdout_fallback:
        train_keys = list(groups)
        fallback = True

    samples: list[dict] = []
    skipped: list[dict] = []
    train_tracks: list[tuple[str, str]] = []
    for key in train_keys:
        row = _row_for(rows, key)
        if row is None:
            skipped.append({"track": key[1], "reason": "no map row"})
            continue
        tf = track_features(lab_root, row, cache)
        if tf is None:
            skipped.append({"track": key[1], "reason": "no audio/features"})
            continue
        y, b = build_labels(groups[key], tf["times"])
        samples.append({"album": key[0], "track": key[1],
                        "features": tf["features"], "role": y, "boundary": b})
        train_tracks.append(key)

    eval_samples: list[dict] = []
    eval_tracks: list[tuple[str, str]] = []
    for key in groups:
        if key not in holdout:
            continue
        row = _row_for(rows, key)
        if row is None:
            continue
        tf = track_features(lab_root, row, cache)
        if tf is None:
            continue
        y, b = build_labels(groups[key], tf["times"])
        eval_samples.append({"album": key[0], "track": key[1],
                             "features": tf["features"], "role": y, "boundary": b})
        eval_tracks.append(key)

    info = {
        "n_keepers": sum(len(v) for v in groups.values()),
        "n_tracks": len(groups),
        "train_tracks": train_tracks,
        "eval_tracks": eval_tracks,
        "eval_samples": eval_samples,
        "holdout_fallback": fallback,
        "skipped": skipped,
    }
    return samples, info


# --- model -------------------------------------------------------------------


def _torch():
    import torch

    return torch


def _net_class():
    global _NET_CLASS
    if _NET_CLASS is None:
        import torch.nn as nn

        class StructureNet(nn.Module):
            def __init__(self, n_features: int, n_roles: int, hidden: int = HIDDEN):
                super().__init__()
                self.conv1 = nn.Conv1d(n_features, hidden, kernel_size=5, padding=2)
                self.conv2 = nn.Conv1d(hidden, hidden, kernel_size=5, padding=2)
                self.drop = nn.Dropout(0.1)
                self.role = nn.Linear(hidden, n_roles)
                self.boundary = nn.Linear(hidden, 1)

            def forward(self, x):  # x: (B, T, F)
                h = x.transpose(1, 2)
                h = _torch().relu(self.conv1(h))
                h = _torch().relu(self.conv2(h))
                h = h.transpose(1, 2)
                h = self.drop(h)
                return self.role(h), self.boundary(h).squeeze(-1)

        _NET_CLASS = StructureNet
    return _NET_CLASS


def _fit_norm(samples: list[dict]):
    x = np.concatenate([s["features"] for s in samples], axis=0)
    mean = x.mean(axis=0).astype("float32")
    std = x.std(axis=0).astype("float32")
    std[std < 1e-6] = 1.0
    return mean, std


def _normalize(samples: list[dict], mean, std) -> None:
    for s in samples:
        s["_x"] = ((s["features"] - mean) / std).astype("float32")


def _train_model(samples: list[dict], *, n_features: int, n_roles: int,
                 epochs: int, init_state=None, device: str = "cpu"):
    torch = _torch()
    nn = torch.nn
    Net = _net_class()
    model = Net(n_features, n_roles, HIDDEN).to(device)
    if init_state is not None:
        try:
            model.load_state_dict(init_state)
        except Exception:
            pass  # architecture changed / stale checkpoint -> fresh weights
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.train()
    for _epoch in range(max(1, int(epochs))):
        for s in samples:
            x = torch.from_numpy(s["_x"]).unsqueeze(0).to(device)
            yr = torch.from_numpy(s["role"]).unsqueeze(0).to(device)
            yb = torch.from_numpy(s["boundary"]).unsqueeze(0).to(device)
            role_logits, b_logits = model(x)
            loss = nn.functional.cross_entropy(
                role_logits.reshape(-1, n_roles), yr.reshape(-1))
            pos = float(yb.sum())
            neg = float(yb.numel()) - pos
            pos_weight = torch.tensor(
                [min(20.0, max(1.0, neg / max(pos, 1.0)))],
                dtype=torch.float32, device=device)
            loss = loss + nn.functional.binary_cross_entropy_with_logits(
                b_logits.reshape(-1), yb.reshape(-1), pos_weight=pos_weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


def _eval(model, samples: list[dict], device: str) -> dict:
    torch = _torch()
    model.eval()
    role_hit = role_tot = 0
    tp = fp = fn = 0
    with torch.no_grad():
        for s in samples:
            x = torch.from_numpy(s["_x"]).unsqueeze(0).to(device)
            role_logits, b_logits = model(x)
            pred = role_logits.argmax(-1)[0].cpu().numpy()
            truth = s["role"]
            role_hit += int((pred == truth).sum())
            role_tot += int(len(truth))
            bp = (torch.sigmoid(b_logits)[0].cpu().numpy() >= 0.5).astype(int)
            bt = s["boundary"].astype(int)
            tp += int(((bp == 1) & (bt == 1)).sum())
            fp += int(((bp == 1) & (bt == 0)).sum())
            fn += int(((bp == 0) & (bt == 1)).sum())
    acc = role_hit / role_tot if role_tot else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"role_acc": round(acc, 4), "boundary_precision": round(prec, 4),
            "boundary_recall": round(rec, 4), "boundary_f1": round(f1, 4),
            "n_frames": role_tot}


def _save_files(md: Path, model, *, classes: list[str], n_features: int,
                mean, std, metrics: dict) -> None:
    md.mkdir(parents=True, exist_ok=True)
    _torch().save(model.state_dict(), str(md / "weights.pt"))
    config = {
        "model": MODEL_NAME,
        "source": SOURCE,
        "n_features": int(n_features),
        "n_roles": len(classes),
        "hidden": HIDDEN,
        "hop_sec": HOP_SEC,
        "sample_rate": SAMPLE_RATE,
        "n_mels": N_MELS,
        "feature_mean": [float(v) for v in mean],
        "feature_std": [float(v) for v in std],
        "ts": metrics.get("ts"),
    }
    (md / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (md / "label_map.json").write_text(
        json.dumps({"classes": classes, "none": NONE_ROLE, "source": SOURCE}, indent=2),
        encoding="utf-8")
    (md / "metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")


def train(lab_root, *, album: str | None = None, epochs: int = DEFAULT_EPOCHS,
          rows=None, cache=None, allow_holdout_fallback: bool | None = None) -> dict:
    """Train / fine-tune from keepers. Writes `work/models/structure-v1/`.
    Zero usable keepers exits cleanly (`trained: False`), never raises."""
    from .device import torch_device

    lab_root = Path(lab_root)
    cache = Path(cache) if cache else lab_root / "work" / "stems"
    rows = list(rows) if rows is not None else _map_rows(lab_root)
    if allow_holdout_fallback is None:
        allow_holdout_fallback = holdout_fallback_enabled()

    samples, info = build_dataset(
        lab_root, rows, album=album, cache=cache,
        allow_holdout_fallback=allow_holdout_fallback)
    if not samples:
        if info.get("n_keepers") and not allow_holdout_fallback and not info.get("train_tracks"):
            reason = ("holdout-only keepers; pass allow_holdout_fallback=True or "
                      "set BOO_PREDICT_HOLDOUT_FALLBACK=1 to opt in")
        else:
            reason = ("no usable keepers with audio (need heard human/guess-accepted "
                      "boxes on a track with a FLAC)")
        print("predict-train:", reason)
        return {"trained": False, "reason": reason, "n_tracks": 0,
                "n_keepers": info["n_keepers"], "holdout_fallback": False}

    mean, std = _fit_norm(samples)
    _normalize(samples, mean, std)
    _normalize(info["eval_samples"], mean, std)
    classes = role_classes()
    n_features = int(samples[0]["features"].shape[1])
    device = torch_device()
    md = model_dir(lab_root)
    init_state = None
    if (md / "weights.pt").exists():
        try:
            init_state = _torch().load(str(md / "weights.pt"), map_location="cpu")
        except Exception:
            init_state = None

    model = _train_model(samples, n_features=n_features, n_roles=len(classes),
                         epochs=epochs, init_state=init_state, device=device)

    metrics = {
        "trained": True,
        "source": SOURCE,
        "model": MODEL_NAME,
        "device": device,
        "epochs": int(epochs),
        "fine_tuned_from_checkpoint": init_state is not None,
        "n_keepers": info["n_keepers"],
        "n_tracks": len(info["train_tracks"]),
        "tracks": [[a, t] for a, t in info["train_tracks"]],
        "n_frames": int(sum(len(s["role"]) for s in samples)),
        "holdout_fallback": bool(info["holdout_fallback"]),
        "skipped": info["skipped"],
        "train": _eval(model, samples, device),
        "holdout": _eval(model, info["eval_samples"], device) if info["eval_samples"] else None,
        "ts": round(time.time(), 3),
    }
    _save_files(md, model, classes=classes, n_features=n_features,
                mean=mean, std=std, metrics=metrics)
    print("predict-train: %d track(s), %d keeper row(s), %d frames, %d epoch(s), device=%s"
          % (metrics["n_tracks"], metrics["n_keepers"], metrics["n_frames"],
             metrics["epochs"], device))
    print("predict-train: train role_acc=%.3f boundary_f1=%.3f%s -> %s"
          % (metrics["train"]["role_acc"], metrics["train"]["boundary_f1"],
             "" if metrics["holdout"] is None
             else " | holdout role_acc=%.3f boundary_f1=%.3f"
                  % (metrics["holdout"]["role_acc"], metrics["holdout"]["boundary_f1"]),
             md))
    if metrics["holdout_fallback"]:
        print("predict-train: holdout-only keepers -- cold-start overfit smoke "
              "(holdout_fallback=true); holdout is never trained in a mixed lab")
    return metrics


# --- inference ---------------------------------------------------------------


def load_model(lab_root) -> dict | None:
    md = model_dir(lab_root)
    cfg_path = md / "config.json"
    weights = md / "weights.pt"
    if not (cfg_path.exists() and weights.exists()):
        return None
    try:
        config = json.loads(cfg_path.read_text(encoding="utf-8"))
        label_map = {}
        lm = md / "label_map.json"
        if lm.exists():
            label_map = json.loads(lm.read_text(encoding="utf-8"))
        torch = _torch()
        Net = _net_class()
        model = Net(config["n_features"], config["n_roles"],
                    config.get("hidden", HIDDEN))
        model.load_state_dict(torch.load(str(weights), map_location="cpu"))
        model.eval()
        mean = np.asarray(config["feature_mean"], dtype="float32")
        std = np.asarray(config["feature_std"], dtype="float32")
        return {"model": model, "config": config,
                "classes": label_map.get("classes") or role_classes(),
                "mean": mean, "std": std}
    except Exception:
        return None


def _runs_to_boxes(times, role_ids, none_i: int, classes: list[str],
                   min_span: float = MIN_BOX_SEC) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    i = 0
    total = len(role_ids)
    while i < total:
        role = int(role_ids[i])
        if role == none_i or role < 0 or role >= len(classes):
            i += 1
            continue
        j = i
        while j + 1 < total and int(role_ids[j + 1]) == role:
            j += 1
        start = float(times[i])
        end = float(times[j]) + HOP_SEC
        if end - start >= min_span:
            out.append((round(start, 3), round(end, 3), classes[role]))
        i = j + 1
    return out


def predict_track(lab_root, row: dict, cache=None,
                  loaded: dict | None = None) -> list[dict] | None:
    """Unheard keeper-model draft boxes for one row, or `None` when the model
    or the audio is unavailable."""
    state = loaded if loaded is not None else load_model(lab_root)
    if state is None:
        return None
    lab_root = Path(lab_root)
    cache = Path(cache) if cache else lab_root / "work" / "stems"
    tf = track_features(lab_root, row, cache)
    if tf is None:
        return None
    x = ((tf["features"] - state["mean"]) / state["std"]).astype("float32")
    torch = _torch()
    model = state["model"]
    with torch.no_grad():
        role_logits, b_logits = model(torch.from_numpy(x).unsqueeze(0))
        role_ids = role_logits.argmax(-1)[0].cpu().numpy()
    classes = state["classes"]
    none_i = classes.index(NONE_ROLE) if NONE_ROLE in classes else -1
    boxes = _runs_to_boxes(tf["times"], role_ids, none_i, classes)
    return [
        stamp_box(start, end, role, source=SOURCE, heard=False,
                  extra={"album": row.get("album"), "track": row.get("track")})
        for start, end, role in boxes
    ]


def load_drafts(lab_root, album: str, track: str) -> list[dict]:
    """Existing keeper-model drafts for one song (fast read; no torch)."""
    path = Path(lab_root) / "data" / "drafts.jsonl"
    return [r for r in _read_jsonl(path)
            if (r.get("album") or "") == album
            and (r.get("track") or "") == track
            and r.get("source") == SOURCE]


def load_keeper_model_drafts(lab_root, album: str, track: str,
                             existing: list[dict] | None = None,
                             tol: float = 0.35) -> list[dict]:
    """Keeper-model drafts for `album/track` not already covered by `existing`.
    Used by Guess to merge pre-written drafts without running the model."""
    out: list[dict] = []
    for rec in load_drafts(lab_root, album, track):
        try:
            start, end = float(rec.get("start")), float(rec.get("end"))
        except (TypeError, ValueError):
            continue
        role = rec.get("role")
        if not role or end <= start:
            continue
        dup = any(
            abs(float(o.get("start", 0.0)) - start) <= tol
            and abs(float(o.get("end", 0.0)) - end) <= tol
            and (o.get("role") or "") == role
            for o in (existing or [])
        )
        if dup:
            continue
        out.append({**rec, "source": SOURCE, "heard": False})
    return out


def _target_rows(rows: list[dict], album: str | None, track: str | None) -> list[dict]:
    from .catalogue import _track_key

    out = list(rows)
    if album:
        out = [r for r in out if _album_ok(r, album)]
    if track:
        tk = _track_key(track)
        out = [r for r in out if _track_key(r.get("track")) == tk]
    return out


def build_drafts(lab_root, rows, album: str | None = None,
                 track: str | None = None, cache=None) -> dict:
    """Predict every target row and merge keeper-model rows into
    `data/drafts.jsonl`, replacing only prior keeper-model rows for those
    songs. NEVER writes `sections.jsonl`."""
    lab_root = Path(lab_root)
    cache = Path(cache) if cache else lab_root / "work" / "stems"
    if not model_exists(lab_root):
        print("predict: no model at %s -- run `boo-lab predict-train`" % model_dir(lab_root))
        return {"written": 0, "tracks": 0, "reason": "no model"}

    targets = _target_rows(list(rows), album, track)
    if not targets:
        print("predict: no target rows")
        return {"written": 0, "tracks": 0, "reason": "no target rows"}

    target_keys = {(r.get("album") or "", r.get("track") or "") for r in targets}
    state = load_model(lab_root)
    if state is None:
        return {"written": 0, "tracks": 0, "reason": "unreadable model"}

    new_recs: list[dict] = []
    done = 0
    for row in targets:
        try:
            recs = predict_track(lab_root, row, cache, loaded=state)
        except Exception as exc:  # noqa: BLE001 - one bad row never aborts the run
            print("SKIP predict", row.get("track"), exc)
            recs = None
        if recs is None:
            continue
        new_recs.extend(recs)
        done += 1
        print("PREDICT", row.get("track"), len(recs), "box(es)")

    draft_path = lab_root / "data" / "drafts.jsonl"
    kept = [r for r in _read_jsonl(draft_path)
            if not (((r.get("album") or "", r.get("track") or "")) in target_keys
                    and r.get("source") == SOURCE)]
    if new_recs:
        write_jsonl_atomic(draft_path, kept + new_recs)
    else:
        print("predict: 0 drafts written; leaving", draft_path.name, "untouched")
    return {"written": len(new_recs), "tracks": done, "out": str(draft_path),
            "model": str(model_dir(lab_root))}


# --- Save hook ---------------------------------------------------------------


def _has_real_audio(lab_root, album: str, track: str, min_bytes: int = 4096) -> bool:
    """Cheap guard so a tiny synthetic fixture never spins a training thread."""
    from .catalogue import _track_key, load_map, resolve

    path = Path(lab_root) / "data" / "map.csv"
    if not path.exists():
        return False
    fr = os.environ.get("BOO_FLAC_ROOT")
    gr = os.environ.get("BOO_GP_ROOT")
    for r in load_map(path):
        if album and not _album_ok(r, album):
            continue
        if track and (_track_key(r.get("track")) != _track_key(track)):
            continue
        rr = resolve(r, Path(fr) if fr else None, Path(gr) if gr else None)
        fp = rr.get("flac_path") or rr.get("flac") or ""
        try:
            if fp and Path(fp).stat().st_size >= min_bytes:
                return True
        except OSError:
            continue
    return False


def maybe_train_on_save(lab_root, album: str = "", track: str = ""):
    """Fire a low-epoch fine-tune in a daemon thread after keepers land. Skip
    (return `None`) when disabled, no real audio, or a train is already
    running. Never raises into Save."""
    if os.environ.get("BOO_PREDICT_SAVE_TRAIN", "1") == "0":
        return None
    if not _has_real_audio(lab_root, album, track):
        return None
    if not _TRAIN_LOCK.acquire(blocking=False):
        return None

    def _run():
        try:
            train(lab_root, album=album or None, epochs=SAVE_EPOCHS,
                  allow_holdout_fallback=holdout_fallback_enabled())
        except Exception as exc:  # noqa: BLE001 - Save must never be harmed
            print("predict: save-train skipped:", exc)
        finally:
            _TRAIN_LOCK.release()

    thread = threading.Thread(target=_run, daemon=True, name="boo-predict-train")
    thread.start()
    return thread
