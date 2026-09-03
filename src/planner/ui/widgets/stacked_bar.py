"""Barre empilée horizontale (assiduité, §5.8) — segments aux couleurs de statut.

Les séparateurs de 2 px laissent voir le fond de la carte entre les segments ;
la légende (icône + libellé + compte) vit dans la vue, jamais la couleur seule.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

_GAP = 2.0       # séparateur : le fond de la carte apparaît entre les segments
_RADIUS = 6.0


class StackedBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments: list[tuple[int, str]] = []  # (compte, couleur)
        self.setFixedHeight(16)

    def set_segments(self, segments: list[tuple[int, str]]) -> None:
        """Segments (compte, couleur) ; les comptes nuls sont ignorés au dessin."""
        self.segments = [(count, color) for count, color in segments if count > 0]
        self.update()

    def paintEvent(self, _event) -> None:
        total = sum(count for count, _ in self.segments)
        if total == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # les extrémités de la barre complète sont arrondies via un chemin de découpe
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                            _RADIUS, _RADIUS)
        painter.setClipPath(clip)

        gaps = _GAP * (len(self.segments) - 1)
        available = max(self.width() - gaps, 1.0)
        x = 0.0
        for count, color in self.segments:
            width = available * count / total
            painter.fillRect(QRectF(x, 0, width, self.height()), QColor(color))
            x += width + _GAP
        painter.end()
