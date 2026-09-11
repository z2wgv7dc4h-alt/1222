from boo_lab.gate import lock_score, pass_gate


def test_lock_perfect():
    beats = [0.0, 0.5, 1.0, 1.5]
    notes = [0.0, 0.5, 1.0]
    assert lock_score(beats, notes) == 1.0
    assert pass_gate(1.0)


def test_lock_miss():
    beats = [0.0, 1.0]
    notes = [0.37]
    assert lock_score(beats, notes) < 0.5
