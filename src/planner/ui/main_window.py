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

from planner.resources import resource_path
from planner.ui.views.constraints_view import ConstraintsView
from planner.ui.views.courses_view import CoursesView
from planner.ui.views.dashboard_view import DashboardView
from planner.ui.views.import_view import ImportView
from planner.ui.views.schedule_view import ScheduleView
from planner.ui.views.settings_view import SettingsView

STYLE_PATH = resource_path("planner/ui/style.qss")


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

        self._build_toolbar()
        self._build_tray()

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

    # ------------------------------------------------------------ barre d'outils

    def _build_toolbar(self) -> None:
        from PySide6.QtWidgets import QToolBar

        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction("Importer un JSON", lambda: self.nav.setCurrentRow(1))
        toolbar.addAction("Recalculer le plan", self._recalculate)
        toolbar.addSeparator()
        toolbar.addAction("Exporter .ics", self._export_ics)
        toolbar.addAction("Exporter la semaine en PDF", self._export_pdf)
        toolbar.addSeparator()
        toolbar.addAction("Sauvegarder la base", self._backup)
        toolbar.addAction("Restaurer…", self._restore)

    def _recalculate(self) -> None:
        self.nav.setCurrentRow(4)
        self.schedule_view.recalculate()
        self.notify_next_block()

    def _export_ics(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from planner.export import export_ics

        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en .ics", "plan_etudes.ics", "Calendrier (*.ics)"
        )
        if path:
            count = export_ics(self.conn, path)
            self.statusBar().showMessage(f"{count} événement(s) exporté(s) vers {path}",
                                         8000)

    def _export_pdf(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la semaine en PDF", "semaine.pdf", "PDF (*.pdf)"
        )
        if path:
            self.nav.setCurrentRow(4)
            self.schedule_view.export_pdf(path)
            self.statusBar().showMessage(f"Semaine exportée vers {path}", 8000)

    def _backup(self) -> None:
        from planner.storage.db import DEFAULT_DB_PATH, backup_database

        dest = backup_database(DEFAULT_DB_PATH)
        self.statusBar().showMessage(
            f"Base sauvegardée : {dest}" if dest else "Aucune base sur disque à sauvegarder.",
            8000,
        )

    def _restore(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from planner.storage.db import DEFAULT_DB_PATH, restore_database

        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une sauvegarde", str(Path(DEFAULT_DB_PATH).parent / "backups"),
            "Base SQLite (*.db)",
        )
        if not path:
            return
        confirmation = QMessageBox.question(
            self, "Restaurer",
            "Remplacer la base actuelle par cette sauvegarde ?\n"
            "(L'état actuel est lui-même sauvegardé d'abord.)",
        )
        if confirmation != QMessageBox.Yes:
            return
        self.conn.close()
        restore_database(DEFAULT_DB_PATH, path)
        QMessageBox.information(
            self, "Restaurer",
            "Base restaurée. L'application va se fermer : la relancer pour recharger.",
        )
        self.close()

    # ------------------------------------------------------------ tray

    def _build_tray(self) -> None:
        from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
        from PySide6.QtWidgets import QSystemTrayIcon

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#2f6fed"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.drawText(pixmap.rect(), 0x84, "PÉ")  # AlignCenter
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(pixmap), self)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.setToolTip("Plan-Études")
            self.tray.show()

    def notify_next_block(self) -> None:
        """Notification Windows du prochain bloc planifié (§ Phase 6)."""
        from datetime import datetime

        from planner.storage import repositories as repos

        if not getattr(self, "tray", None) or not self.tray.isVisible():
            return
        now = datetime.now()
        upcoming = [
            b for b in repos.list_study_blocks(self.conn)
            if b.status in ("planned", "moved") and b.start_at >= now
        ]
        if not upcoming:
            return
        block = min(upcoming, key=lambda b: b.start_at)
        courses = repos.list_courses(self.conn)
        evaluations = {
            e.id: e for c in courses
            for e in repos.list_evaluations(self.conn, course_id=c.id)
        }
        ev = evaluations.get(block.evaluation_id)
        title = ev.title if ev else "bloc d'étude"
        self.tray.showMessage(
            "Prochain bloc d'étude",
            f"{block.start_at:%a %d/%m %H:%M} — {title} ({block.planned_minutes} min)",
        )

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
