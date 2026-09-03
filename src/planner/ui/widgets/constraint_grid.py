"""Grille hebdomadaire peignable — niveau 2 de la vue Contraintes (ARCHITECTURE §5.3).

Confort, jamais un bloqueur : le moteur ne lit que le modèle de données. La grille
convertit cellules ↔ contraintes hebdomadaires via deux fonctions pures testables.
Peinture par sélection glissée puis « Peindre » / « Effacer » ; annulation par pile
de sauvegardes (bouton ou Ctrl+Z) ; « Enregistrer » remplace les contraintes
hebdomadaires en base. La catégorie se choisit par chips arrondies à pastille.
"""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from planner.core.models import CONSTRAINT_CATEGORIES, WEEKDAYS, Constraint
from planner.ui import theme
from planner.ui.theme import CATEGORY_COLORS  # noqa: F401  (réexport historique)
from planner.ui.widgets.badge import Badge

Cells = dict[tuple[int, int], str]  # (jour 0-6, rangée) -> catégorie


def slots_in_window(wake_start: time, wake_end: time) -> int:
    return (wake_end.hour * 60 + wake_end.minute
            - wake_start.hour * 60 - wake_start.minute) // 30


def row_to_time(row: int, wake_start: time) -> time:
    minutes = wake_start.hour * 60 + wake_start.minute + row * 30
    return time(minutes // 60, minutes % 60)


def cells_from_constraints(
    constraints: list[Constraint], wake_start: time, wake_end: time
) -> Cells:
    """Projette les contraintes hebdomadaires sur la grille (fonction pure)."""
    cells: Cells = {}
    total_rows = slots_in_window(wake_start, wake_end)
    base = wake_start.hour * 60 + wake_start.minute
    for c in constraints:
        if c.weekday is None:
            continue
        start = c.start.hour * 60 + c.start.minute
        end = c.end.hour * 60 + c.end.minute
        first = max(0, (start - base) // 30)
        last = min(total_rows, -(-(end - base) // 30))  # arrondi supérieur
        for row in range(first, last):
            cells[(c.weekday, row)] = c.category
    return cells


def constraints_from_cells(
    cells: Cells, wake_start: time
) -> list[Constraint]:
    """Fusionne les cellules contiguës de même catégorie en contraintes (fonction pure)."""
    constraints: list[Constraint] = []
    for weekday in range(7):
        rows = sorted(row for (d, row) in cells if d == weekday)
        i = 0
        while i < len(rows):
            start_row = rows[i]
            category = cells[(weekday, start_row)]
            end_row = start_row
            while (i + 1 < len(rows) and rows[i + 1] == end_row + 1
                   and cells[(weekday, rows[i + 1])] == category):
                i += 1
                end_row = rows[i]
            constraints.append(Constraint(
                id=None, label=category, category=category, weekday=weekday,
                specific_date=None,
                start=row_to_time(start_row, wake_start),
                end=row_to_time(end_row + 1, wake_start),
            ))
            i += 1
    return constraints


class CategoryChips(QWidget):
    """Rangée de chips arrondies (pastille couleur + nom) — une seule active.

    Expose la même API que le QComboBox qu'elle remplace :
    `currentText()` / `setCurrentText()`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for name in CONSTRAINT_CATEGORIES:
            color = theme.CATEGORY_COLORS[name]
            chip = QPushButton(name.capitalize())
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            dot = QPixmap(10, 10)
            dot.fill(Qt.transparent)
            painter = QPainter(dot)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(0, 0, 10, 10)
            painter.end()
            chip.setIcon(QIcon(dot))
            chip.setStyleSheet(
                "QPushButton { background-color: #1a202b; border: 1px solid #2d3542;"
                " border-radius: 16px; padding: 0 14px; min-height: 30px;"
                " font-size: 12px; color: #9da6b5; }"
                f" QPushButton:hover {{ border-color: {theme.rgba(color, 0.6)}; }}"
                " QPushButton:checked {"
                f" background-color: {theme.rgba(color, 0.14)};"
                f" border: 1px solid {theme.rgba(color, 0.6)}; color: #e8ebf0; }}"
            )
            self._group.addButton(chip)
            layout.addWidget(chip)
        layout.addStretch(1)
        self._group.buttons()[0].setChecked(True)

    def currentText(self) -> str:
        return self._group.checkedButton().text().lower()

    def setCurrentText(self, name: str) -> None:
        for button in self._group.buttons():
            if button.text().lower() == name.lower():
                button.setChecked(True)
                return


class ConstraintGrid(QWidget):
    saved = Signal()

    ROW_HEIGHT = 30      # px par demi-heure (lisibilité de la grille)

    def __init__(self, conn, wake_start: time = time(8, 0), wake_end: time = time(22, 0),
                 parent=None):
        super().__init__(parent)
        self.conn = conn
        self.wake_start = wake_start
        self.wake_end = wake_end
        self.cells: Cells = {}
        self._undo_stack: list[Cells] = []

        rows = slots_in_window(wake_start, wake_end)
        self.table = QTableWidget(rows, 7)
        self.table.setHorizontalHeaderLabels([d.capitalize() for d in WEEKDAYS])
        # étiquette d'heure sur les rangées pleines seulement : plus respirant
        self.table.setVerticalHeaderLabels([
            row_to_time(r, wake_start).strftime("%H:%M")
            if row_to_time(r, wake_start).minute == 0 else ""
            for r in range(rows)
        ])
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setShowGrid(True)

        self.category = CategoryChips()
        paint = QPushButton("Peindre la sélection")
        paint.clicked.connect(self._paint)
        erase = QPushButton("Effacer la sélection")
        erase.clicked.connect(self._erase)
        undo = QPushButton("Annuler")
        undo.setToolTip("Ctrl+Z")
        undo.clicked.connect(self._undo)
        save = QPushButton("Enregistrer la grille")
        save.setProperty("kind", "primary")
        save.clicked.connect(self._save)
        QShortcut(QKeySequence.Undo, self, activated=self._undo)

        self.feedback = Badge("Glisser pour sélectionner, puis peindre ou effacer.",
                              kind="neutral")

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(paint)
        actions.addWidget(erase)
        actions.addWidget(undo)
        actions.addStretch()
        actions.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.category)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        layout.addWidget(self.feedback)
        self.reload()

    # ------------------------------------------------------------ synchronisation

    def reload(self) -> None:
        from planner.storage import repositories as repos

        weekly = [c for c in repos.list_constraints(self.conn) if c.weekday is not None]
        self.cells = cells_from_constraints(weekly, self.wake_start, self.wake_end)
        self._undo_stack.clear()
        self._render()

    def _render(self) -> None:
        rows = self.table.rowCount()
        for row in range(rows):
            for col in range(7):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                category = self.cells.get((col, row))
                if category:
                    color = theme.qcolor(theme.CATEGORY_COLORS[category], 0.55)
                    item.setBackground(color)
                    item.setToolTip(category)
                else:
                    item.setBackground(QColor(theme.BG_SURFACE))
                    item.setToolTip("")

    # ------------------------------------------------------------ actions

    def _snapshot(self) -> None:
        self._undo_stack.append(dict(self.cells))
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _selected_cells(self) -> list[tuple[int, int]]:
        return [(index.column(), index.row()) for index in self.table.selectedIndexes()]

    def _paint(self) -> None:
        selected = self._selected_cells()
        if not selected:
            return
        self._snapshot()
        category = self.category.currentText()
        for key in selected:
            self.cells[key] = category
        self._render()

    def _erase(self) -> None:
        selected = self._selected_cells()
        if not selected:
            return
        self._snapshot()
        for key in selected:
            self.cells.pop(key, None)
        self._render()

    def _undo(self) -> None:
        if self._undo_stack:
            self.cells = self._undo_stack.pop()
            self._render()

    def _save(self) -> None:
        from planner.storage import repositories as repos

        new_constraints = constraints_from_cells(self.cells, self.wake_start)
        with self.conn:
            for c in repos.list_constraints(self.conn):
                if c.weekday is not None:
                    self.conn.execute("DELETE FROM constraints WHERE id = ?", (c.id,))
            for c in new_constraints:
                self.conn.execute(
                    """INSERT INTO constraints (label, category, weekday, specific_date,
                                                start, end, priority)
                       VALUES (?, ?, ?, NULL, ?, ?, 0)""",
                    (c.label, c.category, c.weekday, c.start.isoformat(),
                     c.end.isoformat()),
                )
        self.feedback.set_status(
            f"{len(new_constraints)} contrainte(s) hebdomadaire(s) enregistrée(s).", "ok"
        )
        self.saved.emit()
