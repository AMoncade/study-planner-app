"""Barres verticales « heures par semaine » dessinées au QPainter (§5.8).

Heures faites en accent sur piste des heures planifiées ; étiquettes de valeur
directes au-dessus des barres non nulles seulement, chiffres tabulaires.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from planner.scheduler.stats import WeekStat
from planner.ui import theme

_TOP = 22        # place pour les étiquettes de valeur
_BOTTOM = 22     # place pour l'axe des semaines
_RADIUS = 2.5    # coins arrondis côté haut seulement


def _top_rounded_bar(painter: QPainter, x: float, top: float, width: float,
                     bottom: float, color: str) -> None:
    """Barre à base plate : coins arrondis en haut, alignée sur la ligne de base."""
    height = bottom - top
    if height <= 0 or width <= 0:
        return
    radius = min(_RADIUS, height / 2, width / 2)
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, top, width, height + radius), radius, radius)
    painter.save()
    painter.setClipRect(QRectF(x, top, width, height))
    painter.fillPath(path, QColor(color))
    painter.restore()


class WeekBarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.weeks: list[WeekStat] = []
        self.setMinimumHeight(170)

    def set_weeks(self, weeks: list[WeekStat]) -> None:
        self.weeks = weeks
        self.update()

    def paintEvent(self, _event) -> None:
        if not self.weeks:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        baseline = self.height() - _BOTTOM
        plot_height = baseline - _TOP
        maximum = max((max(w.planned_hours, w.done_hours) for w in self.weeks),
                      default=0.0)
        slot = self.width() / len(self.weeks)
        bar_width = min(26.0, slot * 0.6)

        value_font = theme.tabular_font(self.font())
        value_font.setPixelSize(11)
        axis_font = theme.tabular_font(self.font())
        axis_font.setPixelSize(10)
        # éclaircir l'axe si les colonnes sont serrées (la semaine courante reste)
        label_step = 1 if slot >= 30 else 2

        for i, week in enumerate(self.weeks):
            x = i * slot + (slot - bar_width) / 2
            if maximum > 0:
                track_top = baseline - plot_height * week.planned_hours / maximum
                done_top = baseline - plot_height * week.done_hours / maximum
                _top_rounded_bar(painter, x, track_top, bar_width, baseline,
                                 theme.SEPARATOR)
                _top_rounded_bar(painter, x, done_top, bar_width, baseline,
                                 theme.ACCENT)
                if week.done_hours > 0:
                    painter.setFont(value_font)
                    painter.setPen(QColor(theme.TEXT_SECONDARY))
                    painter.drawText(
                        QRectF(i * slot - slot, min(track_top, done_top) - 18,
                               slot * 3, 14),
                        Qt.AlignHCenter | Qt.AlignBottom,
                        f"{round(week.done_hours, 1):g}",
                    )
            if week.is_current or i % label_step == 0:
                painter.setFont(axis_font)
                painter.setPen(QColor(theme.ACCENT if week.is_current
                                      else theme.TEXT_MUTED))
                painter.drawText(QRectF(i * slot, baseline + 4, slot, 14),
                                 Qt.AlignHCenter | Qt.AlignTop, week.label)

        # ligne de base fine, commune à toutes les barres
        painter.setPen(QColor(theme.SEPARATOR))
        painter.drawLine(0, baseline, self.width(), baseline)
        painter.end()
