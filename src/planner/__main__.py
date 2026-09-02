"""CLI de Plan-Études : import et consultation sans interface graphique (Phase 1).

Usage :
    python -m planner import tests/fixtures/mat1400_a26.json
    python -m planner list
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planner", description="Plan-Études (CLI)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="chemin de la base SQLite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="importer un JSON de cours généré par Claude")
    p_import.add_argument("file", help="chemin du fichier .json")
    p_import.set_defaults(func=cmd_import)

    p_list = sub.add_parser("list", help="lister les cours et évaluations")
    p_list.set_defaults(func=cmd_list)

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
