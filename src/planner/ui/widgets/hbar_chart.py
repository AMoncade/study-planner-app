"""Barres horizontales dessinées à la main — aucune bibliothèque graphique (§5.5).

Deux modes :
- `set_rows` : une valeur par ligne sur piste pleine largeur (tableau de bord) ;
- `set_progress_rows` : heures faites sur piste des heures planifiées, avec la
  valeur « x / y h » à droite (vue Statistiques, §5.8).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from planner.ui import theme


class HBarChart(QWidget):
    ROW = 24
    LABEL_WIDTH = 190
    VALUE_WIDTH = 92  # colonne « x / y h » du mode progression

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, float, str]] = []  # (libellé, valeur, couleur)
        # (libellé, heures faites, heures planifiées, couleur)
        self.progress_rows: list[tuple[str, float, float, str]] = []
        self.unit = "h"

    def set_rows(self, rows: list[tuple[str, float, str]], unit: str = "h") -> None:
        self.rows = rows
        self.progress_rows = []
        self.unit = unit
        self.setMinimumHeight(self.ROW * max(1, len(rows)) + 8)
        self.update()

    def set_progress_rows(self, rows: list[tuple[str, float, float, str]],
                          unit: str = "h") -> None:
        """Lignes (libellé, heures faites, heures planifiées, couleur du cours)."""
        self.progress_rows = rows
        self.rows = []
        self.unit = unit
        self.setMinimumHeight(self.ROW * max(1, len(rows)) + 8)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.progress_rows:
            self._paint_progress(painter)
        else:
            self._paint_simple(painter)
        painter.end()

    # ------------------------------------------------------------ modes

    def _paint_simple(self, painter: QPainter) -> None:
        maximum = max((v for _, v, _ in self.rows), default=0.0)
        for i, (label, value, color) in enumerate(self.rows):
            y = 4 + i * self.ROW
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(QRect(0, y, self.LABEL_WIDTH - 8, self.ROW - 4),
                             Qt.AlignRight | Qt.AlignVCenter, label)
            available = self.width() - self.LABEL_WIDTH - 64
            width = 0 if maximum == 0 else int(available * value / maximum)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.SEPARATOR))  # piste
            painter.drawRoundedRect(self.LABEL_WIDTH, y + 3, max(available, 2),
                                    self.ROW - 10, 4, 4)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(self.LABEL_WIDTH, y + 3, max(width, 2),
                                    self.ROW - 10, 4, 4)
            painter.setPen(QColor(theme.TEXT_PRIMARY))
            painter.drawText(QRect(self.LABEL_WIDTH + width + 6, y, 58, self.ROW - 4),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             f"{theme.fmt_number(value)} {self.unit}")

    def _paint_progress(self, painter: QPainter) -> None:
        """Barre = heures faites (couleur du cours) sur piste = heures planifiées."""
        maximum = max((max(done, planned) for _, done, planned, _ in self.progress_rows),
                      default=0.0)
        available = self.width() - self.LABEL_WIDTH - self.VALUE_WIDTH - 12
        value_font = theme.tabular_font(self.font())
        for i, (label, done, planned, color) in enumerate(self.progress_rows):
            y = 4 + i * self.ROW
            painter.setFont(self.font())
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(QRect(0, y, self.LABEL_WIDTH - 8, self.ROW - 4),
                             Qt.AlignRight | Qt.AlignVCenter, label)
            track = 0 if maximum == 0 else int(available * planned / maximum)
            width = 0 if maximum == 0 else int(available * done / maximum)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.SEPARATOR))  # piste : heures planifiées
            painter.drawRoundedRect(self.LABEL_WIDTH, y + 3, max(track, 2),
                                    self.ROW - 10, 4, 4)
            if width > 0:
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(self.LABEL_WIDTH, y + 3, max(width, 2),
                                        self.ROW - 10, 4, 4)
            painter.setFont(value_font)
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(
                QRect(self.width() - self.VALUE_WIDTH, y, self.VALUE_WIDTH,
                      self.ROW - 4),
                Qt.AlignRight | Qt.AlignVCenter,
                f"{theme.fmt_number(done)} / {theme.fmt_number(planned)} {self.unit}",
            )
