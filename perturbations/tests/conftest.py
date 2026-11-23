"""
pytest / sys.path bootstrap.

Adds ``src/`` to ``sys.path`` so tests can ``import wiggle`` and the legacy
``import typeclass_mutate`` / ``import bounds`` without any installation step.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
