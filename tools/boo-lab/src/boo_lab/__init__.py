"""boo-lab: catalogue + structure + gated riff extract. Not a writer."""

from . import _natten_compat

# Apply the allin1/madmom compatibility shims as early as possible. Any
# `import boo_lab...` (doctor, structure, the CLI) must have the py2 builtins /
# numpy / collections aliases in place before madmom or allin1 are imported.
# `install()` is idempotent and imports no torch.
_natten_compat.install()

__version__ = "0.1.0"
