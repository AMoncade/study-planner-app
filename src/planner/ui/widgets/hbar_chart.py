"""Barres horizontales dessinées à la main — aucune bibliothèque graphique (§5.5)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class HBarChart(QWidget):
    ROW = 24
    LABEL_WIDTH = 190

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, float, str]] = []  # (libellé, valeur, couleur)
        self.unit = "h"

    def set_rows(self, rows: list[tuple[str, float, str]], unit: str = "h") -> None:
        self.rows = rows
        self.unit = unit
        self.setMinimumHeight(self.ROW * max(1, len(rows)) + 8)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        maximum = max((v for _, v, _ in self.rows), default=0.0)
        for i, (label, value, color) in enumerate(self.rows):
            y = 4 + i * self.ROW
            painter.setPen(QColor("#9aa0aa"))
            painter.drawText(QRect(0, y, self.LABEL_WIDTH - 8, self.ROW - 4),
                             Qt.AlignRight | Qt.AlignVCenter, label)
            available = self.width() - self.LABEL_WIDTH - 64
            width = 0 if maximum == 0 else int(available * value / maximum)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(self.LABEL_WIDTH, y + 3, max(width, 2),
                                    self.ROW - 10, 3, 3)
            painter.setPen(QColor("#d6d9de"))
            painter.drawText(QRect(self.LABEL_WIDTH + width + 6, y, 58, self.ROW - 4),
                             Qt.AlignLeft | Qt.AlignVCenter, f"{value:g} {self.unit}")
        painter.end()
