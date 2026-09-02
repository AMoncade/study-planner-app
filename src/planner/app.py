"""Point d'entrée graphique : python -m planner.app"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from planner.storage.db import DEFAULT_DB_PATH, connect
from planner.ui.main_window import MainWindow, apply_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Plan-Études")
    apply_style(app)
    conn = connect(DEFAULT_DB_PATH)
    window = MainWindow(conn)
    window.show()
    code = app.exec()
    conn.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
