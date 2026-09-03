# Journal de travail — Plan-Études

Une entrée par tâche terminée, la plus récente en haut.

---

## 2026-09-03 — Phase 14 : vue Statistiques

- **`scheduler/stats.py`** (pur, `now` en paramètre) : `compute_overview` (heures faites,
  taux de complétion = blocs échus faits+partiels / blocs échus, efficacité moyenne des
  blocs faits qui en ont une, écart signé heures faites − heures planifiées échues),
  `weekly_hours` (semaines ISO contiguës, vides incluses), `hours_by_course`
  (`color_index` = rang du cours : la couleur suit le cours), `attendance` (fait /
  partiel / manqué / non renseigné des blocs échus). Tests `tests/test_stats.py`.
- **`ui/views/stats_view.py`** : 4 tuiles (avance/retard en vert/orange avec icône
  tendance + libellé), « Heures par semaine » (`widgets/week_bars.py`, barres QPainter,
  faites en accent sur piste planifiée, étiquettes 11 px tabulaires sur barres non
  nulles, semaine courante en accent), « Heures par cours »
  (`HBarChart.set_progress_rows`, valeur « x / y h »), « Assiduité »
  (`widgets/stacked_bar.py` + légende icône/libellé/compte). États vides guidés.
- Navigation : entrée « Statistiques » entre Planning et Paramètres (icône `chart`
  + icônes `minus-circle`/`help-circle`/`trend-up`/`trend-down` dans `ui/icons.py`) ;
  rafraîchie sur `schedule_view.changed` et après import. `HBarChart` passé aux jetons
  de `theme`. ARCHITECTURE §5.8 ajouté ; capture `screenshots/stats.png` ; toutes les
  captures régénérées. pytest 159 verts, ruff propre.

---

## 2026-09-03 — Finition post-merge (phases 11+12+13 sur main)

- Merge des branches phase11-curve, phase12-ics, phase13-ui dans `main` ; pytest 136 verts
  (Postgres inclus), ruff propre.
- Calendrier : titres de blocs élidés sur une ligne (les titres longs « Examen intra/final »
  chevauchaient la ligne d'heure).
- Recalcul appliqué sur la base réelle avec le nouveau moteur : 175 blocs, 9-17 h/semaine
  réguliers, couverture 100 % (sauvegarde : data/plan_etudes.avant-recalcul-20260903.db).
- Captures d'écran régénérées avec le plan peuplé (screenshots/).

---

## 2026-09-02 — Phase 13 : refonte visuelle (thème sombre × bleu UdeM)

- **Jetons** : `ui/theme.py` centralise fonds (#131720/#10141c/#161b25/#1a202b),
  séparateurs #232a36, bordures #2d3542, texte (#e8ebf0/#9da6b5/#6a7484), accents
  (marque #0057AC, primaire #1f6fd0, interactif #3987e5), statuts (#0ca30c/#fab219/
  #ec835a/#d03b3b), couleurs de cours validées daltonisme (#d95926/#199e70/#c98500/
  #9085e9) et catégories de contraintes. `week_calendar.COURSE_COLORS` et
  `constraint_grid.CATEGORY_COLORS` réexportent depuis `theme`.
- **`style.qss` réécrit** : Segoe UI, boutons 32 px rayon 7, un primaire par vue
  (`QPushButton[kind="primary"]`), bouton danger, focus 2 px #3987e5, champs avec
  propriété `error`, QToolBar/QGroupBox/QProgressBar/QScrollBar/QSplitter/QMenu/
  QDialog/QCheckBox/QComboBox/QHeaderView couverts, libellés typés par propriété
  `role` (viewTitle 20 px, sectionTitle, secondary, caption, tuiles).
- **Barre latérale fixe 232 px** (`main_window.py`) : pastille « P » UdeM + titre +
  session, 6 icônes SVG inline 18 px trait 1.8 (`ui/icons.py`, rendu QSvgRenderer 2×),
  item actif en lavis accent, pied « ● Synchronisé · il y a N min » (mtime de la base).
  Tray en #0057AC. Le `QSplitter` rétrécissable est remplacé par un layout fixe.
- **`Badge`** (`ui/widgets/badge.py`) : icône SVG + texte, fond teinté 10 %, bordure
  40 %, rayon 12 — remplace les emoji ✅⚠❌🔴🟠🟡 dans import, paramètres, planning,
  tableau de bord et grille ; cellules du rapport d'import en icône + mot.
- **WeekCalendar** : fond #161b25, gridlines chaque heure, heures 10 px, colonne du
  jour teintée 5 %, ligne « maintenant » 2 px + point (via `now_provider` injectable),
  blocs 16 %/55 % (fait 34 %/80 % + ✓, manqué 8 % + texte discret), séances et
  contraintes en hachures grises 45°, rayon 6, texte 11 px 600 + heure tabulaire 10 px.
- **Grille de contraintes** : rangées 30 px, chips de catégorie arrondies à pastille
  (`CategoryChips`, API `currentText`/`setCurrentText` compatible tests), Ctrl+Z
  branché sur l'undo existant, en-têtes lisibles.
- **Tableau de bord** : 4 tuiles (Cette semaine, Couverture — `metrics.coverage` du
  recalcul à blanc déjà exécuté pour les alertes —, Prochaine échéance, Assiduité
  14 jours), alertes en badges, barres de progression 8 px en couleur de cours,
  aucune nouvelle métrique lourde.
- **Bug corrigé** (`constraints_view.py`) : la bordure d'erreur du dialogue de
  contrainte est maintenant réinitialisée quand l'erreur est corrigée (propriété QSS
  `error` + repolish, début **et** fin marqués).
- Marges 24 px / espacement 14 px sur toutes les vues, lignes de table 34 px,
  `setAlternatingRowColors` ; `scripts/screenshots.py` produit `screenshots/*.png`
  (6 vues + onglet grille) pour validation. `ARCHITECTURE.md` §5.0 mis à jour.
  Aucune dépendance ajoutée (QtSvg fait partie de PySide6).

---

## 2026-09-02 — Phase 12 : import de l'horaire .ics du centre étudiant

- `core/ics_import.py` : parse le `.ics` UdeM (icalendar), développe les RRULE avec
  dateutil (EXDATE → `except_dates`, une séance par jour de semaine, bornes = première/
  dernière occurrence), convertit les heures `America/Toronto` en heure locale naïve
  (zoneinfo, stdlib). Rattachement au cours par sigle dans SUMMARY/DESCRIPTION
  (`[A-Z]{2,4}[ -]?\d{4}` normalisé). Les séances vont dans la table `sessions` (pas dans
  `constraints` : le moteur les bloque déjà via §4.4 et elles restent liées au cours).
  Réconciliation par `(weekday, start, end)` : ré-import idempotent, `kind` du JSON
  conservé à la mise à jour, séances hors `.ics` jamais supprimées.
- Examens (*intra*/*final*/*quiz*/*examen*, insensible casse/accents) : pas de séance ;
  confrontation aux évaluations de type compatible → confirmé / conflit / sans évaluation
  connue. `--apply-exam-dates` applique la date du `.ics` sur la candidate la plus proche
  et invalide ses blocs planifiés (même logique que §2.5).
- CLI `import-ics <fichier.ics> [--apply-exam-dates]` (avec sauvegarde préalable de la
  base) ; rapport texte partagé (`format_ics_report`). Vue Importer : bouton
  « Importer un horaire (.ics)… » + dépôt d'un `.ics` routé par extension, rapport dans
  la zone de statut — volontairement minimal (refonte visuelle sur une autre branche).
- Nouvelles fonctions repos : `insert_session`, `update_session_schedule`,
  `update_evaluation_due_at`. Aucune dépendance ajoutée (icalendar et python-dateutil
  étaient déjà là). ARCHITECTURE : nouveau §2.7, §5.1 amendé.
- Fixture `tests/fixtures/horaire_a26.ics` (4 cours MAT, RRULE hebdo sept→déc, EXDATE
  Action de grâce + relâche, examen confirmé, examen en conflit, quiz sans évaluation,
  sigle inconnu IFT-1015, rendez-vous sans sigle) ; 11 tests `test_ics_import.py` +
  1 test UI. 140 tests, exit 0 ; ruff propre.
## 2026-09-02 — Phase 11 : courbe aplatie, « régulier dès maintenant »

Décision utilisateur actée : étude constante chaque semaine dès le début du semestre,
montée douce avant les examens (l'ancien réglage donnait ~1 h/semaine en septembre et
29-32 h/semaine en décembre — l'app paraissait « vide » à l'ouverture).

- `scheduler/curve.py` : la fenêtre d'un **examen** (intra/final) couvre désormais
  **tout l'horizon restant** — `depth = max(D(type), jours jusqu'à l'échéance)` — pour
  que l'étude commence aujourd'hui même quand l'examen est à 14 semaines. Sans cela,
  une fenêtre fixe (même 28-42 j) laissait les 2-3 premières semaines du trimestre
  quasi vides sur les vraies données.
- `config.py` : `D_TYPE` — `examen_final` 14 → 84 j et `examen_intra` 14 → 42 j
  (minimums, voir ci-dessus), `quiz` 5 → 7 j, `presentation` 10 → 14 j (travail/projet
  inchangés à 21 j) ; courbe aplatie — `lam` 0,35 → 0,60, `tau_ratio` 3,0 → 1,5
  (τ = D/1,5 : décroissance douce).
- `scheduler/curve.day_targets` : les cibles journalières restent **fractionnaires**
  (l'arrondi 0,5 h est supprimé) — sur une fenêtre de ~100 j les cibles valent ~0,25 h
  et l'arrondi les faisait disparaître entièrement.
- `scheduler/placer.py` : **carry jour à jour** dans le parcours de fenêtre (du plus
  lointain vers l'échéance) — la courbe aplatie produit des cibles sous `bloc_min`
  (1 h) ; sans carry elles n'étaient jamais placées et tout le volume partait dans le
  report massif, entassé au début de fenêtre (semaines à 32 h, semaines à 0 h). Le
  carry agrège les fractions en blocs plaçables tous les 2-4 jours et dérive vers
  l'échéance : la veille récupère le reliquat et reste le jour le plus chargé. Le
  reliquat final se place au plus PRÈS de l'échéance (au lieu du plus loin).
- `scheduler/placer.py` : **amorce** du carry — au premier jour de fenêtre ayant de
  la capacité, la demande est montée à `bloc_min` pour déposer un premier bloc
  immédiatement ; le carry devient négatif et rembourse l'avance (masse conservée).
  Sans amorce, chaque évaluation accumulait 3-5 jours de cibles fractionnaires avant
  son premier bloc : plan généré un mercredi → rien avant le dimanche, semaine
  courante vide (le symptôme d'origine). Après : mer 4 h, jeu 4 h, ven 1 h sur les
  fixtures réelles ; test `test_first_days_are_not_empty` (3 premiers jours ≥ 2 h).
- Aucun lissage hebdomadaire global nécessaire : fenêtres-horizon + courbe plate +
  carry suffisent (semaine max 23 h sur 32 h de capacité théorique).
- Nouveaux tests `test_weekly_balance.py` (scénario semestre synthétique : quiz hebdos,
  intras à 6 semaines, finaux à ~15 semaines) : chaque semaine > 0 h, première semaine
  ≥ 3 h — y compris **sans aucun quiz** (examens seuls, cas réel de début de session),
  ratio semaine max / semaine médiane ≤ 3, capacité hebdo respectée, veille d'examen
  = jour le plus chargé de sa fenêtre.
- Tests adaptés (ancienne forme encodée) : `test_curve.py` — fenêtre d'examen = horizon
  complet, profondeur fixe testée sur un type non-examen, conservation de la masse sur
  fenêtre longue (remplace le test d'arrondi 0,5 h) ; `test_integration.py::
  test_full_semester_plan` — les finaux de décembre tiennent dans leur fenêtre-horizon :
  plus aucun déficit sur le trimestre réel (l'assertion « déficit signalé » devient
  « aucun déficit, couverture ≥ 0,95 »).
- Distribution hebdo sur les 4 fixtures réelles (sept → déc, 16 semaines) : avant
  `1 1 1 2 9 16 17 21 3 1 4 2 8 32 32 7` (ratio pic/médiane 4,6, couverture 0,90) ;
  après `4 9 12 14 17 18 16 14 7 9 13 11 11 12 9 2` (ratio 1,46, couverture 1,00,
  zéro déficit).
- `ARCHITECTURE.md` §4 mis à jour (fenêtre-horizon des examens, table D, λ/τ, correctif
  granularité, pseudo-code de l'étape E avec carry vers l'échéance, philosophie
  « régulier dès maintenant »).

---

## 2026-09-02 — Phase 10 : reprise sur machine neuve (sync-restore, doctor, ETAT.md)

- `sync.restore(pg_conn, sqlite_conn, force=False)` : inverse de push — reconstruit la
  base SQLite complète depuis Postgres (7 tables, id conservés, transaction unique
  SQLite, colonnes lues côté Postgres via information_schema puisque SQLite peut être
  vide). Refuse si SQLite contient déjà des cours (`LocalDataExistsError`, nouvelle
  exception) sauf `--force` ; la CLI `sync-restore` sauvegarde le fichier d'abord.
  Testé : égalité table par table + identité des id, refus sans force (base intacte),
  force qui passe, et compteurs SQLite corrects après restore (INTEGER PRIMARY KEY
  repart de max+1 nativement — pas de recalage nécessaire, prouvé par insertion).
- `doctor.py` + CLI `doctor` : Python, paquets de requirements.txt, clés d'environnement
  (présente/absente SEULEMENT), avertissement si base de test = base réelle
  (utilisateur+hôte via urllib.parse), base SQLite (chemin + comptes), Postgres
  (connexion, version du schéma, comptes), blocs divergents (`unpulled_changes`).
  Sortie ligne par ligne OK/ATTENTION/BLOQUANT, code non nul si bloquant.
  Vérifié en réel : environnement sain, exit 0, aucune valeur affichée.
- `docs/ETAT.md` : document de reprise (machine neuve pas à pas, lancement bureau/API/
  téléphone, rituel push→cocher→pull, phases 0-10, décisions à ne pas défaire avec
  leurs raisons, pièges connus — dont le conseil parfois faux d'unpulled_changes et le
  champ note bidirectionnel — et les 3 tâches restantes).
- README : lien vers ETAT.md + liste complète des commandes CLI.
- 129 tests, exit 0 ; ruff propre.

---

## 2026-09-02 — Phase 9 : API web + page mobile minimale

- **Dépendances ajoutées** : `fastapi` + `uvicorn[standard]` (API mobile) dans
  requirements.txt ; `httpx` (TestClient) dans requirements-dev.txt.
  `requirements-web.txt` = dépendances de l'API SEULEMENT (sans PySide6), référencé par
  `api/requirements.txt` — le runtime Python de Vercel installe le requirements situé
  à côté de la fonction.
- `web/api.py` (`create_app`, lancement local `uvicorn --factory planner.web.api:create_app`) :
  - GET /api/health (sans auth) ; GET /api/week?offset= (blocs de la semaine avec code
    du cours + titre d'évaluation, jointure SQL portable via substr) ;
  - POST /api/blocks/{id}/status (Literal pydantic → 422 sur statut invalide, 404 si
    bloc inconnu, retourne le bloc mis à jour) ;
  - POST /api/recalculate : **APERÇU PUR, décision imposée** — jamais
    d'apply_rebalance, rien d'écrit (un recalcul persistant créerait des orphelins que
    sync-push détruirait) ; renvoie diff kept/moved/added/removed + semaine simulée.
- Auth : PIN dans APP_PIN, en-tête X-App-Pin exigé partout sauf /api/health,
  `secrets.compare_digest` ; sans APP_PIN, `create_app()` REFUSE de démarrer.
- Connexions : une par requête (`connect_pg(migrate=False)`, fermée en finally) ;
  nouvelle CLI `pg-migrate` pour migrer une fois au déploiement.
- `web/static/index.html` : page unique sans framework ni CDN — PIN en sessionStorage,
  semaine en liste par jour, gros boutons, Fait/Manqué/Partiel (minutes), navigation
  semaine, Recalculer avec mention « aperçu, non enregistré » ; `manifest.json`
  standalone (Ajouter à l'écran d'accueil), pas de service worker.
- Vercel : `api/index.py` (sys.path + create_app) + `vercel.json` (rewrites vers la
  fonction, includeFiles src/**). Non déployé.
- `tests/test_api.py` (8 tests, sautés sans DATABASE_URL_TEST, seeding par sync.push
  force=True) : health sans PIN, 401 sans/mauvais PIN, semaine étiquetée, 422 statut
  invalide, statut persisté, 404 bloc inconnu, recalculate strictement sans effet
  (mêmes id avant/après), page et manifest servis. **8/8 verts.**
- Suite complète : **126 tests, exit 0** (le résumé final de pytest est avalé par la
  console Windows, le code de sortie fait foi).

---

## 2026-09-02 — Phase 8d : push refusé si des statuts web attendent un pull

- `sync.unpulled_changes(sqlite_conn, pg_conn)` : id des blocs dont
  status/actual_minutes/efficiency/note diffèrent entre les deux bases (appariement
  par id, blocs absents d'un côté ignorés).
- `sync.push(..., force=False)` : si des changements non rapatriés existent, lève
  `UnpulledChangesError` (nouvelle exception dans `core/errors.py`, porte la liste
  des id) **avant tout TRUNCATE** — un push oublié ne détruit plus en silence ce qui
  a été coché sur mobile. `force=True` passe outre.
- CLI `sync-push` : attrape l'exception, affiche le nombre de blocs concernés,
  code de sortie 2 ; option `--force` ajoutée.
- Tests : push refusé avec Postgres strictement intact (statut coché compris),
  `--force` passe outre, push propre passe sans force. Découverte en test : le
  premier push d'une session refuse légitimement les restes du run précédent — le
  push initial du test est donc `force=True` (réplique initiale faisant autorité).
- 118 tests verts (7 sync), ruff propre.

---

## 2026-09-02 — Phase 8c : synchronisation SQLite <-> Postgres

- `sync.py` : `push` (réplique intégrale SQLite → Postgres, transaction unique
  tout-ou-rien, TRUNCATE ... RESTART IDENTITY CASCADE, recopie brute par
  `pragma_table_info` — indépendante du mapping des modèles — avec **id d'origine
  conservés**, puis **recalage des séquences IDENTITY** via
  `setval(pg_get_serial_sequence(t,'id'), max(id)+1, false)` : sans lui, la première
  écriture web violerait l'unicité, testé) ; `pull` (statuts seulement :
  status/actual_minutes/efficiency/note des blocs appariés par id, ne crée ni ne
  supprime rien, ne touche à aucune autre table, orphelins comptés et ignorés,
  transaction unique côté SQLite).
- CLI `sync-push` / `sync-pull` : `backup_database()` du fichier SQLite avant chacun
  (pull modifie SQLite ; push par précaution), compteurs affichés. `sync-pull` ouvre
  Postgres avec `migrate=False` (lecture seule du schéma déjà en place).
- `tests/test_sync.py` (sautés sans DATABASE_URL_TEST, même garde-fou d'égalité que le
  smoke) : comptes ET id identiques table par table après push ; insertion post-push
  sans collision (id = max+1) ; aller-retour Fait côté web → pull → SQLite reflète
  statut/minutes/efficacité et rien d'autre ne change ; double push idempotent et
  Postgres redevient l'exact reflet de SQLite. **4/4 verts contre la base de test.**
- Suite complète : 115 tests verts (104 SQLite + 7 smoke PG + 4 sync).

---

## 2026-09-02 — Phase 8b : durcissement de l'adaptateur Postgres

- **Sécurité du test de fumée** (il TRONQUE les tables) : il ne lit plus jamais
  DATABASE_URL — connexion uniquement via `DATABASE_URL_TEST` passée explicitement à
  `connect_pg(url=...)`, skip si absente, et échec explicite si elle est égale à
  DATABASE_URL (opt-in `PG_TEST_ALLOW_TRUNCATE=1` pour l'assumer). Avertissement
  « test destructif » en tête de fichier. Sans base de test configurée, les 6 tests
  sont sautés : un simple `pytest` ne peut plus effacer la base réelle.
- `connect_pg(url=None, migrate=True)` : `migrate=False` saute `migrate_pg` (chemin
  chaud d'une future API — économise deux allers-retours par connexion ; migrer au
  démarrage du service).
- Migrations sûres en concurrence : `pg_advisory_xact_lock` (transactionnel, compatible
  pooler en mode transaction, contrairement au verrou de session) + relecture de la
  version après verrou + `IF NOT EXISTS` sur tous les CREATE. Deux connexions
  simultanées sur une base neuve ne se marchent plus dessus.
- Vérifié en réel (non destructif) : migration idempotente sous verrou (version 1/1)
  et connexion `migrate=False` fonctionnelle contre le pooler Supabase.

### Complément (message complet reçu) — points 2 fin, 3 et 4

- `schema_version` : contrainte mono-ligne (`id INTEGER PRIMARY KEY CHECK (id = 1)`) —
  une double insertion concurrente échoue proprement (CheckViolation vérifiée en réel).
  La table préexistante sous l'ancienne forme est recréée **sous verrou en préservant
  la version courante** (détection via information_schema).
- `validation.py` / `cross_course_conflicts` (règle 9) : `date(x)` → `substr(x, 1, 10)`,
  identique sur SQLite et Postgres puisque `due_at` est du texte ISO. Tests SQLite qui
  l'exercent (CLI import, dashboard) toujours verts.
- Smoke test : + `test_cross_course_conflicts_on_postgres`. Nota : les 4 fixtures
  réelles n'ont AUCUN examen le même jour (finaux les 10/11/16/17 décembre) — le test
  vérifie l'exécution sans erreur sur les vraies données puis fabrique un conflit par
  UPDATE non commité (rollback ensuite) pour prouver la détection.
- Vérifications : sans DATABASE_URL_TEST → 7 tests SAUTÉS, 104 SQLite verts ; garde-fou
  d'égalité → échec explicite confirmé ; avec DATABASE_URL_TEST + opt-in
  PG_TEST_ALLOW_TRUNCATE=1 (base inspectée d'abord : uniquement les données de fixtures
  du smoke précédent) → **7/7 verts contre le pooler Supabase**.

---

## 2026-09-02 — Phase 8a : adaptateur Postgres (Supabase) à côté de SQLite

- **Dépendances ajoutées** : `psycopg[binary]>=3.2` (client Postgres pour le backend web
  futur) et `python-dotenv>=1.0` (lecture de DATABASE_URL depuis `.env`, jamais commité —
  entrée `.env` ajoutée au `.gitignore`).
- `storage/pg.py` : `connect_pg()` (dotenv + `prepare_threshold=None`, obligatoire avec
  le pooler Supabase en mode transaction) ; `PgConnection` qui imite le contrat sqlite3
  consommé par `repositories.py` — `?`→`%s`, `RETURNING id`→`lastrowid` (sauf tables sans
  id), proxy de curseur (fetchone/fetchall/iter/rowcount), et surtout `with conn:` qui
  committe/rollback SANS fermer (le `with` psycopg3 natif ferme la connexion) ;
  `MIGRATIONS_PG` (IDENTITY, DOUBLE PRECISION, dates en TEXT ISO conservées) ;
  `migrate_pg` via table `schema_version` (remplace PRAGMA user_version).
- **Incompatibilité absorbée par l'adaptateur** : `end` est un mot réservé Postgres
  (colonnes `sessions.end`, `constraints.end`) → réécriture `\bend\b` → `"end"` dans
  chaque SQL (les identifiants `end_at`/`end_date` ne sont pas touchés).
- **Limite connue, hors périmètre** : `cross_course_conflicts` (validation, règle 9)
  utilise `date(a.due_at)` sur du TEXT — valide en SQLite, pas en Postgres. Non exercé
  par le backend web actuel (CLI/dashboard seulement) ; à adapter si un jour le
  tableau de bord passe sur Postgres.
- `tests/test_pg_smoke.py` (sauté sans DATABASE_URL) : truncate ré-exécutable, import
  des 4 fixtures réelles (4 cours / 28 évaluations), plan complet (> 100 blocs), CRUD
  de blocs, et le piège `with conn:` + requête suivante. **5/5 verts contre le vrai
  pooler Supabase** ; les 104 tests SQLite restent verts (109 au total).
- Aucun module existant modifié : `db.py`, `repositories.py` et l'app bureau sont intacts.

---

## 2026-09-01 — Phase 7 : packaging Windows

- **Dépendance ajoutée** : `pyinstaller==6.*` dans `requirements-dev.txt` — packaging
  de l'exe, prescrit par ARCHITECTURE §1.1 (Phase 7). Jamais embarqué à l'exécution.
- `resources.py` : `resource_path()` résout les ressources (schéma JSON, prompt, QSS)
  en dev comme dans l'exe gelé (`sys._MEIPASS`).
- Base de données de l'exe : `%LOCALAPPDATA%\PlanEtudes\plan_etudes.db`
  (`sys.frozen`) ; `data/` inchangé en développement.
- `build_exe.ps1` : `pyinstaller --onefile --windowed` + `--add-data` (schéma, prompt,
  style). Produit `dist/PlanEtudes.exe` (~50 Mo, non versionné).
- Crochet `PLANNER_SMOKE_TEST=1` dans `app.py` : l'exe s'ouvre, attend 3 s, quitte —
  vérifié : exit 0, base créée au bon endroit.
- README réécrit : flux complet (extraction → import → réglage → plan → suivi),
  commandes CLI, construction de l'exe, procédure de mise à jour.

Reste volontairement hors de cette session (§4.9) : la **calibration manuelle** des
coefficients contre le trimestre réel — tâche de jugement à faire à l'usage, puis
re-figer `test_integration.py`.

---

## 2026-09-01 — Phase 6 : export et intégrations locales

- 3 nouveaux tests (`test_export.py`) : 104 au total, verts.
- `export.py` : construction `.ics` (`icalendar`, déjà justifié en Phase 0) — un VEVENT
  par bloc d'étude (les `skipped` exclus) + un par échéance (⚑, avec salle et durée).
  CLI `python -m planner export --out plan.ics` ; 138 événements sur les 4 cours réels.
- `ScheduleView.export_pdf` : semaine affichée rendue en PDF A4 paysage (`QPdfWriter`).
- Barre d'outils (§5.0 complétée) : Importer · Recalculer · Exporter .ics · Exporter la
  semaine en PDF · Sauvegarder la base · Restaurer… (avec confirmation ; l'état courant
  est sauvegardé avant toute restauration, l'app se ferme pour recharger proprement).
- `QSystemTrayIcon` + `notify_next_block()` : notification Windows du prochain bloc
  planifié après un recalcul. Aucune dépendance externe.
- **Bug corrigé au passage** : deux sauvegardes de base dans la même seconde
  s'écrasaient (noms horodatés identiques) — suffixe compteur ajouté, testé.

**Prochaine étape — Phase 7 :** packaging PyInstaller.

---

## 2026-09-01 — Phase 5 : tableau de bord, paramètres, grille peignable

- 15 nouveaux tests (`test_settings_io`, `test_constraint_grid`, `test_ui_phase5`) :
  101 au total, verts.
- `config.py` : `EngineSettings.to_dict/from_dict` + `load/save_engine_settings` —
  les coefficients §4.9 sont persistés dans la table `settings` (JSON) et repris par
  toutes les vues (arbre des cours, planning, contraintes) à chaque rafraîchissement.
- `ui/views/dashboard_view.py` (§5.5) : alertes issues d'un recalcul À BLANC (ρ,
  déficits, dates manquantes, examens en conflit via la règle 9), échéances à 14 jours
  avec compte à rebours, progression par évaluation (`QProgressBar` heures faites /
  H_total), charge restante par cours et historique hebdomadaire dessinés à la main
  (`ui/widgets/hbar_chart.py`). Rafraîchi à l'affichage de la vue seulement (coût du
  recalcul à blanc).
- `ui/views/settings_view.py` (§5.6) : plage d'éveil, plafonds, tailles de bloc,
  α/β/λ/υ/τ, coûts C1–C5, table B(type)/D(type) éditable, Enregistrer / Réinitialiser.
- `ui/widgets/constraint_grid.py` (§5.3 niveau 2) : grille 7×28 peignable par sélection
  glissée (catégorie colorée), annulation par pile, Enregistrer fusionne les cellules
  contiguës en contraintes hebdomadaires (convertisseurs purs testés) — troisième onglet
  de la vue Contraintes, synchronisé avec le tableau.
- Vérification GUI réelle : les 6 vues s'affichent avec les 4 cours importés.

**Prochaine étape — Phase 6 :** export .ics, notification tray, sauvegarde/restauration.

---

## 2026-09-01 — Phase 4 : vue Planning + recalcul incrémental

- 13 nouveaux tests (`test_rebalance.py`, `test_ui_schedule.py`) : 86 au total, verts.
- `scheduler/placer.py` étendu : `fixed_blocks` (occupent la grille, comptent comme
  placés) et `hours_done` (réduisent la charge restante) — toujours pur et déterministe.
- `scheduler/rebalance.py` (étape F) : H_fait = Σ minutes réelles × η (done/partial),
  `skipped` ne réduit rien (travail repoussé, pas fait), blocs verrouillés figés,
  blocs planifiés futurs libérés puis replacés avec P_stabilité ; différentiel
  (inchangés/déplacés/ajoutés/supprimés) + `apply_rebalance`.
- `ui/widgets/week_calendar.py` (§5.4) : calendrier hebdo dessiné (`paintEvent`),
  contraintes hachurées, séances grises, blocs colorés par cours avec statut (✓ ◐ ✗ 🔒),
  sélection, menu contextuel, glisser-déposer avec accrochage 30 min, double-clic détail.
- `ui/views/schedule_view.py` : navigation semaine, bandeau (h planifiées / faites,
  alertes), Recalculer avec `RecalcDiffDialog` (aperçu du différentiel avant application),
  statuts Fait / Partiellement fait (`BlockCompletionDialog` : minutes + efficacité) /
  Manqué / Verrouiller / Supprimer ; un déplacement manuel verrouille le bloc (`moved`).
- Vérifié en GUI réelle : 111 blocs générés sur les 4 cours, semaine de pointe d'octobre
  affichée sans erreur ; un bloc marqué fait survit au recalcul, un bloc déplacé reste
  en place.

**Prochaine étape — Phase 5 :** tableau de bord, paramètres, grille peignable niveau 2.

---

## 2026-09-01 — Phase 3 : UI — coquille, Importer, Cours, Contraintes (tableau)

- 7 tests pytest-qt (`test_ui_views.py`) : navigation, import via la vue, rejet d'un
  fichier invalide, édition difficulté/override persistée, dialogue contrainte,
  rafraîchissement. 73 tests au total, tous verts.
- `ui/main_window.py` : `QMainWindow` + barre latérale `QListWidget` + `QStackedWidget`
  (Importer / Cours / Contraintes / Planning-placeholder), barre d'état (n cours,
  n évaluations, n sans date), signal `data_changed`.
- `ui/views/import_view.py` (§5.1) : parcourir + glisser-déposer, bouton « Copier le
  prompt d'extraction », rapport de validation ✅/⚠/❌, aperçu des évaluations avec
  `source_excerpt` en infobulle, import avec résumé de réconciliation.
- `ui/models/course_tree.py` + `ui/views/courses_view.py` (§5.2) : `QAbstractItemModel`
  maison cours → évaluations ; colonnes éditables difficulté (1–5), ×effort (0,5–2,0),
  override (h) — persistées et charge recalculée en direct ; jaune = confiance < high,
  rouge = date manquante ; panneau de détail (matière, ressources, notes, extrait).
- `ui/views/constraints_view.py` (§5.3 niveau 1) : deux onglets (hebdomadaires /
  exceptions ponctuelles), `ConstraintDialog` (§5.7), Ajouter/Modifier/Dupliquer/
  Supprimer, étiquette « temps libre disponible cette semaine » calculée par le moteur.
- `ui/style.qss` : thème sombre sans composant tiers. `app.py` : `python -m planner.app`.
- GUI vérifiée en lancement réel avec les 4 cours importés.

**Prochaine étape — Phase 4 :** vue Planning (calendrier hebdo dessiné) + rebalance.

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
