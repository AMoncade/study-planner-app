"""Vue Cours & évaluations (ARCHITECTURE §5.2) : arbre éditable + panneau de détail."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from planner.ui.models.course_tree import CourseTreeModel


class CoursesView(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.model = CourseTreeModel(conn, self)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.expandAll()
        for column, width in ((0, 320), (3, 140), (4, 90)):
            self.tree.setColumnWidth(column, width)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Sélectionner une évaluation pour voir le détail.")

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        title = QLabel("Cours et évaluations")
        title.setProperty("role", "viewTitle")

        hint = QLabel(
            "Double-clic pour éditer : difficulté et × effort sur une ligne de cours, "
            "override (h) sur une évaluation. Fond ambré = confiance à vérifier, "
            "fond rouge = date à saisir."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "caption")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(hint)
        row = QHBoxLayout()
        row.addWidget(splitter)
        layout.addLayout(row, 1)

        self.tree.selectionModel().currentChanged.connect(self._show_detail)

    def refresh(self) -> None:
        self.model.reload()
        self.tree.expandAll()

    def _show_detail(self, current, _previous) -> None:
        node = self.model._node(current) if current.isValid() else None
        if not node or node[0] != "eval":
            self.detail.clear()
            return
        ev = node[1]
        parts = [f"{ev.external_id} — {ev.title}", ""]
        if ev.content_scope:
            parts += ["Matière couverte :"] + [f"  • {s}" for s in ev.content_scope] + [""]
        if ev.resources:
            parts += ["Ressources :"] + [f"  • {r}" for r in ev.resources] + [""]
        if ev.notes:
            parts += [f"Notes : {ev.notes}", ""]
        if ev.source_excerpt:
            parts += [f"Extrait du plan de cours : « {ev.source_excerpt} »"]
        self.detail.setPlainText("\n".join(parts))
