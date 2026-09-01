# Plan-Études

Planificateur d'études universitaire, local et gratuit, pour Windows.

Les plans de cours (PDF) sont transformés en JSON dans le chat Claude, puis importés ici.
L'application calcule la charge de travail de chaque évaluation et place automatiquement des
blocs d'étude de 1 à 2 h dans les créneaux libres des semaines précédant chaque échéance.

- Aucune API payante, aucun compte, aucun appel réseau à l'exécution.
- Données locales dans une base SQLite.

## Installation

```
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

## Utilisation

```
.venv/Scripts/python.exe -m planner import <fichier.json>   # importer un cours
.venv/Scripts/python.exe -m planner plan --semaines 2        # générer un plan (CLI)
.venv/Scripts/python.exe -m planner.app                      # interface graphique
```

Architecture et plan de développement : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
