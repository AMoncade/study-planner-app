"""Exceptions du domaine."""

from __future__ import annotations


class PlannerError(Exception):
    """Erreur de base de l'application."""


class ImportBlockedError(PlannerError):
    """Import refusé : au moins une règle bloquante a échoué (ARCHITECTURE §2.4)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))
