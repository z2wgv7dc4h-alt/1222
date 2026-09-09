import sys
from pathlib import Path

_ENGINE_DIR = Path(__file__).resolve().parent.parent.parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
