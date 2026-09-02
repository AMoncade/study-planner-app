"""Synchronisation SQLite <-> Postgres (Phase 8c).

Le bureau (SQLite) est la SOURCE DE VÉRITÉ ; Postgres est une copie de travail pour la
future interface web où seuls les statuts de blocs seront cochés (Fait / Manqué).

- push : réplique intégrale SQLite -> Postgres, transaction unique tout-ou-rien,
  id d'origine CONSERVÉS (indispensable pour que pull puisse apparier les blocs),
  puis recalage des séquences IDENTITY — après des insertions à id explicite, elles
  restent à 1 et la première écriture web lèverait une violation d'unicité.
- pull : rapatrie UNIQUEMENT status / actual_minutes / efficiency / note des
  study_blocks présents des deux côtés avec le même id. Ne crée rien, ne supprime
  rien, ne touche à aucune autre table.

La recopie lit les colonnes brutes (PRAGMA table_info) et les réécrit telles quelles :
aucune dépendance au mapping des modèles de repositories.py.
"""

from __future__ import annotations

# Ordre d'insertion respectant les clés étrangères ; TRUNCATE ... CASCADE côté Postgres.
TABLES_IN_DEPENDENCY_ORDER = (
    "courses", "sessions", "evaluations", "generations",
    "study_blocks", "constraints", "settings",
)

# Tables dont la colonne id est une IDENTITY à recaler après insertion explicite.
TABLES_WITH_ID = (
    "courses", "sessions", "evaluations", "generations", "study_blocks", "constraints",
)

PULL_COLUMNS = ("status", "actual_minutes", "efficiency", "note")


def _columns(sqlite_conn, table: str) -> list[str]:
    rows = sqlite_conn.execute(
        "SELECT name FROM pragma_table_info(?) ORDER BY cid", (table,)
    ).fetchall()
    return [r[0] for r in rows]


def unpulled_changes(sqlite_conn, pg_conn) -> list[int]:
    """Id des blocs dont les champs de statut diffèrent entre Postgres et SQLite.

    Comparaison par id ; les blocs absents d'un côté sont ignorés (ils relèvent de la
    réplique normale, pas d'un statut coché en attente).
    """
    columns = ", ".join(("id",) + PULL_COLUMNS)
    pg_rows = {
        r[0]: tuple(r[1:])
        for r in pg_conn.execute(f"SELECT {columns} FROM study_blocks").fetchall()
    }
    sqlite_rows = {
        r[0]: tuple(r[1:])
        for r in sqlite_conn.execute(f"SELECT {columns} FROM study_blocks").fetchall()
    }
    return sorted(
        block_id for block_id in pg_rows.keys() & sqlite_rows.keys()
        if pg_rows[block_id] != sqlite_rows[block_id]
    )


def push(sqlite_conn, pg_conn, force: bool = False) -> dict[str, int]:
    """Réplique SQLite -> Postgres. Retourne le nombre de lignes copiées par table.

    Refuse (UnpulledChangesError, AVANT tout TRUNCATE) d'écraser des statuts cochés
    côté web et pas encore rapatriés par pull — sauf force=True.
    """
    if not force:
        pending = unpulled_changes(sqlite_conn, pg_conn)
        if pending:
            from planner.core.errors import UnpulledChangesError

            raise UnpulledChangesError(pending)
    counters: dict[str, int] = {}
    with pg_conn:  # transaction unique : tout ou rien
        pg_conn.execute(
            f"TRUNCATE {', '.join(TABLES_IN_DEPENDENCY_ORDER)} RESTART IDENTITY CASCADE"
        )
        for table in TABLES_IN_DEPENDENCY_ORDER:
            columns = _columns(sqlite_conn, table)
            placeholders = ", ".join("?" for _ in columns)
            insert = (
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            )
            rows = sqlite_conn.execute(
                f"SELECT {', '.join(columns)} FROM {table}"
            ).fetchall()
            for row in rows:
                pg_conn.execute(insert, tuple(row))
            counters[table] = len(rows)
        # Recalage des séquences IDENTITY : nextval = max(id) + 1 (1 si table vide).
        for table in TABLES_WITH_ID:
            pg_conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"
                f" COALESCE((SELECT max(id) FROM {table}), 0) + 1, false)"
            )
    return counters


def pull(pg_conn, sqlite_conn) -> dict[str, int]:
    """Rapatrie les statuts de blocs Postgres -> SQLite. Retourne les compteurs."""
    rows = pg_conn.execute(
        f"SELECT id, {', '.join(PULL_COLUMNS)} FROM study_blocks"
    ).fetchall()
    counters = {"blocs_web": len(rows), "mis_a_jour": 0, "orphelins": 0}
    with sqlite_conn:  # transaction unique côté SQLite
        for block_id, status, actual_minutes, efficiency, note in rows:
            cursor = sqlite_conn.execute(
                "UPDATE study_blocks SET status = ?, actual_minutes = ?,"
                " efficiency = ?, note = ? WHERE id = ?",
                (status, actual_minutes, efficiency, note, block_id),
            )
            if cursor.rowcount == 0:
                counters["orphelins"] += 1  # bloc inconnu côté SQLite : ignoré
            else:
                counters["mis_a_jour"] += 1
    return counters
