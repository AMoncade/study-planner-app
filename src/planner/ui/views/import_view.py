"""Vue Importer (ARCHITECTURE §5.1) : dépôt/choix d'un JSON, rapport de validation,
aperçu des évaluations, import avec résumé de réconciliation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from planner.core.errors import ImportBlockedError
from planner.core.importer import import_course_data
from planner.core.validation import validate_document
from planner.resources import resource_path

PROMPT_PATH = resource_path("docs/PROMPT_EXTRACTION.md")


class ImportView(QWidget):
    imported = Signal(str)  # code du cours importé

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._data: dict | None = None
        self.setAcceptDrops(True)

        self.status = QLabel("Déposer un fichier .json ici, ou cliquer sur « Parcourir… ».")
        self.status.setWordWrap(True)

        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        copy_prompt = QPushButton("Copier le prompt d'extraction")
        copy_prompt.clicked.connect(self._copy_prompt)
        self.import_button = QPushButton("Importer")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._do_import)

        buttons = QHBoxLayout()
        buttons.addWidget(browse)
        buttons.addWidget(copy_prompt)
        buttons.addStretch()
        buttons.addWidget(self.import_button)

        self.report = QTableWidget(0, 2)
        self.report.setHorizontalHeaderLabels(["Statut", "Message"])
        self.report.horizontalHeader().setStretchLastSection(True)
        self.report.verticalHeader().setVisible(False)
        self.report.setEditTriggers(QTableWidget.NoEditTriggers)

        self.preview = QTableWidget(0, 5)
        self.preview.setHorizontalHeaderLabels(["Id", "Titre", "Type", "Poids %", "Échéance"])
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Rapport de validation :"))
        layout.addWidget(self.report, 1)
        layout.addWidget(QLabel("Aperçu des évaluations détectées :"))
        layout.addWidget(self.preview, 2)

    # ------------------------------------------------------------ chargement

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(Path(url.toLocalFile()))
            break

    def _browse(self):
        name, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier JSON de cours", "", "JSON (*.json)"
        )
        if name:
            self.load_file(Path(name))

    def _copy_prompt(self):
        QApplication.clipboard().setText(PROMPT_PATH.read_text(encoding="utf-8"))
        self.status.setText("Prompt d'extraction copié dans le presse-papiers : "
                            "le coller dans le chat Claude avec le PDF du plan de cours.")

    def load_file(self, path: Path) -> None:
        """Charge et valide un fichier sans l'importer ; remplit rapport et aperçu."""
        self._data = None
        self.import_button.setEnabled(False)
        self.report.setRowCount(0)
        self.preview.setRowCount(0)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.status.setText(f"❌ {path.name} : fichier illisible — {exc}")
            return
        errors, warnings = validate_document(data)
        rows = [("❌", e) for e in errors] + [("⚠", w) for w in warnings]
        if not rows:
            rows = [("✅", "Toutes les règles de validation passent.")]
        self.report.setRowCount(len(rows))
        for i, (icon, message) in enumerate(rows):
            self.report.setItem(i, 0, QTableWidgetItem(icon))
            self.report.setItem(i, 1, QTableWidgetItem(message))
        if errors:
            self.status.setText(f"❌ {path.name} : import refusé ({len(errors)} erreur(s)).")
            return
        self._data = data
        course = data["course"]
        evaluations = data["evaluations"]
        self.preview.setRowCount(len(evaluations))
        for i, ev in enumerate(evaluations):
            for j, value in enumerate((
                ev["id"], ev["title"], ev["type"], f"{ev['weight']:g}",
                ev["due_date"] or "à saisir ⚠",
            )):
                item = QTableWidgetItem(str(value))
                if ev.get("source_excerpt"):
                    item.setToolTip(f"« {ev['source_excerpt']} »")
                self.preview.setItem(i, j, item)
        self.status.setText(
            f"{path.name} : {course['code']} — {course['title']} ({course['term']}), "
            f"{len(evaluations)} évaluation(s). Prêt à importer."
        )
        self.import_button.setEnabled(True)

    def _do_import(self):
        if self._data is None:
            return
        try:
            report = import_course_data(self.conn, self._data, today=date.today())
        except ImportBlockedError as exc:
            self.status.setText("❌ Import refusé : " + " ; ".join(exc.errors))
            return
        summary = (f"✅ {report.course_code} importé : {report.created} nouvelle(s) · "
                   f"{report.updated} modifiée(s) · {report.unchanged} inchangée(s) · "
                   f"{report.archived} archivée(s).")
        if report.warnings:
            summary += f"  ({len(report.warnings)} avertissement(s) — voir le rapport)"
            self.report.setRowCount(len(report.warnings))
            for i, warning in enumerate(report.warnings):
                self.report.setItem(i, 0, QTableWidgetItem("⚠"))
                self.report.setItem(i, 1, QTableWidgetItem(warning))
        self.status.setText(summary)
        self.import_button.setEnabled(False)
        self.imported.emit(report.course_code)
