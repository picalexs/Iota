from __future__ import annotations

import sys
from pathlib import Path


# Ensure imports like `from quantum_diag...` resolve when tests are run from repo root.
PROJECTS_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECTS_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECTS_ROOT))
