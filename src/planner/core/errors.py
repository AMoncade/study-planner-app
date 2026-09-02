"""Exceptions du domaine."""

from __future__ import annotations


class PlannerError(Exception):
    """Erreur de base de l'application."""


class ImportBlockedError(PlannerError):
    """Import refusé : au moins une règle bloquante a échoué (ARCHITECTURE §2.4)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class LocalDataExistsError(PlannerError):
    """Restauration refusée : la base SQLite locale contient déjà des cours."""

    def __init__(self, course_count: int):
        self.course_count = course_count
        super().__init__(
            f"La base SQLite locale contient déjà {course_count} cours : restaurer "
            "depuis Postgres écraserait des données locales possiblement plus "
            "récentes. Relancer avec --force pour l'assumer (une sauvegarde est "
            "faite d'abord)."
        )


class UnpulledChangesError(PlannerError):
    """Push refusé : des statuts cochés côté web n'ont pas encore été rapatriés."""

    def __init__(self, block_ids: list[int]):
        self.block_ids = list(block_ids)
        super().__init__(
            f"{len(self.block_ids)} bloc(s) modifié(s) côté web non rapatriés : "
            "lancer `sync-pull` d'abord, ou `sync-push --force` pour les écraser."
        )
