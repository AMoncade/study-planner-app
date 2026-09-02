"""Point d'entrée Vercel : expose l'application FastAPI de src/planner/web/api.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from planner.web.api import create_app  # noqa: E402

app = create_app()
