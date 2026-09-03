"""Jetons du thème sombre Plan-Études (phase 13) — source unique des couleurs UI.

Les valeurs sont validées sur maquettes (thème sombre moderne × bleu UdeM).
Le QSS (`style.qss`) reprend les mêmes valeurs en dur : toute modification ici
doit être répercutée là-bas.
"""

from __future__ import annotations

import contextlib

from PySide6.QtGui import QColor, QFont

# ---- fonds
BG_WINDOW = "#131720"
BG_SIDEBAR = "#10141c"
BG_SURFACE = "#161b25"      # calendrier, tables
BG_CARD = "#1a202b"         # cartes, panneaux, QGroupBox
SEPARATOR = "#232a36"
CONTROL_BORDER = "#2d3542"

# ---- texte
TEXT_PRIMARY = "#e8ebf0"
TEXT_SECONDARY = "#9da6b5"
TEXT_MUTED = "#6a7484"

# ---- accents
BRAND = "#0057AC"           # pastille logo, icône tray (bleu UdeM)
PRIMARY = "#1f6fd0"         # bouton primaire
PRIMARY_HOVER = "#2a7ada"
ACCENT = "#3987e5"          # sélection nav, focus, aujourd'hui
SELECTION_WASH = "rgba(57,135,229,0.14)"

# ---- statuts (toujours icône + texte, jamais couleur seule)
STATUS_OK = "#0ca30c"
STATUS_WARN = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

# ---- couleurs de cours (ordre fixe, validées daltonisme)
COURSE_COLORS = ("#d95926", "#199e70", "#c98500", "#9085e9")

# ---- catégories de contraintes
CATEGORY_COLORS = {
    "cours": "#3987e5",
    "travail": "#d55181",
    "entrainement": "#22a3c9",
    # le reste de la famille « indisponible »
    "transport": "#4b5568",
    "sommeil": "#4b5568",
    "personnel": "#4b5568",
    "autre": "#4b5568",
}


def qcolor(hex_color: str, alpha: float = 1.0) -> QColor:
    """QColor depuis un hex + opacité 0-1."""
    color = QColor(hex_color)
    color.setAlphaF(alpha)
    return color


def rgba(hex_color: str, alpha: float) -> str:
    """Chaîne CSS ``rgba(r,g,b,a)`` pour les stylesheets dynamiques."""
    color = QColor(hex_color)
    return f"rgba({color.red()},{color.green()},{color.blue()},{alpha:g})"


def lightened(hex_color: str, factor: float = 0.65) -> QColor:
    """Teinte claire d'une couleur de cours, pour le texte sur bloc sombre."""
    color = QColor(hex_color)
    r = round(color.red() + (255 - color.red()) * factor)
    g = round(color.green() + (255 - color.green()) * factor)
    b = round(color.blue() + (255 - color.blue()) * factor)
    return QColor(r, g, b)


def tabular_font(base: QFont, point_size: int | None = None,
                 weight: QFont.Weight | None = None) -> QFont:
    """Police à chiffres tabulaires (feature OpenType `tnum` si disponible)."""
    font = QFont(base)
    if point_size is not None:
        font.setPointSize(point_size)
    if weight is not None:
        font.setWeight(weight)
    # Qt >= 6.7 ; sans la feature, les chiffres restent proportionnels.
    with contextlib.suppress(AttributeError, TypeError):
        font.setFeature(QFont.Tag("tnum"), 1)
    return font


def fmt_number(value: float, decimals: int = 1) -> str:
    """Nombre à la française : virgule décimale, zéros inutiles retirés.

    `fmt_number(1.3) -> "1,3"`, `fmt_number(9.0) -> "9"`, `fmt_number(0.25, 2) -> "0,25"`.
    L'unité (h, %) reste à la charge de l'appelant (parfois « x / y h »).
    """
    rounded = round(float(value), decimals)
    text = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return (text or "0").replace(".", ",")
