"""Vue Statistiques (ARCHITECTURE §5.8) : bilan de la session à partir de l'historique.

La vue ne calcule rien : les agrégats viennent du module pur `scheduler.stats`.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from planner.scheduler.stats import (
    attendance,
    compute_overview,
    hours_by_course,
    weekly_hours,
)
from planner.storage import repositories as repos
from planner.ui import theme
from planner.ui.icons import svg_pixmap
from planner.ui.widgets.hbar_chart import HBarChart
from planner.ui.widgets.stacked_bar import StackedBar
from planner.ui.widgets.week_bars import WeekBarChart

# Invitation commune des états vides : dire quoi faire, pas montrer un graphique cassé.
_EMPTY_HINT = ("Coche tes blocs Fait/Manqué dans le Planning "
               "pour voir tes statistiques.")


def _label(text: str, role: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    return label


class _Tile(QFrame):
    """Tuile de métrique, même style que le tableau de bord (tileLabel/Value/Sub)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.title = _label(title.upper(), "tileLabel")
        self.value = _label("—", "tileValue")
        self.value.setFont(theme.tabular_font(self.value.font()))
        self.sub_icon = QLabel()
        self.sub_icon.setFixedSize(14, 14)
        self.sub_icon.hide()
        self.sub = _label("", "tileSub")
        sub_row = QHBoxLayout()
        sub_row.setContentsMargins(0, 0, 0, 0)
        sub_row.setSpacing(5)
        sub_row.addWidget(self.sub_icon)
        sub_row.addWidget(self.sub, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addLayout(sub_row)

    def set(self, value: str, sub: str = "", value_color: str | None = None,
            icon: str | None = None, icon_color: str | None = None) -> None:
        self.value.setText(value)
        # la couleur appuie le message ; l'icône et le libellé le portent seuls
        self.value.setStyleSheet(f"color: {value_color};" if value_color else "")
        self.sub.setText(sub)
        if icon and icon_color:
            self.sub_icon.setPixmap(svg_pixmap(icon, icon_color, size=12))
            self.sub_icon.show()
        else:
            self.sub_icon.hide()


class _LegendEntry(QWidget):
    """Icône + libellé + compte : le statut reste lisible sans la couleur."""

    def __init__(self, icon: str, color: str, label: str, parent=None):
        super().__init__(parent)
        self._icon = QLabel()
        self._icon.setFixedSize(14, 14)
        self._icon.setPixmap(svg_pixmap(icon, color, size=14))
        self._text = _label(label, "secondary")
        self.count = _label("0", "secondary")
        self.count.setFont(theme.tabular_font(self.count.font()))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        layout.addWidget(self.count)

    def set_count(self, count: int) -> None:
        self.count.setText(str(count))


def _card(inner_layout: QVBoxLayout) -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    inner_layout.setContentsMargins(18, 16, 18, 16)
    inner_layout.setSpacing(10)
    frame.setLayout(inner_layout)
    return frame


class StatsView(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        title = _label("Statistiques", "viewTitle")

        # ---- tuiles
        self.tile_hours = _Tile("Heures d'étude faites")
        self.tile_completion = _Tile("Taux de complétion")
        self.tile_efficiency = _Tile("Efficacité moyenne")
        self.tile_delta = _Tile("Avance / retard")
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        for tile in (self.tile_hours, self.tile_completion,
                     self.tile_efficiency, self.tile_delta):
            tiles.addWidget(tile, 1)

        # ---- heures par semaine
        self.week_chart = WeekBarChart()
        self.weekly_empty = _label(_EMPTY_HINT, "caption")
        self.weekly_empty.setWordWrap(True)
        weekly_layout = QVBoxLayout()
        weekly_layout.addWidget(_label("Heures par semaine", "sectionTitle"))
        weekly_layout.addWidget(self.week_chart)
        weekly_layout.addWidget(self.weekly_empty)
        weekly_card = _card(weekly_layout)

        # ---- heures par cours
        self.course_chart = HBarChart()
        self.course_empty = _label(_EMPTY_HINT, "caption")
        self.course_empty.setWordWrap(True)
        course_layout = QVBoxLayout()
        course_layout.addWidget(_label("Heures par cours", "sectionTitle"))
        course_layout.addWidget(self.course_chart)
        course_layout.addWidget(self.course_empty)
        course_card = _card(course_layout)

        # ---- assiduité
        self.attendance_bar = StackedBar()
        self.attendance_empty = _label("", "caption")
        self.attendance_empty.setWordWrap(True)
        self.legend_done = _LegendEntry("check-circle", theme.STATUS_OK, "Fait")
        self.legend_partial = _LegendEntry("minus-circle", theme.STATUS_SERIOUS,
                                           "Partiel")
        self.legend_skipped = _LegendEntry("x-circle", theme.STATUS_CRITICAL,
                                           "Manqué")
        self.legend_pending = _LegendEntry("help-circle", theme.TEXT_MUTED,
                                           "Non renseigné")
        legend = QHBoxLayout()
        legend.setSpacing(18)
        for entry in (self.legend_done, self.legend_partial,
                      self.legend_skipped, self.legend_pending):
            legend.addWidget(entry)
        legend.addStretch()
        attendance_layout = QVBoxLayout()
        attendance_layout.addWidget(_label("Assiduité", "sectionTitle"))
        attendance_layout.addWidget(self.attendance_bar)
        attendance_layout.addLayout(legend)
        attendance_layout.addWidget(self.attendance_empty)
        attendance_card = _card(attendance_layout)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(tiles)
        layout.addWidget(weekly_card)
        layout.addWidget(course_card)
        layout.addWidget(attendance_card)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh()

    # ------------------------------------------------------------ rafraîchissement

    def refresh(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        courses = repos.list_courses(self.conn)
        evaluations = [
            e for c in courses for e in repos.list_evaluations(self.conn, course_id=c.id)
        ]
        blocks = repos.list_study_blocks(self.conn)

        # ---- tuiles
        overview = compute_overview(blocks, now)
        self.tile_hours.set(f"{theme.fmt_number(overview.done_hours)} h",
                            "sur toute la session")

        if overview.completion_rate is not None:
            self.tile_completion.set(
                f"{overview.completion_rate * 100:.0f} %",
                f"{overview.completed_due_blocks} / {overview.due_blocks} blocs échus",
            )
        else:
            self.tile_completion.set("—", "aucun bloc échu pour l'instant")

        if overview.avg_efficiency is not None:
            self.tile_efficiency.set(f"{overview.avg_efficiency * 100:.0f} %",
                                     "des blocs faits avec efficacité saisie")
        else:
            self.tile_efficiency.set("—", "saisie à la complétion d'un bloc")

        delta = overview.plan_delta_hours
        if overview.due_blocks or overview.done_hours:
            ahead = delta >= 0
            sign = "+" if ahead else "−"
            self.tile_delta.set(
                f"{sign}{theme.fmt_number(abs(delta))} h",
                "en avance sur le plan" if ahead else "en retard sur le plan",
                value_color=theme.STATUS_OK if ahead else theme.STATUS_SERIOUS,
                icon="trend-up" if ahead else "trend-down",
                icon_color=theme.STATUS_OK if ahead else theme.STATUS_SERIOUS,
            )
        else:
            self.tile_delta.set("—", "rien d'échu à comparer au plan")

        # ---- heures par semaine
        weeks = weekly_hours(blocks, now)
        has_done_week = any(w.done_hours > 0 for w in weeks)
        self.week_chart.set_weeks(weeks)
        self.week_chart.setVisible(bool(weeks))
        if not weeks:
            self.weekly_empty.setText("Aucun bloc planifié — importe un cours puis "
                                      "recalcule le plan.")
        elif not has_done_week:
            self.weekly_empty.setText(_EMPTY_HINT)
        self.weekly_empty.setVisible(not has_done_week)

        # ---- heures par cours (la couleur suit le cours, jamais son rang)
        course_stats = hours_by_course(blocks, evaluations, courses)
        rows = [
            (s.code, round(s.done_hours, 1), round(s.planned_hours, 1),
             theme.COURSE_COLORS[s.color_index % len(theme.COURSE_COLORS)])
            for s in course_stats if s.planned_hours > 0 or s.done_hours > 0
        ]
        self.course_chart.set_progress_rows(rows)
        self.course_chart.setVisible(bool(rows))
        has_done_course = any(done > 0 for _, done, _, _ in rows)
        if not rows:
            self.course_empty.setText("Aucun bloc planifié — importe un cours puis "
                                      "recalcule le plan.")
        elif not has_done_course:
            self.course_empty.setText(_EMPTY_HINT)
        self.course_empty.setVisible(not has_done_course)

        # ---- assiduité (blocs échus seulement)
        att = attendance(blocks, now)
        self.attendance_bar.set_segments([
            (att.done, theme.STATUS_OK),
            (att.partial, theme.STATUS_SERIOUS),
            (att.skipped, theme.STATUS_CRITICAL),
            (att.pending, theme.TEXT_MUTED),
        ])
        has_due = att.total > 0
        self.attendance_bar.setVisible(has_due)
        for entry, count in ((self.legend_done, att.done),
                             (self.legend_partial, att.partial),
                             (self.legend_skipped, att.skipped),
                             (self.legend_pending, att.pending)):
            entry.set_count(count)
            entry.setVisible(has_due)
        self.legend_pending.setVisible(has_due and att.pending > 0)
        self.attendance_empty.setText(
            "Aucun bloc échu pour l'instant — reviens après tes premiers blocs, "
            "et coche-les Fait/Manqué dans le Planning."
        )
        self.attendance_empty.setVisible(not has_due)


