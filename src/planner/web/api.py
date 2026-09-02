"""API web minimale (Phase 9) — consulter la semaine et cocher des blocs depuis mobile.

Postgres est la COPIE DE TRAVAIL (voir sync.py) ; SQLite reste la source de vérité.
DÉCISION IMPOSÉE : POST /api/recalculate est un APERÇU PUR — il n'appelle jamais
apply_rebalance et n'écrit rien : un recalcul persistant créerait des blocs orphelins
que sync-push détruirait ensuite.

Authentification : code PIN dans APP_PIN, exigé en en-tête X-App-Pin sur toutes les
routes /api sauf /api/health, comparé avec secrets.compare_digest. Sans APP_PIN dans
l'environnement, l'application REFUSE de démarrer.

Lancement local :  uvicorn --factory planner.web.api:create_app
"""

from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from planner.core.models import WEEKDAYS

STATIC_DIR = Path(__file__).parent / "static"

# ------------------------------------------------------------------ dépendances


def _require_pin(x_app_pin: str = Header(default="")) -> None:
    expected = os.environ.get("APP_PIN") or ""
    if not expected or not secrets.compare_digest(x_app_pin, expected):
        raise HTTPException(status_code=401, detail="PIN invalide")


def _get_db():
    """Une connexion Postgres par requête, fermée quoi qu'il arrive.

    migrate=False : pas de migration sur le chemin chaud — utiliser la sous-commande
    CLI `pg-migrate` au déploiement.
    """
    from planner.storage.pg import connect_pg

    conn = connect_pg(migrate=False)
    try:
        yield conn
    finally:
        conn.close()


_DB = Depends(_get_db)  # singleton module : évite l'appel dans un défaut (B008)

# ------------------------------------------------------------------ sérialisation


def _week_bounds(offset: int) -> tuple[date, date]:
    monday = date.today() - timedelta(days=date.today().weekday()) \
        + timedelta(weeks=offset)
    return monday, monday + timedelta(days=7)


_WEEK_SQL = """
    SELECT b.id, b.start_at, b.end_at, b.planned_minutes, b.status, b.locked,
           c.code, e.title
    FROM study_blocks b
    JOIN evaluations e ON e.id = b.evaluation_id
    JOIN courses c ON c.id = e.course_id
    WHERE substr(b.start_at, 1, 10) >= ? AND substr(b.start_at, 1, 10) < ?
    ORDER BY b.start_at
"""


def _block_dict(row) -> dict:
    block_id, start_at, end_at, minutes, status, locked, code, title = row
    return {
        "id": block_id,
        "start": start_at,
        "end": end_at,
        "planned_minutes": minutes,
        "status": status,
        "locked": bool(locked),
        "course": code,
        "evaluation": title,
    }


def _group_by_day(blocks: list[dict], monday: date) -> list[dict]:
    days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        prefix = day.isoformat()
        days.append({
            "date": prefix,
            "label": f"{WEEKDAYS[day.weekday()].capitalize()} {day.day:02d}/{day.month:02d}",
            "blocks": [b for b in blocks if b["start"][:10] == prefix],
        })
    return days


class StatusUpdate(BaseModel):
    status: Literal["planned", "done", "partial", "skipped"]
    actual_minutes: int | None = None


# ------------------------------------------------------------------ application


def create_app() -> FastAPI:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    load_dotenv()
    if not os.environ.get("APP_PIN"):
        raise RuntimeError(
            "APP_PIN manquant dans l'environnement : refus de servir le planning sans "
            "protection. Définir APP_PIN (code PIN de l'interface mobile) puis relancer."
        )

    app = FastAPI(title="Plan-Études — API mobile", docs_url=None, redoc_url=None)
    protected = [Depends(_require_pin)]

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/week", dependencies=protected)
    def week(offset: int = 0, conn=_DB) -> dict:
        monday, sunday_excl = _week_bounds(offset)
        rows = conn.execute(
            _WEEK_SQL, (monday.isoformat(), sunday_excl.isoformat())
        ).fetchall()
        blocks = [_block_dict(r) for r in rows]
        return {"monday": monday.isoformat(), "offset": offset,
                "days": _group_by_day(blocks, monday)}

    @app.post("/api/blocks/{block_id}/status", dependencies=protected)
    def set_status(block_id: int, body: StatusUpdate, conn=_DB) -> dict:
        from planner.storage import repositories as repos

        exists = conn.execute(
            "SELECT id FROM study_blocks WHERE id = ?", (block_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Bloc introuvable")
        repos.update_study_block_status(
            conn, block_id, body.status, actual_minutes=body.actual_minutes
        )
        row = conn.execute(
            """SELECT b.id, b.start_at, b.end_at, b.planned_minutes, b.status,
                      b.locked, c.code, e.title
               FROM study_blocks b
               JOIN evaluations e ON e.id = b.evaluation_id
               JOIN courses c ON c.id = e.course_id
               WHERE b.id = ?""",
            (block_id,),
        ).fetchone()
        return _block_dict(row)

    @app.post("/api/recalculate", dependencies=protected)
    def recalculate(offset: int = 0, conn=_DB) -> dict:
        """APERÇU SEULEMENT : calcule le différentiel et la semaine « telle qu'elle
        serait », sans JAMAIS appeler apply_rebalance ni écrire quoi que ce soit.
        La persistance d'un recalcul appartient au bureau (source de vérité)."""
        from planner.config import load_engine_settings
        from planner.scheduler.rebalance import rebalance
        from planner.storage import repositories as repos

        courses = repos.list_courses(conn)
        evaluations = [
            e for c in courses for e in repos.list_evaluations(conn, course_id=c.id)
        ]
        if not evaluations:
            raise HTTPException(
                status_code=409,
                detail="Aucune évaluation : faire un sync-push d'abord",
            )
        blocks = repos.list_study_blocks(conn)
        result, diff = rebalance(
            courses, evaluations, repos.list_constraints(conn), blocks,
            load_engine_settings(conn), datetime.now(),
        )

        labels = {}
        for course in courses:
            for ev in evaluations:
                if ev.course_id == course.id:
                    labels[ev.id] = (course.code, ev.title)
        monday, sunday_excl = _week_bounds(offset)

        def in_week(start_at: datetime) -> bool:
            return monday <= start_at.date() < sunday_excl

        freed = set(diff.freed_ids)
        preview = [
            {
                "id": b.id, "start": b.start_at.isoformat(), "end": b.end_at.isoformat(),
                "planned_minutes": b.planned_minutes, "status": b.status,
                "locked": bool(b.locked),
                "course": labels.get(b.evaluation_id, ("?", "?"))[0],
                "evaluation": labels.get(b.evaluation_id, ("?", "?"))[1],
            }
            for b in list(diff.new_blocks) + [
                x for x in blocks if x.id not in freed and x.status != "planned"
            ]
            if in_week(b.start_at)
        ]
        preview.sort(key=lambda b: b["start"])
        return {
            "persisted": False,
            "diff": {"kept": diff.kept, "moved": diff.moved,
                     "added": diff.added, "removed": diff.removed},
            "rho": result.rho,
            "monday": monday.isoformat(),
            "preview_blocks": preview,
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/manifest.json")
    def manifest() -> FileResponse:
        return FileResponse(STATIC_DIR / "manifest.json")

    return app
