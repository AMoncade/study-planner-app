"""Vue Contraintes, niveau 1 : tableau + dialogue (ARCHITECTURE §5.3).

Deux onglets : contraintes hebdomadaires récurrentes et exceptions ponctuelles.
La grille peignable (niveau 2) viendra en Phase 5 — le moteur ne lit que les données.
"""

from __future__ import annotations

from datetime import date, time, timedelta

from PySide6.QtCore import QDate, QTime, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from planner.config import EngineSettings
from planner.core.models import CONSTRAINT_CATEGORIES, WEEKDAYS, Constraint
from planner.scheduler.availability import build_grid, free_hours
from planner.storage import repositories as repos
from planner.ui import theme


class ConstraintDialog(QDialog):
    """Saisie d'une contrainte, hebdomadaire (weekly=True) ou ponctuelle."""

    def __init__(self, weekly: bool, constraint: Constraint | None = None, parent=None):
        super().__init__(parent)
        self.weekly = weekly
        self.setWindowTitle("Contrainte hebdomadaire" if weekly else "Exception ponctuelle")

        self.label_edit = QLineEdit()
        self.category = QComboBox()
        self.category.addItems(CONSTRAINT_CATEGORIES)
        self.start = QTimeEdit(QTime(9, 0))
        self.end = QTimeEdit(QTime(17, 0))
        for w in (self.start, self.end):
            w.setDisplayFormat("HH:mm")

        form = QFormLayout(self)
        form.addRow("Libellé :", self.label_edit)
        form.addRow("Catégorie :", self.category)
        if weekly:
            self.weekday = QComboBox()
            self.weekday.addItems(WEEKDAYS)
            form.addRow("Jour :", self.weekday)
        else:
            self.date_edit = QDateEdit(QDate.currentDate())
            self.date_edit.setCalendarPopup(True)
            form.addRow("Date :", self.date_edit)
        form.addRow("Début :", self.start)
        form.addRow("Fin :", self.end)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if constraint is not None:
            self.label_edit.setText(constraint.label)
            self.category.setCurrentText(constraint.category)
            self.start.setTime(QTime(constraint.start.hour, constraint.start.minute))
            self.end.setTime(QTime(constraint.end.hour, constraint.end.minute))
            if weekly and constraint.weekday is not None:
                self.weekday.setCurrentIndex(constraint.weekday)
            elif not weekly and constraint.specific_date is not None:
                d = constraint.specific_date
                self.date_edit.setDate(QDate(d.year, d.month, d.day))

    def _set_error(self, widget, error: bool) -> None:
        """Marque (ou efface) la bordure d'erreur via la propriété QSS `error`."""
        widget.setProperty("error", error)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _validate(self):
        if self.start.time() >= self.end.time():
            self._set_error(self.start, True)
            self._set_error(self.end, True)
            return
        # bordure réinitialisée dès que l'erreur est corrigée
        self._set_error(self.start, False)
        self._set_error(self.end, False)
        if not self.label_edit.text().strip():
            self.label_edit.setText(self.category.currentText())
        self.accept()

    def to_constraint(self, constraint_id: int | None = None) -> Constraint:
        qt_start, qt_end = self.start.time(), self.end.time()
        return Constraint(
            id=constraint_id,
            label=self.label_edit.text().strip(),
            category=self.category.currentText(),
            weekday=self.weekday.currentIndex() if self.weekly else None,
            specific_date=None if self.weekly else self.date_edit.date().toPython(),
            start=time(qt_start.hour(), qt_start.minute()),
            end=time(qt_end.hour(), qt_end.minute()),
        )


class _ConstraintTable(QWidget):
    changed = Signal()

    def __init__(self, conn, weekly: bool, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.weekly = weekly
        self.rows: list[Constraint] = []

        first_column = "Jour" if weekly else "Date"
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [first_column, "Début", "Fin", "Catégorie", "Libellé"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(lambda _i: self._edit())

        add = QPushButton("Ajouter")
        add.clicked.connect(self._add)
        edit = QPushButton("Modifier")
        edit.clicked.connect(self._edit)
        duplicate = QPushButton("Dupliquer")
        duplicate.clicked.connect(self._duplicate)
        remove = QPushButton("Supprimer")
        remove.setProperty("kind", "danger")
        remove.clicked.connect(self._remove)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        for b in (add, edit, duplicate, remove):
            buttons.addWidget(b)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(buttons)
        layout.addWidget(self.table)
        self.refresh()

    def _selected(self) -> Constraint | None:
        row = self.table.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def refresh(self) -> None:
        all_rows = repos.list_constraints(self.conn)
        self.rows = [c for c in all_rows if (c.weekday is not None) == self.weekly]
        self.table.setRowCount(len(self.rows))
        for i, c in enumerate(self.rows):
            first = WEEKDAYS[c.weekday] if self.weekly else c.specific_date.isoformat()
            values = (first, c.start.strftime("%H:%M"), c.end.strftime("%H:%M"),
                      c.category, c.label)
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(value))

    def _add(self):
        dialog = ConstraintDialog(self.weekly, parent=self)
        if dialog.exec() == QDialog.Accepted:
            repos.insert_constraint(self.conn, dialog.to_constraint())
            self.refresh()
            self.changed.emit()

    def _edit(self):
        current = self._selected()
        if current is None:
            return
        dialog = ConstraintDialog(self.weekly, current, parent=self)
        if dialog.exec() == QDialog.Accepted:
            repos.update_constraint(self.conn, dialog.to_constraint(current.id))
            self.refresh()
            self.changed.emit()

    def _duplicate(self):
        current = self._selected()
        if current is None:
            return
        copy = Constraint(
            id=None, label=current.label, category=current.category,
            weekday=current.weekday, specific_date=current.specific_date,
            start=current.start, end=current.end,
        )
        repos.insert_constraint(self.conn, copy)
        self.refresh()
        self.changed.emit()

    def _remove(self):
        current = self._selected()
        if current is None:
            return
        repos.delete_constraint(self.conn, current.id)
        self.refresh()
        self.changed.emit()


class ConstraintsView(QWidget):
    changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        from planner.ui.widgets.constraint_grid import ConstraintGrid

        self.weekly_table = _ConstraintTable(conn, weekly=True)
        self.exception_table = _ConstraintTable(conn, weekly=False)
        settings = EngineSettings()
        self.grid = ConstraintGrid(conn, settings.wake_start, settings.wake_end)
        tabs = QTabWidget()
        tabs.addTab(self.weekly_table, "Hebdomadaires")
        tabs.addTab(self.exception_table, "Exceptions ponctuelles")
        tabs.addTab(self.grid, "Grille (peindre)")
        self.grid.saved.connect(self._on_grid_saved)

        title = QLabel("Contraintes")
        title.setProperty("role", "viewTitle")

        self.free_label = QLabel()
        self.free_label.setProperty("role", "secondary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(tabs)
        layout.addWidget(self.free_label)

        for table in (self.weekly_table, self.exception_table):
            table.changed.connect(self._on_changed)
        self._update_free_time()

    def refresh(self) -> None:
        self.weekly_table.refresh()
        self.exception_table.refresh()
        self.grid.reload()
        self._update_free_time()

    def _on_changed(self):
        self.grid.reload()
        self._update_free_time()
        self.changed.emit()

    def _on_grid_saved(self):
        self.weekly_table.refresh()
        self._update_free_time()
        self.changed.emit()

    def _update_free_time(self) -> None:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        constraints = repos.list_constraints(self.conn)
        courses = repos.list_courses(self.conn)
        grid = build_grid(monday, monday + timedelta(days=6), constraints, courses,
                          EngineSettings())
        hours = sum(free_hours(slots) for slots in grid.values())
        self.free_label.setText(
            f"Temps libre disponible cette semaine : {theme.fmt_number(hours)} h "
            "(contraintes et séances de cours déduites)")
