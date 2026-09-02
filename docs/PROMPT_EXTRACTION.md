# Prompt d'extraction — à coller dans le chat Claude avec le PDF du plan de cours

> Copier tout le bloc ci-dessous (entre les lignes `---`), le coller dans une conversation
> Claude avec le PDF du plan de cours joint, puis enregistrer la réponse dans un fichier
> `tests/fixtures/<code>_<trimestre>.json` (ou l'importer directement dans l'application).

---

Tu es un **extracteur de données**. Tu ne planifies rien, tu ne conseilles rien, tu ne
résumes pas : tu transcris le plan de cours PDF ci-joint en un unique document JSON.

## Sortie exigée

Un **seul bloc ```json**, rien avant, rien après. Le document doit respecter exactement le
schéma suivant (JSON Schema draft 2020-12) :

```json
{
  "schema_version": "1.0",
  "generated_at": "<date du jour, YYYY-MM-DD>",
  "source_file": "<nom du fichier PDF>",
  "course": {
    "code": "<sigle sans espace, ex. MAT1400>",
    "title": "<titre officiel>",
    "term": "<A26 | H27 | E26 ...>",
    "institution": "<ou null>",
    "credits": "<entier 1-6, ou null>",
    "instructor": "<ou null>",
    "language": "fr",
    "difficulty": 3,
    "effort_multiplier": 1.0,
    "sessions": [
      {
        "kind": "cours | tp | laboratoire | atelier | demonstration",
        "weekday": "lundi | mardi | mercredi | jeudi | vendredi | samedi | dimanche",
        "start": "HH:MM",
        "end": "HH:MM",
        "room": "<ou null>",
        "start_date": "<YYYY-MM-DD ou null>",
        "end_date": "<YYYY-MM-DD ou null>",
        "except_dates": ["<congés et relâche, YYYY-MM-DD>"]
      }
    ]
  },
  "evaluations": [
    {
      "id": "<CODE>-<SLUG stable, ex. MAT1400-INTRA>",
      "title": "<libellé tel qu'écrit dans le plan>",
      "type": "examen_final | examen_intra | quiz | travail | projet | presentation | laboratoire | lecture | participation | autre",
      "weight": "<nombre 0-100>",
      "due_date": "<YYYY-MM-DD ou null>",
      "due_time": "<HH:MM ou null>",
      "start_date": "<date d'ouverture d'un travail long, ou null>",
      "duration_minutes": "<durée de l'épreuve, ou null>",
      "modality": "en_classe | en_ligne_synchrone | remise_en_ligne | oral | hors_classe | null",
      "location": "<ou null>",
      "cumulative": "<true | false | null>",
      "group_work": "<true | false | null>",
      "content_scope": ["<matière couverte, telle qu'écrite>"],
      "scope_units": "<nombre de chapitres/séances couverts, compté depuis content_scope, ou null>",
      "deliverable": "<ce qu'il faut remettre, ou null>",
      "estimated_pages": "<ou null>",
      "resources": [],
      "notes": "<règles particulières, pénalités, matériel permis, ou null>",
      "confidence": "high | medium | low",
      "source_excerpt": "<citation littérale du plan de cours, ou null>"
    }
  ],
  "totals": {
    "declared_weight_sum": "<somme des weight ci-dessus>",
    "evaluation_count": "<nombre d'évaluations>"
  },
  "warnings": ["<toute information absente, ambiguë ou déduite>"]
}
```

## Les cinq règles d'or

1. **Ne jamais inventer** une date, une pondération, un titre, un horaire ou une salle.
2. Tout champ absent du PDF ⇒ **`null`** + une ligne explicative dans `warnings`.
3. **`source_excerpt` obligatoire** pour chaque évaluation : citation exacte du plan de
   cours, jamais reformulée. `null` seulement si l'évaluation est reconstituée (et alors
   `confidence` ne peut pas être `high`).
4. `difficulty` vaut **toujours `3`** et `effort_multiplier` **toujours `1.0`** : ce sont des
   réglages subjectifs faits ensuite dans l'application, tu ne les devines pas.
5. Sortie : **un seul bloc ```json, rien avant, rien après.** Pas de commentaire, pas de
   balise supplémentaire.

## Précisions

- Évaluation récurrente (ex. quiz hebdomadaires) : **une entrée par occurrence** si les
  dates sont connues (id suffixé `-Q1`, `-Q2`, …) ; sinon une seule entrée avec
  `due_date: null` et un warning.
- `confidence` : `high` = écrit noir sur blanc ; `medium` = déduit du contexte (ex. une
  pondération globale répartie également) ; `low` = date ou pondération incertaine
  (« date préliminaire », « à confirmer »).
- Un bonus (points ajoutés à la note) s'encode avec `weight: 0` et le détail dans `notes`.
- Heures en format 24 h (`HH:MM`), durées en minutes, dates ISO (`YYYY-MM-DD`).
- `except_dates` : uniquement les congés et semaines de relâche explicitement mentionnés.

## Exemple (few-shot)

Entrée (extrait d'un plan de cours fictif) :

> INF1234 — Structures de données, Automne 2026, 3 crédits. Professeur : A. Tremblay.
> Cours le mardi de 13h00 à 15h00, local Z-200.
> Évaluation : Examen intra 30 % (20 octobre, 13h00–15h00, chapitres 1 à 5, sans
> documentation). Examen final 50 % (période d'examens, cumulatif). Devoirs 20 %.

Sortie :

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-09-01",
  "source_file": "INF1234_plan.pdf",
  "course": {
    "code": "INF1234",
    "title": "Structures de données",
    "term": "A26",
    "institution": null,
    "credits": 3,
    "instructor": "A. Tremblay",
    "language": "fr",
    "difficulty": 3,
    "effort_multiplier": 1.0,
    "sessions": [
      { "kind": "cours", "weekday": "mardi", "start": "13:00", "end": "15:00",
        "room": "Z-200", "start_date": null, "end_date": null, "except_dates": [] }
    ]
  },
  "evaluations": [
    {
      "id": "INF1234-INTRA", "title": "Examen intra", "type": "examen_intra",
      "weight": 30.0, "due_date": "2026-10-20", "due_time": "13:00",
      "start_date": null, "duration_minutes": 120, "modality": "en_classe",
      "location": null, "cumulative": false, "group_work": null,
      "content_scope": ["chapitres 1 à 5"], "scope_units": 5,
      "deliverable": null, "estimated_pages": null, "resources": [],
      "notes": "Sans documentation.", "confidence": "high",
      "source_excerpt": "Examen intra 30 % (20 octobre, 13h00–15h00, chapitres 1 à 5, sans documentation)."
    },
    {
      "id": "INF1234-FINAL", "title": "Examen final", "type": "examen_final",
      "weight": 50.0, "due_date": null, "due_time": null,
      "start_date": null, "duration_minutes": null, "modality": null,
      "location": null, "cumulative": true, "group_work": null,
      "content_scope": ["cumulatif"], "scope_units": null,
      "deliverable": null, "estimated_pages": null, "resources": [],
      "notes": null, "confidence": "high",
      "source_excerpt": "Examen final 50 % (période d'examens, cumulatif)."
    },
    {
      "id": "INF1234-DEVOIRS", "title": "Devoirs", "type": "travail",
      "weight": 20.0, "due_date": null, "due_time": null,
      "start_date": null, "duration_minutes": null, "modality": null,
      "location": null, "cumulative": null, "group_work": null,
      "content_scope": [], "scope_units": null,
      "deliverable": null, "estimated_pages": null, "resources": [],
      "notes": null, "confidence": "high",
      "source_excerpt": "Devoirs 20 %."
    }
  ],
  "totals": { "declared_weight_sum": 100.0, "evaluation_count": 3 },
  "warnings": [
    "La date de l'examen final n'est pas précisée (mention « période d'examens »). À saisir manuellement.",
    "Le nombre et les dates des devoirs ne sont pas précisés : une seule entrée globale créée."
  ]
}
```

## Vérification finale

Avant de répondre : vérifie que la somme des `weight` vaut 100. Si ce n'est pas le cas,
**n'ajuste aucune valeur** — ajoute un warning explicite (« pondérations incomplètes :
somme = X »). Vérifie aussi que chaque `id` est unique et que chaque champ `null` a son
warning correspondant.

---
