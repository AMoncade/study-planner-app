"""Modèle arborescent cours → évaluations (ARCHITECTURE §5.2).

Colonnes : titre, type, poids, échéance, charge estimée, difficulté, ×effort,
override, confiance. Les colonnes difficulté / ×effort s'éditent sur une ligne de
cours ; override sur une ligne d'évaluation. Toute édition est persistée puis la
charge est recalculée en direct.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

from planner.config import EngineSettings
from planner.scheduler.workload import total_hours
from planner.storage import repositories as repos

COLUMNS = (
    "Titre", "Type", "Poids %", "Échéance", "Charge (h)",
    "Difficulté", "× Effort", "Override (h)", "Confiance",
)
COL_TITLE, COL_TYPE, COL_WEIGHT, COL_DUE, COL_LOAD = 0, 1, 2, 3, 4
COL_DIFFICULTY, COL_EFFORT, COL_OVERRIDE, COL_CONFIDENCE = 5, 6, 7, 8

_ROOT = QModelIndex()

WARNING_BRUSH = QBrush(QColor(120, 100, 20))
ERROR_BRUSH = QBrush(QColor(130, 45, 45))


class CourseTreeModel(QAbstractItemModel):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.settings = EngineSettings()
        self.courses = []
        self.evals_by_course = {}
        self.reload()

    # ------------------------------------------------------------ chargement

    def reload(self) -> None:
        self.beginResetModel()
        self.courses = repos.list_courses(self.conn)
        self.evals_by_course = {
            c.id: repos.list_evaluations(self.conn, course_id=c.id) for c in self.courses
        }
        self.endResetModel()

    # ------------------------------------------------------------ structure

    def index(self, row, column, parent=_ROOT):
        if not parent.isValid():  # ligne de cours
            if 0 <= row < len(self.courses):
                return self.createIndex(row, column, 0)  # id interne 0 = cours
            return QModelIndex()
        if parent.internalId() == 0:  # enfant d'un cours = évaluation
            course = self.courses[parent.row()]
            if 0 <= row < len(self.evals_by_course[course.id]):
                # id interne = index du cours + 1 (0 est réservé aux cours)
                return self.createIndex(row, column, parent.row() + 1)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(int(index.internalId()) - 1, 0, 0)

    def rowCount(self, parent=_ROOT):
        if not parent.isValid():
            return len(self.courses)
        if parent.internalId() == 0 and parent.column() == 0:
            return len(self.evals_by_course[self.courses[parent.row()].id])
        return 0

    def columnCount(self, parent=_ROOT):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    # ------------------------------------------------------------ accès

    def _node(self, index):
        """Retourne ('course', Course) ou ('eval', Evaluation, Course)."""
        if index.internalId() == 0:
            return ("course", self.courses[index.row()])
        course = self.courses[int(index.internalId()) - 1]
        return ("eval", self.evals_by_course[course.id][index.row()], course)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = self._node(index)
        col = index.column()

        if node[0] == "course":
            course = node[1]
            if role in (Qt.DisplayRole, Qt.EditRole):
                if col == COL_TITLE:
                    return f"{course.code} — {course.title} ({course.term})"
                if col == COL_TYPE:
                    return f"{course.credits} crédits" if course.credits else ""
                if col == COL_DIFFICULTY:
                    return course.difficulty
                if col == COL_EFFORT:
                    return course.effort_multiplier
            return None

        _, ev, course = node
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == COL_TITLE:
                return ev.title
            if col == COL_TYPE:
                return ev.type
            if col == COL_WEIGHT:
                return ev.weight
            if col == COL_DUE:
                return ev.due_at.strftime("%Y-%m-%d %H:%M") if ev.due_at else "à saisir ⚠"
            if col == COL_LOAD:
                return total_hours(ev, course, self.settings)
            if col == COL_OVERRIDE:
                return ev.manual_hours_override if role == Qt.EditRole \
                    else (ev.manual_hours_override or "")
            if col == COL_CONFIDENCE:
                return ev.confidence
        if role == Qt.BackgroundRole:
            if ev.due_at is None:
                return ERROR_BRUSH
            if ev.confidence != "high":
                return WARNING_BRUSH
        if role == Qt.ToolTipRole and ev.source_excerpt:
            return f"« {ev.source_excerpt} »"
        return None

    # ------------------------------------------------------------ édition

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        node = self._node(index)
        col = index.column()
        if node[0] == "course" and col in (COL_DIFFICULTY, COL_EFFORT):
            return base | Qt.ItemIsEditable
        if node[0] == "eval" and col == COL_OVERRIDE:
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole:
            return False
        node = self._node(index)
        col = index.column()
        try:
            if node[0] == "course":
                course = node[1]
                if col == COL_DIFFICULTY:
                    difficulty = max(1, min(5, int(value)))
                    repos.update_course_manual_fields(self.conn, course.id,
                                                     difficulty=difficulty)
                elif col == COL_EFFORT:
                    effort = max(0.5, min(2.0, float(value)))
                    repos.update_course_manual_fields(self.conn, course.id,
                                                     effort_multiplier=effort)
                else:
                    return False
            else:
                _, ev, _ = node
                if col != COL_OVERRIDE:
                    return False
                override = None if value in ("", None) else max(0.0, float(value))
                repos.set_manual_hours_override(self.conn, ev.id, override)
        except (TypeError, ValueError):
            return False
        self.reload()  # recharge et recalcule les charges affichées
        return True
