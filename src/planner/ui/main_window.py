"""Coquille de l'application (ARCHITECTURE §5.0) : barre latérale + QStackedWidget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from planner.ui.views.constraints_view import ConstraintsView
from planner.ui.views.courses_view import CoursesView
from planner.ui.views.dashboard_view import DashboardView
from planner.ui.views.import_view import ImportView
from planner.ui.views.schedule_view import ScheduleView
from planner.ui.views.settings_view import SettingsView

STYLE_PATH = Path(__file__).with_name("style.qss")


class _Placeholder(QWidget):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout

        label = QLabel(message)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()


class MainWindow(QMainWindow):
    data_changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Plan-Études")
        self.resize(1200, 760)

        self.dashboard_view = DashboardView(conn)
        self.import_view = ImportView(conn)
        self.courses_view = CoursesView(conn)
        self.constraints_view = ConstraintsView(conn)
        self.schedule_view = ScheduleView(conn)
        self.settings_view = SettingsView(conn)

        self.stack = QStackedWidget()
        self.nav = QListWidget()
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setMaximumWidth(210)
        for name, widget in (
            ("Tableau de bord", self.dashboard_view),
            ("Importer", self.import_view),
            ("Cours et évaluations", self.courses_view),
            ("Contraintes", self.constraints_view),
            ("Planning", self.schedule_view),
            ("Paramètres", self.settings_view),
        ):
            QListWidgetItem(name, self.nav)
            self.stack.addWidget(widget)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        splitter = QSplitter()
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        status = QStatusBar()
        self.setStatusBar(status)
        self._update_status()

        self.import_view.imported.connect(self._on_data_changed)
        self.constraints_view.changed.connect(self._on_constraints_changed)
        self.schedule_view.changed.connect(self._on_blocks_changed)
        self.settings_view.changed.connect(self._on_data_changed)
        # Le tableau de bord fait un recalcul à blanc : le rafraîchir seulement
        # quand on l'affiche évite de payer ce calcul à chaque modification.
        self.nav.currentRowChanged.connect(self._maybe_refresh_dashboard)

    def _maybe_refresh_dashboard(self, row: int) -> None:
        if row == 0:
            self.dashboard_view.refresh()

    def _on_constraints_changed(self) -> None:
        self.schedule_view.refresh()
        self._update_status()

    def _on_blocks_changed(self) -> None:
        self._update_status()

    def _on_data_changed(self, _course_code: str = "") -> None:
        self.courses_view.refresh()
        self.constraints_view.refresh()
        self.schedule_view.refresh()
        self.dashboard_view.refresh()
        self._update_status()
        self.data_changed.emit()

    def _update_status(self) -> None:
        from planner.storage import repositories as repos

        courses = repos.list_courses(self.conn)
        evaluations = [
            e for c in courses for e in repos.list_evaluations(self.conn, course_id=c.id)
        ]
        missing = sum(1 for e in evaluations if e.due_at is None)
        message = (f"{len(courses)} cours · {len(evaluations)} évaluations"
                   + (f" · ⚠ {missing} sans date" if missing else ""))
        self.statusBar().showMessage(message)


def apply_style(app) -> None:
    if STYLE_PATH.exists():
        app.setStyleSheet(STYLE_PATH.read_text(encoding="utf-8"))
