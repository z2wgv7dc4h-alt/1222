class Fretboard:
    def __init__(self, tuning: list[int], max_fret: int = 24):
        if not tuning:
            raise ValueError("tuning must have at least one string")
        if max_fret < 0:
            raise ValueError("max_fret must be >= 0")
        self.tuning = list(tuning)
        self.max_fret = max_fret

    def fret_to_midi(self, string: int, fret: int) -> int:
        if not (0 <= string < len(self.tuning)):
            raise ValueError(f"string out of range: {string}")
        if not (0 <= fret <= self.max_fret):
            raise ValueError(f"fret out of range: {fret}")
        return self.tuning[string] + fret

    def midi_to_frets(self, midi: int) -> list[tuple[int, int]]:
        positions = []
        for string, open_note in enumerate(self.tuning):
            fret = midi - open_note
            if 0 <= fret <= self.max_fret:
                positions.append((string, fret))
        return positions

    def pitch_to_fret(
        self,
        pitch: int,
        max_fret: int = 12,
        prev: tuple[int, int] | None = None,
    ) -> tuple[int, int]:
        """Ported from reference/ww-forge-prior-attempt/engine/tab_score.py.

        Unlike the source, this rejects unplayable pitches instead of
        fabricating a fret position — a note must be a real (string, fret).
        """
        search_max = min(max_fret, self.max_fret)
        candidates = []
        for string, open_note in enumerate(self.tuning):
            fret = pitch - open_note
            if 0 <= fret <= search_max:
                candidates.append((string, fret))
        if not candidates:
            raise ValueError(f"pitch {pitch} is not playable within max_fret={search_max}")
        if prev is None:
            return min(candidates, key=lambda c: (c[0], c[1]))
        prev_string, prev_fret = prev
        return min(
            candidates,
            key=lambda c: (abs(c[1] - prev_fret) + abs(c[0] - prev_string) * 2, c[0]),
        )
