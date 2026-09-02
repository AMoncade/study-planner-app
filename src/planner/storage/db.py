"""Connexion SQLite et migrations (ARCHITECTURE §3.2).

Migrations en avant seulement, numérotées par PRAGMA user_version.
Le schéma de référence est maintenu en parallèle dans docs/schema/db.sql.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# Chaque entrée = une migration ; user_version = nombre de migrations appliquées.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE courses (
        id INTEGER PRIMARY KEY,
        code TEXT NOT NULL,
        title TEXT NOT NULL,
        term TEXT NOT NULL,
        institution TEXT,
        credits INTEGER,
        instructor TEXT,
        language TEXT NOT NULL DEFAULT 'fr',
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
        effort_multiplier REAL NOT NULL DEFAULT 1.0,
        archived INTEGER NOT NULL DEFAULT 0,
        UNIQUE (code, term)
    );

    CREATE TABLE sessions (
        id INTEGER PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        room TEXT,
        start_date TEXT,
        end_date TEXT,
        except_dates TEXT NOT NULL DEFAULT '[]'
    );

    CREATE TABLE evaluations (
        id INTEGER PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        external_id TEXT NOT NULL,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        weight REAL NOT NULL,
        due_at TEXT,
        start_date TEXT,
        duration_minutes INTEGER,
        modality TEXT,
        location TEXT,
        cumulative INTEGER,
        group_work INTEGER,
        content_scope TEXT NOT NULL DEFAULT '[]',
        scope_units INTEGER,
        deliverable TEXT,
        estimated_pages INTEGER,
        resources TEXT NOT NULL DEFAULT '[]',
        notes TEXT,
        confidence TEXT NOT NULL DEFAULT 'high',
        source_excerpt TEXT,
        manual_hours_override REAL,
        status TEXT NOT NULL DEFAULT 'active',
        archived INTEGER NOT NULL DEFAULT 0,
        UNIQUE (course_id, external_id)
    );

    CREATE TABLE constraints (
        id INTEGER PRIMARY KEY,
        label TEXT NOT NULL,
        category TEXT NOT NULL,
        weekday INTEGER CHECK (weekday BETWEEN 0 AND 6),
        specific_date TEXT,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        rrule TEXT,
        priority INTEGER NOT NULL DEFAULT 0,
        color TEXT,
        CHECK ((weekday IS NULL) != (specific_date IS NULL))
    );

    CREATE TABLE generations (
        id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL,
        params_hash TEXT NOT NULL,
        coverage REAL,
        deficit_total REAL
    );

    CREATE TABLE study_blocks (
        id INTEGER PRIMARY KEY,
        evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        planned_minutes INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'planned',
        locked INTEGER NOT NULL DEFAULT 0,
        generation_id INTEGER REFERENCES generations(id),
        actual_minutes INTEGER,
        efficiency REAL,
        note TEXT
    );

    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE INDEX idx_evaluations_course ON evaluations(course_id);
    CREATE INDEX idx_blocks_evaluation ON study_blocks(evaluation_id);
    CREATE INDEX idx_blocks_start ON study_blocks(start_at);
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)

DEFAULT_DB_PATH = Path("data") / "plan_etudes.db"


def connect(path: str | Path) -> sqlite3.Connection:
    """Ouvre (et migre si besoin) la base. `:memory:` est accepté pour les tests."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
        with conn:
            conn.executescript(script)
            conn.execute(f"PRAGMA user_version = {number}")


def backup_database(path: str | Path) -> Path | None:
    """Copie horodatée du fichier .db dans <dossier>/backups/. None si la base n'existe pas."""
    src = Path(path)
    if not src.exists():
        return None
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"{src.stem}-{stamp}{src.suffix}"
    shutil.copy2(src, dest)
    return dest
