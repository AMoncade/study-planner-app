"""Vue Paramètres (ARCHITECTURE §5.6) : tous les coefficients de §4.9, persistés en base."""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import QTime, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from planner.config import EngineSettings, load_engine_settings, save_engine_settings
from planner.core.models import EVALUATION_TYPES
from planner.ui.widgets.badge import Badge


def _spin(minimum: float, maximum: float, step: float = 0.05) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setSingleStep(step)
    box.setDecimals(2)
    return box


class SettingsView(QWidget):
    changed = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        # ---- journées
        self.wake_start = QTimeEdit()
        self.wake_end = QTimeEdit()
        for w in (self.wake_start, self.wake_end):
            w.setDisplayFormat("HH:mm")
        self.h_week = _spin(1, 12, 0.5)
        self.h_weekend = _spin(1, 12, 0.5)
        self.h_eval = _spin(1, 8, 0.5)
        self.bloc_min = _spin(0.5, 4, 0.5)
        self.bloc_max = _spin(0.5, 4, 0.5)
        day_box = QGroupBox("Journées et blocs")
        day_form = QFormLayout(day_box)
        day_form.addRow("Début d'éveil :", self.wake_start)
        day_form.addRow("Fin d'éveil :", self.wake_end)
        day_form.addRow("Plafond semaine (h/jour) :", self.h_week)
        day_form.addRow("Plafond week-end (h/jour) :", self.h_weekend)
        day_form.addRow("Plafond par évaluation (h/jour) :", self.h_eval)
        day_form.addRow("Durée min. d'un bloc (h) :", self.bloc_min)
        day_form.addRow("Durée max. d'un bloc (h) :", self.bloc_max)

        # ---- coefficients de l'algorithme
        self.alpha = _spin(0.1, 1.0)
        self.beta = _spin(0.0, 0.5)
        self.lam = _spin(0.0, 1.0)
        self.upsilon = _spin(0.1, 1.0)
        self.tau_ratio = _spin(1.0, 10.0, 0.5)
        algo_box = QGroupBox("Coefficients de l'algorithme (§4.9)")
        algo_form = QFormLayout(algo_box)
        algo_form.addRow("α — sensibilité au poids :", self.alpha)
        algo_form.addRow("β — pente de difficulté :", self.beta)
        algo_form.addRow("λ — plancher d'étalement :", self.lam)
        algo_form.addRow("υ — taux d'utilisation du temps libre :", self.upsilon)
        algo_form.addRow("τ ratio — décroissance (D/τ) :", self.tau_ratio)

        # ---- fonction de coût
        self.costs = {name: _spin(0.0, 5.0, 0.1) for name in
                      ("c1_horaire", "c2_fragmentation", "c3_diversite",
                       "c4_enchainement", "c5_stabilite")}
        cost_box = QGroupBox("Fonction de coût du placement")
        cost_form = QFormLayout(cost_box)
        for name, widget in self.costs.items():
            cost_form.addRow(f"{name} :", widget)

        # ---- table des charges de base et fenêtres par type
        self.type_table = QTableWidget(len(EVALUATION_TYPES), 2)
        self.type_table.setHorizontalHeaderLabels(["Charge de base (h)", "Fenêtre (jours)"])
        self.type_table.setVerticalHeaderLabels(list(EVALUATION_TYPES))
        self.type_table.horizontalHeader().setStretchLastSection(True)
        self.type_table.verticalHeader().setDefaultSectionSize(34)
        self.type_table.setAlternatingRowColors(True)
        self.type_table.setMinimumHeight(34 * (len(EVALUATION_TYPES) + 1) + 12)
        type_box = QGroupBox("Charges de base B(type) et fenêtres D(type)")
        type_layout = QVBoxLayout(type_box)
        type_layout.addWidget(self.type_table)

        title = QLabel("Paramètres")
        title.setProperty("role", "viewTitle")

        save = QPushButton("Enregistrer")
        save.setProperty("kind", "primary")
        save.clicked.connect(self._save)
        reset = QPushButton("Réinitialiser aux valeurs par défaut")
        reset.clicked.connect(self._reset)
        self.feedback = Badge(kind="neutral")
        self.feedback.hide()
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(save)
        buttons.addWidget(reset)
        buttons.addWidget(self.feedback)
        buttons.addStretch(1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(day_box)
        layout.addWidget(algo_box)
        layout.addWidget(cost_box)
        layout.addWidget(type_box)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 10, 24, 14)
        footer_layout.addLayout(buttons)
        outer.addWidget(footer)

        self._load(load_engine_settings(conn))

    # ------------------------------------------------------------ chargement

    def _load(self, s: EngineSettings) -> None:
        self.wake_start.setTime(QTime(s.wake_start.hour, s.wake_start.minute))
        self.wake_end.setTime(QTime(s.wake_end.hour, s.wake_end.minute))
        self.h_week.setValue(s.h_jour_max_week)
        self.h_weekend.setValue(s.h_jour_max_weekend)
        self.h_eval.setValue(s.h_jour_eval)
        self.bloc_min.setValue(s.bloc_min)
        self.bloc_max.setValue(s.bloc_max)
        self.alpha.setValue(s.alpha)
        self.beta.setValue(s.beta)
        self.lam.setValue(s.lam)
        self.upsilon.setValue(s.upsilon)
        self.tau_ratio.setValue(s.tau_ratio)
        for name, widget in self.costs.items():
            widget.setValue(getattr(s, name))
        for row, type_name in enumerate(EVALUATION_TYPES):
            self.type_table.setItem(
                row, 0, QTableWidgetItem(f"{s.b_type.get(type_name, 6.0):g}"))
            self.type_table.setItem(
                row, 1, QTableWidgetItem(str(s.d_type.get(type_name, 7))))

    def current_settings(self) -> EngineSettings:
        s = EngineSettings()
        qs, qe = self.wake_start.time(), self.wake_end.time()
        s.wake_start = time(qs.hour(), qs.minute())
        s.wake_end = time(qe.hour(), qe.minute())
        s.h_jour_max_week = self.h_week.value()
        s.h_jour_max_weekend = self.h_weekend.value()
        s.h_jour_eval = self.h_eval.value()
        s.bloc_min = min(self.bloc_min.value(), self.bloc_max.value())
        s.bloc_max = max(self.bloc_min.value(), self.bloc_max.value())
        s.alpha = self.alpha.value()
        s.beta = self.beta.value()
        s.lam = self.lam.value()
        s.upsilon = self.upsilon.value()
        s.tau_ratio = self.tau_ratio.value()
        for name, widget in self.costs.items():
            setattr(s, name, widget.value())
        for row, type_name in enumerate(EVALUATION_TYPES):
            try:
                s.b_type[type_name] = float(self.type_table.item(row, 0).text())
                s.d_type[type_name] = int(float(self.type_table.item(row, 1).text()))
            except (TypeError, ValueError, AttributeError):
                pass  # valeur illisible : on garde le défaut
        return s

    # ------------------------------------------------------------ actions

    def _save(self) -> None:
        save_engine_settings(self.conn, self.current_settings())
        self.feedback.set_status(
            "Paramètres enregistrés — recalculer le plan pour les appliquer.", "ok"
        )
        self.feedback.show()
        self.changed.emit()

    def _reset(self) -> None:
        self._load(EngineSettings())
        self.feedback.set_status("Valeurs par défaut restaurées (non enregistrées).",
                                 "neutral")
        self.feedback.show()
