"""The legacy-NATTEN shim is what makes `allin1` importable on modern
natten/torch. These tests pin the exact index ports and the shape/softmax
contract so a future refactor cannot silently break allin1 again."""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from boo_lab import _natten_compat as nc  # noqa: E402


def test_window_start_matches_natten_015_values():
    # length=5, kernel_size=3, dilation=1 -> neighborhood_size=1
    assert nc._window_start_1d(5, 3, 1).tolist() == [0, 0, 1, 2, 2]


def test_pb_start_matches_natten_015_values():
    assert nc._pb_start_1d(5, 3, 1).tolist() == [2, 1, 1, 1, 0]


def test_1d_shapes_and_softmax_is_normalized():
    q = torch.randn(2, 3, 40, 8)
    k = torch.randn(2, 3, 40, 8)
    v = torch.randn(2, 3, 40, 8)
    rpb = torch.randn(3, 2 * 7 - 1)
    scores = nc.natten1dqkrpb(q, k, rpb, 7, 1)
    assert tuple(scores.shape) == (2, 3, 40, 7)
    assert torch.isfinite(scores).all()
    probs = torch.softmax(scores, dim=-1)
    assert torch.allclose(probs.sum(-1), torch.ones_like(probs.sum(-1)))
    assert tuple(nc.natten1dav(probs, v, 7, 1).shape) == (2, 3, 40, 8)


def test_1d_dilated_is_finite():
    q = torch.randn(1, 2, 30, 4)
    rpb = torch.randn(2, 2 * 5 - 1)
    assert torch.isfinite(nc.natten1dqkrpb(q, q, rpb, 5, 3)).all()


def test_2d_shapes_and_softmax_is_normalized():
    q = torch.randn(2, 3, 9, 11, 8)
    k = torch.randn(2, 3, 9, 11, 8)
    v = torch.randn(2, 3, 9, 11, 8)
    rpb = torch.randn(3, 2 * 3 - 1, 2 * 3 - 1)
    scores = nc.natten2dqkrpb(q, k, rpb, 3, 1)
    assert tuple(scores.shape) == (2, 3, 9, 11, 9)
    probs = torch.softmax(scores, dim=-1)
    assert torch.allclose(probs.sum(-1), torch.ones_like(probs.sum(-1)))
    assert tuple(nc.natten2dav(probs, v, 3, 1).shape) == (2, 3, 9, 11, 8)


def test_install_restores_legacy_names_when_natten_present():
    pytest.importorskip("natten")
    nc.install()
    import natten.functional as F

    for name in ("natten1dqkrpb", "natten1dav", "natten2dqkrpb", "natten2dav"):
        assert hasattr(F, name)


def test_install_restores_py2_builtins_and_numpy_aliases():
    import builtins

    nc.install()
    assert builtins.basestring is str
    assert builtins.long is int
    assert builtins.integer is int
