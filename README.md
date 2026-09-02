# Plan-Études (Study Planner App)

Planificateur d'études universitaire, local et gratuit, pour Windows.

Les plans de cours (PDF) sont transformés en JSON dans le chat Claude, puis importés ici.
L'application calcule la charge de travail de chaque évaluation et place automatiquement des
blocs d'étude de 1 à 2 h dans les créneaux libres des semaines précédant chaque échéance.

- Aucune API payante, aucun compte, aucun appel réseau à l'exécution.
- Données locales dans une base SQLite (sauvegardée automatiquement avant chaque import).

## Flux de travail

1. **Extraire** : copier le prompt de [`docs/PROMPT_EXTRACTION.md`](docs/PROMPT_EXTRACTION.md)
   (ou le bouton « Copier le prompt d'extraction » dans l'app), le coller dans une
   conversation Claude avec le PDF du plan de cours, et enregistrer le JSON obtenu.
2. **Importer** : vue *Importer* (ou `planner import <fichier.json>`). Le rapport de
   validation signale dates manquantes, pondérations incohérentes et champs incertains.
3. **Régler** : vue *Cours et évaluations* — difficulté (1–5), multiplicateur d'effort,
   override d'heures ; vue *Contraintes* — travail, sport, sommeil (tableau ou grille à
   peindre).
4. **Planifier** : vue *Planning* → « Recalculer le plan » (aperçu du différentiel avant
   application). Glisser un bloc le verrouille ; clic droit : Fait / Partiellement fait /
   Manqué / Supprimer. Le recalcul respecte l'historique et les blocs verrouillés.
5. **Suivre** : vue *Tableau de bord* — alertes (surcharge ρ, déficits, conflits
   d'examens), progression, charge par cours.

## Installation (développement)

```
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv/Scripts/python.exe -m pip install -e .
```

> **Reprise du projet sur une autre machine : lire [`docs/ETAT.md`](docs/ETAT.md).**

## Utilisation

```
.venv/Scripts/python.exe -m planner import <fichier.json>   # importer un cours
.venv/Scripts/python.exe -m planner list                     # lister les évaluations
.venv/Scripts/python.exe -m planner plan --semaines 2        # plan en ASCII (--save pour persister)
.venv/Scripts/python.exe -m planner export --out plan.ics    # export calendrier
.venv/Scripts/python.exe -m planner doctor                   # diagnostic d'environnement
.venv/Scripts/python.exe -m planner pg-migrate               # migrations Postgres (déploiement)
.venv/Scripts/python.exe -m planner sync-push [--force]      # répliquer SQLite -> Postgres
.venv/Scripts/python.exe -m planner sync-pull                # rapatrier les statuts cochés
.venv/Scripts/python.exe -m planner sync-restore [--force]   # reconstruire SQLite depuis Postgres
.venv/Scripts/python.exe -m planner.app                      # interface graphique
```

## Exécutable Windows

```
.\build_exe.ps1        # produit dist\PlanEtudes.exe (PyInstaller --onefile --windowed)
```

L'exe range sa base dans `%LOCALAPPDATA%\PlanEtudes\plan_etudes.db`.
**Mise à jour** : reconstruire l'exe puis remplacer l'ancien fichier — la base et les
paramètres sont conservés (et migrés automatiquement si le schéma a évolué).

## Web mobile (optionnel)

Postgres (Supabase) sert de copie de travail pour cocher des blocs depuis un téléphone ;
SQLite reste la source de vérité. `DATABASE_URL` et `APP_PIN` vont dans `.env` (jamais
commité).

```
.venv/Scripts/python.exe -m planner pg-migrate     # une fois, au déploiement
.venv/Scripts/python.exe -m planner sync-push      # répliquer SQLite -> Postgres
.venv/Scripts/uvicorn.exe --factory planner.web.api:create_app   # API + page mobile
.venv/Scripts/python.exe -m planner sync-pull      # rapatrier les statuts cochés
```

Le recalcul côté web est un **aperçu** : rien n'est enregistré depuis le téléphone à
part les statuts de blocs. Déploiement Vercel : `api/index.py` + `vercel.json`
(dépendances web sans PySide6 : `requirements-web.txt`).

## Tests

```
.venv/Scripts/python.exe -m pytest        # 104 tests
.venv/Scripts/python.exe -m ruff check src tests
```

Architecture et plan de développement : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Journal de travail : [`WORKLOG.md`](WORKLOG.md).
