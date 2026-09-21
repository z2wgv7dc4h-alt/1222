"""Retuned pack_phrase_spans; helpers live in tabnotes_drafts (monkeypatch-friendly)."""
from __future__ import annotations

from . import tabnotes

def pack_phrase_spans(
    pack,
    *,
    min_span: float = 6.0,
    max_span: float = 28.0,
    gap_split: float = 0.75,
    rate_frac: float = 0.45,
    rate_floor: float = 2.0,
    fp_split: float = 0.50,
    identity_jaccard: float = 0.38,
) -> list[dict]:
    """Phrase-level riff boxes from pack guitar activity + pitch contour.

    Finer than the coverage spine (~4 blobs) and coarser than unique bar-run
    hashes (~60 one-shots). Splits on silence gaps, meter/tempo cuts,
    guitar-density jumps, and bar-fingerprint (pitch/articulation) changes.
    Returning phrases reuse the first `figure_id` when fuzzy bar-fp Jaccard
    >= `identity_jaccard`. `[]` when no guitar.
    """
    import bisect
    import statistics
    from . import tabnotes_drafts as _td

    times = tabnotes.onsets_audio(pack, category="guitar")
    measures = list(getattr(pack, "measures", None) or [])
    if len(measures) < 4 or len(times) < 8:
        return []

    # Guitar track with most unique nonempty bar_fps (pitch variety) for structure
    track_idx = _td._pick_structure_track(pack)

    def _once(min_span, max_span, gap_split, rate_frac, rate_floor, fp_split, identity_jaccard):

        rows: list[tuple[float, float, int, float, str]] = []
        for m in measures:
            a = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
            b = _td._measure_audio_end(m)
            if b <= a:
                continue
            lo = bisect.bisect_left(times, a)
            hi = bisect.bisect_left(times, b)
            n = hi - lo
            if n < 2:
                continue
            try:
                fp = tabnotes.bar_fp_tab(pack, m, track_idx)
            except Exception:
                fp = ""
            rows.append((a, b, n, n / (b - a), fp))
        if not rows:
            return []

        rates = [r[3] for r in rows]
        med = statistics.median(rates) if rates else 0.0
        cuts = set(_td.meter_cuts(pack))

        segs: list[list[tuple[float, float, int, float, str]]] = [[rows[0]]]
        for prev, cur in zip(rows, rows[1:]):
            gap = cur[0] - prev[1]
            r0, r1 = prev[3], cur[3]
            at_cut = any(abs(cur[0] - c) < 0.35 for c in cuts)
            fp_jump = _td._fp_jaccard(prev[4], cur[4]) < fp_split if (prev[4] or cur[4]) else False
            split = (
                gap > gap_split
                or at_cut
                or abs(r1 - r0) > max(med * rate_frac, rate_floor)
                or fp_jump
            )
            if split:
                segs.append([cur])
            else:
                segs[-1].append(cur)

        raw = [(seg[0][0], seg[-1][1]) for seg in segs]
        merged: list[list[float]] = []
        for s, e in raw:
            if merged and (e - s) < min_span and (merged[-1][1] - merged[-1][0]) < max_span:
                merged[-1][1] = e
            else:
                merged.append([s, e])

        final: list[tuple[float, float]] = []
        for s, e in merged:
            if e - s <= max_span:
                final.append((round(s, 3), round(e, 3)))
                continue
            cands = [r for r in rows if s + min_span <= r[0] <= e - min_span]
            if not cands:
                final.append((round(s, 3), round(e, 3)))
                continue
            mid = (s + e) / 2.0
            # Prefer a strong fingerprint jump near the middle when splitting longs
            def score(r):
                # lower is better: distance to mid, prefer low jaccard vs prev bar
                return abs(r[0] - mid)
            best = min(cands, key=score)
            final.append((round(s, 3), round(best[0], 3)))
            final.append((round(best[0], 3), round(e, 3)))

        # Assign figure_ids with returning identity
        phrases: list[dict] = []
        seen: list[tuple[str, str]] = []  # (fp, figure_id)
        letter_i = 0
        for s, e in final:
            if e - s < min_span * 0.5:
                continue
            fp = _td._phrase_fingerprint(pack, s, e, track_idx)
            fid = None
            # Empty fingerprints (no notes resolved) must not collapse everything
            # to riff-A via Jaccard(empty, empty) == 1.
            if fp and any(tok.strip("|") for tok in fp.split("||")):
                for prev_fp, prev_id in seen:
                    if not prev_fp:
                        continue
                    if _td._fp_jaccard(fp, prev_fp) >= identity_jaccard:
                        fid = prev_id
                        break
            if fid is None:
                fid = "riff-%s" % _td._letter(letter_i)
                letter_i += 1
                if fp:
                    seen.append((fp, fid))
            phrases.append({
                "role": "riff", "start": s, "end": e, "figure_id": fid,
                "guitar_track": track_idx,
            })
        from collections import Counter
        counts = Counter(p["figure_id"] for p in phrases)
        for p in phrases:
            p["unique"] = counts[p["figure_id"]] == 1
        return phrases

    # Build once, then retune split thresholds toward ~8-20 mid-grain phrases
    # with some returning figure_ids (not 1 blob, not 60 crumbs).
    # Rich bar_fp (full MIDI + 16ths) needs a lower identity_jaccard than the
    # old pitch-class sludge; defaults aim ~0.35-0.45.
    base = dict(min_span=min_span, max_span=max_span, gap_split=gap_split,
                rate_frac=rate_frac, rate_floor=rate_floor, fp_split=fp_split,
                identity_jaccard=identity_jaccard)
    configs = [base]
    # more splits / shorter phrases / looser identity
    configs.append({**base, "fp_split": min(0.62, fp_split + 0.12),
                    "min_span": max(4.5, min_span - 1.5),
                    "identity_jaccard": max(0.28, identity_jaccard - 0.08)})
    # fewer splits / longer phrases / tighter identity
    configs.append({**base, "fp_split": max(0.28, fp_split - 0.12),
                    "min_span": min_span + 2.0, "max_span": max_span + 10.0,
                    "identity_jaccard": min(0.55, identity_jaccard + 0.08)})
    # denser fingerprint cuts
    configs.append({**base, "fp_split": min(0.70, fp_split + 0.20),
                    "rate_frac": max(0.25, rate_frac - 0.1),
                    "min_span": max(4.0, min_span - 2.0),
                    "identity_jaccard": max(0.28, identity_jaccard - 0.05)})
    # mid-grain sweet spot (Mindful / New Reign style)
    configs.append({**base, "min_span": 5.0, "max_span": 24.0,
                    "fp_split": 0.55, "identity_jaccard": 0.40})

    def _score(phrases):
        n = len(phrases)
        if n == 0:
            return -999
        from collections import Counter
        c = Counter(p["figure_id"] for p in phrases)
        returning = sum(1 for v in c.values() if v > 1)
        # prefer 8..20, reward returning figures, penalize extremes
        if 8 <= n <= 20:
            band = 100
        elif 5 <= n <= 24:
            band = 60
        else:
            band = 20 - abs(n - 14)
        return band + 8 * returning - abs(n - 14)

    best, best_s = None, -10**9
    for cfg in configs:
        got = _once(**cfg)
        sc = _score(got)
        if sc > best_s:
            best, best_s = got, sc
    return best or []
