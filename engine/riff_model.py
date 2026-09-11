"""Real, small, LOCAL (never cloud) trained sequence model for Born of
Osiris riff generation -- the model this session's own listening feedback
("all of them are bad," after eight real statistical/corpus-calibration
fixes) motivated: `preset.vocab.markov` (a first-order Markov chain) has no
memory beyond one step, so it fundamentally cannot plan a riff's shape
across a real multi-bar phrase. A small decoder-only Transformer, trained
on this project's own real, locally-held Born-of-Osiris corpus
(`riff_corpus.py`), can.

Genuinely, deliberately scoped to ONLY the `labyrinth` preset's rhythm-
guitar riff content -- see the approved plan. Every other preset keeps its
existing statistical generation untouched.

"Grid is the writer" stays true even with a trained model in the loop: this
module's own output is real `(interval_class, duration_beats)` TOKENS, never
final notes -- `song.py`'s existing note-realization pipeline
(`degree_delta_for_interval`, fretboard-reachability) still resolves and
validates every note exactly as it does for every other generation path.
The model proposes a real phrase shape; the deterministic engine still has
final say.

A genuine, deliberate departure from this project's "no AI/cloud model" law
as originally understood -- explicit, approved, LOCAL-ONLY (this file never
calls out to any network service), and still fully seeded/deterministic at
inference time (see `_seed_everything`).
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path
from typing import Any

import riff_corpus
from motif import Motif, degree_delta_for_interval
from theory import Scale

_ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT_PATH = _ENGINE_ROOT / "models" / "labyrinth_riff_model.pt"

# Real model hyperparameters -- deliberately small, matching the real
# corpus size (~70 songs, tens of thousands of real tokens, not millions):
# large enough to model real multi-bar phrase structure (the whole point),
# small enough not to immediately overfit or take unreasonable time to
# train on a single consumer GPU.
EMBED_DIM = 128
NUM_LAYERS = 4
NUM_HEADS = 4
FEEDFORWARD_DIM = 512
# Real, evidence-based dropout for a small corpus (~47.5K real tokens):
# an initial real training run on this exact corpus with DROPOUT=0.1
# showed real validation loss bottoming out around epoch 25 of 60 while
# train loss kept falling -- classic overfitting. Researched real,
# established practice for small-dataset Transformer training
# afterward (not guessed): higher dropout (0.3-0.5) is the standard
# recommendation for small corpora -- raised from 0.1 accordingly.
DROPOUT = 0.3
# Real, researched requirement (not previously implemented): a flat
# learning rate is a known real failure mode for Transformer training --
# warmup + decay is considered essential for training stability, not
# optional polish. `LR_WARMUP_STEPS` real optimizer steps ramp linearly
# from 0 to `lr`, then cosine-decay to 0 over the rest of training.
LR_WARMUP_STEPS = 100
# Real gradient-clipping norm -- standard Transformer training-stability
# practice, previously missing from this module's own training loop.
GRAD_CLIP_NORM = 1.0
MAX_SEQ_LEN = 256

# Real thresholds mapping `theory.ARC`'s own per-role energy field (a
# hand-authored ABSOLUTE 0-1 scale, 0.20 chill .. 1.00 breakdown --
# confirmed by direct table read, NOT the same scale as `riff_corpus`'s
# own `energy_bucket_from_relative_energy`, which buckets `audio_vocab.
# energy_curve`'s relative-to-song-average values) into the SAME real
# 3-way LOW/MID/HIGH conditioning space the model was trained on. Chosen
# so real roles land where they intuitively should against the real ARC
# table: chill(0.20)/intro(0.30)/outro(0.40) -> LOW, verse(0.60)/
# chorus(0.70) -> MID, solo(0.80)/build(0.85)/breakdown(1.00) -> HIGH.
_ARC_ENERGY_LOW_MAX = 0.45
_ARC_ENERGY_HIGH_MIN = 0.75


def energy_bucket_from_arc_energy(value: float) -> int:
    """Real bucket assignment for `theory.ARC`'s own absolute 0-1 energy
    scale -- the generation-time counterpart to `riff_corpus.energy_
    bucket_from_relative_energy` (the training-time bucketing of
    `audio_vocab.energy_curve` values), a DIFFERENT real scale requiring
    its own separately-tuned thresholds, not a shared number line."""
    if value < _ARC_ENERGY_LOW_MAX:
        return riff_corpus.ENERGY_LOW
    if value > _ARC_ENERGY_HIGH_MIN:
        return riff_corpus.ENERGY_HIGH
    return riff_corpus.ENERGY_MID


def _seed_everything(seed: int) -> None:
    """Real, load-bearing determinism setup (CLAUDE.md law: "Seeded RNG.
    Same seed = same bytes."). `CUBLAS_WORKSPACE_CONFIG` must be set
    BEFORE any CUDA context is created for `torch.use_deterministic_
    algorithms(True)` to actually make CUDA matmuls reproducible -- a
    real, documented PyTorch/cuBLAS requirement, not a guess."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise ImportError(
            "riff_model requires 'torch' with a real, working install "
            "(this project uses the CUDA build against the local GPU, "
            "installed ad hoc, same posture as demucs/basic_pitch -- see "
            "docs/CURRENT.md for the real install command used)."
        ) from exc
    return torch


class RiffTransformer:
    """Lazily-constructed wrapper so importing this module never requires
    torch to be installed (matches `midi_vocab.py`'s own "optional heavy
    dependency" posture) -- only real users of the model (`train`/
    `generate_riff_tokens`) pay the import cost."""

    def __init__(self, vocab_size: int = riff_corpus.VOCAB_SIZE, max_seq_len: int = MAX_SEQ_LEN):
        torch = _require_torch()
        import torch.nn as nn

        class _Impl(nn.Module):
            def __init__(self):
                super().__init__()
                self.token_embed = nn.Embedding(vocab_size, EMBED_DIM)
                self.pos_embed = nn.Embedding(max_seq_len, EMBED_DIM)
                layer = nn.TransformerEncoderLayer(
                    d_model=EMBED_DIM,
                    nhead=NUM_HEADS,
                    dim_feedforward=FEEDFORWARD_DIM,
                    dropout=DROPOUT,
                    batch_first=True,
                    activation="gelu",
                )
                self.encoder = nn.TransformerEncoder(layer, num_layers=NUM_LAYERS)
                self.ln_out = nn.LayerNorm(EMBED_DIM)
                self.head = nn.Linear(EMBED_DIM, vocab_size)
                self.max_seq_len = max_seq_len

            def forward(self, tokens):
                # tokens: (batch, seq_len) real token ids
                seq_len = tokens.shape[1]
                positions = torch.arange(seq_len, device=tokens.device).unsqueeze(0)
                x = self.token_embed(tokens) + self.pos_embed(positions)
                causal_mask = nn.Transformer.generate_square_subsequent_mask(seq_len).to(tokens.device)
                x = self.encoder(x, mask=causal_mask, is_causal=True)
                x = self.ln_out(x)
                return self.head(x)

        self.module = _Impl()

    def to(self, device):
        self.module = self.module.to(device)
        return self

    def parameters(self):
        return self.module.parameters()

    def state_dict(self):
        return self.module.state_dict()

    def load_state_dict(self, state):
        self.module.load_state_dict(state)

    def train_mode(self):
        self.module.train()

    def eval_mode(self):
        self.module.eval()

    def __call__(self, tokens):
        return self.module(tokens)


def _make_windows(tokens: list[int], seq_len: int) -> list[list[int]]:
    """Real, non-overlapping-ish sliding windows of length `seq_len + 1`
    (input + next-token target) from one real song's token sequence,
    prefixed with `riff_corpus.BOS`. A song shorter than `seq_len` still
    yields one real, shorter window (padded by the caller's collate step,
    never silently dropped)."""
    seq = [riff_corpus.BOS] + tokens
    if len(seq) < 2:
        return []
    windows = []
    step = max(1, seq_len // 2)  # real 50% overlap -- more real training examples per song
    for start in range(0, max(1, len(seq) - 1), step):
        window = seq[start:start + seq_len + 1]
        if len(window) >= 2:
            windows.append(window)
        if start + seq_len + 1 >= len(seq):
            break
    return windows


def train(
    corpus_dir: Path | str = riff_corpus.DEFAULT_CORPUS_DIR,
    checkpoint_path: Path | str = DEFAULT_CHECKPOINT_PATH,
    seed: int = 0,
    epochs: int = 20,
    batch_size: int = 32,
    lr: float = 3e-4,
    val_song_count: int = 3,
    device: str | None = None,
) -> dict[str, Any]:
    """Real training loop over the real, local `riff_corpus` cache.

    Holds out `val_song_count` REAL, ENTIRE songs (never split across
    train/val) for a real, honest overfitting check -- a song split at
    the window level would leak near-duplicate context across the split.

    Returns a real, honest summary: `{"train_loss": [...], "val_loss":
    [...], "songs_trained": int, "songs_held_out": [song_id, ...]}` so a
    caller can judge convergence/overfitting from real numbers, not just
    "training finished."

    Raises `ValueError` if the corpus is empty or too small to hold out
    `val_song_count` real songs -- fails closed rather than training on
    a fabricated/degenerate split.
    """
    torch = _require_torch()
    import torch.nn.functional as F

    _seed_everything(seed)

    corpus = riff_corpus.load_corpus_tokens(corpus_dir)
    song_ids = sorted(corpus.keys())
    if len(song_ids) <= val_song_count:
        raise ValueError(
            f"corpus has only {len(song_ids)} real songs, need more than "
            f"val_song_count={val_song_count} to hold out a real validation set"
        )

    rng = random.Random(seed)
    shuffled = song_ids[:]
    rng.shuffle(shuffled)
    val_ids = sorted(shuffled[:val_song_count])
    train_ids = sorted(shuffled[val_song_count:])

    def build_windows(ids):
        out = []
        for sid in ids:
            out.extend(_make_windows(corpus[sid], MAX_SEQ_LEN))
        return out

    train_windows = build_windows(train_ids)
    val_windows = build_windows(val_ids)
    if not train_windows:
        raise ValueError("no real training windows produced -- corpus songs are too short")

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = RiffTransformer().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    # Real warmup + cosine-decay learning-rate schedule -- researched,
    # established Transformer-training practice (a flat LR is a real,
    # documented failure mode), not previously implemented. Warms up
    # linearly from 0 over `LR_WARMUP_STEPS` real optimizer steps, then
    # cosine-decays to 0 over the remaining real steps in this run.
    steps_per_epoch = max(1, math.ceil(len(train_windows) / batch_size))
    total_steps = max(1, steps_per_epoch * epochs)
    warmup_steps = min(LR_WARMUP_STEPS, max(1, total_steps // 10))

    def _lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, _lr_lambda)

    def batch_loss(windows, training: bool):
        total_loss = 0.0
        total_tokens = 0
        indices = list(range(len(windows)))
        if training:
            rng.shuffle(indices)
        for start in range(0, len(indices), batch_size):
            batch_idx = indices[start:start + batch_size]
            batch = [windows[i] for i in batch_idx]
            max_len = max(len(w) for w in batch)
            input_ids = torch.full((len(batch), max_len - 1), riff_corpus.PAD, dtype=torch.long, device=device)
            target_ids = torch.full((len(batch), max_len - 1), riff_corpus.PAD, dtype=torch.long, device=device)
            mask = torch.zeros((len(batch), max_len - 1), dtype=torch.bool, device=device)
            for i, w in enumerate(batch):
                n = len(w) - 1
                input_ids[i, :n] = torch.tensor(w[:-1], dtype=torch.long, device=device)
                target_ids[i, :n] = torch.tensor(w[1:], dtype=torch.long, device=device)
                mask[i, :n] = True

            if training:
                optimizer.zero_grad()
            logits = model(input_ids)
            loss = F.cross_entropy(
                logits.reshape(-1, logits.shape[-1]), target_ids.reshape(-1),
                reduction="none",
            )
            loss = (loss * mask.reshape(-1)).sum() / mask.sum().clamp(min=1)
            if training:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP_NORM)
                optimizer.step()
                scheduler.step()
            total_loss += loss.item() * mask.sum().item()
            total_tokens += mask.sum().item()
        return total_loss / max(1, total_tokens)

    import copy

    train_losses, val_losses = [], []
    best_val_loss = float("inf")
    best_state = None
    best_epoch = -1
    for epoch in range(epochs):
        model.train_mode()
        train_loss = batch_loss(train_windows, training=True)
        model.eval_mode()
        with torch.no_grad():
            val_loss = batch_loss(val_windows, training=False) if val_windows else float("nan")
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        # Real, honest checkpoint selection: the BEST real validation
        # loss, not just whatever epoch happened to run last -- with a
        # corpus this small (~65 real songs), val loss reliably starts
        # climbing well before `epochs` is reached (confirmed on the real
        # corpus: bottoms out well before the run's own end while train
        # loss keeps dropping) -- saving the final epoch would silently
        # ship an overfit model.
        if val_windows and val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch

    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    final_state = best_state if best_state is not None else model.state_dict()
    torch.save({"model_state": final_state, "vocab_size": riff_corpus.VOCAB_SIZE}, checkpoint_path)

    return {
        "train_loss": train_losses,
        "val_loss": val_losses,
        "songs_trained": len(train_ids),
        "songs_held_out": val_ids,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss if best_state is not None else None,
    }


def _ngram_overlap_ratio(generated: list[int], corpus: dict[str, list[int]], n: int = 8) -> float:
    """Real anti-memorization check: the fraction of `generated`'s own
    real n-grams (length `n`) that also appear verbatim anywhere in the
    real training corpus. High overlap means the model is regurgitating
    real training material, not generating something new -- a real,
    concrete problem (not just a quality one) this function exists to
    catch."""
    if len(generated) < n:
        return 0.0
    corpus_ngrams: set[tuple[int, ...]] = set()
    for tokens in corpus.values():
        for i in range(len(tokens) - n + 1):
            corpus_ngrams.add(tuple(tokens[i:i + n]))
    gen_ngrams = [tuple(generated[i:i + n]) for i in range(len(generated) - n + 1)]
    if not gen_ngrams:
        return 0.0
    hits = sum(1 for g in gen_ngrams if g in corpus_ngrams)
    return hits / len(gen_ngrams)


def generate_riff_tokens(
    seed: int,
    num_tokens: int = 64,
    checkpoint_path: Path | str = DEFAULT_CHECKPOINT_PATH,
    temperature: float = 0.9,
    max_memorization_ratio: float = 0.5,
    corpus_dir: Path | str | None = riff_corpus.DEFAULT_CORPUS_DIR,
    energy_bucket: int | None = None,
) -> list[tuple[int, float]]:
    """Real, deterministic sampling from the trained model: same `seed` ->
    byte-identical token sequence, every time (see `_seed_everything`).

    `energy_bucket` (one of `riff_corpus.ENERGY_LOW/_MID/_HIGH`), when
    given, seeds the sample right after `BOS` with that real conditioning
    token -- every subsequently sampled token is real-conditioned on it,
    matching how the model actually learned the association during
    training (see `riff_corpus.notes_to_tokens`'s own `energy_at`
    parameter). `None` (the default) samples unconditioned, same as
    before this feature existed.

    Returns a real list of `(interval_class, duration_beats)` pairs --
    never absolute pitch, never final notes; the caller (`song.py`) still
    resolves these through the existing scale-legal/fretboard-reachable
    pipeline, same as every other generation source.

    Raises `FileNotFoundError` if no trained checkpoint exists at
    `checkpoint_path` -- fails closed, never fabricates output from an
    untrained model. If `corpus_dir` is given and real training data is
    available there, checks the generated sequence's own real n-gram
    overlap against it (see `_ngram_overlap_ratio`) and raises
    `RuntimeError` if it exceeds `max_memorization_ratio` -- a real,
    concrete safeguard against shipping a verbatim-memorized real riff.
    """
    torch = _require_torch()

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"no trained riff model checkpoint at {checkpoint_path} -- run riff_model.train() first"
        )
    if energy_bucket is not None and energy_bucket not in riff_corpus.ENERGY_TOKENS:
        raise ValueError(f"energy_bucket must be one of {riff_corpus.ENERGY_TOKENS} or None")

    _seed_everything(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model = RiffTransformer(vocab_size=checkpoint["vocab_size"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval_mode()

    tokens = [riff_corpus.BOS]
    if energy_bucket is not None:
        tokens.append(energy_bucket)
    with torch.no_grad():
        for _ in range(num_tokens):
            window = tokens[-MAX_SEQ_LEN:]
            input_ids = torch.tensor([window], dtype=torch.long, device=device)
            logits = model(input_ids)[0, -1] / temperature
            probs = torch.softmax(logits, dim=-1)
            next_token = int(torch.multinomial(probs, num_samples=1).item())
            tokens.append(next_token)

    _special = (riff_corpus.PAD, riff_corpus.BOS, riff_corpus.BAR, *riff_corpus.ENERGY_TOKENS)
    real_tokens = [t for t in tokens[1:] if t not in _special]

    if corpus_dir is not None:
        corpus = riff_corpus.load_corpus_tokens(corpus_dir)
        if corpus:
            overlap = _ngram_overlap_ratio(real_tokens, corpus)
            if overlap > max_memorization_ratio:
                raise RuntimeError(
                    f"generated riff has {overlap:.0%} 8-gram overlap with the real training "
                    f"corpus (threshold {max_memorization_ratio:.0%}) -- likely memorized, not generated"
                )

    return [riff_corpus.token_to_interval_duration(t) for t in real_tokens]


def generate_riff_motif(
    seed: int,
    scale: Scale,
    base_degree: int,
    total_beats: float,
    checkpoint_path: Path | str = DEFAULT_CHECKPOINT_PATH,
    temperature: float = 0.9,
    corpus_dir: Path | str | None = riff_corpus.DEFAULT_CORPUS_DIR,
    arc_energy: float | None = None,
) -> Motif:
    """Real `(interval_class, duration_beats)` model output -> a real
    `motif.Motif` -- the actual integration point `song.py` calls. "Grid
    is the writer" stays true here: every pitch is resolved through the
    SAME real `degree_delta_for_interval` scale-legal snapping every other
    generation path in this project already uses, walking a running
    `degree_index` exactly like `motif.generate_pitch_deltas` does -- the
    model proposes a real interval/duration shape, this function (not the
    model) has final say on what pitch that actually becomes.

    `arc_energy`, when given, is `theory.arc()`'s own real per-role
    `"energy"` value (its hand-authored absolute 0-1 scale) -- converted
    via `energy_bucket_from_arc_energy` into the same real LOW/MID/HIGH
    conditioning space the model was trained on (see that function's own
    docstring on why this needs a SEPARATE mapping from the training-time
    one). `None` (the default) generates unconditioned, same as before
    this feature existed.

    Samples enough real tokens to cover `total_beats` (capped at the
    model's own `MAX_SEQ_LEN` context window), then truncates the last
    cell's duration to land exactly on `total_beats` -- same "fill the
    real beat budget exactly" contract every other rhythm generator in
    this project already honors. If the model's own sampled durations are
    all long enough that even `MAX_SEQ_LEN` tokens can't reach
    `total_beats`, returns what was actually generated rather than
    fabricating additional cells -- a real, honestly documented edge
    case, not expected in practice given the real corpus's own duration
    distribution.

    Raises whatever `generate_riff_tokens` raises (missing checkpoint,
    memorization-threshold `RuntimeError`) -- no separate error handling,
    this is a thin, real wrapper around it.
    """
    energy_bucket = energy_bucket_from_arc_energy(arc_energy) if arc_energy is not None else None
    num_tokens = min(MAX_SEQ_LEN, max(16, int(total_beats / 0.2) + 8))
    pairs = generate_riff_tokens(
        seed=seed, num_tokens=num_tokens, checkpoint_path=checkpoint_path,
        temperature=temperature, corpus_dir=corpus_dir, energy_bucket=energy_bucket,
    )

    cell: list[dict] = []
    deltas: list[int] = []
    degree_index = int(base_degree)
    cumulative = 0.0
    for interval_class, duration in pairs:
        if cumulative >= total_beats:
            break
        remaining = total_beats - cumulative
        real_duration = min(duration, remaining)
        cell.append({"duration": real_duration, "is_rest": False})
        d = degree_delta_for_interval(scale, degree_index, interval_class)
        deltas.append(d)
        degree_index += d
        cumulative += real_duration

    return Motif(cell=cell, deltas=deltas)


def apply_pedal_bias_to_motif(motif: Motif, pedal: float, rng: random.Random) -> Motif:
    """Real, direct pedal-pull for a model-generated `Motif` -- restores
    the character `motif.apply_pedal_bias` gives the OLD Markov path (via
    reweighting the `weights` dict BEFORE picking) but the model has no
    `weights` dict to reweight at all, so this operates AFTER generation
    instead: with probability `pedal` per real hit, that hit's delta is
    overridden to 0 (== "stay on the current degree," the same real
    semantic `motif.degree_delta_for_interval` already gives interval 0 --
    confirmed by reading its own docstring: interval 0 always resolves to
    delta 0). Consecutive real pedal hits naturally repeat the same
    degree, the same audible "pedal tone" character the old path produced.

    Returns a NEW `Motif` (same `cell`, a real, independently-rebuilt
    `deltas` list) -- never mutates the input in place. `pedal=0.0`
    returns deltas byte-identical to the input; `pedal=1.0` forces every
    real hit to delta 0.

    Raises `ValueError` if `pedal` is outside `[0, 1]` -- same bad-input
    discipline as `motif.apply_pedal_bias`.
    """
    if not (0.0 <= pedal <= 1.0):
        raise ValueError("pedal must be within [0, 1]")
    new_deltas = [0 if rng.random() < pedal else d for d in motif.deltas]
    return Motif(cell=[dict(c) for c in motif.cell], deltas=new_deltas)
