"""Calendrier hebdomadaire dessiné à la main (ARCHITECTURE §5.4).

QWidget avec paintEvent : colonnes = jours, axe vertical = heures d'éveil.
Superpositions : contraintes en gris hachuré, séances de cours en gris plein,
blocs d'étude en couleur du cours. Interactions : sélection, menu contextuel,
glisser-déposer (verrouille le bloc), double-clic (signal de détail).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from planner.core.models import WEEKDAYS

# Couleurs par cours (cycle) et par statut.
COURSE_COLORS = ("#2f6fed", "#2fa46a", "#c77b2f", "#a04fc9", "#c94f5e", "#3aa6b9")
STATUS_ALPHA = {"planned": 220, "moved": 220, "done": 110, "partial": 150, "skipped": 80}


@dataclass
class BlockView:
    """Ce que le calendrier a besoin de savoir d'un bloc pour le dessiner."""

    id: int
    start_at: datetime
    end_at: datetime
    label: str          # sigle du cours + titre court
    course_key: int     # index de couleur
    status: str
    locked: bool


@dataclass
class BusyView:
    """Contrainte ou séance à dessiner en fond."""

    day: date
    start: time
    end: time
    label: str
    hatched: bool       # True = contrainte, False = séance de cours


class WeekCalendar(QWidget):
    block_move_requested = Signal(int, object)   # id, nouveau datetime de début
    block_context_requested = Signal(int, object)  # id, position globale QPoint
    block_activated = Signal(int)                # double-clic

    GUTTER = 46          # marge gauche pour l'axe des heures
    HEADER = 28          # bandeau des jours

    def __init__(self, day_start: time = time(8, 0), day_end: time = time(22, 0),
                 parent=None):
        super().__init__(parent)
        self.day_start = day_start
        self.day_end = day_end
        self.monday: date = date.today() - timedelta(days=date.today().weekday())
        self.blocks: list[BlockView] = []
        self.busy: list[BusyView] = []
        self.selected_id: int | None = None
        self._drag: tuple[int, QPoint] | None = None   # (id de bloc, position souris)
        self._drag_pos: QPoint | None = None
        self.setMinimumHeight(420)
        self.setMouseTracking(False)

    # ------------------------------------------------------------ données

    def set_week(self, monday: date) -> None:
        self.monday = monday
        self.update()

    def set_data(self, blocks: list[BlockView], busy: list[BusyView]) -> None:
        self.blocks = blocks
        self.busy = busy
        self.update()

    # ------------------------------------------------------------ géométrie

    def _hours_span(self) -> float:
        return (self.day_end.hour + self.day_end.minute / 60) - \
               (self.day_start.hour + self.day_start.minute / 60)

    def _column_width(self) -> float:
        return (self.width() - self.GUTTER) / 7

    def _y(self, t: time) -> float:
        hours = (t.hour + t.minute / 60) - (self.day_start.hour + self.day_start.minute / 60)
        usable = self.height() - self.HEADER
        return self.HEADER + max(0.0, min(1.0, hours / self._hours_span())) * usable

    def _rect_for(self, day: date, start: time, end: time) -> QRect:
        col = (day - self.monday).days
        x = self.GUTTER + col * self._column_width()
        y1, y2 = self._y(start), self._y(end)
        return QRect(int(x + 2), int(y1), int(self._column_width() - 4), int(y2 - y1))

    def _time_at(self, pos: QPoint) -> tuple[date, time] | None:
        """Jour et heure (arrondie à 30 min) sous le curseur."""
        if pos.x() < self.GUTTER or pos.y() < self.HEADER:
            return None
        col = int((pos.x() - self.GUTTER) / self._column_width())
        if not 0 <= col <= 6:
            return None
        fraction = (pos.y() - self.HEADER) / (self.height() - self.HEADER)
        hours = self.day_start.hour + self.day_start.minute / 60 \
            + fraction * self._hours_span()
        half_hours = round(hours * 2)
        hour, minute = divmod(half_hours, 2)
        hour = max(0, min(23, hour))
        return self.monday + timedelta(days=col), time(hour, 30 * minute)

    def block_at(self, pos: QPoint) -> BlockView | None:
        for block in self.blocks:
            rect = self._rect_for(
                block.start_at.date(), block.start_at.time(), block.end_at.time()
            )
            if rect.contains(pos):
                return block
        return None

    # ------------------------------------------------------------ dessin

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()
        column = self._column_width()

        painter.fillRect(0, 0, width, height, QColor("#1e2126"))

        # en-têtes de jours + fond des colonnes
        for col in range(7):
            day = self.monday + timedelta(days=col)
            x = self.GUTTER + col * column
            if day == date.today():
                painter.fillRect(int(x), self.HEADER, int(column), height - self.HEADER,
                                 QColor("#23262c"))
            painter.setPen(QPen(QColor("#8b919b")))
            painter.drawText(QRect(int(x), 0, int(column), self.HEADER), Qt.AlignCenter,
                             f"{WEEKDAYS[col][:3]} {day.day:02d}/{day.month:02d}")

        # lignes horaires + axe
        painter.setPen(QPen(QColor("#2c313a")))
        hour = self.day_start.hour
        while hour <= self.day_end.hour:
            y = int(self._y(time(hour, 0)))
            painter.drawLine(self.GUTTER, y, width, y)
            painter.setPen(QPen(QColor("#6b7078")))
            painter.drawText(QRect(0, y - 8, self.GUTTER - 6, 16),
                             Qt.AlignRight | Qt.AlignVCenter, f"{hour:02d}h")
            painter.setPen(QPen(QColor("#2c313a")))
            hour += 2

        # séparateurs de colonnes
        for col in range(8):
            x = int(self.GUTTER + col * column)
            painter.drawLine(x, self.HEADER, x, height)

        # contraintes et séances
        for busy in self.busy:
            if not (self.monday <= busy.day <= self.monday + timedelta(days=6)):
                continue
            rect = self._rect_for(busy.day, busy.start, busy.end)
            if busy.hatched:
                painter.fillRect(rect, QBrush(QColor(90, 95, 104, 90), Qt.BDiagPattern))
            else:
                painter.fillRect(rect, QColor(90, 95, 104, 140))
            painter.setPen(QPen(QColor("#9aa0aa")))
            painter.drawText(rect.adjusted(4, 2, -2, -2),
                             Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap, busy.label)

        # blocs d'étude
        for block in self.blocks:
            if not (self.monday <= block.start_at.date() <= self.monday + timedelta(days=6)):
                continue
            rect = self._rect_for(
                block.start_at.date(), block.start_at.time(), block.end_at.time()
            )
            if self._drag and self._drag[0] == block.id and self._drag_pos is not None:
                rect.moveTopLeft(rect.topLeft() + (self._drag_pos - self._drag[1]))
            color = QColor(COURSE_COLORS[block.course_key % len(COURSE_COLORS)])
            color.setAlpha(STATUS_ALPHA.get(block.status, 220))
            if block.id == self.selected_id:
                painter.setPen(QPen(QColor("#f0f2f5"), 2))
            else:
                painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QPen(QColor("#0d0f12") if block.status in ("planned", "moved")
                                else QColor("#c8ccd2")))
            duration = (block.end_at - block.start_at).total_seconds() / 3600
            prefix = "🔒 " if block.locked else ""
            suffix = {"done": " ✓", "partial": " ◐", "skipped": " ✗"}.get(block.status, "")
            painter.drawText(rect.adjusted(5, 2, -4, -2),
                             Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
                             f"{prefix}{block.label}{suffix}\n{duration:g} h")
        painter.end()

    # ------------------------------------------------------------ souris

    def mousePressEvent(self, event) -> None:
        block = self.block_at(event.position().toPoint())
        self.selected_id = block.id if block else None
        if event.button() == Qt.LeftButton and block and not block.locked \
                and block.status == "planned":
            self._drag = (block.id, event.position().toPoint())
            self._drag_pos = event.position().toPoint()
        elif event.button() == Qt.RightButton and block:
            self.block_context_requested.emit(block.id, event.globalPosition().toPoint())
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag:
            self._drag_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if not self._drag:
            return
        block_id, origin = self._drag
        self._drag = None
        self._drag_pos = None
        drop = self._time_at(event.position().toPoint())
        moved_enough = (event.position().toPoint() - origin).manhattanLength() > 8
        if drop and moved_enough:
            day, at = drop
            self.block_move_requested.emit(block_id, datetime.combine(day, at))
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        block = self.block_at(event.position().toPoint())
        if block:
            self.block_activated.emit(block.id)
