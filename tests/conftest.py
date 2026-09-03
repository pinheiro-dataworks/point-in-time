"""Shared pytest configuration.

Puts the repo root on sys.path so ``import dashboard.*`` resolves the same
way it does for ``streamlit run dashboard/app.py`` — see dashboard/app.py's
own sys.path note. ``src/`` is on the path via the editable install
(``pip install -e .``), so ``pit_lab`` needs no equivalent here.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
