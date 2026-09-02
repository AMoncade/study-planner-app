# État du projet — reprise rapide

> Écrit pour reprendre le projet dans deux semaines sur une autre machine.
> Dernière mise à jour : 2026-09-02. Détails techniques : `docs/ARCHITECTURE.md` ;
> historique : `WORKLOG.md`.

## Reprise sur une machine neuve

```
git clone https://github.com/AMoncade/study-planner-app.git
cd study-planner-app
py -3.12 -m venv .venv                # 3.12 obligatoire (PySide6)
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install -e .
```

Recréer `.env` à la racine (jamais commité, une variable par ligne, aucune valeur ici) :

- `DATABASE_URL` — chaîne **Transaction pooler** du projet Supabase principal :
  tableau de bord Supabase → le projet → Connect → Transaction pooler (port 6543).
- `DATABASE_URL_TEST` — même chose pour le **second** projet Supabase, jetable
  (obligatoire pour lancer les tests Postgres : ils TRONQUENT la base visée).
- `APP_PIN` — le code PIN de l'interface mobile (celui que tu utilises déjà).

Puis :

```
.venv\Scripts\python.exe -m planner doctor          # tout doit être OK ou ATTENTION
.venv\Scripts\python.exe -m planner sync-restore    # récupère les données depuis Supabase
.venv\Scripts\python.exe -m pytest                  # 126+ tests verts attendus
```

## Lancer

```
.venv\Scripts\python.exe -m planner.app                            # app bureau
.venv\Scripts\uvicorn.exe --factory planner.web.api:create_app --host 0.0.0.0   # API + page mobile
```

Depuis le téléphone, sur le même wifi : `http://<ip-du-pc>:8000` (l'IP locale s'obtient
avec `ipconfig`), entrer le PIN. « Ajouter à l'écran d'accueil » installe la page.

## Le rituel de synchronisation

1. `sync-push` avant de partir (réplique tout SQLite → Postgres) ;
2. cocher les blocs Fait / Manqué / Partiel sur le téléphone ;
3. `sync-pull` au retour (rapatrie uniquement les statuts).

`sync-push` refuse s'il y a des statuts cochés non rapatriés (`--force` pour écraser).

## Phases livrées

- **0** — bootstrap : venv 3.12, arborescence, `docs/ARCHITECTURE.md`.
- **0.5** — schéma JSON, prompt d'extraction, 4 fixtures réelles (cours A26).
- **1** — noyau données : modèles, validation, importateur (réconciliation), SQLite, CLI.
- **2** — moteur de planification (charge, courbe, disponibilité, placement EDF, métriques).
- **3** — UI : coquille, Importer, Cours et évaluations, Contraintes (tableau).
- **4** — vue Planning dessinée + recalcul incrémental (P_stabilité, verrouillage).
- **5** — tableau de bord, paramètres persistés, grille de contraintes peignable.
- **6** — export .ics, PDF de la semaine, notification tray, sauvegarde/restauration.
- **7** — PyInstaller : `build_exe.ps1` → `dist\PlanEtudes.exe`.
- **8** — adaptateur Postgres/Supabase (a), durcissement + garde-fous tests (b),
  `sync-push`/`sync-pull` (c), refus d'écraser des statuts non rapatriés (d).
- **9** — API FastAPI + page mobile PIN ; Vercel préparé (`api/index.py`), non déployé.
- **10** — `sync-restore`, `doctor`, ce document.

## Décisions d'architecture à ne pas défaire

- **SQLite est la source de vérité.** Postgres n'est qu'une copie de travail :
  `sync-push` peut la détruire et la reconstruire à tout moment. Toute édition de
  fond (cours, contraintes, recalculs) se fait sur le bureau.
- **Le recalcul web est un aperçu, jamais persisté.** Un recalcul persistant côté web
  créerait des blocs inconnus de SQLite (orphelins), détruits au `sync-push` suivant :
  l'utilisateur croirait son planning enregistré alors qu'il est condamné.
- **Les tests Postgres sont destructifs, base jetable obligatoire.** Ils ne lisent que
  `DATABASE_URL_TEST` et refusent une URL identique à `DATABASE_URL` ; ne contourne pas
  ce garde-fou (l'opt-in `PG_TEST_ALLOW_TRUNCATE=1` existe mais ne devrait jamais
  servir en usage normal).
- Le moteur (`scheduler/`) reste une fonction pure et déterministe : pas de `random`,
  pas de `datetime.now()` caché — l'instant courant est toujours un paramètre.

## Pièges connus

- `unpulled_changes` détecte un écart de statut mais **ne sait pas de quel côté il
  vient** : son conseil « sync-pull d'abord » est faux si l'écart vient du bureau
  (bloc coché dans l'app PySide6 après le dernier push) — dans ce cas
  `sync-push --force` est le bon choix.
- Le champ `note` des blocs circule dans les deux sens (push ET pull) : ne l'éditer
  que d'un seul côté à la fois, sinon la dernière synchronisation gagne.
- `sync-push` recopie ligne par ligne à travers le pooler : plusieurs secondes pour un
  trimestre. Jamais depuis une fonction Vercel (délai + TRUNCATE en plein service).
- `uvicorn[standard]` ne sert qu'en local ; Vercel apporte son propre serveur
  (il est dans `requirements-web.txt` par simplicité, inoffensif mais inutile là-bas).
- Les variables d'environnement de Vercel (`DATABASE_URL`, `APP_PIN`) se saisissent
  dans le tableau de bord Vercel (Settings → Environment Variables), pas via `.env` —
  le `.env` local n'est jamais déployé.
- La colonne `end` est un mot réservé Postgres : l'adaptateur `pg.py` réécrit chaque
  SQL (`\bend\b` → `"end"`). Ne pas nommer une future colonne d'un autre mot réservé.

## À faire

1. **Vérifier 4 données d'extraction douteuses** (vue Cours, surlignées) :
   `MAT1000-Q1` et `MAT1000-Q2` (confiance *low* : dates préliminaires, pondération
   10 % répartie par déduction), `MAT1400-FINAL` (confiance *medium* : horaire « à
   confirmer », double schéma de pondération), `MAT1600-QUIZTP` (sans date et à
   pondération nulle : bonus, non planifié).
2. **Saisir les vraies disponibilités** dans la vue Contraintes (travail, sport,
   sommeil, transport) — le plan n'a de sens qu'avec elles.
3. **Calibrer les coefficients** (`ARCHITECTURE.md` §4.9) après quelques semaines
   d'usage réel : comparer les charges estimées au temps passé, ajuster `B_TYPE` puis
   `ALPHA` puis `LAMBDA` dans la vue Paramètres, et re-figer `tests/test_integration.py`.
