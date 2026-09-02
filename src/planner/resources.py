"""Résolution des ressources embarquées, en développement comme dans l'exe PyInstaller."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Chemin absolu d'une ressource.

    - exe PyInstaller : sous le dossier d'extraction (sys._MEIPASS) ;
    - développement : sous la racine du dépôt, en essayant aussi src/.
    """
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / relative
    root = Path(__file__).resolve().parents[2]
    candidate = root / relative
    if candidate.exists():
        return candidate
    return root / "src" / relative
