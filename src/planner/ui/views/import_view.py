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
from planner.core.ics_import import format_ics_report, import_ics_file
from planner.core.importer import import_course_data
from planner.core.validation import validate_document
from planner.resources import resource_path
from planner.ui import theme
from planner.ui.icons import svg_icon
from planner.ui.widgets.badge import Badge

PROMPT_PATH = resource_path("docs/PROMPT_EXTRACTION.md")


class ImportView(QWidget):
    imported = Signal(str)  # code du cours importé

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._data: dict | None = None
        self.setAcceptDrops(True)

        title = QLabel("Importer")
        title.setProperty("role", "viewTitle")

        self.status = Badge("Déposer un fichier .json ou .ics ici, "
                            "ou cliquer sur « Parcourir… ».", kind="neutral")

        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        browse_ics = QPushButton("Importer un horaire (.ics)…")
        browse_ics.clicked.connect(self._browse_ics)
        copy_prompt = QPushButton("Copier le prompt d'extraction")
        copy_prompt.clicked.connect(self._copy_prompt)
        self.import_button = QPushButton("Importer")
        self.import_button.setProperty("kind", "primary")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._do_import)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(browse)
        buttons.addWidget(browse_ics)
        buttons.addWidget(copy_prompt)
        buttons.addStretch()
        buttons.addWidget(self.import_button)

        self.report = QTableWidget(0, 2)
        self.report.setHorizontalHeaderLabels(["Statut", "Message"])
        self.report.horizontalHeader().setStretchLastSection(True)
        self.report.verticalHeader().setVisible(False)
        self.report.verticalHeader().setDefaultSectionSize(34)
        self.report.setColumnWidth(0, 150)
        self.report.setEditTriggers(QTableWidget.NoEditTriggers)
        self.report.setAlternatingRowColors(True)

        self.preview = QTableWidget(0, 5)
        self.preview.setHorizontalHeaderLabels(["Id", "Titre", "Type", "Poids %", "Échéance"])
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.verticalHeader().setVisible(False)
        self.preview.verticalHeader().setDefaultSectionSize(34)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setAlternatingRowColors(True)

        report_title = QLabel("Rapport de validation")
        report_title.setProperty("role", "sectionTitle")
        preview_title = QLabel("Aperçu des évaluations détectées")
        preview_title.setProperty("role", "sectionTitle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        layout.addWidget(report_title)
        layout.addWidget(self.report, 1)
        layout.addWidget(preview_title)
        layout.addWidget(self.preview, 2)

    # ------------------------------------------------------------ aides

    @staticmethod
    def _report_item(kind: str) -> QTableWidgetItem:
        """Cellule de statut du rapport : icône + mot (jamais couleur seule)."""
        color, icon_name, word = {
            "ok": (theme.STATUS_OK, "check-circle", "OK"),
            "warn": (theme.STATUS_WARN, "alert-triangle", "Avertissement"),
            "error": (theme.STATUS_CRITICAL, "x-circle", "Erreur"),
        }[kind]
        item = QTableWidgetItem(word)
        item.setIcon(svg_icon(icon_name, color, size=14))
        return item

    # ------------------------------------------------------------ chargement

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".ics":
                self.import_ics(path)
            else:
                self.load_file(path)
            break

    def _browse(self):
        name, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier JSON de cours", "", "JSON (*.json)"
        )
        if name:
            self.load_file(Path(name))

    def _browse_ics(self):
        name, _ = QFileDialog.getOpenFileName(
            self, "Choisir l'horaire .ics du centre étudiant", "", "Calendrier (*.ics)"
        )
        if name:
            self.import_ics(Path(name))

    def import_ics(self, path: Path) -> None:
        """Importe directement un horaire .ics et affiche le rapport dans la zone de statut."""
        try:
            report = import_ics_file(self.conn, path, today=date.today())
        except ImportBlockedError as exc:
            self.status.set_status("Import .ics refusé : " + " ; ".join(exc.errors),
                                   "critical")
            return
        created = sum(r.created for r in report.courses.values())
        updated = sum(r.updated for r in report.courses.values())
        summary = (f"{path.name} : {created} séance(s) créée(s) · "
                   f"{updated} mise(s) à jour · {len(report.exams)} examen(s) détecté(s) · "
                   f"{len(report.ignored)} événement(s) ignoré(s).")
        self.status.set_status(summary + "\n" + format_ics_report(report), "ok")
        self.imported.emit("ics")

    def _copy_prompt(self):
        QApplication.clipboard().setText(PROMPT_PATH.read_text(encoding="utf-8"))
        self.status.set_status("Prompt d'extraction copié dans le presse-papiers : "
                               "le coller dans le chat Claude avec le PDF du plan de cours.",
                               "info")

    def load_file(self, path: Path) -> None:
        """Charge et valide un fichier sans l'importer ; remplit rapport et aperçu."""
        self._data = None
        self.import_button.setEnabled(False)
        self.report.setRowCount(0)
        self.preview.setRowCount(0)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.status.set_status(f"{path.name} : fichier illisible — {exc}", "critical")
            return
        errors, warnings = validate_document(data)
        rows = [("error", e) for e in errors] + [("warn", w) for w in warnings]
        if not rows:
            rows = [("ok", "Toutes les règles de validation passent.")]
        self.report.setRowCount(len(rows))
        for i, (kind, message) in enumerate(rows):
            self.report.setItem(i, 0, self._report_item(kind))
            self.report.setItem(i, 1, QTableWidgetItem(message))
        if errors:
            self.status.set_status(
                f"{path.name} : import refusé ({len(errors)} erreur(s)).", "critical"
            )
            return
        self._data = data
        course = data["course"]
        evaluations = data["evaluations"]
        self.preview.setRowCount(len(evaluations))
        for i, ev in enumerate(evaluations):
            for j, value in enumerate((
                ev["id"], ev["title"], ev["type"], theme.fmt_number(ev["weight"], 2),
                ev["due_date"] or "à saisir",
            )):
                item = QTableWidgetItem(str(value))
                if j == 4 and not ev["due_date"]:
                    item.setIcon(svg_icon("alert-triangle", theme.STATUS_WARN, size=14))
                if ev.get("source_excerpt"):
                    item.setToolTip(f"« {ev['source_excerpt']} »")
                self.preview.setItem(i, j, item)
        self.status.set_status(
            f"{path.name} : {course['code']} — {course['title']} ({course['term']}), "
            f"{len(evaluations)} évaluation(s). Prêt à importer.", "info"
        )
        self.import_button.setEnabled(True)

    def _do_import(self):
        if self._data is None:
            return
        try:
            report = import_course_data(self.conn, self._data, today=date.today())
        except ImportBlockedError as exc:
            self.status.set_status("Import refusé : " + " ; ".join(exc.errors), "critical")
            return
        summary = (f"{report.course_code} importé : {report.created} nouvelle(s) · "
                   f"{report.updated} modifiée(s) · {report.unchanged} inchangée(s) · "
                   f"{report.archived} archivée(s).")
        if report.warnings:
            summary += f"  ({len(report.warnings)} avertissement(s) — voir le rapport)"
            self.report.setRowCount(len(report.warnings))
            for i, warning in enumerate(report.warnings):
                self.report.setItem(i, 0, self._report_item("warn"))
                self.report.setItem(i, 1, QTableWidgetItem(warning))
        self.status.set_status(summary, "ok")
        self.import_button.setEnabled(False)
        self.imported.emit(report.course_code)
