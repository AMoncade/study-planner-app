"""Captures d'écran de chaque vue pour validation visuelle (phase 13).

Usage : .venv/Scripts/python.exe scripts/screenshots.py
Nécessite data/plan_etudes.db ; écrit les PNG dans screenshots/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # DEFAULT_DB_PATH est relatif à la racine du dépôt
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from planner.storage.db import DEFAULT_DB_PATH, connect  # noqa: E402
from planner.ui.main_window import MainWindow, apply_style  # noqa: E402

# (rangée de navigation, nom de fichier)
SHOTS = (
    (0, "dashboard"),
    (1, "import"),
    (2, "cours"),
    (3, "contraintes"),
    (4, "planning"),
    (5, "stats"),
    (6, "parametres"),
)


def main() -> int:
    out_dir = ROOT / "screenshots"
    out_dir.mkdir(exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Plan-Études")
    apply_style(app)
    conn = connect(DEFAULT_DB_PATH)
    window = MainWindow(conn)
    window.resize(1280, 800)
    window.show()
    app.processEvents()

    for row, name in SHOTS:
        window.nav.setCurrentRow(row)
        app.processEvents()
        app.processEvents()
        window.grab().save(str(out_dir / f"{name}.png"))
        print(f"screenshots/{name}.png")

    # bonus : l'onglet grille peignable de la vue Contraintes
    from PySide6.QtWidgets import QTabWidget

    window.nav.setCurrentRow(3)
    tab_widget = window.constraints_view.findChild(QTabWidget)
    if tab_widget is not None:
        tab_widget.setCurrentIndex(2)
        app.processEvents()
        window.grab().save(str(out_dir / "contraintes_grille.png"))
        print("screenshots/contraintes_grille.png")

    window.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
