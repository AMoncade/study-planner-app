"""Vue Tableau de bord (ARCHITECTURE §5.5) : tuiles, échéances, progression, alertes."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from planner.config import load_engine_settings
from planner.core.validation import cross_course_conflicts
from planner.scheduler.rebalance import hours_done_by_evaluation, rebalance
from planner.scheduler.workload import total_hours
from planner.storage import repositories as repos
from planner.ui import theme
from planner.ui.theme import COURSE_COLORS
from planner.ui.widgets.badge import Badge
from planner.ui.widgets.hbar_chart import HBarChart


def _label(text: str, role: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    return label


class _Tile(QFrame):
    """Tuile de métrique : libellé MAJUSCULES, valeur 26 px, sous-texte discret."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.title = _label(title.upper(), "tileLabel")
        self.value = _label("—", "tileValue")
        self.value.setFont(theme.tabular_font(self.value.font()))
        self.sub = _label("", "tileSub")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.sub)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


def _card(inner_layout: QVBoxLayout) -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    inner_layout.setContentsMargins(18, 16, 18, 16)
    inner_layout.setSpacing(10)
    frame.setLayout(inner_layout)
    return frame


class DashboardView(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        title = _label("Tableau de bord", "viewTitle")

        # ---- tuiles
        self.tile_week = _Tile("Cette semaine")
        self.tile_coverage = _Tile("Couverture")
        self.tile_next = _Tile("Prochaine échéance")
        self.tile_streak = _Tile("Assiduité 14 jours")
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        for tile in (self.tile_week, self.tile_coverage, self.tile_next,
                     self.tile_streak):
            tiles.addWidget(tile, 1)

        # ---- alertes (badges) et échéances
        self.alerts_holder = QVBoxLayout()
        self.alerts_holder.setSpacing(8)
        alerts_layout = QVBoxLayout()
        alerts_layout.addWidget(_label("Alertes", "sectionTitle"))
        alerts_layout.addLayout(self.alerts_holder)
        alerts_card = _card(alerts_layout)

        self.upcoming = QLabel()
        self.upcoming.setWordWrap(True)
        self.upcoming.setTextFormat(Qt.RichText)
        upcoming_layout = QVBoxLayout()
        upcoming_layout.addWidget(_label("Prochaines échéances (14 jours)",
                                         "sectionTitle"))
        upcoming_layout.addWidget(self.upcoming)
        upcoming_card = _card(upcoming_layout)

        # ---- progression par évaluation (barres en couleur de cours)
        self.progress_holder = QVBoxLayout()
        self.progress_holder.setSpacing(8)
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(_label("Progression par évaluation", "sectionTitle"))
        progress_layout.addLayout(self.progress_holder)
        progress_card = _card(progress_layout)

        # ---- charges et historique
        self.course_chart = HBarChart()
        chart_layout = QVBoxLayout()
        chart_layout.addWidget(_label("Charge restante par cours", "sectionTitle"))
        chart_layout.addWidget(self.course_chart)
        chart_card = _card(chart_layout)

        self.history_chart = HBarChart()
        history_layout = QVBoxLayout()
        history_layout.addWidget(_label("Heures étudiées par semaine", "sectionTitle"))
        history_layout.addWidget(self.history_chart)
        history_card = _card(history_layout)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(tiles)
        layout.addWidget(alerts_card)
        layout.addWidget(upcoming_card)
        layout.addWidget(progress_card)
        layout.addWidget(chart_card)
        layout.addWidget(history_card)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh()

    # ------------------------------------------------------------ rafraîchissement

    def refresh(self, today: date | None = None) -> None:
        today = today or date.today()
        settings = load_engine_settings(self.conn)
        courses = repos.list_courses(self.conn)
        course_by_id = {c.id: c for c in courses}
        course_color = {
            c.id: COURSE_COLORS[i % len(COURSE_COLORS)] for i, c in enumerate(courses)
        }
        evaluations = [
            e for c in courses for e in repos.list_evaluations(self.conn, course_id=c.id)
        ]
        blocks = repos.list_study_blocks(self.conn)
        done_hours = hours_done_by_evaluation(blocks)

        # ---- alertes : recalcul à blanc (rien n'est appliqué)
        alerts: list[tuple[str, str]] = []   # (kind, message)
        coverage = None
        if evaluations:
            result, _diff = rebalance(
                courses, evaluations, repos.list_constraints(self.conn), blocks,
                settings, datetime.combine(today, datetime.min.time()),
            )
            if result.metrics is not None:
                coverage = result.metrics.coverage
            if result.rho < 1.0:
                alerts.append(("critical",
                               f"Semestre en surcharge : facteur ρ = {result.rho:.2f}."))
            for external_id, deficit in sorted(result.deficits.items()):
                if deficit > 0:
                    alerts.append(("serious", f"{external_id} : déficit de {deficit:g} h "
                                              "(préparation insuffisante)."))
            for external_id, reason in sorted(result.exclusions.items()):
                if "manquante" in reason:
                    alerts.append(("warn", f"{external_id} : {reason}."))
        alerts.extend(("warn", c) for c in cross_course_conflicts(self.conn))
        self._set_alerts(alerts)

        # ---- tuiles
        monday = today - timedelta(days=today.weekday())
        week_blocks = [
            b for b in blocks if monday <= b.start_at.date() <= monday + timedelta(days=6)
        ]
        planned = sum(b.planned_minutes for b in week_blocks) / 60
        done = sum(
            (b.actual_minutes if b.actual_minutes is not None else b.planned_minutes)
            for b in week_blocks if b.status in ("done", "partial")
        ) / 60
        self.tile_week.set(f"{done:g} / {planned:g} h", "faites / planifiées")

        self.tile_coverage.set(
            f"{coverage * 100:.0f} %" if coverage is not None else "—",
            "des heures visées sont placées",
        )

        future = [e for e in evaluations
                  if e.due_at is not None and e.due_at.date() >= today]
        if future:
            nxt = min(future, key=lambda e: e.due_at)
            days_left = (nxt.due_at.date() - today).days
            self.tile_next.set(f"J−{days_left}",
                               f"{course_by_id[nxt.course_id].code} · {nxt.title}")
        else:
            self.tile_next.set("—", "aucune échéance datée")

        past = [b for b in blocks
                if today - timedelta(days=14) <= b.start_at.date() < today]
        past_planned = sum(b.planned_minutes for b in past)
        past_done = sum(
            (b.actual_minutes if b.actual_minutes is not None else b.planned_minutes)
            for b in past if b.status in ("done", "partial")
        )
        if past_planned:
            self.tile_streak.set(f"{past_done / past_planned * 100:.0f} %",
                                 "des minutes planifiées ont été faites")
        else:
            self.tile_streak.set("—", "aucun bloc sur les 14 derniers jours")

        # ---- échéances à 14 jours
        horizon = today + timedelta(days=14)
        rows = []
        for ev in sorted(evaluations, key=lambda e: (e.due_at is None, e.due_at)):
            if ev.due_at is None or not (today <= ev.due_at.date() <= horizon):
                continue
            days_left = (ev.due_at.date() - today).days
            code = course_by_id[ev.course_id].code
            rows.append(f"<b>J−{days_left}</b> · {code} — {ev.title} "
                        f"({ev.weight:g} %) · {ev.due_at:%a %d/%m %H:%M}")
        self.upcoming.setText("<br>".join(rows) if rows else "Rien dans les 14 jours.")

        # ---- progression par évaluation, barre en couleur du cours
        self._clear_layout(self.progress_holder)
        for ev in sorted(evaluations, key=lambda e: (e.due_at is None, e.due_at)):
            if ev.weight <= 0 or ev.due_at is None or ev.due_at.date() < today:
                continue
            course = course_by_id[ev.course_id]
            target = total_hours(ev, course, settings)
            done_ev = min(done_hours.get(ev.id, 0.0), target)
            bar = QProgressBar()
            bar.setMaximum(max(1, int(target * 2)))
            bar.setValue(int(done_ev * 2))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                "QProgressBar { background-color: #232a36; border: none;"
                " border-radius: 4px; }"
                f" QProgressBar::chunk {{ background-color:"
                f" {course_color[ev.course_id]}; border-radius: 4px; }}"
            )
            label = QLabel(f"{course.code} · {ev.title}")
            label.setProperty("role", "secondary")
            label.setMinimumWidth(240)
            hours_label = QLabel(f"{done_ev:g} / {target:g} h")
            hours_label.setProperty("role", "caption")
            hours_label.setFont(theme.tabular_font(hours_label.font()))
            hours_label.setMinimumWidth(70)
            hours_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(hours_label)
            self.progress_holder.addLayout(row)
        if not self.progress_holder.count():
            empty = QLabel("Aucune évaluation à venir.")
            empty.setProperty("role", "caption")
            self.progress_holder.addWidget(empty)

        # ---- charge restante par cours
        chart_rows = []
        for course in courses:
            remaining = sum(
                max(0.0, total_hours(e, course, settings) - done_hours.get(e.id, 0.0))
                for e in evaluations
                if e.course_id == course.id and e.weight > 0
                and e.due_at is not None and e.due_at.date() >= today
            )
            if remaining > 0:
                chart_rows.append((course.code, round(remaining, 1),
                                   course_color[course.id]))
        self.course_chart.set_rows(chart_rows)

        # ---- historique : heures faites par semaine ISO
        per_week: dict[str, float] = {}
        for b in blocks:
            if b.status not in ("done", "partial"):
                continue
            year, week, _ = b.start_at.isocalendar()
            minutes = b.actual_minutes if b.actual_minutes is not None else b.planned_minutes
            key = f"S{week:02d} {year}"
            per_week[key] = per_week.get(key, 0.0) + minutes / 60
        history = [(k, round(v, 1), theme.STATUS_OK) for k, v in sorted(per_week.items())]
        self.history_chart.set_rows(history)

    # ------------------------------------------------------------ aides

    def _set_alerts(self, alerts: list[tuple[str, str]]) -> None:
        self._clear_layout(self.alerts_holder)
        if not alerts:
            self.alerts_holder.addWidget(Badge("Aucune alerte.", kind="ok"))
            return
        for kind, message in alerts:
            self.alerts_holder.addWidget(Badge(message, kind=kind))

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    inner = sub.takeAt(0)
                    if inner.widget():
                        inner.widget().deleteLater()
                sub.deleteLater()
