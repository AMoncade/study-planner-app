# Journal de travail — Plan-Études

Une entrée par tâche terminée, la plus récente en haut.

---

## 2026-09-01 — Phase 2 : moteur de planification (sans UI)

- Tests écrits d'abord (`test_workload/curve/availability/placer/integration.py`) :
  66 tests au total, tous verts.
- `config.py` : `EngineSettings` (dataclass) portant tous les coefficients §4.9 — valeurs de
  départ, à calibrer contre le trimestre réel.
- `scheduler/workload.py` (étape A) : H_total = clamp(B·f_w·f_d·f_u·f_g·m_c), arrondi 0,5 h.
- `scheduler/curve.py` (étapes B+C) : fenêtre par type (travail/projet depuis start_date),
  courbe exp + plancher λ, redistribution des jours bloqués, plafond 3 h/éval/jour,
  reversement de l'excédent vers les jours proches.
- `scheduler/availability.py` (étape D) : grille 48×30 min/jour, éveil 08–22 h, contraintes
  hebdo/ponctuelles, séances de cours (bornes + except_dates), tampon transport 30 min,
  capacité min(libre, plafond jour), capacité totale × υ.
- `scheduler/placer.py` (étape E) : EDF (échéance, puis poids), coût C1–C5 (horaire,
  fragmentation, diversité, enchaînement, stabilité), report du reliquat vers les jours
  éloignés, pause dure ≥ 1 créneau entre blocs. **Décisions consignées** :
  1. la fenêtre s'arrête la veille de l'échéance (jour J réservé à l'épreuve — plus strict
     que la marge ε de §4) ;
  2. le déficit se mesure contre la charge NON réduite par ρ (l'alerte « préparation
     insuffisante » reste visible en surcharge) ;
  3. poids 0 (bonus) exclus du placement.
- `scheduler/metrics.py` (étape G) : couverture, écart-type journalier, KL, pointe.
- CLI `python -m planner plan --semaines N [--date] [--save]` : agenda ASCII, métriques,
  alertes (ρ < 1, déficits, exclusions).
- Sur les 4 cours réels : 174 h visées, couverture 89 %, ρ = 1, et le moteur signale
  honnêtement l'entassement des 4 finaux de décembre (déficits MAT1400/MAT1720-FINAL).
- Régression figée sur fixtures réelles (`test_integration.py`) — à re-figer après la
  calibration manuelle §4.9 (tâche de jugement, pas de code).

**Prochaine étape — Phase 3 :** UI (coquille, Importer, Cours, Contraintes tableau).

---

## 2026-09-01 — Phase 1 : noyau données (sans UI)

- Tests écrits d'abord (`test_importer.py`, `test_storage.py`) : 22 tests, tous verts.
- `core/models.py` : dataclasses pures (Course, Session, Evaluation, Constraint, StudyBlock)
  + constantes d'énumération. `weekday` en entier 0–6 aligné sur `date.weekday()`.
- `core/validation.py` : règles §2.4 — bloquantes (version de schéma, jsonschema, ids
  uniques, dates réellement parsables, start ≤ due) et avertissements (somme des poids ±0,5,
  due_date null, confiance < high, échéance hors trimestre) ; règle 9 (conflits d'examens
  inter-cours) via requête SQL, affichée à l'import CLI.
- `core/importer.py` : mapping JSON → modèles, défaut d'heure d'échéance (08:00 examen,
  23:59 remise), réconciliation §2.5 en transaction unique — upsert par
  `(code, term)` + `external_id`, champs manuels préservés, blocs `planned` invalidés quand
  `due_at`/`weight`/`scope_units`/`cumulative`/`type` change, évaluations disparues archivées.
- `storage/db.py` : migrations en avant par `PRAGMA user_version`, sauvegarde horodatée
  avant import (`backup_database`). `docs/schema/db.sql` **généré** depuis `MIGRATIONS`
  (synchronisation garantie par construction).
- `storage/repositories.py` : CRUD complet des 7 tables.
- CLI `python -m planner import <f.json>` / `list` opérationnelle sur les 4 fixtures
  réelles ; sortie UTF-8 forcée (console Windows cp1252).
- Projet installé en editable dans le venv (`pip install -e .`) pour que `python -m planner`
  fonctionne hors pytest — pas une dépendance, c'est le paquet lui-même.

**Prochaine étape — Phase 2 :** moteur de planification (workload, curve, availability,
placer, metrics) + `python -m planner plan`.

---

## 2026-09-01 — Phase 0.5 : données réelles + dépôt GitHub

- Dépôt GitHub `AMoncade/Study-Creator` renommé en **`AMoncade/study-planner-app`**, ajouté
  comme remote `origin`, historiques fusionnés (README local conservé), `main` poussée.
- `docs/schema/cours.schema.json` rédigé (JSON Schema draft 2020-12, contrat §2 de
  l'ARCHITECTURE, `additionalProperties: false` partout).
- `docs/PROMPT_EXTRACTION.md` rédigé : rôle extracteur, schéma littéral, 5 règles d'or,
  exemple few-shot, vérification finale des poids.
- **4 fixtures réelles** extraites des vrais plans de cours A26 (extraction faite par Claude
  en session, les PDF ne sont pas commités) :
  - `mat1000_a26.json` — Analyse 1 : 4 évals, dates de quiz préliminaires (confidence low),
    crédits absents du plan.
  - `mat1720_a26.json` — Probabilités : 2 évals, aucun horaire de séances dans le plan.
  - `mat1600_a26.json` — Algèbre linéaire : 5 évals dont un bonus weight 0, heures
    d'examens absentes, séances sans horaire (centre étudiant).
  - `mat1400_a26.json` — Calcul 1 : 17 évals (11 quiz datés + 2 quiz longs + intra + final
    + 2 bonus), double schéma de pondération documenté en warning, sessions avec
    `except_dates` (congés + relâche).
- Les 4 fixtures passent la validation `jsonschema` (script ad hoc) ; somme des poids 100
  (100,25 pour MAT1400, plafond des quiz documenté).
- Le trio de cas voulu par la phase est couvert : cours propre (MAT1720), cours flou
  (MAT1000/MAT1600), cours à évaluations multiples (MAT1400).

**Prochaine étape — Phase 1 :** noyau données (models, validation, importer, SQLite, CLI
import/list), tests d'abord contre ces fixtures.

---

## 2026-09-01 — Phase 0 : bootstrap

- Dépôt `git` initialisé (branche `main`).
- venv sur **Python 3.12.3** (`py -3.12`) plutôt que le 3.14 par défaut de la machine :
  les roues PySide6 pour 3.14 sont encore incertaines, le venv fige donc 3.12.
- Dépendances installées et vérifiées : PySide6 6.11.2, jsonschema 4.26, python-dateutil 2.9,
  icalendar 7.3, pytest 9.1, pytest-qt 4.5, pytest-cov 7.1, ruff 0.16.
  Justification de chaque paquet : voir `docs/ARCHITECTURE.md` §1.1.
- Arborescence `src/planner/{core,scheduler,storage,ui}` + `tests/fixtures/` + `docs/` créée.
- `docs/ARCHITECTURE.md` rédigé : contrat JSON complet, algorithme de placement (étapes A→G
  avec formules), 7 vues PySide6, phases 0 à 7, risques, conventions.
- `CLAUDE.md` écrit comme point d'entrée des sessions suivantes.

**Prochaine étape — Phase 0.5 (bloquante) :** faire passer un vrai plan de cours PDF dans le
chat Claude avec le prompt de `docs/PROMPT_EXTRACTION.md`, et déposer le JSON obtenu dans
`tests/fixtures/`. Aucun code d'import ne s'écrit avant d'avoir un fichier réel sous la main.
