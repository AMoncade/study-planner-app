# Plan-Études — Architecture & plan de développement

> Application Windows de planification universitaire.
> Centralise les échéances d'un trimestre et génère un plan d'étude dynamique.
> **Document de référence du projet.** Toute session de travail commence par le lire.

---

## 0. Cadre du projet

### 0.1 Objectif

Transformer un ensemble de plans de cours (PDF) en un **agenda d'étude concret**, placé dans
les vraies cases horaires libres de la semaine, en tenant compte de la pondération, de la
difficulté et de la proximité de chaque échéance.

### 0.2 Contraintes non négociables

| Contrainte | Conséquence architecturale |
|---|---|
| **Zéro coût, zéro API payante** | Aucun appel réseau à l'exécution. Pas de clé API, pas de SDK LLM, pas de service cloud. |
| **L'intelligence d'extraction vient du chat Claude** | Le PDF n'est jamais parsé par le programme. Claude (abonnement existant) produit un JSON ; l'app ne fait que **valider et importer**. |
| **100 % local, hors-ligne** | SQLite + fichiers dans `data/`. Aucune télémétrie. |
| **Windows d'abord** | PySide6, chemins `pathlib`, packaging PyInstaller. Le code reste portable, mais on ne teste que Windows. |
| **Déterministe** | Aucun `random`. Deux exécutions sur les mêmes données produisent le même planning — indispensable pour tester, et pour la confiance de l'utilisateur. |

### 0.3 Frontière explicite : ce que l'app NE fait PAS

- Elle ne lit pas de PDF. (Pas de `pdfplumber`, pas d'OCR, pas de heuristique de parsing.)
- Elle ne devine pas les dates manquantes : elle les signale et demande une saisie manuelle.
- Elle ne se connecte à aucun calendrier en ligne. L'export `.ics` est un fichier, à importer soi-même.

### 0.4 Flux complet

```
  [PDF plan de cours]
          |
          |  (1) copier-coller du prompt standardisé + téléversement du PDF
          v
  [ Chat Claude ]  --->  cours_XXX.json   (contrat §2)
                                |
                                |  (2) import + validation jsonschema
                                v
                        [ Plan-Études (PySide6) ]
                                |
          +---------------------+---------------------+
          |                                           |
  (3) saisie des contraintes                 (4) moteur de placement
      (travail, gym, cours, sommeil)              (algorithme §4)
          |                                           |
          +---------------------+---------------------+
                                v
                    [ Agenda d'étude hebdomadaire ]
                       + suivi, recalcul, export .ics
```

---

## 1. Stack et arborescence

### 1.1 Stack

| Couche | Choix | Justification |
|---|---|---|
| Langage | Python 3.12 (venv local) | 3.14 est installé sur la machine, mais les roues PySide6 y sont encore incertaines. Le venv fige 3.12. |
| UI | PySide6 (Qt 6, LGPL) | Gratuit, natif Windows, widgets tableaux solides. |
| Validation | `jsonschema` | Le contrat JSON est un schéma versionné, pas une convention orale. |
| Dates | `python-dateutil` | Récurrences hebdomadaires, `rrule`, arithmétique de dates. |
| Stockage | `sqlite3` (stdlib) | Zéro dépendance, transactionnel, requêtable. |
| Export | `icalendar` | `.ics` importable dans n'importe quel calendrier. |
| Tests | `pytest`, `pytest-qt` | Le moteur est testé sans UI ; l'UI est testée séparément. |
| Qualité | `ruff` | Lint + format en un seul outil. |
| Packaging | PyInstaller (Phase 7) | `.exe` autonome, pas d'installation Python requise. |

**Aucune dépendance n'est ajoutée sans justification écrite dans le WORKLOG.**

### 1.2 Arborescence cible

```
plan-etudes/
├── .venv/                          # Python 3.12 isolé (non versionné)
├── CLAUDE.md                       # point d'entrée pour les sessions Claude Code
├── WORKLOG.md                      # journal daté, une entrée par tâche terminée
├── README.md
├── requirements.txt / requirements-dev.txt
├── pyproject.toml                  # config ruff + pytest
├── docs/
│   ├── ARCHITECTURE.md             # ce document
│   ├── PROMPT_EXTRACTION.md        # le prompt à coller dans le chat Claude
│   └── schema/
│       ├── cours.schema.json       # JSON Schema draft 2020-12, source de vérité
│       └── db.sql                  # schéma SQLite de référence
├── data/                           # base SQLite + sauvegardes (non versionné)
├── src/planner/
│   ├── __main__.py                 # point d'entrée CLI  : python -m planner
│   ├── app.py                      # point d'entrée GUI  : python -m planner.app
│   ├── config.py                   # constantes + paramètres calibrables (§4.9)
│   ├── core/
│   │   ├── models.py               # dataclasses : Course, Evaluation, Constraint, StudyBlock
│   │   ├── importer.py             # lecture + validation + mapping JSON -> modèles
│   │   ├── validation.py           # règles métier (somme des poids, cohérence des dates)
│   │   └── errors.py
│   ├── scheduler/
│   │   ├── workload.py             # étape A : charge totale par évaluation
│   │   ├── curve.py                # étape C : répartition temporelle
│   │   ├── availability.py         # étape D : grille de créneaux libres
│   │   ├── placer.py               # étape E : placement glouton + débordement
│   │   ├── rebalance.py            # étape F : recalcul incrémental
│   │   └── metrics.py              # étape G : indicateurs de qualité
│   ├── storage/
│   │   ├── db.py                   # connexion, migrations
│   │   └── repositories.py         # CRUD par entité
│   └── ui/
│       ├── main_window.py
│       ├── views/                  # une vue = un fichier (§5)
│       ├── widgets/                # composants réutilisables
│       ├── models/                 # QAbstractTableModel / QAbstractItemModel
│       └── style.qss
└── tests/
    ├── fixtures/                   # VRAIS JSON exportés du chat Claude
    ├── test_importer.py
    ├── test_workload.py
    ├── test_curve.py
    ├── test_availability.py
    ├── test_placer.py
    └── test_ui_*.py
```

---

## 2. Contrat de données — le JSON que Claude doit produire

C'est **la pièce la plus importante du projet**. Tout le reste en dépend.
Le schéma vit dans `docs/schema/cours.schema.json` et est versionné par `schema_version`.

### 2.1 Principes

1. **Un fichier = un cours.** Plus simple à régénérer quand un plan de cours change.
2. **Aucune invention.** Si l'information n'est pas dans le PDF, le champ vaut `null` et une
   entrée est ajoutée dans `warnings`. Un champ deviné silencieusement est un bug.
3. **Tout est explicite et typé.** Dates ISO-8601 (`YYYY-MM-DD`), heures 24 h (`HH:MM`),
   durées en minutes, pondérations en pourcentage décimal.
4. **`confidence` par évaluation.** L'app met en surbrillance tout ce qui n'est pas `high`.

### 2.2 Structure exacte

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-09-01",
  "source_file": "IFT1015_A26_plan_de_cours.pdf",

  "course": {
    "code": "IFT1015",
    "title": "Programmation 1",
    "term": "A26",
    "institution": "UdeM",
    "credits": 3,
    "instructor": "Nom Prénom",
    "language": "fr",
    "difficulty": 3,
    "effort_multiplier": 1.0,
    "sessions": [
      {
        "kind": "cours",
        "weekday": "mardi",
        "start": "13:00",
        "end": "15:00",
        "room": "Z-260",
        "start_date": "2026-09-08",
        "end_date": "2026-12-08",
        "except_dates": ["2026-10-20"]
      },
      {
        "kind": "tp",
        "weekday": "jeudi",
        "start": "10:00",
        "end": "12:00",
        "room": "Z-315",
        "start_date": "2026-09-10",
        "end_date": "2026-12-10",
        "except_dates": []
      }
    ]
  },

  "evaluations": [
    {
      "id": "IFT1015-INTRA",
      "title": "Examen intra",
      "type": "examen_intra",
      "weight": 25.0,
      "due_date": "2026-10-27",
      "due_time": "13:00",
      "start_date": null,
      "duration_minutes": 120,
      "modality": "en_classe",
      "location": "Z-260",
      "cumulative": false,
      "group_work": false,
      "content_scope": [
        "Chapitres 1 à 6 du manuel",
        "Séances de cours 1 à 7",
        "TP 1 et 2"
      ],
      "scope_units": 7,
      "deliverable": null,
      "estimated_pages": null,
      "resources": ["Manuel ch. 1-6", "Diapositives 1-7"],
      "notes": "Documentation non permise. Calculatrice interdite.",
      "confidence": "high",
      "source_excerpt": "Examen intra — 25 % — 27 octobre, 13h00, en classe (2 h)."
    },
    {
      "id": "IFT1015-TP3",
      "title": "Travail pratique 3",
      "type": "travail",
      "weight": 15.0,
      "due_date": "2026-11-17",
      "due_time": "23:59",
      "start_date": "2026-11-03",
      "duration_minutes": null,
      "modality": "remise_en_ligne",
      "location": null,
      "cumulative": false,
      "group_work": true,
      "content_scope": ["Chapitres 7 à 9"],
      "scope_units": 3,
      "deliverable": "Rapport PDF + code source",
      "estimated_pages": 8,
      "resources": [],
      "notes": "Équipes de 2. Pénalité de 10 %/jour de retard.",
      "confidence": "high",
      "source_excerpt": "TP3 — 15 % — remise le 17 novembre à 23h59 sur StudiUM."
    }
  ],

  "totals": {
    "declared_weight_sum": 100.0,
    "evaluation_count": 2
  },

  "warnings": [
    "La date de l'examen final n'est pas précisée dans le plan de cours (mention « période d'examens »). À saisir manuellement.",
    "La pondération de la participation (5 %) est mentionnée sans modalité d'évaluation."
  ]
}
```

### 2.3 Dictionnaire des champs

**`course`**

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `code` | string | oui | Sigle officiel, sans espace. Clé naturelle. |
| `title` | string | oui | |
| `term` | string | oui | Format libre mais stable (`A26`, `H27`, `E26`). |
| `institution` | string | non | |
| `credits` | integer | non | 1–6. |
| `instructor` | string \| null | non | |
| `language` | `"fr"` \| `"en"` | non | Défaut `"fr"`. |
| `difficulty` | integer 1–5 | non | **Toujours `3` à la génération.** Champ subjectif que je règle moi-même dans l'app. Claude ne le devine pas. |
| `effort_multiplier` | number 0.5–2.0 | non | Défaut `1.0`. Idem : réglé à la main. |
| `sessions[]` | array | non | Séances récurrentes. Elles bloquent des créneaux (§4.4). |

**`sessions[]`** — `kind` ∈ `cours` \| `tp` \| `laboratoire` \| `atelier` \| `demonstration`.
`weekday` en toutes lettres, minuscules, français. `except_dates` = congés et relâche.

**`evaluations[]`**

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | string | oui | `{code}-{SLUG}`. Unique dans le fichier. **Stable entre deux régénérations** — c'est la clé de réconciliation à la ré-importation. |
| `title` | string | oui | Libellé tel qu'écrit dans le plan. |
| `type` | enum | oui | `examen_final`, `examen_intra`, `quiz`, `travail`, `projet`, `presentation`, `laboratoire`, `lecture`, `participation`, `autre`. Pilote la charge de base (§4.1). |
| `weight` | number 0–100 | oui | Pourcentage de la note finale. |
| `due_date` | date \| null | oui (peut valoir `null`) | `null` ⇒ obligatoirement un `warning` correspondant. |
| `due_time` | time \| null | non | Défaut appliqué par l'app : `23:59` pour une remise, `08:00` pour un examen. |
| `start_date` | date \| null | non | Date d'ouverture d'un travail long. |
| `duration_minutes` | integer \| null | non | Durée de l'épreuve, pas de la préparation. |
| `modality` | enum | non | `en_classe`, `en_ligne_synchrone`, `remise_en_ligne`, `oral`, `hors_classe`. |
| `cumulative` | boolean | non | `true` ⇒ facteur de couverture majoré (§4.1). |
| `group_work` | boolean | non | `true` ⇒ charge individuelle réduite (§4.1). |
| `content_scope[]` | string[] | non | Matière couverte, telle qu'écrite. |
| `scope_units` | integer \| null | non | **Nombre de chapitres / séances couverts**, compté à partir de `content_scope`. Variable clé de l'estimation. `null` si indéterminable. |
| `deliverable` | string \| null | non | Ce qu'il faut remettre. |
| `estimated_pages` | integer \| null | non | Longueur exigée d'un travail écrit. |
| `resources[]` | string[] | non | |
| `notes` | string \| null | non | Règles particulières, pénalités, matériel permis. |
| `confidence` | `high`\|`medium`\|`low` | oui | `high` = écrit noir sur blanc. `medium` = un champ déduit du contexte. `low` = date ou pondération incertaine. |
| `source_excerpt` | string \| null | oui | **Citation littérale du plan de cours.** Permet de vérifier en deux secondes sans rouvrir le PDF. |

### 2.4 Règles de validation appliquées à l'import

Bloquantes (import refusé) :

1. `schema_version` reconnue.
2. JSON Schema valide.
3. `course.code` non vide ; `evaluations` non vide.
4. `id` uniques dans le fichier.
5. Dates parsables, et `start_date <= due_date` quand les deux existent.

Avertissements (import accepté, bandeau jaune dans l'UI) :

6. `|Σ weight − 100| > 0.5` → « pondérations incomplètes ou excédentaires ».
7. Une évaluation avec `due_date = null` → à compléter avant la planification.
8. `confidence != "high"` → à vérifier contre `source_excerpt`.
9. Deux évaluations de cours différents à la même date → conflit signalé au tableau de bord.
10. `due_date` hors des bornes du trimestre déduites des `sessions`.

### 2.5 Réconciliation à la ré-importation

Un plan de cours peut être régénéré (date modifiée en cours de trimestre). L'import fait un
**upsert par `(course.code, evaluation.id)`** :

- évaluation nouvelle → insérée ;
- évaluation existante, champs identiques → ignorée ;
- évaluation existante, `due_date` ou `weight` modifié → mise à jour, et **les blocs d'étude
  déjà placés pour elle sont invalidés** puis replanifiés (sauf ceux marqués « fait ») ;
- évaluation absente du nouveau fichier → marquée `archived`, jamais supprimée : l'historique
  de travail réalisé doit survivre.

Les champs réglés à la main (`difficulty`, `effort_multiplier`, `manual_hours_override`) ne
sont **jamais** écrasés par un import.

### 2.6 Le prompt d'extraction

Vit dans `docs/PROMPT_EXTRACTION.md`, à copier-coller dans le chat Claude avec le PDF.
Sa structure :

1. Rôle : « Tu es un extracteur de données. Tu ne planifies rien, tu ne conseilles rien. »
2. Le schéma ci-dessus, en littéral.
3. Les cinq règles d'or :
   - ne jamais inventer une date, une pondération ou un titre ;
   - tout champ absent du PDF ⇒ `null` + une ligne dans `warnings` ;
   - `source_excerpt` obligatoire : citation exacte, jamais reformulée ;
   - `difficulty` toujours `3`, `effort_multiplier` toujours `1.0` ;
   - sortie : **un seul bloc ```json, rien avant, rien après**.
4. Un exemple complet entrée → sortie (few-shot) pour ancrer le format.
5. Instruction finale : « Vérifie que la somme des `weight` vaut 100. Si non, ajoute un
   warning explicite au lieu d'ajuster les valeurs. »

### 2.7 Import de l'horaire `.ics` du centre étudiant (Phase 12)

Deuxième source de données, complémentaire au JSON : le fichier `.ics` exporté du centre
étudiant UdeM fournit les **séances de cours réelles** (le JSON les connaît rarement).
`planner import-ics <fichier.ics>` (cœur : `core/ics_import.py`) applique ces règles :

- **Rattachement au cours** : sigle détecté dans `SUMMARY` puis `DESCRIPTION`
  (`[A-Z]{2,4}[ -]?\d{4}`, normalisé sans séparateur : `IFT-1015` → `IFT1015`). Événement
  sans sigle, ou sigle absent de la base → **ignoré mais listé** dans le rapport ; l'import
  ne crée jamais de cours.
- **Heures** : `DTSTART`/`DTEND` avec fuseau (`America/Toronto`) sont convertis en
  **heure locale naïve**, la convention de toute l'app.
- **Récurrences** : `RRULE` développée avec `dateutil` (une séance par jour de semaine ;
  `start_date`/`end_date` = première/dernière occurrence) ; `EXDATE` → `except_dates`.
- **Examens** : si le `SUMMARY` contient *intra*, *final*, *quiz* ou *examen* (insensible
  à la casse et aux accents), **aucune séance n'est créée** ; l'événement est confronté aux
  évaluations du cours de type compatible : dates égales → *match confirmé* ; dates
  différentes → *conflit*, signalé seulement (la date du `.ics` n'écrase la base qu'avec
  `--apply-exam-dates`, qui invalide alors les blocs planifiés comme en §2.5) ; aucune
  évaluation compatible → *examen sans évaluation connue*.
- **Réconciliation** : upsert par `(weekday, start, end)` — ré-importer le même fichier ne
  duplique rien ; une séance existante au même créneau est mise à jour (salle, bornes,
  exceptions) mais son `kind` réglé par le JSON est conservé ; les séances absentes du
  `.ics` ne sont **jamais supprimées**.

---

## 3. Modèle interne et stockage

### 3.1 Entités

```
Course(id, code, title, term, credits, instructor, difficulty, effort_multiplier, archived)
  └─ Session(id, course_id, kind, weekday, start, end, start_date, end_date, except_dates)
  └─ Evaluation(id, course_id, external_id, title, type, weight, due_at, start_date,
                duration_minutes, modality, cumulative, group_work, scope_units,
                estimated_pages, confidence, source_excerpt, notes,
                manual_hours_override, status, archived)

Constraint(id, label, category, weekday | specific_date, start, end, rrule, priority, color)
        category ∈ travail | entrainement | transport | sommeil | personnel | cours | autre

StudyBlock(id, evaluation_id, start_at, end_at, planned_minutes, status, locked,
           generation_id, actual_minutes, efficiency, note)
        status ∈ planned | done | partial | skipped | moved

Settings(key, value)                                    # préférences + coefficients
Generation(id, created_at, params_hash, coverage, deficit_total)   # historique des calculs
```

### 3.2 Stockage

SQLite unique : `data/plan_etudes.db`.

- `db.py` gère les migrations par numéro de version (`PRAGMA user_version`), en avant seulement.
- Le schéma SQL de référence vit dans `docs/schema/db.sql`, **maintenu synchronisé** — même
  discipline que pour le JSON.
- Sauvegarde : copie horodatée du `.db` avant toute migration et avant tout import.
- Les blocs `done` ne sont jamais supprimés par un recalcul : ils constituent l'historique réel.

---

## 4. Algorithme de répartition — logique mathématique

Le moteur est une **fonction pure** :
`plan(evaluations, constraints, settings, today) → [StudyBlock]`.
Pas d'accès base, pas d'UI, pas d'aléatoire. C'est ce qui le rend testable et rejouable.

Notations : `e` = une évaluation, `w_e` sa pondération (%), `d_c` la difficulté du cours (1–5),
`u_e` = `scope_units`, `T_e` la date-heure d'échéance, `t` = nombre de jours avant `T_e`.

---

### Étape A — Charge totale d'étude par évaluation

```
H_total(e) = clamp( B(type_e) · f_w(w_e) · f_d(d_c) · f_u(u_e) · f_g(e) · m_c ,  H_min , H_max )
```

**B(type)** — charge de base en heures, pour une évaluation « standard » (20 %, difficulté 3,
5 unités de matière) :

| type | B (h) |
|---|---|
| `examen_final` | 14 |
| `examen_intra` | 10 |
| `quiz` | 3 |
| `travail` | 12 |
| `projet` | 20 |
| `presentation` | 7 |
| `laboratoire` | 4 |
| `lecture` | 2 |
| `participation` | 1 |
| `autre` | 6 |

**f_w — facteur de pondération**, sous-linéaire : un examen à 40 % ne demande pas le double
d'un examen à 20 %, parce que ni la matière ni le temps de préparation ne doublent.

```
f_w(w) = (w / 20)^α          avec α = 0.6
```

> `w=10 → 0,66` · `w=20 → 1,00` · `w=30 → 1,27` · `w=40 → 1,52` · `w=60 → 1,93`

**f_d — facteur de difficulté**, linéaire et borné :

```
f_d(d) = 1 + β · (d − 3)     avec β = 0.15,  d ∈ [1,5]   ⇒   f_d ∈ [0,70 ; 1,30]
```

**f_u — facteur de couverture de matière**, en racine carrée (rendements décroissants :
réviser 10 chapitres ne coûte pas le double de 5) :

```
f_u(u) = (u / u_ref)^0.5     avec u_ref = 5 ;  f_u = 1.0 si u est null
si e.cumulative :  f_u ← f_u · 1.25
```

**f_g — travail d'équipe** : la charge individuelle baisse, mais pas proportionnellement
(coordination, réunions).

```
f_g = 0.75 si group_work sinon 1.0
```

**m_c** — `effort_multiplier` du cours, réglé à la main (défaut 1.0). C'est la soupape : si un
cours me coûte systématiquement plus cher, je monte ce nombre au lieu de bricoler l'algorithme.

**Bornes** : `H_min = 1,0 h`, `H_max = 24 h`.

**Court-circuit** : si `manual_hours_override` est défini sur l'évaluation, il remplace
intégralement le calcul. L'algorithme doit toujours pouvoir être contredit à la main.

---

### Étape B — Fenêtre de révision

```
W(e) = [ max(aujourd'hui, T_e − D(type_e)) ,  T_e − ε(e) ]
```

**D(type)** — profondeur de la fenêtre, en jours. Décision 2026-09-02 (« régulier dès
maintenant ») : pour les **examens** (`examen_intra`, `examen_final`), la fenêtre couvre
**tout l'horizon restant** — `D ← max(D(type), jours entre aujourd'hui et T_e)` — de
sorte que l'étude d'un examen commence *aujourd'hui*, quel que soit son éloignement.
Le plancher λ de la courbe (étape C) répartit cette charge dès la première semaine du
trimestre ; la décroissance exponentielle garde la veille comme jour le plus chargé.
Les valeurs de la table sont donc des **minimums** pour les examens, et des profondeurs
effectives pour les autres types :

| type | D (jours) |
|---|---|
| `examen_final` | 84 (minimum — en pratique : jusqu'à aujourd'hui) |
| `examen_intra` | 42 (minimum — en pratique : jusqu'à aujourd'hui) |
| `quiz` | 7 |
| `travail` / `projet` | 21 (ou depuis `start_date` si celle-ci est plus tardive) |
| `presentation` | 14 |
| autres | 7 |

**ε(e)** — marge de sécurité avant l'échéance :

- examen : aucun bloc ne peut chevaucher ni dépasser `T_e` ; le dernier bloc doit finir
  **au moins 30 min avant** le début de l'épreuve ;
- remise : aucun bloc après `T_e − 2 h`, garde-fou contre la remise à la dernière minute.

Si `W(e)` est vide (échéance passée, ou dans moins de ε), l'évaluation est **exclue** du
placement et signalée comme « trop tard » au tableau de bord.

---

### Étape C — Courbe de répartition temporelle

Combien d'heures placer à `t` jours de l'échéance ? Deux forces opposées : la révision espacée
(mémorisation à long terme) contre la fraîcheur (réviser près de l'examen paie). On mélange
les deux — et depuis la décision « régulier dès maintenant » (2026-09-02), la révision
espacée **domine** : courbe presque plate, montée douce vers l'échéance.

```
g(t) = (1 − λ) · exp( −(t − 1) / τ )  +  λ / D          pour t = 1 … D

τ = D / 1.5      (constante de décroissance — décroissance douce)
λ = 0.60         (plancher uniforme majoritaire : garantit l'étalement)

p(t) = g(t) / Σ_{k=1..D} g(k)               (normalisation, Σ p = 1)
h(t) = H_total · p(t)                        (heures visées ce jour-là)
```

La veille (`t = 1`) reste le jour le plus chargé de la fenêtre, mais le ratio
`g(1) / g(D)` est **modéré** (~3-4× au niveau du jour, < 2× en agrégat hebdomadaire
mesuré sur un trimestre type) — jamais le mur de dernière minute (15×) que produisait
l'ancien réglage `λ = 0,35`, `τ = D/3`.

> Exemple `D = 42`, `H_total = 24 h` : ≈ 1,0 h/jour sur la dernière semaine,
> ≈ 0,5 h/jour sur la première. La charge hebdomadaire est quasi constante du début de
> la fenêtre à l'échéance, avec une crête douce la dernière semaine.

Réglage de `λ` : `λ → 0` = bachotage pur, `λ → 1` = étalement plat. `0,60` est la valeur
actée le 2026-09-02 (« régulier dès maintenant ») ; recalibrable contre un vrai
trimestre (§4.9).

**Correctifs appliqués à `h(t)` avant placement :**

1. **Jours indisponibles** — si le jour `t` a une capacité nulle, sa masse `p(t)` est
   redistribuée proportionnellement sur les jours restants de la fenêtre.
2. **Plafond par évaluation et par jour** — `h(t) ≤ H_jour_eval = 3 h`. Étudier 5 h la même
   matière dans une seule journée n'est pas réaliste.
3. **Granularité** — les cibles `h(t)` restent **fractionnaires** ; l'agrégation en blocs
   de 0,5 h se fait au placement (carry jour à jour, étape E). Arrondir ici ferait
   disparaître la masse des fenêtres longues, dont les cibles journalières sont bien
   sous 0,5 h.

---

### Étape D — Grille de disponibilité

L'horizon (aujourd'hui → dernière échéance) est discrétisé en **créneaux de 30 minutes**.

```
libre(s)  ⟺   s ⊂ [éveil_début, éveil_fin]                    (défaut 08:00–22:00)
          ∧   s ∩ contraintes_fixes  = ∅
          ∧   s ∩ séances_de_cours   = ∅
          ∧   s ∩ blocs_déjà_placés  = ∅
          ∧   s ∉ tampon_transport(contrainte)                 (défaut 30 min de part et
                                                                d'autre d'une contrainte
                                                                hors domicile)
```

Implémentation : un tableau de booléens par jour (28 créneaux pour 14 h d'éveil). Simple,
rapide, trivialement testable.

**Capacité journalière :**

```
C(jour) = min( Σ créneaux libres · 0,5 h ,  H_jour_max(jour) )

H_jour_max = 4 h en semaine,  6 h le week-end          (paramétrable)
```

**Ajustement global de la demande.** Avant tout placement, on compare demande et capacité sur
l'horizon :

```
Demande  = Σ_e H_total(e)
Capacité = Σ_jours C(jour) · υ         avec υ = 0,80  (taux d'utilisation cible : on ne
                                        remplit jamais 100 % du temps libre)

si Demande > Capacité :
    ρ = Capacité / Demande
    H_total(e) ← H_total(e) · ρ        pour tout e
    → alerte « semestre en surcharge : facteur ρ appliqué »
```

Point important : plutôt que de générer un plan impossible à tenir, l'application réduit
uniformément **et le dit**.

---

### Étape E — Placement

Algorithme **glouton, piloté par échéance (EDF), avec débordement contrôlé**.

```
1. Ordonner les évaluations par T_e croissant ; à égalité, w_e décroissant.
   (EDF est optimal en faisabilité sur machine unique ; le poids départage.)

2. Pour chaque évaluation e :
     report ← 0
     Pour chaque jour j de W(e), traité du PLUS LOINTAIN de T_e au plus proche :

        besoin ← h(j) + report
        au premier jour ayant de la capacité : besoin ← max(besoin, bloc_min)
            (amorce : un premier bloc tombe dès l'ouverture de la fenêtre — sinon
             chaque évaluation accumulerait 3-5 jours de cibles fractionnaires et
             les premiers jours du plan resteraient vides ; le report devient
             négatif et rembourse l'avance, la masse totale est conservée)
        si besoin < bloc_min (1 h) :
            report ← besoin ; jour suivant
            (carry : la courbe aplatie produit des cibles fractionnaires, sous
             bloc_min — on les agrège en blocs plaçables tous les 2-4 jours ; le
             report dérive vers l'échéance, si bien que la veille récupère le
             reliquat de fin de parcours et reste le jour le plus chargé)
        tant que besoin ≥ bloc_min :
            durée     ← min(besoin, bloc_max = 2 h), arrondi à 0,5 h
            candidats ← toutes les plages libres contiguës ≥ durée dans j
            si candidats = ∅ : sortir de la boucle
            choisir le candidat de coût C minimal (ci-dessous)
            placer le bloc, marquer les créneaux occupés
            besoin ← besoin − durée
        report ← besoin

     si un reliquat subsiste après le parcours de W(e) (pertes d'arrondi, jours
     saturés) : le replacer au PLUS PRÈS de T_e — la fraîcheur paie, et la veille
     reste le jour le plus chargé de la fenêtre.

     si le report échoue : accumuler dans deficit(e)

3. Retourner (blocs, déficit par évaluation, métriques)
```

**Fonction de coût d'un placement candidat** (à minimiser) — c'est ici que se joue la qualité
perçue du planning :

```
C = c1 · P_horaire(heure_début)
  + c2 · P_fragmentation(plage restante après placement)
  + c3 · P_diversité(nb de matières déjà planifiées ce jour-là)
  + c4 · P_enchaînement(bloc adjacent de la même matière)
  + c5 · P_stabilité(distance au placement précédent de ce bloc)
```

| Terme | Rôle | Défaut |
|---|---|---|
| `P_horaire` | Préférence circadienne. Table de pénalité par heure : 0 sur les bonnes plages, croissante tôt le matin et tard le soir. Réglable dans les paramètres. | c1 = 1.0 |
| `P_fragmentation` | Pénalise un placement qui laisse un trou inutilisable (< 1 h). Favorise l'usage des bords de plage. | c2 = 1.5 |
| `P_diversité` | Pénalise la 4ᵉ matière différente dans une même journée (coût de changement de contexte). | c3 = 0.8 |
| `P_enchaînement` | Pénalise plus de 2 blocs consécutifs sans pause de 15 min, et plus de 3 h de la même matière d'affilée. | c4 = 2.0 |
| `P_stabilité` | **Anti-agitation.** Lors d'un recalcul, un bloc qui reste en place coûte 0 ; un bloc déplacé coûte proportionnellement au déplacement. Évite qu'un planning entier change à chaque modification mineure. | c5 = 1.2 |

**Contraintes dures** (jamais violées, non négociables par le coût) :

- aucun chevauchement avec une contrainte fixe, une séance de cours ou un bloc verrouillé ;
- `1 h ≤ durée ≤ 2 h`, alignée sur 30 min ;
- bloc entièrement inclus dans `W(e)` ;
- `Σ durée(jour) ≤ H_jour_max(jour)` ;
- pause ≥ 15 min entre deux blocs consécutifs.

**Complexité** : `O(E · D · S)` — E évaluations, D jours de fenêtre, S créneaux par jour.
Pour un trimestre réaliste (10 évaluations × 21 jours × 28 créneaux) ≈ 6 000 évaluations de
coût : instantané. Aucune optimisation prématurée nécessaire.

---

### Étape F — Recalcul incrémental

Déclenché par : un bloc marqué fait/manqué, une contrainte modifiée, un import, un changement
de paramètre.

```
Pour chaque évaluation e non terminée :

    H_fait(e)    = Σ ( minutes_réelles(b) / 60 · η(b) )  sur les blocs status ∈ {done, partial}
                   η = efficacité auto-déclarée ∈ [0,5 ; 1,2], défaut 1,0

    H_restant(e) = max(0, H_total(e) − H_fait(e))

Replanifier UNIQUEMENT sur [maintenant, T_e] :
    - les blocs passés sont figés (historique) ;
    - les blocs `locked` (déplacés à la main) sont figés, et leur temps compte comme placé ;
    - les blocs futurs non verrouillés sont libérés puis replacés, avec P_stabilité qui les
      ramène vers leurs positions actuelles.
```

Un bloc `skipped` **ne réduit pas** `H_restant` : le travail reste à faire, il est simplement
repoussé. Cela augmente mécaniquement la densité des jours suivants et déclenche l'alerte de
surcharge si la fenêtre ne suffit plus. C'est le comportement honnête.

---

### Étape G — Métriques de qualité

Calculées à chaque génération, affichées au tableau de bord :

| Métrique | Formule | Lecture |
|---|---|---|
| Taux de couverture | `Σ heures placées / Σ H_total` | < 0,9 ⇒ semestre en surcharge |
| Déficit par évaluation | `H_total(e) − heures placées(e)` | > 0 ⇒ alerte rouge sur cette évaluation |
| Équilibre journalier | écart-type des heures par jour | élevé ⇒ planning en dents de scie |
| Fidélité à la courbe | divergence de Kullback-Leibler entre `p(t)` visé et réalisé | mesure la déformation imposée par les contraintes |
| Charge de pointe | `max(heures/jour)` | dépasse `H_jour_max` ⇒ bug |

Ces métriques sont **le harnais de test du moteur** : une modification de coefficient se juge
sur elles, pas à l'œil.

---

### 4.9 Paramètres à calibrer (⚠ valeurs de départ, pas des vérités)

Tous dans `config.py`, tous exposés dans la vue Paramètres, tous persistés en base.

```python
B_TYPE            # table des charges de base par type
ALPHA      = 0.60 # exposant de pondération
BETA       = 0.15 # pente de difficulté
U_REF      = 5    # unités de matière de référence
LAMBDA     = 0.60 # plancher d'étalement de la courbe (« régulier dès maintenant »)
TAU_RATIO  = 1.5  # tau = D / TAU_RATIO (décroissance douce)
D_TYPE            # profondeur de fenêtre par type
H_JOUR_MAX = {"semaine": 4.0, "weekend": 6.0}
H_JOUR_EVAL = 3.0
BLOC_MIN, BLOC_MAX = 1.0, 2.0
UPSILON    = 0.80 # taux d'utilisation cible du temps libre
C1..C5            # poids de la fonction de coût
```

**Méthode de calibration** (à faire en Phase 2, avec de vraies données) :

1. Importer un trimestre déjà terminé, dont je connais le temps réellement passé.
2. Comparer `H_total(e)` calculé au temps réel, évaluation par évaluation.
3. Ajuster d'abord `B_TYPE` (l'échelle), ensuite `ALPHA` (la sensibilité au poids), en dernier
   `LAMBDA` (la forme de la courbe).
4. Figer les valeurs retenues par un test de régression sur la fixture réelle.

---

## 5. Interface PySide6 — vues à construire

### 5.0 Coquille — `MainWindow`

`QMainWindow` + barre latérale de navigation (`QListWidget` icônes + texte) pilotant un
`QStackedWidget`. Barre d'outils : *Importer un JSON* · *Recalculer le plan* · *Exporter .ics*.
Barre d'état : dernière génération, taux de couverture, nombre d'alertes. Thème sombre via
`style.qss`. Aucun composant tiers.

Depuis la phase 13, la barre latérale est un panneau **fixe de 232 px** (plus de
`QSplitter`) : en-tête pastille « P » bleu UdeM + titre + session, navigation à icônes SVG
inline (`ui/icons.py`), pied « ● Synchronisé · il y a N min » d'après l'horodatage de la
base. Les jetons de couleur du thème vivent dans `ui/theme.py` (repris en dur dans
`style.qss`) ; les statuts s'affichent via le widget `Badge` (icône + texte, jamais la
couleur seule) et les couleurs de cours/catégories sont centralisées là aussi.

Règle d'architecture UI : **les vues ne contiennent aucune logique métier.** Elles appellent
`core` et `scheduler`, puis affichent le résultat. Tout calcul de plus de 200 ms part dans un
`QThread` avec barre de progression — le recalcul complet en fait partie dès qu'il y a un
trimestre entier.

---

### 5.1 Vue **Importer**

- Zone de dépôt (glisser-déposer) + bouton *Parcourir* pour un `.json` ; la même zone
  accepte un `.ics` du centre étudiant (bouton *Importer un horaire (.ics)…*), importé
  directement avec le rapport de §2.7 affiché dans la zone de statut.
- Lien visible *Copier le prompt d'extraction* (met `PROMPT_EXTRACTION.md` dans le presse-papiers).
- **Rapport de validation** en tableau : une ligne par règle, statut ✅ / ⚠ / ❌, message.
- Aperçu des évaluations détectées avant confirmation, `source_excerpt` en infobulle.
- Résumé de réconciliation en cas de ré-import : « 2 nouvelles · 1 modifiée (date) · 5 inchangées ».
- Boutons : *Annuler* / *Importer*.

### 5.2 Vue **Cours & évaluations**

- `QTreeView` : cours → évaluations, sur un `QAbstractItemModel` maison.
- Colonnes : titre · type · poids · échéance · charge estimée (h) · statut · confiance.
- **Colonnes éditables** : `difficulty` (spinbox 1–5), `effort_multiplier`,
  `manual_hours_override`. Toute édition recalcule la charge affichée en direct.
- Surlignage : `confidence != high` en jaune, `due_date = null` en rouge.
- Panneau latéral de détail : `content_scope`, `notes`, `source_excerpt`, ressources.
- Filtres : trimestre, cours, « à vérifier », « à venir ».

### 5.3 Vue **Contraintes**

Le morceau le plus délicat de l'interface. **Deux niveaux, livrés dans cet ordre :**

**Niveau 1 (obligatoire, Phase 3) — tableau.**
`QTableView` éditable : `jour · début · fin · catégorie · libellé · couleur`. Plus un onglet
« exceptions » pour les dates ponctuelles (`date · début · fin · libellé`). Boutons Ajouter /
Dupliquer / Supprimer. C'est austère, mais complet et robuste.

**Niveau 2 (confort, Phase 5 ou plus tard) — grille hebdomadaire peignable.**
`QTableWidget` 7 colonnes × 28 lignes (30 min), sélection par glisser pour peindre une
catégorie, couleurs par catégorie, `QUndoStack` pour annuler.

> ⚠ Décision d'architecture : la grille est un **confort, jamais un bloqueur**. Le moteur ne
> lit que le modèle de données, jamais le widget. Si la grille coince, le tableau suffit et le
> projet avance. Ne pas retarder la Phase 4 pour une grille inachevée.

Aperçu commun aux deux niveaux : « temps libre disponible cette semaine : 23 h ».

### 5.4 Vue **Planning** (cœur de l'application)

- Calendrier hebdomadaire : `QWidget` personnalisé avec `paintEvent` — colonnes = jours, axe
  vertical = heures, blocs dessinés en rectangles arrondis.
  (Pas de `QCalendarWidget` : il ne propose pas de vue horaire.)
- Superposition : contraintes fixes en gris hachuré, séances de cours en gris plein, blocs
  d'étude en couleur du cours.
- Sur chaque bloc : sigle du cours, titre court de l'évaluation, durée.
- Interactions :
  - clic droit → *Fait* / *Partiellement fait (saisie des minutes)* / *Manqué* /
    *Verrouiller* / *Supprimer* ;
  - glisser-déposer pour déplacer → le bloc devient `locked` automatiquement ;
  - double-clic → détail de l'évaluation.
- Navigation : semaine précédente / suivante, « aujourd'hui », sélecteur de date.
- Bandeau supérieur : heures planifiées / heures faites cette semaine, alertes du jour.
- Bouton *Recalculer* avec aperçu du différentiel avant application
  (« 4 blocs déplacés, 1 ajouté, 0 supprimé — Appliquer / Annuler »).

### 5.5 Vue **Tableau de bord**

- Prochaines échéances (14 jours), triées, avec compte à rebours.
- Progression par évaluation : `QProgressBar` heures faites / `H_total`.
- Alertes : déficit, surcharge (`ρ < 1`), échéances sans date, examens en conflit le même jour.
- Répartition de la charge par cours — barres dessinées à la main, sans bibliothèque graphique.
- Historique : heures étudiées par semaine sur le trimestre.

### 5.6 Vue **Paramètres**

- Plage d'éveil, plafonds journaliers semaine / week-end, granularité, durées min et max de bloc.
- Préférences horaires : table d'heures avec curseur de préférence par tranche.
- Coefficients de l'algorithme (§4.9), avec *Réinitialiser aux valeurs par défaut*.
- Chemin de la base, sauvegarde / restauration, export-import des paramètres en JSON.

### 5.7 Dialogues

`ConstraintDialog` · `EvaluationEditDialog` · `ImportReportDialog` · `RecalcDiffDialog` ·
`BlockCompletionDialog` (minutes réelles + efficacité).

### 5.8 Vue **Statistiques** (phase 14)

Bilan de la session à partir de l'historique des blocs (statuts, `actual_minutes`,
`efficiency`) et du plan courant. Dans la barre latérale entre *Planning* et *Paramètres*.
Les agrégats vivent dans le module **pur** `scheduler/stats.py` (fonctions
`(blocks, evaluations, courses, now) -> dataclasses`, `now` toujours en paramètre) ; la vue
(`ui/views/stats_view.py`) ne fait qu'afficher.

Conventions de calcul :

- **bloc échu** : `end_at <= now` ; les blocs futurs sont exclus de tous les taux ;
- **heures faites** d'un bloc fait/partiel : `actual_minutes`, repli sur `planned_minutes` ;
- **taux de complétion** : blocs échus faits + partiels / blocs échus (tous statuts) ;
- **efficacité moyenne** : moyenne des `efficiency` des blocs *faits* qui en ont une ;
- **avance/retard** : heures faites (session) − heures planifiées échues, valeur signée.

Contenu (cartes) : 4 tuiles (heures faites, complétion, efficacité, avance/retard avec
icône tendance + libellé — jamais la couleur seule) ; « Heures par semaine » en barres
verticales QPainter (faites en accent sur piste planifiée, étiquettes directes sur les
barres non nulles seulement, libellés courts « s36 », semaine courante en accent) ;
« Heures par cours » via `HBarChart.set_progress_rows` (couleur du cours en ordre fixe
`theme.COURSE_COLORS` — la couleur suit le cours, jamais son rang ; valeur « x / y h ») ;
« Assiduité » en barre empilée (`widgets/stacked_bar.py`) aux couleurs de statut avec
séparateurs 2 px et légende icône + libellé + compte. États vides : chaque carte reste
lisible et dit quoi faire. Rafraîchie par `schedule_view.changed` et les imports.

---

## 6. Phases de développement

Une phase = une session de travail = un commit au minimum. **Tests écrits avant le code.**
Aucune phase ne commence tant que la précédente n'a pas validé sa « définition de terminé ».

---

### Phase 0 — Bootstrap ✅ *(faite)*

venv Python 3.12 · `git init` · `requirements.txt` / `requirements-dev.txt` · arborescence ·
`docs/ARCHITECTURE.md` · `CLAUDE.md` · `WORKLOG.md` · `.gitignore`.

---

### Phase 0.5 — Données réelles ⚠ *(à faire avant toute ligne de code)*

**Faire passer un vrai plan de cours dans le chat Claude et sauvegarder le JSON obtenu dans
`tests/fixtures/`.** Idéalement trois : un cours bien structuré, un cours flou (dates
manquantes), un cours à évaluations multiples.

Un importateur écrit contre un schéma hypothétique casse sur le premier fichier réel. Cette
phase existe précisément pour que ça n'arrive pas. Elle produit aussi la version finale de
`docs/PROMPT_EXTRACTION.md` et de `docs/schema/cours.schema.json`.

*Terminé quand* : au moins une fixture réelle est en dépôt, le schéma JSON est figé, le prompt
est rédigé.

---

### Phase 1 — Noyau données (sans UI)

À coder : `models.py` · `validation.py` · `importer.py` · `storage/db.py` ·
`storage/repositories.py` · CLI `python -m planner import <fichier.json>` et `list`.

Tests d'abord : import d'une fixture valide · rejet d'un JSON malformé · détection d'une somme
de poids ≠ 100 · réconciliation (upsert, champs manuels préservés) · aller-retour SQLite.

*Terminé quand* :
`python -m planner import tests/fixtures/ift1015.json && python -m planner list`
affiche correctement les évaluations, et `pytest` est vert.
**Ne pas toucher à l'UI.**

---

### Phase 2 — Moteur de planification (sans UI) — *phase la plus délicate*

À coder : `workload.py` (étape A) · `curve.py` (étape C) · `availability.py` (étape D) ·
`placer.py` (étape E) · `metrics.py` (étape G) · CLI `python -m planner plan --semaines 2`
affichant un agenda ASCII.

Tests d'abord :

- **charge** — monotonie en `w`, en `d`, en `u` ; bornes respectées ; `manual_override` prioritaire ;
- **courbe** — `Σ p = 1` ; décroissance en `t` ; plancher `λ` respecté ; redistribution sur un
  jour bloqué ;
- **disponibilité** — chevauchements exclus ; tampons ; capacité journalière ;
- **placement** — aucun chevauchement dur ; tailles de blocs valides ; plafonds journaliers ;
  déterminisme (deux appels ⇒ résultat identique) ;
- **bout en bout** — semaine vide, semaine saturée, deux examens le même jour, échéance dans
  2 jours, semestre en surcharge (`ρ < 1`).

**Puis calibration manuelle** contre un vrai trimestre (§4.9). Le code est structurel, les
nombres relèvent du jugement personnel : ils se règlent à la main, pas par génération de code.

*Terminé quand* : la sortie ASCII sur données réelles est jugée réaliste, et les valeurs
retenues sont figées par un test de régression.

---

### Phase 3 — UI : coquille, import, cours, contraintes (tableau)

`main_window.py` + navigation · vue Importer · vue Cours & évaluations · vue Contraintes
**niveau 1 (tableau uniquement)** · persistance des paramètres de base.

*Terminé quand* : je peux importer un JSON, régler difficulté et multiplicateur, saisir mes
vraies contraintes hebdomadaires, et tout relire après redémarrage — sans jamais toucher à la CLI.

---

### Phase 4 — UI : vue Planning

Calendrier hebdomadaire dessiné · affichage des blocs, contraintes et séances · menu contextuel
de statut · glisser-déposer et verrouillage · recalcul avec aperçu du différentiel ·
`rebalance.py` (étape F) branché.

*Terminé quand* : je génère un plan, je déplace un bloc, j'en marque un fait, je recalcule, et
le reste du planning ne part pas en vrille — `P_stabilité` fait son travail.

---

### Phase 5 — Tableau de bord, paramètres, confort

Vue Tableau de bord · vue Paramètres complète (coefficients réglables à chaud) · grille de
contraintes peignable **niveau 2** · thème sombre finalisé.

---

### Phase 6 — Export et intégrations locales

Export `.ics` (blocs + échéances) · impression / export PDF de la semaine · notification
Windows du prochain bloc (`QSystemTrayIcon`, aucune dépendance externe) · sauvegarde et
restauration de la base.

---

### Phase 7 — Packaging

`pyproject.toml` finalisé · PyInstaller `--onefile --windowed` · icône · README d'utilisation ·
procédure de mise à jour · vérification sur une session Windows propre.

---

### Ordre de priorité si le temps manque

`0.5 → 1 → 2 → 3 → 4` constituent le produit minimum réellement utile.
`5`, `6`, `7` sont du confort. Une application lancée par `python -m planner.app` depuis le
venv est parfaitement utilisable au quotidien : le `.exe` n'est pas une exigence.

---

## 7. Stratégie de test

| Niveau | Portée | Outil |
|---|---|---|
| Unitaire | `workload`, `curve`, `availability`, `placer`, `importer` | pytest, aucune I/O |
| Propriétés | invariants du placement : jamais de chevauchement, jamais hors fenêtre, déterminisme | pytest paramétré sur scénarios générés |
| Intégration | JSON réel → base → plan → métriques | pytest + SQLite temporaire |
| UI | ouverture des vues, import via l'interface, édition d'une contrainte | pytest-qt |
| Régression | métriques figées sur la fixture réelle après calibration | pytest, comparaison de valeurs |

Règle : **tout bug corrigé entre d'abord dans un test qui échoue.**

---

## 8. Risques identifiés

| Risque | Parade |
|---|---|
| Le JSON de Claude dérive d'une génération à l'autre | Schéma versionné + validation stricte + fixtures réelles en dépôt + `source_excerpt` pour audit rapide |
| Les constantes de charge sont fausses | Toutes paramétrables et exposées dans l'UI ; calibration explicite en Phase 2 ; `manual_hours_override` comme échappatoire |
| Le planning « saute » à chaque recalcul | Terme `P_stabilité` dans la fonction de coût + verrouillage des blocs déplacés à la main |
| Le semestre est objectivement en surcharge | Facteur `ρ` + alerte explicite, plutôt qu'un plan irréaliste |
| La grille de contraintes bloque le projet | Niveau 1 (tableau) livré d'abord, niveau 2 repoussé en Phase 5 |
| PySide6 incompatible avec Python 3.14 | Le venv est figé sur 3.12 |
| Dérive de portée | §0.3 énumère ce que l'app ne fait pas. Toute exception passe par une entrée dans le WORKLOG. |

---

## 9. Conventions

- **Langue** : code et identifiants en anglais, commentaires et interface en français.
- **Commits** : `phase<N>: <verbe> <objet>` — ex. `phase2: implement study curve with uniform floor`.
- **Une phase = une session Claude Code.** Contexte frais à chaque phase.
- **`WORKLOG.md`** : une entrée datée par tâche terminée, écrite avant le commit.
- **Ne jamais commiter** : PDF de plans de cours, `data/*.db`, `.venv/`.
- **Aucune dépendance ajoutée** sans une ligne de justification dans le WORKLOG.
