# Phase 6 — Contrats entre modules (audit Bridge Bank)

**Date** : 13/10/2026 · **Mode** : lecture seule (aucune correction) · **Périmètre** : `src/` — 55 modules, ~10 980 lignes + fichiers racine (`main.py`, `portfolio.py`, `alerts.py`, `notify.py`, `regles.py`, `report.py`, `taxation.py`)
**Méthode** : graphe d'imports extrait par AST (2 passes : importeurs → dépendances), inventaire des fichiers d'état producteurs/consommateurs, lecture des contrats centraux (`paths.py`, `regles.py`, `taxation.py`), exécution du contrôle existant `scripts/verifier_chemins.py`.

## Synthèse

| # | Item | Sévérité | Statut |
|---|---|---|---|
| P6-01 | **Centralisation des chemins incomplète** — 6 redéfinitions locales de fichiers déjà constants | Moyenne | ✅ **CORRIGÉ 13/10** (lot 6 — 8 redéfinitions migrées*) |
| P6-02 | Cycle bidirectionnel `portfolio ⇄ speculation` (imports locaux documentés) | Basse | Assumé (tracé) |
| P6-03 | `portfolio.json` (état vivant) vs `portfolio_state.json` : contrat ambigu, centralisation « à l'envers » | Basse | ✅ **CORRIGÉ 13/10** (lot 6) |
| P6-04 | `history_clean.pkl` : 3 chemins redéfinis, format implicite, lectures multiples | Moyenne | Chemins ✅ 13/10 ; garde de format : ouvert |
| P6-05 | Règle de centralisation non écrite pour ~15 fichiers d'état (dont 3 multi-consommateurs hors `paths.py`) | Basse | ✅ **CORRIGÉ 13/10** (lot 6) |

*6 signalées + 2 découvertes pendant la correction : `report.py` (`portfolio_state.json`) et `portfolio.py` (`reversal_profiles.json`).

**Aucun item de sévérité haute.** Le squelette des contrats est sain (voir constats positifs) ; les items sont des écarts de DISCIPLINE qui préparent des pannes silencieuses pour la prochaine réorganisation.

## Constats positifs (à préserver)

- **`src/infrastructure/paths.py` = LE contrat de chemins** (92 lignes, **23 importeurs** — le module le plus importé du projet) : docstring qui explique le POURQUOI (profondeur implicite), 9 constantes de fichiers + 4 de dossiers, fonction `chemin_data()`, fonction `verifier()`. Centralisation réelle et testée.
- **`scripts/verifier_chemins.py`** : contrôle automatique exécuté (`TOTAL : 0 occurrence` aujourd'hui) — il attrape l'idiome `Path(__file__)...parent / "data"` (avec filtre anti-faux-positifs sur les docstrings). **Mais son motif ne couvre que ce seul idiome** → voir P6-01.
- **`src/regles.py` + `src/taxation.py` (10 importeurs chacun)** : catalogue unique des règles métier, alias à l'import, tests gardiens récursifs (LOT 3/C4) — le contrat le mieux verrouillé du projet.
- **`src/portefeuille/format_fr.py` (8 importeurs)** : invariant E1 (format FR) appliqué partout, test gardien des sorties.
- **Graphe sans dépendances circulaires bloquantes** : 1 seul cycle (P6-02), contourné par imports locaux EXPLICITEMENT documentés (« évite la circularité »).
- **`src.domaine.models`** : types partagés (`Barre`, `DividendPosition`, `SpecPosition`…) — 4 importeurs, contrat de données stable.

## Items détaillés

### P6-01 — Centralisation des chemins incomplète (MOYENNE)
**Constat** : `paths.py` déclare « le nom vit ici, jamais recopié dans un module » — mais **6 modules redéfinissent localement** des chemins déjà constants :
| Module | Ligne | Redéfinit | Constante existante dans `paths.py` |
|---|---|---|---|
| `src/analyse/fondamentaux_historiques.py` | 53 | `CACHE = RACINE/"data"/"fondamentaux_historiques.json"` | `FUNDAMENTALS_HISTORIQUES` |
| `src/collecte/divisions_officielles.py` | 37 | `FICHIER = RACINE/"data"/"divisions_officielles.json"` | `DIVISIONS_OFFICIELLES` |
| `src/calibration/regime_marche.py` | 139-140 | `history_clean.pkl` + `regime_marche.json` | `HISTORY_CACHE` |
| `src/backtesting/challenge_validateur.py` | 499 | `RACINE/"data"/"history_clean.pkl"` | `HISTORY_CACHE` |
| `src/calibration/seuils_vente.py` | 59-60 | `profit_thresholds.json` + `seuils_journal.jsonl` | `PROFIT_THRESHOLDS`, `SEUILS_JOURNAL` |
| `src/collecte/cache_integrity.py` | 24 | `reversal_profiles.json` | `REVERSAL_PROFILES` |

**Impact** : le scénario que `paths.py` est censé prévenir (déplacement/réorganisation de `data/` → chargements silencieusement vides) reste possible sur ces 6 fichiers. Le contrôle `verifier_chemins.py` **ne les détecte pas** (son motif ne cherche que `Path(__file__)`, pas `RACINE/"data"` importé).
**Recommandation** : soit migrer les 6 redéfinitions vers les constantes, soit étendre le motif du contrôle (idéal : les deux, le contrôle garantit la non-régression). **Décision LEO requise** (aucune correction appliquée).

### P6-02 — Cycle portfolio ⇄ speculation (BASSE — assumé)
**Constat** : `src/portfolio.py:849` importe `load_positions` de `speculation`, et `src/strategie/speculation.py:281` importe `load_portfolio` de `portfolio` — **imports locaux** (dans les fonctions) avec commentaire « import local : évite la circularité ».
**Impact** : fonctionne, mais tout déplacement futur d'un des deux casse l'autre sans prévenir au build. C'est une dette TRACÉE, pas un bug.
**Recommandation** : acceptable en l'état ; la voie propre serait un module `domaine/` portant les deux loaders (aligné avec le plan de réorg `docs/architecture.md`). À inscrire comme dette assumée si non corrigé.

### P6-03 — `portfolio.json` vs `portfolio_state.json` (BASSE)
**Constat** : deux fichiers au nom quasi identique, aux rôles différents :
- `data/portfolio.json` (état VIVANT : positions, écrit à chaque exécution ; constante locale `PORTFOLIO_FILE` dans `portfolio.py:599` — **hors `paths.py`** ; suivi git ✓) ;
- `data/portfolio_state.json` (trajectoire mensuelle pour le rapport ; `report.py:26` + **dans `paths.py`** sous `PORTFOLIO_STATE` ; exclu du drapeau d'empreinte).
**Impact** : confusion possible en session (deux « portfolio ») ; incohérence de centralisation (le fichier CRITIQUE est dehors, le secondaire dedans).
**Recommandation** : clarifier (renommer `portfolio_state.json` → `portfolio_history.json` ?) ou documenter la distinction dans `paths.py`. Décision LEO.

### P6-04 — `history_clean.pkl` : contrat de données implicite (MOYENNE)
**Constat** : 3 définitions de chemin (paths.HISTORY_CACHE + 2 recalculs, cf. P6-01) et **plusieurs implémentations de lecture** (`regime_marche.charger_series_quotidiennes`, `challenge_validateur:499`, lecture dans `backtest.py`). Le FORMAT (pickle d'objets barres avec `.date`/`.close`) est un contrat implicite producteur → consommateurs, sans garde de version. `cache_integrity.py` contrôle les VALEURS (cassures > 3×, fraîcheur, cohérence dernière barre) et versionne `reversal_profiles.json` par signature du cache — **mais aucun autre dérivé ne porte cette signature**.
**Impact** : un changement de format/source du cache ne casse pas au chargement — il produit des résultats faux ou vides (famille incident 21/08).
**Recommandation** : centraliser la LECTURE dans un seul module (ex. `collecte/`) + étendre la signature du cache à tous les dérivés (fondamentaux, regime_marche). Décision LEO.

### P6-05 — Règle de centralisation non écrite pour les autres fichiers d'état (BASSE)
**Constat** : ~15 fichiers d'état (`alerts_state`, `boc_state`, `news_state`, `radar_alert_state`, `value_state`, `fundamentals_cache`, `regime_marche`, `dividendes`, `bonds_*`, `spec_positions`, `spec_seen_state`, `noyau_check`…) déclarent leur constante LOCALEMENT. Acceptable pour les fichiers à consommateur unique ; **mais 3 sont multi-consommateurs** : `spec_positions.json` (speculation + main + bonds + close_check — 4), `reversal_profiles.json` (radar + cache_integrity + scripts), `radar_seen_state.json` (radar + monitor cron).
**Recommandation** : écrire la règle « ≥ 2 consommateurs → constante dans `paths.py` » dans la docstring de `paths.py`, puis migrer ces 3. Décision LEO.

## Limites de cet audit
- Analyse STATIQUE (AST + greps + lectures) — aucun test exécuté, aucune correction.
- L'inventaire des fichiers d'état couvre les 17 principaux ; les fichiers purement internes à un module n'ont pas été exhaustivement listés.
- `scripts/` (86 scripts) hors périmètre, sauf pour les preuves citées.
