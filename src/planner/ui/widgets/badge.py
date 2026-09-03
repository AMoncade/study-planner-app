"""Badge de statut : icône SVG + texte sur fond teinté (phase 13).

Remplace les emoji ✅⚠❌🔴🟠🟡 concaténés dans des QLabel : le statut reste
lisible par l'icône ET le texte, jamais par la couleur seule.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from planner.ui import theme
from planner.ui.icons import svg_pixmap

# kind -> (couleur, icône)
KINDS = {
    "ok": (theme.STATUS_OK, "check-circle"),
    "warn": (theme.STATUS_WARN, "alert-triangle"),
    "serious": (theme.STATUS_SERIOUS, "alert-circle"),
    "critical": (theme.STATUS_CRITICAL, "x-circle"),
    "info": (theme.ACCENT, "info-circle"),
    "neutral": (theme.TEXT_SECONDARY, "info-circle"),
}


class Badge(QFrame):
    """Petit cadre arrondi : fond teinté 10 %, bordure 40 %, rayon 12 px."""

    def __init__(self, text: str = "", kind: str = "neutral", parent=None):
        super().__init__(parent)
        self._kind = ""
        self._icon = QLabel()
        self._icon.setFixedSize(16, 16)
        self._icon.setAlignment(Qt.AlignCenter)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 12, 5)
        layout.setSpacing(7)
        layout.addWidget(self._icon, 0, Qt.AlignTop)
        layout.addWidget(self._label, 1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.set_kind(kind)

    # ---- API compatible QLabel (les tests lisent .text())

    def text(self) -> str:
        return self._label.text()

    def setText(self, text: str) -> None:
        self._label.setText(text)

    def set_kind(self, kind: str) -> None:
        if kind == self._kind:
            return
        self._kind = kind
        color, icon_name = KINDS.get(kind, KINDS["neutral"])
        self._icon.setPixmap(svg_pixmap(icon_name, color, size=14))
        self.setStyleSheet(
            f"Badge {{ background-color: {theme.rgba(color, 0.10)};"
            f" border: 1px solid {theme.rgba(color, 0.40)}; border-radius: 12px; }}"
            f" QLabel {{ background: transparent; border: none;"
            f" color: {theme.TEXT_PRIMARY}; font-size: 12px; }}"
        )

    def set_status(self, text: str, kind: str) -> None:
        """Raccourci : texte + genre en un appel."""
        self.setText(text)
        self.set_kind(kind)
