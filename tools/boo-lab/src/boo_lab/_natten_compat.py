"""Provide the pre-0.17 NATTEN functional API on top of any natten (or torch).

`allin1` (the optional structure intern) calls the old four functions
`natten1dqkrpb` / `natten1dav` / `natten2dqkrpb` / `natten2dav`, which NATTEN
removed in 0.17. There is no Windows/py3.12 wheel for natten <=0.15 (it needs
CUDA to build), so this module reimplements that API in pure PyTorch and
registers it on `natten.functional` before `allin1` is imported.

Semantics mirror natten 0.15's CPU kernels exactly (`csrc/.../naive/
pointwise_neighborhood_*`, `natten_cpu_commons.h`):
  * the neighborhood window START is clamped to stay in bounds
    (`get_window_start`); keys are gathered at `ki*dilation + window_start`;
  * relative-position bias is indexed `rpb[h, get_pb_start(i) + ki]`.
There is no attention mask -- boundary queries attend to the clamped window.
"""


def _window_start_1d(length, kernel_size, dilation):
    """Exact port of natten `get_window_start` (1D)."""
    import torch

    n = kernel_size // 2
    if dilation <= 1:
        i = torch.arange(length)
        return (
            torch.clamp(i - n, min=0)
            + (i + n >= length).long() * (length - i - n - 1)
        )
    vals = []
    for i in range(length):
        ni = i - n * dilation
        if ni < 0:
            vals.append(i % dilation)
        elif i + n * dilation >= length:
            imodd = i % dilation
            a = (length // dilation) * dilation
            b = length - a
            vals.append(
                length - b + imodd - 2 * n * dilation
                if imodd < b
                else a + imodd - kernel_size * dilation
            )
        else:
            vals.append(ni)
    return torch.tensor(vals, dtype=torch.long)


def _pb_start_1d(length, kernel_size, dilation):
    """Exact port of natten `get_pb_start` (1D)."""
    import torch

    n = kernel_size // 2
    if dilation <= 1:
        i = torch.arange(length)
        return (
            n
            + (i < n).long() * (n - i)
            + (i + n >= length).long() * (length - i - 1 - n)
        )
    vals = []
    for i in range(length):
        if i - n * dilation < 0:
            vals.append(kernel_size - 1 - (i // dilation))
        elif i + n * dilation >= length:
            vals.append((length - i - 1) // dilation)
        else:
            vals.append(n)
    return torch.tensor(vals, dtype=torch.long)


def natten1dqkrpb(query, key, rpb, kernel_size, dilation):
    import torch

    b, h, length, dim = query.shape
    ni = _window_start_1d(length, kernel_size, dilation).to(query.device)
    pi = _pb_start_1d(length, kernel_size, dilation).to(query.device)
    ki = torch.arange(kernel_size, device=query.device)
    j = ni[:, None] + ki[None, :] * dilation  # (L, ks)
    kn = key[:, :, j, :]  # (B,H,L,ks,D)
    logits = (query.unsqueeze(-2) * kn).sum(-1)  # (B,H,L,ks)
    return logits + rpb[:, pi[:, None] + ki[None, :]].unsqueeze(0)


def natten1dav(attn, value, kernel_size, dilation):
    b, h, length, _ = attn.shape
    ni = _window_start_1d(length, kernel_size, dilation).to(attn.device)
    ki = _arange(kernel_size, attn)
    j = ni[:, None] + ki[None, :] * dilation
    vn = value[:, :, j, :]  # (B,H,L,ks,D)
    return (attn.unsqueeze(-1) * vn).sum(-2)


def natten2dqkrpb(query, key, rpb, kernel_size, dilation):
    import torch

    b, h, hh, ww, dim = query.shape
    nih = _window_start_1d(hh, kernel_size, dilation).to(query.device)
    niw = _window_start_1d(ww, kernel_size, dilation).to(query.device)
    pih = _pb_start_1d(hh, kernel_size, dilation).to(query.device)
    piw = _pb_start_1d(ww, kernel_size, dilation).to(query.device)
    ks = torch.arange(kernel_size, device=query.device)
    out = []
    for a in range(kernel_size):
        row = []
        jh = nih + a * dilation  # (Hh,)
        for c in range(kernel_size):
            jw = niw + c * dilation  # (Ww,)
            kn = key[:, :, jh][:, :, :, jw, :]  # (B,H,Hh,Ww,D)
            logits = (query * kn).sum(-1)  # (B,H,Hh,Ww)
            bias = rpb[:, pih[:, None] + a, piw[None, :] + c]  # (H,Hh,Ww)
            row.append(logits + bias.unsqueeze(0))
        out.append(torch.stack(row, dim=-1))  # (B,H,Hh,Ww,Ww)
    return torch.stack(out, dim=-2).reshape(b, h, hh, ww, kernel_size * kernel_size)


def natten2dav(attn, value, kernel_size, dilation):
    b, h, hh, ww, _ = attn.shape
    dim = value.shape[-1]
    nih = _window_start_1d(hh, kernel_size, dilation).to(attn.device)
    niw = _window_start_1d(ww, kernel_size, dilation).to(attn.device)
    out = value.new_zeros((b, h, hh, ww, dim))
    for a in range(kernel_size):
        jh = nih + a * dilation
        for c in range(kernel_size):
            jw = niw + c * dilation
            attn_s = attn[..., a * kernel_size + c]
            vn = value[:, :, jh][:, :, :, jw, :]
            out = out + attn_s.unsqueeze(-1) * vn
    return out


def _arange(kernel_size, like):
    import torch

    return torch.arange(kernel_size, device=like.device)


def install(force: bool = False) -> None:
    """Make `allin1` importable/runnable: restore the Python-2 builtins and
    NumPy aliases madmom still reads, make NumPy 2 tolerate madmom's ragged
    arrays, then register the legacy NATTEN names on `natten.functional`."""
    import builtins

    for name, value in (("basestring", str), ("long", int), ("integer", int)):
        if not hasattr(builtins, name):
            setattr(builtins, name, value)

    try:
        import numpy as np

        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name, value in (("int", int), ("float", float),
                                ("complex", complex), ("bool", bool),
                                ("object", object), ("str", str),
                                ("long", int), ("unicode", str)):
                if not hasattr(np, name):
                    setattr(np, name, value)

        # NumPy 2 refuses ragged sequences that NumPy 1 silently made object
        # arrays. madmom's downbeat tracker relies on that (`np.asarray` of a
        # list of `(path_array, log_prob)` pairs). Fall back only when NumPy
        # itself rejects the input, so normal callers are untouched.
        if not getattr(np, "_boo_ragged_asarray", False):
            orig_asarray = np.asarray

            def _asarray(a, dtype=None, order=None, **kwargs):
                try:
                    return orig_asarray(a, dtype=dtype, order=order, **kwargs)
                except ValueError:
                    if (isinstance(a, (list, tuple)) and a
                            and isinstance(a[0], (list, tuple))):
                        width = max(len(r) for r in a)
                        out = np.empty((len(a), width), dtype=object)
                        for i, row in enumerate(a):
                            for j, val in enumerate(row):
                                out[i, j] = val
                        return out
                    raise

            np._boo_ragged_asarray = True
            np.asarray = _asarray
    except Exception:
        pass

    try:
        import natten.functional as F
    except Exception:
        return
    mapping = {
        "natten1dqkrpb": natten1dqkrpb,
        "natten1dav": natten1dav,
        "natten2dqkrpb": natten2dqkrpb,
        "natten2dav": natten2dav,
    }
    for name, fn in mapping.items():
        if force or not hasattr(F, name):
            setattr(F, name, fn)
