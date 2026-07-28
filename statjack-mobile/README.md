# StatJack Mobile 📱

Version téléphone de [StatJack](https://github.com/AMoncade/StatJack), le simulateur probabiliste de Blackjack. Port JavaScript fidèle des modèles Python (`jeu.py`, `sabot.py`, `main_joueur.py`, `probabilites.py`) sous forme de **PWA** (Progressive Web App) : elle s'installe sur l'écran d'accueil, se lance en plein écran comme une app native et fonctionne hors-ligne.

## Fonctionnalités portées

- Moteur de jeu complet : Hit, Stand, Double, Split (as fermés), croupier stand on 17, Blackjack payé 3:2
- Sabot multi-paquets (1 à 8, défaut 6) avec re-mélange automatique sous 20 cartes
- Comptage Hi-Lo : Running Count, True Count, avantage joueur estimé
- Calculateur de probabilités en temps réel : % de bust, % d'amélioration, distribution du croupier (Monte Carlo), EV stand vs EV optimal (récursion avec mémoïsation, mêmes coupures que le modèle Python)
- Statistiques Monte Carlo par action (Stand / Hit / Double : win, push, loss, EV)
- Mode entraînement : interception des décisions sous-optimales avec explication
- Graphe de convergence des gains (1000 mains simulées)
- Banque persistante (localStorage), mise par jetons, effets sonores WebAudio

Non porté pour l'instant : le mode tutoriel pas-à-pas.

## Lancer sur un téléphone

### Option A — GitHub Pages (recommandé)

1. Dans les réglages du dépôt : **Settings → Pages → Source : Deploy from a branch**, choisir la branche et le dossier contenant `statjack-mobile/`.
2. Ouvrir `https://<utilisateur>.github.io/<repo>/statjack-mobile/` sur le téléphone.
3. **iPhone (Safari)** : Partager → « Sur l'écran d'accueil ».
   **Android (Chrome)** : menu ⋮ → « Installer l'application ».

L'icône StatJack apparaît sur l'écran d'accueil et le jeu se lance en plein écran, même sans connexion.

### Option B — test local

```bash
cd statjack-mobile
python3 -m http.server 8000
```

Puis ouvrir `http://<ip-de-votre-machine>:8000` depuis le téléphone sur le même réseau. (Le service worker nécessite HTTPS ou localhost ; en local via IP, le jeu fonctionne mais sans installation/hors-ligne.)

## Structure

```
statjack-mobile/
├── index.html            # Jeu complet (moteur + probabilités + UI), sans dépendance
├── manifest.webmanifest  # Manifeste PWA (installation écran d'accueil)
├── sw.js                 # Service worker (cache hors-ligne)
├── cartes/               # Les 52 cartes du jeu original (optimisées mobile)
├── logo.png              # Logo StatJack
├── icon-192.png / icon-512.png / apple-touch-icon.png
└── README.md
```

Aucune dépendance externe, aucun build. Si les images de cartes sont absentes, le jeu bascule automatiquement sur un rendu CSS.
