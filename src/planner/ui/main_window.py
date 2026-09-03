"""Coquille de l'application (ARCHITECTURE §5.0) : barre latérale fixe + QStackedWidget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from planner.resources import resource_path
from planner.ui import theme
from planner.ui.icons import svg_icon
from planner.ui.views.constraints_view import ConstraintsView
from planner.ui.views.courses_view import CoursesView
from planner.ui.views.dashboard_view import DashboardView
from planner.ui.views.import_view import ImportView
from planner.ui.views.schedule_view import ScheduleView
from planner.ui.views.settings_view import SettingsView

STYLE_PATH = resource_path("planner/ui/style.qss")

SIDEBAR_WIDTH = 232

# (libellé, icône) des six items de navigation, dans l'ordre du QStackedWidget.
NAV_ITEMS = (
    ("Tableau de bord", "dashboard"),
    ("Importer", "import"),
    ("Cours et évaluations", "book"),
    ("Contraintes", "timetable"),
    ("Planning", "calendar"),
    ("Paramètres", "gear"),
)


class MainWindow(QMainWindow):
    data_changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Plan-Études")
        self.resize(1280, 800)

        self.dashboard_view = DashboardView(conn)
        self.import_view = ImportView(conn)
        self.courses_view = CoursesView(conn)
        self.constraints_view = ConstraintsView(conn)
        self.schedule_view = ScheduleView(conn)
        self.settings_view = SettingsView(conn)

        self.stack = QStackedWidget()
        views = (
            self.dashboard_view, self.import_view, self.courses_view,
            self.constraints_view, self.schedule_view, self.settings_view,
        )
        # L'ordre historique du stack (tests, toolbar) : tableau de bord, importer,
        # cours, contraintes, planning, paramètres.
        for widget in views:
            self.stack.addWidget(widget)

        sidebar = self._build_sidebar()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

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

    # ------------------------------------------------------------ barre latérale

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        # En-tête : pastille « P » bleu UdeM + titre + session.
        logo = QLabel("P")
        logo.setObjectName("logoBadge")
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignCenter)
        title = QLabel("Plan-Études")
        title.setObjectName("appTitle")
        self.session_label = QLabel(self._session_text())
        self.session_label.setObjectName("appSubtitle")
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(1)
        titles.addWidget(title)
        titles.addWidget(self.session_label)
        header = QHBoxLayout()
        header.setContentsMargins(16, 18, 16, 14)
        header.setSpacing(10)
        header.addWidget(logo)
        header.addLayout(titles, 1)

        # Navigation : icônes SVG 18 px, item actif en lavis accent.
        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setFocusPolicy(Qt.NoFocus)
        for name, icon_name in NAV_ITEMS:
            item = QListWidgetItem(
                svg_icon(icon_name, theme.TEXT_SECONDARY, theme.TEXT_PRIMARY), name
            )
            item.setSizeHint(QSize(0, 36))
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # Pied : état de synchronisation de la base locale.
        self.sync_label = QLabel()
        self.sync_label.setObjectName("syncStatus")
        self.sync_label.setContentsMargins(16, 10, 16, 14)
        self._update_sync_label()

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.nav, 1)
        layout.addWidget(self.sync_label)
        return sidebar

    def _session_text(self) -> str:
        from planner.storage import repositories as repos

        terms = [c.term for c in repos.list_courses(self.conn) if c.term]
        if not terms:
            return "Aucun cours importé"
        # trimestre le plus fréquent (une session à la fois en pratique)
        term = max(set(terms), key=terms.count)
        return f"Session {term}"

    def _update_sync_label(self) -> None:
        """« ● Synchronisé · il y a N min » d'après l'horodatage de la base locale."""
        from datetime import datetime

        from planner.storage.db import DEFAULT_DB_PATH

        path = Path(DEFAULT_DB_PATH)
        if not path.exists():
            self.sync_label.setText(
                f'<span style="color:{theme.TEXT_MUTED}">●</span> Base en mémoire'
            )
            return
        minutes = int((datetime.now().timestamp() - path.stat().st_mtime) / 60)
        if minutes < 1:
            age = "à l'instant"
        elif minutes < 60:
            age = f"il y a {minutes} min"
        else:
            age = f"il y a {minutes // 60} h"
        self.sync_label.setText(
            f'<span style="color:{theme.STATUS_OK}">●</span> Synchronisé · {age}'
        )

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
        pixmap.fill(QColor(theme.BRAND))
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
                   + (f" · {missing} sans date" if missing else ""))
        self.statusBar().showMessage(message)
        self.session_label.setText(self._session_text())
        self._update_sync_label()


def apply_style(app) -> None:
    if STYLE_PATH.exists():
        app.setStyleSheet(STYLE_PATH.read_text(encoding="utf-8"))
