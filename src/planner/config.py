"""Paramètres du moteur (ARCHITECTURE §4.9).

⚠ Valeurs de départ, pas des vérités : tout est calibrable, exposé dans la vue
Paramètres et persisté en base. La calibration se fait contre un vrai trimestre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

# Charge de base en heures pour une évaluation « standard » (20 %, difficulté 3, 5 unités).
DEFAULT_B_TYPE: dict[str, float] = {
    "examen_final": 14.0,
    "examen_intra": 10.0,
    "quiz": 3.0,
    "travail": 12.0,
    "projet": 20.0,
    "presentation": 7.0,
    "laboratoire": 4.0,
    "lecture": 2.0,
    "participation": 1.0,
    "autre": 6.0,
}

# Profondeur de la fenêtre de révision, en jours, par type (étape B).
DEFAULT_D_TYPE: dict[str, int] = {
    "examen_final": 14,
    "examen_intra": 14,
    "quiz": 5,
    "travail": 21,
    "projet": 21,
    "presentation": 10,
    "laboratoire": 7,
    "lecture": 7,
    "participation": 7,
    "autre": 7,
}

# Pénalité circadienne par heure de début de bloc (étape E, P_horaire) ;
# absente de la table = 0 (bonne plage).
DEFAULT_HOUR_PENALTY: dict[int, float] = {
    8: 0.5, 9: 0.25,
    18: 0.25, 19: 0.5, 20: 1.0, 21: 1.5,
}

# Catégories de contraintes « hors domicile » : tampon transport de part et d'autre.
BUFFERED_CATEGORIES = ("travail", "entrainement", "cours")


@dataclass
class EngineSettings:
    """Tous les paramètres du moteur, avec les valeurs par défaut de §4.9."""

    # Étape A — charge
    b_type: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_B_TYPE))
    alpha: float = 0.60          # exposant de pondération f_w
    beta: float = 0.15           # pente de difficulté f_d
    u_ref: int = 5               # unités de matière de référence f_u
    w_ref: float = 20.0          # pondération de référence (%)
    cumulative_factor: float = 1.25
    group_factor: float = 0.75
    h_min: float = 1.0
    h_max: float = 24.0

    # Étape B — fenêtre
    d_type: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_D_TYPE))
    exam_margin_minutes: int = 30        # dernier bloc >= 30 min avant un examen
    submission_margin_minutes: int = 120  # aucun bloc après T-2h pour une remise

    # Étape C — courbe
    lam: float = 0.35            # plancher d'étalement λ
    tau_ratio: float = 3.0       # τ = D / tau_ratio
    h_jour_eval: float = 3.0     # plafond par évaluation et par jour

    # Étape D — disponibilité
    slot_minutes: int = 30
    wake_start: time = time(8, 0)
    wake_end: time = time(22, 0)
    transport_buffer_minutes: int = 30
    h_jour_max_week: float = 4.0
    h_jour_max_weekend: float = 6.0
    upsilon: float = 0.80        # taux d'utilisation cible du temps libre

    # Étape E — placement
    bloc_min: float = 1.0        # heures
    bloc_max: float = 2.0
    pause_minutes: int = 15      # pause minimale entre deux blocs
    hour_penalty: dict[int, float] = field(default_factory=lambda: dict(DEFAULT_HOUR_PENALTY))
    c1_horaire: float = 1.0
    c2_fragmentation: float = 1.5
    c3_diversite: float = 0.8
    c4_enchainement: float = 2.0
    c5_stabilite: float = 1.2
    max_subjects_per_day: int = 3  # la 4e matière du jour est pénalisée

    def h_jour_max(self, day_weekday: int) -> float:
        return self.h_jour_max_weekend if day_weekday >= 5 else self.h_jour_max_week
