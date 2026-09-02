"""CLI de Plan-Études : import et consultation sans interface graphique (Phase 1).

Usage :
    python -m planner import tests/fixtures/mat1400_a26.json
    python -m planner list
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from planner.core.errors import ImportBlockedError
from planner.core.importer import import_course_file
from planner.core.validation import cross_course_conflicts
from planner.storage import repositories as repos
from planner.storage.db import DEFAULT_DB_PATH, backup_database, connect


def cmd_import(args: argparse.Namespace) -> int:
    backup_database(args.db)  # copie de sûreté avant tout import (§3.2)
    conn = connect(args.db)
    try:
        report = import_course_file(conn, args.file, today=date.today())
    except ImportBlockedError as exc:
        print("IMPORT REFUSÉ :", file=sys.stderr)
        for error in exc.errors:
            print(f"  ❌ {error}", file=sys.stderr)
        return 1
    finally_conflicts = cross_course_conflicts(conn)
    print(f"Cours {report.course_code} importé : "
          f"{report.created} nouvelle(s) · {report.updated} modifiée(s) · "
          f"{report.unchanged} inchangée(s) · {report.archived} archivée(s)")
    for warning in report.warnings:
        print(f"  ⚠ {warning}")
    for conflict in finally_conflicts:
        print(f"  ⚠ {conflict}")
    conn.close()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not Path(args.db).exists():
        print("Aucune base de données. Importer d'abord un fichier JSON.", file=sys.stderr)
        return 1
    conn = connect(args.db)
    courses = repos.list_courses(conn)
    if not courses:
        print("Aucun cours importé.")
        return 0
    for course in courses:
        credits = f", {course.credits} crédits" if course.credits else ""
        print(f"\n{course.code} — {course.title} ({course.term}{credits}) "
              f"[difficulté {course.difficulty}, ×{course.effort_multiplier:g}]")
        for s in course.sessions:
            from planner.core.models import WEEKDAYS
            print(f"    {s.kind:<5} {WEEKDAYS[s.weekday]:<9} "
                  f"{s.start:%H:%M}–{s.end:%H:%M}  {s.room or ''}")
        for ev in repos.list_evaluations(conn, course_id=course.id):
            due = ev.due_at.strftime("%Y-%m-%d %H:%M") if ev.due_at else "date à saisir ⚠"
            flags = []
            if ev.confidence != "high":
                flags.append(f"confiance {ev.confidence}")
            if ev.manual_hours_override is not None:
                flags.append(f"override {ev.manual_hours_override:g} h")
            suffix = f"  ({', '.join(flags)})" if flags else ""
            print(f"  {ev.external_id:<24} {ev.type:<13} {ev.weight:>6.2f} %  {due}{suffix}")
    conn.close()
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from planner.config import EngineSettings
    from planner.core.models import WEEKDAYS
    from planner.scheduler.placer import plan as run_plan

    if not Path(args.db).exists():
        print("Aucune base de données. Importer d'abord un fichier JSON.", file=sys.stderr)
        return 1
    conn = connect(args.db)
    courses = repos.list_courses(conn)
    evaluations = [e for c in courses for e in repos.list_evaluations(conn, course_id=c.id)]
    constraints = repos.list_constraints(conn)
    today = date.fromisoformat(args.date) if args.date else date.today()

    result = run_plan(courses, evaluations, constraints, EngineSettings(), today)

    labels = {e.id: e.external_id for e in evaluations}

    # ---- agenda ASCII sur N semaines
    horizon = today + timedelta(days=7 * args.semaines)
    shown = [b for b in result.blocks if today <= b.start_at.date() < horizon]
    print(f"Plan d'étude du {today} au {horizon - timedelta(days=1)} "
          f"({len(shown)} bloc(s) affichés / {len(result.blocks)} au total)\n")
    current_week = None
    day = today
    while day < horizon:
        week = day.isocalendar()[:2]
        if week != current_week:
            current_week = week
            print(f"=== Semaine {week[1]} ({week[0]}) " + "=" * 40)
        day_blocks = [b for b in shown if b.start_at.date() == day]
        total = sum(b.planned_minutes for b in day_blocks) / 60
        header = f"{WEEKDAYS[day.weekday()]:<9} {day}"
        if day_blocks:
            print(f"{header}  — {total:g} h")
            for b in day_blocks:
                print(f"    {b.start_at:%H:%M}–{b.end_at:%H:%M}  {labels[b.evaluation_id]}")
        else:
            print(f"{header}  — libre")
        day += timedelta(days=1)

    # ---- métriques et alertes
    m = result.metrics
    print(f"\nCouverture : {m.coverage:.0%}  ·  {m.total_planned_hours:g} h placées "
          f"/ {m.total_target_hours:g} h visées  ·  pointe {m.peak_hours:g} h/jour  "
          f"·  écart-type {m.daily_stddev:.2f} h")
    if result.rho < 1.0:
        print(f"  ⚠ SEMESTRE EN SURCHARGE : facteur ρ = {result.rho:.2f} appliqué "
              "(demande réduite uniformément).")
    for external_id, deficit in sorted(result.deficits.items()):
        if deficit > 0:
            print(f"  ⚠ {external_id} : préparation insuffisante, déficit {deficit:g} h.")
    for external_id, reason in sorted(result.exclusions.items()):
        print(f"  ⚠ {external_id} : {reason}")

    if args.save:
        saved = 0
        with conn:
            for e in evaluations:
                repos.delete_planned_blocks(conn, e.id)
            for b in result.blocks:
                repos.insert_study_block(conn, b.evaluation_id, b.start_at, b.end_at)
                saved += 1
        print(f"\n{saved} bloc(s) enregistrés dans la base.")
    conn.close()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from planner.export import export_ics

    if not Path(args.db).exists():
        print("Aucune base de données. Importer d'abord un fichier JSON.", file=sys.stderr)
        return 1
    conn = connect(args.db)
    count = export_ics(conn, args.out)
    conn.close()
    print(f"{count} événement(s) exporté(s) vers {args.out}")
    return 0


def cmd_sync_restore(args: argparse.Namespace) -> int:
    from planner.core.errors import LocalDataExistsError
    from planner.storage.pg import connect_pg
    from planner.sync import restore

    backup_database(args.db)  # sauvegarde avant toute écriture (None si base absente)
    sqlite_conn = connect(args.db)  # crée et migre le schéma SQLite si besoin
    pg_conn = connect_pg(migrate=False)
    try:
        counters = restore(pg_conn, sqlite_conn, force=args.force)
    except LocalDataExistsError as exc:
        print(f"RESTAURATION REFUSÉE : {exc}", file=sys.stderr)
        return 2
    finally:
        pg_conn.close()
        sqlite_conn.close()
    total = sum(counters.values())
    detail = " · ".join(f"{table} {count}" for table, count in counters.items())
    print(f"Restore Postgres → SQLite : {total} ligne(s) copiée(s) ({detail})")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from planner.doctor import run_doctor

    return run_doctor(args.db)


def cmd_pg_migrate(_args: argparse.Namespace) -> int:
    from planner.storage.pg import SCHEMA_VERSION_PG, connect_pg

    conn = connect_pg()  # migre par défaut
    version = conn.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    ).fetchone()[0]
    conn.close()
    print(f"Schéma Postgres à jour : version {version}/{SCHEMA_VERSION_PG}")
    return 0


def cmd_sync_push(args: argparse.Namespace) -> int:
    from planner.core.errors import UnpulledChangesError
    from planner.storage.pg import connect_pg
    from planner.sync import push

    if not Path(args.db).exists():
        print("Aucune base de données. Importer d'abord un fichier JSON.", file=sys.stderr)
        return 1
    backup_database(args.db)  # copie de sûreté avant toute synchronisation
    sqlite_conn = connect(args.db)
    pg_conn = connect_pg()
    try:
        counters = push(sqlite_conn, pg_conn, force=args.force)
    except UnpulledChangesError as exc:
        print(f"PUSH REFUSÉ : {len(exc.block_ids)} bloc(s) coché(s) côté web non "
              "rapatriés. Lancer `sync-pull` d'abord, ou `sync-push --force` "
              "pour les écraser.", file=sys.stderr)
        return 2
    finally:
        pg_conn.close()
        sqlite_conn.close()
    total = sum(counters.values())
    detail = " · ".join(f"{table} {count}" for table, count in counters.items())
    print(f"Push SQLite → Postgres : {total} ligne(s) copiée(s) ({detail})")
    return 0


def cmd_sync_pull(args: argparse.Namespace) -> int:
    from planner.storage.pg import connect_pg
    from planner.sync import pull

    if not Path(args.db).exists():
        print("Aucune base de données. Importer d'abord un fichier JSON.", file=sys.stderr)
        return 1
    backup_database(args.db)  # pull modifie SQLite : copie de sûreté d'abord
    sqlite_conn = connect(args.db)
    pg_conn = connect_pg(migrate=False)
    counters = pull(pg_conn, sqlite_conn)
    pg_conn.close()
    sqlite_conn.close()
    print(f"Pull Postgres → SQLite : {counters['mis_a_jour']} bloc(s) mis à jour "
          f"sur {counters['blocs_web']} · {counters['orphelins']} orphelin(s) ignoré(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planner", description="Plan-Études (CLI)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="chemin de la base SQLite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="importer un JSON de cours généré par Claude")
    p_import.add_argument("file", help="chemin du fichier .json")
    p_import.set_defaults(func=cmd_import)

    p_list = sub.add_parser("list", help="lister les cours et évaluations")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="exporter blocs et échéances en .ics")
    p_export.add_argument("--out", default="plan_etudes.ics", help="fichier de sortie")
    p_export.set_defaults(func=cmd_export)

    p_migrate = sub.add_parser(
        "pg-migrate", help="appliquer les migrations Postgres (une fois, au déploiement)"
    )
    p_migrate.set_defaults(func=cmd_pg_migrate)

    p_push = sub.add_parser(
        "sync-push", help="répliquer la base SQLite vers Postgres (copie web)"
    )
    p_push.add_argument(
        "--force", action="store_true",
        help="écraser les statuts cochés côté web non rapatriés par sync-pull",
    )
    p_push.set_defaults(func=cmd_sync_push)

    p_pull = sub.add_parser(
        "sync-pull", help="rapatrier les statuts de blocs cochés côté web"
    )
    p_pull.set_defaults(func=cmd_sync_pull)

    p_restore = sub.add_parser(
        "sync-restore",
        help="reconstruire la base SQLite complète depuis Postgres (machine neuve)",
    )
    p_restore.add_argument(
        "--force", action="store_true",
        help="écraser une base SQLite locale non vide (sauvegardée d'abord)",
    )
    p_restore.set_defaults(func=cmd_sync_restore)

    p_doctor = sub.add_parser(
        "doctor", help="diagnostic d'environnement (aucune valeur sensible affichée)"
    )
    p_doctor.set_defaults(func=cmd_doctor)

    p_plan = sub.add_parser("plan", help="générer le plan d'étude et l'afficher")
    p_plan.add_argument("--semaines", type=int, default=2, help="semaines à afficher")
    p_plan.add_argument("--date", help="date de départ YYYY-MM-DD (défaut : aujourd'hui)")
    p_plan.add_argument("--save", action="store_true",
                        help="enregistrer les blocs générés dans la base")
    p_plan.set_defaults(func=cmd_plan)

    return parser


def main(argv: list[str] | None = None) -> int:
    # La console Windows est souvent en cp1252 : forcer UTF-8 pour les symboles (⚠, ·).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
