"""Règles métier appliquées à l'import (ARCHITECTURE §2.4).

Deux niveaux : les erreurs bloquent l'import, les avertissements l'accompagnent.
La validation structurelle (types, enums, formats) est faite en amont par jsonschema ;
ici on vérifie ce que le schéma ne peut pas exprimer.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator

SUPPORTED_SCHEMA_VERSIONS = ("1.0",)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "schema" / "cours.schema.json"

WEIGHT_SUM_TOLERANCE = 0.5


@cache
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_document(data: object) -> tuple[list[str], list[str]]:
    """Retourne (erreurs bloquantes, avertissements) pour un document JSON déjà décodé."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1-2. Version reconnue + JSON Schema valide.
    if not isinstance(data, dict):
        return ["Le document n'est pas un objet JSON."], []
    version = data.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"schema_version non reconnue : {version!r}.")
    for err in _schema_validator().iter_errors(data):
        path = "/".join(str(p) for p in err.path) or "racine"
        errors.append(f"Schéma : {path} → {err.message}")
    if errors:
        return errors, warnings

    course = data["course"]
    evaluations = data["evaluations"]

    # 3. Champs essentiels (le schéma garantit déjà code non vide et >= 1 évaluation).

    # 4. Unicité des id.
    ids = [e["id"] for e in evaluations]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        errors.append(f"Identifiants d'évaluation non uniques : {sorted(duplicates)}.")

    # 5. Dates réellement parsables (le motif du schéma laisse passer 2026-02-30)
    #    et start_date <= due_date.
    def check_date(value: str | None, label: str) -> date | None:
        if value is None:
            return None
        parsed = _parse_date(value)
        if parsed is None:
            errors.append(f"Date invalide pour {label} : {value!r}.")
        return parsed

    for session in course.get("sessions", []):
        check_date(session.get("start_date"), f"session {session['weekday']}/start_date")
        check_date(session.get("end_date"), f"session {session['weekday']}/end_date")
        for ex in session.get("except_dates", []):
            check_date(ex, f"session {session['weekday']}/except_dates")

    for ev in evaluations:
        due = check_date(ev.get("due_date"), f"{ev['id']}/due_date")
        start = check_date(ev.get("start_date"), f"{ev['id']}/start_date")
        if due and start and start > due:
            errors.append(f"{ev['id']} : start_date ({start}) postérieure à due_date ({due}).")

    if errors:
        return errors, warnings

    # 6. Somme des pondérations.
    weight_sum = sum(e["weight"] for e in evaluations)
    if abs(weight_sum - 100.0) > WEIGHT_SUM_TOLERANCE:
        warnings.append(
            f"Pondérations incomplètes ou excédentaires : somme = {weight_sum:g} (attendu 100)."
        )

    # 7. Échéances manquantes.
    for ev in evaluations:
        if ev["due_date"] is None:
            warnings.append(
                f"{ev['id']} : due_date manquante, à compléter avant la planification."
            )

    # 8. Confiance non maximale.
    for ev in evaluations:
        if ev["confidence"] != "high":
            warnings.append(
                f"{ev['id']} : confiance {ev['confidence']}, à vérifier contre source_excerpt."
            )

    # 10. Échéance hors des bornes du trimestre déduites des sessions.
    bounds_start = [
        _parse_date(s["start_date"]) for s in course.get("sessions", []) if s.get("start_date")
    ]
    bounds_end = [
        _parse_date(s["end_date"]) for s in course.get("sessions", []) if s.get("end_date")
    ]
    if bounds_start and bounds_end:
        lo, hi = min(bounds_start), max(bounds_end)
        for ev in evaluations:
            due = _parse_date(ev["due_date"]) if ev["due_date"] else None
            if due and not (lo <= due <= hi):
                warnings.append(
                    f"{ev['id']} : échéance {due} hors des bornes du trimestre ({lo} → {hi})."
                )

    return errors, warnings


def cross_course_conflicts(conn) -> list[str]:
    """Règle 9 : deux évaluations de cours différents à la même date (info tableau de bord)."""
    rows = conn.execute(
        """
        SELECT date(a.due_at), ca.code, a.external_id, cb.code, b.external_id
        FROM evaluations a
        JOIN evaluations b ON date(a.due_at) = date(b.due_at) AND a.id < b.id
        JOIN courses ca ON ca.id = a.course_id
        JOIN courses cb ON cb.id = b.course_id
        WHERE a.course_id != b.course_id
          AND a.archived = 0 AND b.archived = 0
          AND a.type IN ('examen_final', 'examen_intra')
          AND b.type IN ('examen_final', 'examen_intra')
        """
    ).fetchall()
    return [
        f"Conflit le {day} : {code_a} {eid_a} et {code_b} {eid_b}."
        for day, code_a, eid_a, code_b, eid_b in rows
    ]
