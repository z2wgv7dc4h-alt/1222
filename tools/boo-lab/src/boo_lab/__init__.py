"""boo-lab: catalogue + structure + gated riff extract. Not a writer."""

from . import _natten_compat

# Apply the allin1/madmom compatibility shims as early as possible. Any
# `import boo_lab...` (doctor, structure, the CLI) must have the py2 builtins /
# numpy / collections aliases in place before madmom or allin1 are imported.
# `install()` is idempotent and imports no torch.
_natten_compat.install()

__version__ = "0.1.0"


def _install_phrase_retune() -> None:
    """Prefer retuned mid-grain pack_phrase_spans when the module is present."""
    try:
        from . import phrase_spans as _ps
        from . import tabnotes_drafts as _td
        _td.pack_phrase_spans = _ps.pack_phrase_spans
    except Exception:
        pass


_install_phrase_retune()
