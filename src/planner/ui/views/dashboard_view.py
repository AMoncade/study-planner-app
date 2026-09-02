"""Vue Tableau de bord (ARCHITECTURE §5.5) : échéances, progression, alertes, charges."""

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
from planner.ui.widgets.hbar_chart import HBarChart
from planner.ui.widgets.week_calendar import COURSE_COLORS


def _section(title: str) -> QLabel:
    label = QLabel(title)
    label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
    return label


class DashboardView(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        self.alerts = QLabel()
        self.alerts.setWordWrap(True)
        self.upcoming = QLabel()
        self.upcoming.setWordWrap(True)
        self.upcoming.setTextFormat(Qt.RichText)
        self.progress_holder = QVBoxLayout()
        self.course_chart = HBarChart()
        self.history_chart = HBarChart()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(_section("Alertes"))
        layout.addWidget(self.alerts)
        layout.addWidget(_section("Prochaines échéances (14 jours)"))
        layout.addWidget(self.upcoming)
        layout.addWidget(_section("Progression par évaluation"))
        holder = QFrame()
        holder.setLayout(self.progress_holder)
        layout.addWidget(holder)
        layout.addWidget(_section("Charge restante par cours"))
        layout.addWidget(self.course_chart)
        layout.addWidget(_section("Heures étudiées par semaine"))
        layout.addWidget(self.history_chart)
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
        evaluations = [
            e for c in courses for e in repos.list_evaluations(self.conn, course_id=c.id)
        ]
        blocks = repos.list_study_blocks(self.conn)
        done_hours = hours_done_by_evaluation(blocks)

        # ---- alertes : recalcul à blanc (rien n'est appliqué)
        alerts: list[str] = []
        if evaluations:
            result, _diff = rebalance(
                courses, evaluations, repos.list_constraints(self.conn), blocks,
                settings, datetime.combine(today, datetime.min.time()),
            )
            if result.rho < 1.0:
                alerts.append(f"🔴 Semestre en surcharge : facteur ρ = {result.rho:.2f}.")
            for external_id, deficit in sorted(result.deficits.items()):
                if deficit > 0:
                    alerts.append(f"🟠 {external_id} : déficit de {deficit:g} h "
                                  "(préparation insuffisante).")
            for external_id, reason in sorted(result.exclusions.items()):
                if "manquante" in reason:
                    alerts.append(f"🟡 {external_id} : {reason}.")
        alerts.extend(f"🟡 {c}" for c in cross_course_conflicts(self.conn))
        self.alerts.setText("\n".join(alerts) if alerts else "✅ Aucune alerte.")

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

        # ---- progression par évaluation (échéances futures, pondération non nulle)
        while self.progress_holder.count():
            item = self.progress_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    inner = sub.takeAt(0)
                    if inner.widget():
                        inner.widget().deleteLater()
                sub.deleteLater()
        for ev in sorted(evaluations, key=lambda e: (e.due_at is None, e.due_at)):
            if ev.weight <= 0 or ev.due_at is None or ev.due_at.date() < today:
                continue
            course = course_by_id[ev.course_id]
            target = total_hours(ev, course, settings)
            done = min(done_hours.get(ev.id, 0.0), target)
            bar = QProgressBar()
            bar.setMaximum(int(target * 2))
            bar.setValue(int(done * 2))
            bar.setFormat(f"{done:g} / {target:g} h")
            row = QHBoxLayout()
            label = QLabel(f"{course.code} · {ev.title}")
            label.setMinimumWidth(240)
            row.addWidget(label)
            row.addWidget(bar, 1)
            self.progress_holder.addLayout(row)

        # ---- charge restante par cours
        chart_rows = []
        for i, course in enumerate(courses):
            remaining = sum(
                max(0.0, total_hours(e, course, settings) - done_hours.get(e.id, 0.0))
                for e in evaluations
                if e.course_id == course.id and e.weight > 0
                and e.due_at is not None and e.due_at.date() >= today
            )
            if remaining > 0:
                chart_rows.append((course.code, round(remaining, 1),
                                   COURSE_COLORS[i % len(COURSE_COLORS)]))
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
        history = [(k, round(v, 1), "#2fa46a") for k, v in sorted(per_week.items())]
        self.history_chart.set_rows(history)
