"""Commande `doctor` : diagnostic d'environnement, ligne par ligne, sans jamais
afficher une valeur sensible (seulement présente/absente pour les clés d'environnement).

Code de sortie non nul si quelque chose de BLOQUANT manque.
"""

from __future__ import annotations

import importlib.metadata
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

OK, WARN, BLOCK = "OK      ", "ATTENTION", "BLOQUANT"

# nom pip -> nom à interroger dans importlib.metadata
REQUIRED_PACKAGES = (
    "PySide6", "jsonschema", "python-dateutil", "icalendar",
    "psycopg", "python-dotenv", "fastapi", "uvicorn",
)

ENV_KEYS = ("DATABASE_URL", "DATABASE_URL_TEST", "APP_PIN")


def _line(level: str, message: str) -> None:
    print(f"[{level.strip():<9}] {message}")


def run_doctor(db_path: str | Path) -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv()
    blocking = 0

    # ---- Python
    version = sys.version_info
    if (3, 12) <= version[:2] < (3, 14):
        _line(OK, f"Python {version.major}.{version.minor}.{version.micro}")
    else:
        blocking += 1
        _line(BLOCK, f"Python {version.major}.{version.minor} — utiliser 3.12 "
                     "(py -3.12 -m venv .venv ; les roues PySide6 3.14 sont incertaines)")

    # ---- dépendances
    for package in REQUIRED_PACKAGES:
        try:
            found = importlib.metadata.version(package)
            _line(OK, f"paquet {package} {found}")
        except importlib.metadata.PackageNotFoundError:
            blocking += 1
            _line(BLOCK, f"paquet {package} absent — pip install -r requirements.txt")

    # ---- clés d'environnement (jamais les valeurs)
    for key in ENV_KEYS:
        if os.environ.get(key):
            _line(OK, f"variable {key} présente")
        elif key == "DATABASE_URL":
            blocking += 1
            _line(BLOCK, "variable DATABASE_URL absente — recréer .env "
                         "(voir docs/ETAT.md, « Reprise sur une machine neuve »)")
        elif key == "APP_PIN":
            _line(WARN, "variable APP_PIN absente — l'API web refusera de démarrer")
        else:
            _line(WARN, "variable DATABASE_URL_TEST absente — les tests Postgres "
                        "(destructifs) seront sautés")

    # ---- même base pour le réel et le test ?
    url, test_url = os.environ.get("DATABASE_URL"), os.environ.get("DATABASE_URL_TEST")
    if url and test_url:
        a, b = urlsplit(url), urlsplit(test_url)
        if (a.username, a.hostname) == (b.username, b.hostname):
            _line(WARN, "DATABASE_URL_TEST désigne la MÊME base que DATABASE_URL — "
                        "les tests sont destructifs : pointer vers une base jetable")
        else:
            _line(OK, "base de test distincte de la base réelle")

    # ---- SQLite
    sqlite_counts = None
    db_path = Path(db_path)
    if not db_path.exists():
        _line(WARN, f"base SQLite absente ({db_path}) — importer un JSON, ou "
                    "`sync-restore` pour récupérer les données depuis Supabase")
    else:
        from planner.storage.db import connect

        conn = connect(db_path)
        sqlite_counts = {
            t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("courses", "evaluations", "study_blocks")
        }
        conn.close()
        _line(OK, f"base SQLite {db_path} — {sqlite_counts['courses']} cours, "
                  f"{sqlite_counts['evaluations']} évaluations, "
                  f"{sqlite_counts['study_blocks']} blocs")

    # ---- Postgres
    if url:
        try:
            from planner.storage.pg import SCHEMA_VERSION_PG, connect_pg

            pg_conn = connect_pg(migrate=False)
            pg_version = pg_conn.execute(
                "SELECT version FROM schema_version WHERE id = 1"
            ).fetchone()
            pg_counts = {
                t: pg_conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in ("courses", "evaluations", "study_blocks")
            }
            shown = pg_version[0] if pg_version else "?"
            _line(OK, f"Postgres joignable — schéma {shown}/{SCHEMA_VERSION_PG}, "
                      f"{pg_counts['courses']} cours, {pg_counts['evaluations']} "
                      f"évaluations, {pg_counts['study_blocks']} blocs")
            if pg_version and pg_version[0] < SCHEMA_VERSION_PG:
                _line(WARN, "schéma Postgres en retard — lancer `pg-migrate`")

            # ---- divergences de statuts
            if sqlite_counts is not None:
                from planner.storage.db import connect
                from planner.sync import unpulled_changes

                sqlite_conn = connect(db_path)
                diverging = unpulled_changes(sqlite_conn, pg_conn)
                sqlite_conn.close()
                if diverging:
                    _line(WARN, f"{len(diverging)} bloc(s) aux statuts divergents "
                                "entre SQLite et Postgres — `sync-pull` si cochés sur "
                                "mobile, `sync-push --force` si l'écart vient du bureau")
                else:
                    _line(OK, "aucun statut de bloc divergent entre les deux bases")
            pg_conn.close()
        except Exception as exc:  # réseau, identifiants, pooler…
            blocking += 1
            _line(BLOCK, f"connexion Postgres échouée ({type(exc).__name__}) — "
                         "vérifier DATABASE_URL dans .env et l'accès réseau au pooler")

    if blocking:
        _line(BLOCK, f"{blocking} problème(s) bloquant(s).")
    else:
        print("\nEnvironnement sain.")
    return 1 if blocking else 0
