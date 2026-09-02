"""Vue Planning (ARCHITECTURE §5.4) : calendrier hebdo, statuts, recalcul avec aperçu."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from planner.config import EngineSettings
from planner.scheduler.rebalance import RebalanceDiff, apply_rebalance, rebalance
from planner.storage import repositories as repos
from planner.ui.widgets.week_calendar import BlockView, BusyView, WeekCalendar


class BlockCompletionDialog(QDialog):
    """Saisie « partiellement fait » : minutes réelles + efficacité (§5.7)."""

    def __init__(self, planned_minutes: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bloc partiellement fait")
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 600)
        self.minutes.setValue(planned_minutes // 2)
        self.minutes.setSuffix(" min")
        self.efficiency = QDoubleSpinBox()
        self.efficiency.setRange(0.5, 1.2)
        self.efficiency.setSingleStep(0.1)
        self.efficiency.setValue(1.0)
        form = QFormLayout(self)
        form.addRow("Minutes réellement étudiées :", self.minutes)
        form.addRow("Efficacité (0,5–1,2) :", self.efficiency)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class RecalcDiffDialog(QDialog):
    """Aperçu du différentiel avant application (§5.4)."""

    def __init__(self, diff: RebalanceDiff, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recalculer le plan")
        summary = QLabel(
            f"{diff.kept} bloc(s) inchangé(s) · {diff.moved} déplacé(s) · "
            f"{diff.added} ajouté(s) · {diff.removed} supprimé(s).\n\nAppliquer ?"
        )
        summary.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(buttons)


class ScheduleView(QWidget):
    changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.settings = EngineSettings()
        self.monday = date.today() - timedelta(days=date.today().weekday())

        previous_week = QPushButton("◀")
        previous_week.clicked.connect(lambda: self._shift_week(-1))
        today_button = QPushButton("Aujourd'hui")
        today_button.clicked.connect(self._go_today)
        next_week = QPushButton("▶")
        next_week.clicked.connect(lambda: self._shift_week(1))
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.recalc_button = QPushButton("Recalculer le plan")
        self.recalc_button.clicked.connect(self.recalculate)

        nav = QHBoxLayout()
        nav.addWidget(previous_week)
        nav.addWidget(today_button)
        nav.addWidget(next_week)
        nav.addWidget(self.week_label, 1)
        nav.addWidget(self.recalc_button)

        self.banner = QLabel()
        self.banner.setWordWrap(True)

        self.calendar = WeekCalendar(self.settings.wake_start, self.settings.wake_end)
        self.calendar.block_context_requested.connect(self._context_menu)
        self.calendar.block_move_requested.connect(self._move_block)
        self.calendar.block_activated.connect(self._show_detail)

        layout = QVBoxLayout(self)
        layout.addLayout(nav)
        layout.addWidget(self.banner)
        layout.addWidget(self.calendar, 1)

        self.refresh()

    # ------------------------------------------------------------ données

    def _load(self):
        courses = repos.list_courses(self.conn)
        evaluations = [
            e for c in courses for e in repos.list_evaluations(self.conn, course_id=c.id)
        ]
        blocks = repos.list_study_blocks(self.conn)
        return courses, evaluations, blocks

    def refresh(self) -> None:
        courses, evaluations, blocks = self._load()
        course_index = {c.id: i for i, c in enumerate(courses)}
        eval_by_id = {e.id: e for e in evaluations}
        self._blocks_by_id = {b.id: b for b in blocks}

        views = []
        for b in blocks:
            ev = eval_by_id.get(b.evaluation_id)
            if ev is None:
                continue
            code = next((c.code for c in courses if c.id == ev.course_id), "?")
            views.append(BlockView(
                id=b.id, start_at=b.start_at, end_at=b.end_at,
                label=f"{code} · {ev.title}",
                course_key=course_index.get(ev.course_id, 0),
                status=b.status, locked=b.locked,
            ))

        busy = []
        week_days = [self.monday + timedelta(days=i) for i in range(7)]
        for c in repos.list_constraints(self.conn):
            for day in week_days:
                applies = (c.specific_date == day if c.specific_date is not None
                           else c.weekday == day.weekday())
                if applies:
                    busy.append(BusyView(day=day, start=c.start, end=c.end,
                                         label=c.label, hatched=True))
        for course in courses:
            for session in course.sessions:
                for day in week_days:
                    if session.weekday != day.weekday():
                        continue
                    if session.start_date and day < session.start_date:
                        continue
                    if session.end_date and day > session.end_date:
                        continue
                    if day in session.except_dates:
                        continue
                    busy.append(BusyView(
                        day=day, start=session.start, end=session.end,
                        label=f"{course.code} ({session.kind})", hatched=False,
                    ))

        self.calendar.set_week(self.monday)
        self.calendar.set_data(views, busy)
        self.week_label.setText(
            f"Semaine du {self.monday:%d/%m/%Y} au {self.monday + timedelta(days=6):%d/%m/%Y}"
        )

        week_blocks = [
            b for b in blocks
            if self.monday <= b.start_at.date() <= self.monday + timedelta(days=6)
        ]
        planned = sum(b.planned_minutes for b in week_blocks) / 60
        done = sum(
            (b.actual_minutes if b.actual_minutes is not None else b.planned_minutes)
            for b in week_blocks if b.status in ("done", "partial")
        ) / 60
        missing = sum(1 for e in evaluations if e.due_at is None)
        message = f"Cette semaine : {planned:g} h planifiées · {done:g} h faites."
        if missing:
            message += f"  ⚠ {missing} évaluation(s) sans date."
        if not blocks:
            message += "  Aucun bloc : cliquer sur « Recalculer le plan »."
        self.banner.setText(message)

    # ------------------------------------------------------------ navigation

    def _shift_week(self, delta: int) -> None:
        self.monday += timedelta(weeks=delta)
        self.refresh()

    def _go_today(self) -> None:
        self.monday = date.today() - timedelta(days=date.today().weekday())
        self.refresh()

    # ------------------------------------------------------------ recalcul

    def recalculate(self, now: datetime | None = None, interactive: bool = True) -> None:
        courses, evaluations, blocks = self._load()
        if not evaluations:
            self.banner.setText("Aucune évaluation : importer un cours d'abord.")
            return
        now = now or datetime.now()
        _result, diff = rebalance(
            courses, evaluations, repos.list_constraints(self.conn), blocks,
            self.settings, now,
        )
        if interactive:
            dialog = RecalcDiffDialog(diff, self)
            if dialog.exec() != QDialog.Accepted:
                return
        apply_rebalance(self.conn, diff)
        self.refresh()
        self.changed.emit()

    # ------------------------------------------------------------ interactions

    def _move_block(self, block_id: int, new_start: datetime) -> None:
        block = self._blocks_by_id.get(block_id)
        if block is None:
            return
        duration = block.end_at - block.start_at
        repos.move_study_block(self.conn, block_id, new_start, new_start + duration)
        self.refresh()
        self.changed.emit()

    def set_block_status(self, block_id: int, status: str,
                         actual_minutes: int | None = None,
                         efficiency: float | None = None) -> None:
        repos.update_study_block_status(self.conn, block_id, status,
                                        actual_minutes=actual_minutes,
                                        efficiency=efficiency)
        self.refresh()
        self.changed.emit()

    def toggle_lock(self, block_id: int) -> None:
        block = self._blocks_by_id.get(block_id)
        if block is not None:
            repos.set_study_block_lock(self.conn, block_id, not block.locked)
            self.refresh()

    def delete_block(self, block_id: int) -> None:
        repos.delete_study_block(self.conn, block_id)
        self.conn.commit()
        self.refresh()
        self.changed.emit()

    def _context_menu(self, block_id: int, global_pos) -> None:
        block = self._blocks_by_id.get(block_id)
        if block is None:
            return
        menu = QMenu(self)
        menu.addAction("Fait ✓", lambda: self.set_block_status(block_id, "done"))
        menu.addAction("Partiellement fait…", lambda: self._partial(block_id))
        menu.addAction("Manqué ✗", lambda: self.set_block_status(block_id, "skipped"))
        menu.addAction(
            "Déverrouiller" if block.locked else "Verrouiller",
            lambda: self.toggle_lock(block_id),
        )
        menu.addSeparator()
        menu.addAction("Supprimer", lambda: self.delete_block(block_id))
        menu.exec(global_pos)

    def _partial(self, block_id: int) -> None:
        block = self._blocks_by_id.get(block_id)
        if block is None:
            return
        dialog = BlockCompletionDialog(block.planned_minutes, self)
        if dialog.exec() == QDialog.Accepted:
            self.set_block_status(block_id, "partial",
                                  actual_minutes=dialog.minutes.value(),
                                  efficiency=dialog.efficiency.value())

    def _show_detail(self, block_id: int) -> None:
        block = self._blocks_by_id.get(block_id)
        if block is None:
            return
        courses, evaluations, _ = self._load()
        ev = next((e for e in evaluations if e.id == block.evaluation_id), None)
        if ev is None:
            return
        course = next((c for c in courses if c.id == ev.course_id), None)
        lines = [
            f"{ev.external_id} — {ev.title}",
            f"Cours : {course.code} — {course.title}" if course else "",
            f"Échéance : {ev.due_at:%Y-%m-%d %H:%M}" if ev.due_at else "Échéance : à saisir",
            f"Poids : {ev.weight:g} %",
        ]
        if ev.notes:
            lines.append(f"Notes : {ev.notes}")
        QMessageBox.information(self, "Détail de l'évaluation",
                                "\n".join(line for line in lines if line))
