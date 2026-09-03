"""Icônes SVG inline (18 px, trait 1.8) — aucune ressource externe.

Chaque icône est un fragment de chemins SVG ; `svg_icon()` l'habille d'une couleur
et la rend en QIcon via QSvgRenderer, avec un rendu 2× pour les écrans HiDPI.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Fragments de chemins (viewBox 24×24), style « trait fin arrondi ».
_PATHS: dict[str, str] = {
    # navigation
    "dashboard": (
        '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/>'
        '<rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/>'
        '<rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/>'
        '<rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>'
    ),
    "import": (
        '<path d="M12 3.5v10.5"/><path d="M8 10.5l4 4 4-4"/>'
        '<path d="M4.5 16.5v2a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2"/>'
    ),
    "book": (
        '<path d="M4.5 19a2.5 2.5 0 0 1 2.5-2.5H19.5"/>'
        '<path d="M7 3.5h12.5V20.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5z"/>'
    ),
    "timetable": (
        '<rect x="3.5" y="4.5" width="17" height="16" rx="2"/>'
        '<path d="M3.5 10h17"/><path d="M9.5 4.5v16"/><path d="M15.5 10v10.5"/>'
    ),
    "calendar": (
        '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/>'
        '<path d="M8 3v4"/><path d="M16 3v4"/><path d="M3.5 10.5h17"/>'
    ),
    "gear": (
        '<circle cx="12" cy="12" r="3.2"/>'
        '<path d="M12 2.8v2.4"/><path d="M12 18.8v2.4"/>'
        '<path d="M2.8 12h2.4"/><path d="M18.8 12h2.4"/>'
        '<path d="M5.5 5.5l1.7 1.7"/><path d="M16.8 16.8l1.7 1.7"/>'
        '<path d="M18.5 5.5l-1.7 1.7"/><path d="M7.2 16.8l-1.7 1.7"/>'
    ),
    "chart": (
        '<path d="M4 20h16"/>'
        '<path d="M7 20v-6"/><path d="M12 20V9.5"/><path d="M17 20v-8.5"/>'
    ),
    # statuts
    "check-circle": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M8.2 12.4l2.6 2.6 5-5.4"/>'
    ),
    "alert-triangle": (
        '<path d="M12 3.8L21 19.2H3z"/>'
        '<path d="M12 9.5v4"/><path d="M12 16.4v.01"/>'
    ),
    "alert-circle": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 7.5v5"/><path d="M12 15.9v.01"/>'
    ),
    "x-circle": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M9.2 9.2l5.6 5.6"/><path d="M14.8 9.2l-5.6 5.6"/>'
    ),
    "info-circle": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 11v5"/><path d="M12 7.6v.01"/>'
    ),
    "minus-circle": (
        '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12h7"/>'
    ),
    "help-circle": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M9.6 9.3a2.4 2.4 0 1 1 3.5 2.6c-.8.4-1.1.9-1.1 1.7"/>'
        '<path d="M12 16.4v.01"/>'
    ),
    # tendances (tuile avance/retard)
    "trend-up": (
        '<path d="M3.5 16.5L9 11l3.5 3.5L20.5 7"/><path d="M15.5 7h5v5"/>'
    ),
    "trend-down": (
        '<path d="M3.5 7.5L9 13l3.5-3.5 8 8"/><path d="M15.5 17h5v-5"/>'
    ),
}


def svg_bytes(name: str, color: str, stroke_width: float = 1.8) -> bytes:
    """Document SVG complet de l'icône `name`, tracée en `color`."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{_PATHS[name]}</svg>'
    ).encode()


def svg_pixmap(name: str, color: str, size: int = 18,
               stroke_width: float = 1.8) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_bytes(name, color, stroke_width)))
    pixmap = QPixmap(size * 2, size * 2)  # rendu 2× pour les écrans HiDPI
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def svg_icon(name: str, color: str, selected_color: str | None = None,
             size: int = 18) -> QIcon:
    """QIcon d'une icône, avec une variante optionnelle pour l'état sélectionné."""
    icon = QIcon()
    icon.addPixmap(svg_pixmap(name, color, size), QIcon.Normal)
    if selected_color:
        icon.addPixmap(svg_pixmap(name, selected_color, size), QIcon.Selected)
    return icon
