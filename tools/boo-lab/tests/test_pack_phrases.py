
"""Pack phrase-level Guess structure (mid-grain, not unique 2-bar spam)."""
from types import SimpleNamespace

from boo_lab.tabnotes_drafts import pack_phrase_spans, SOURCE_PHRASE
from boo_lab import schema


def _meas(i, start, end, n_onsets=8):
    # Fake measure with audio times; pack_phrase_spans counts onsets via bisect on times
    return SimpleNamespace(
        measure=i,
        start_sec_audio=start,
        start_ms=start * 1000,
        time_signature=(4, 4),
        # end via duration helper — set attributes _measure_audio_end reads
        duration_sec=end - start,
        end_sec_audio=end,
    )


def test_pack_phrase_spans_mid_grain_not_one_blob(monkeypatch):
    """Dense guitar with rate jumps should yield several phrases, not one spine blob."""
    import boo_lab.tabnotes_drafts as td
    import boo_lab.tabnotes as tn

    # 60s of guitar: slow then fast then slow — expect >= 2 phrases
    times = []
    for t0, rate in [(0.0, 4.0), (20.0, 12.0), (40.0, 4.0)]:
        # onsets for 20s at given rate
        step = 1.0 / rate
        t = t0
        while t < t0 + 20.0 - 1e-6:
            times.append(t)
            t += step

    measures = []
    for i in range(30):  # 2s bars across 60s
        a = i * 2.0
        measures.append(SimpleNamespace(
            measure=i + 1,
            start_sec_audio=a,
            start_ms=a * 1000,
            time_signature=(4, 4),
            end_sec_audio=a + 2.0,
            duration_ms=2000,
        ))

    pack = SimpleNamespace(measures=measures)

    monkeypatch.setattr(tn, "onsets_audio", lambda pack, category="guitar": times)
    monkeypatch.setattr(td, "meter_cuts", lambda pack: [])
    # _measure_audio_end: ensure it works
    monkeypatch.setattr(td, "_measure_audio_end", lambda m: float(getattr(m, "end_sec_audio", 0) or 0))

    spans = pack_phrase_spans(pack, min_span=6.0, max_span=28.0)
    assert 2 <= len(spans) <= 12
    assert all(s["role"] == "riff" and s["end"] > s["start"] for s in spans)
    assert spans[0]["figure_id"].startswith("riff-")


def test_tabnotes_phrase_is_allowed_source():
    box = schema.stamp_box(0.0, 10.0, "riff", source=SOURCE_PHRASE, figure_id="riff-A", heard=False)
    assert box["source"] == SOURCE_PHRASE
    assert box["heard"] is False
