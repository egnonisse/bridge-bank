# Phase 7 — Sécurité et intégrité (audit Bridge Bank)

**Date** : 13/10/2026 · **Mode** : lecture seule (aucune correction) · **Périmètre** : secrets, réseau, entrées non fiables, intégrité des données d'état, hygiène des logs/backups.

## Synthèse

| # | Item | Sévérité | Statut |
|---|---|---|---|
| P7-01 | **Atomicité non généralisée** — `spec_positions.json` (trading réel) écrit directement + le loader avale la corruption en silence | **HAUTE** | ✅ **CORRIGÉ 13/10** (lot 5) |
| P7-02 | Le token du bot peut fuiter dans les logs d'erreur (exceptions `requests` qui contiennent l'URL) | Moyenne | ✅ **CORRIGÉ 13/10** (lot 6 — `_sans_token` + test) |
| P7-03 | `pickle.load` du cache historique sans contrôle de provenance AVANT chargement | Basse-Moyenne | Règle écrite 13/10 ; option SHA non retenue* |
| P7-04 | Micro : `open()` sans context manager ; journal `.jsonl` sans garde de ligne tronquée | Basse | ✅ **CORRIGÉ 13/10** (lot 6 — context manager ; journal : aucun lecteur en `src/`, constaté) |

*P7-03 : la règle « provenance locale uniquement, jamais de .pkl externe, le cache se régénère » est
inscrite près de `HISTORY_CACHE` dans `paths.py`. Le SHA pré-chargement n'est PAS retenu : qui peut
altérer le `.pkl` peut altérer son `.sha` — la défense utile est la règle + les contrôles existants
(`cache_integrity`). À re-trancher par LEO si le besoin apparaît.

**1 item de sévérité haute** (P7-01) — limité à l'intégrité des données d'état, pas à une faille exploitable. Le reste est sain (voir ci-dessous).

## Constats positifs (vérifiés, à préserver)

| Contrôle | Résultat |
|---|---|
| **Secrets en dur dans `src/`** | **AUCUN** — les seules occurrences (`bot_token` etc.) sont des lectures d'env ; aucune valeur littérale |
| **Historique git des secrets** | `bot_token` a **toujours été vide** dans `config.yaml` (parcours complet de `git log -p --all` — jamais de valeur non vide) |
| **`config.yaml` versionné** | Ne contient AUCUN secret (`bot_token: ''`, `chat_id: ''`) — le vrai token vit dans `.env` (non versionné) |
| **TLS** | `verify=False` restant : **1 seul** (`bsapi.py`/BSTrade — certificat serveur invalide, données publiques, documenté) ; les 5 autres sources corrigées au LOT 3 |
| **Timeouts réseau** | **Tous les appels `requests` directs ont un timeout** (10/10 vérifiés ; Telegram 15 s, BS API documenté) |
| **`subprocess`** | 1 seul usage (`empreinte.py` → `git`) : liste d'arguments (pas de shell), `timeout=15`, exceptions gérées |
| **`.gitignore`** | `data/avis/releves*` et `logs/` exclus ✓ |
| **Écritures atomiques (LOT 1)** | `portfolio.json`, `per_cache.json` (avec verrou inter-processus), `titres_inactifs.json`, helper `schema_seuils.py` — motif `tmp` + `replace` correct |
| **Journal des alertes** | Append-only (`alertes_journal.jsonl`) — pas de réécriture, pas de perte par troncature de réécriture |

## Items détaillés

### P7-01 — Atomicité non généralisée + corruption silencieuse (HAUTE)
**Constat** :
1. Écriture NON atomique de **`data/spec_positions.json`** — les positions de trading RÉEL de la poche spéculative : `speculation.py:232` (`POSITIONS_FILE.write_text(...)` direct, sans `.tmp` + replace). Ce fichier est lu par 4 modules (`speculation`, `main`, `bonds`, `scripts/close_check.py`) et suivi git ✓ (mitigation partielle : perte bornée au dernier backup/commit).
2. Le même défaut frappe ~13 autres fichiers d'état (liste : `alerts.py:58`, `boc.py:164`, `bonds.py:128`, `fondamentaux_historiques.py:334`, `news.py:124`, `radar.py:38+56`, `screener.py:49+209`, `regime_marche.py:154`, `dividends.py:31`, `main.py:708`, `portfolio.py:746+829`, `report.py:50`, `noyau_check.py:41`, `spec_veille.py:39`, `speculation.py:353`). Parmi eux, **7 NON suivis par git** (aucun backup) : `alerts_state`, `boc_state`, `news_state`, `value_state`, `dividendes`, `bonds_positions`, `portf_alert_state`.
3. **Aggravant** : `load_positions()` (`speculation.py:225-227`) attrape `json.JSONDecodeError` et **retourne `[]` silencieusement** — une écriture tronquée par un crash ferait VOIR « aucune position spé » sans aucune alerte. C'est la classe d'incident que la doctrine du LOT 4 (« un système qui échoue en silence est dangereux ») interdit.
**Impact** : perte/contournement du suivi de la poche spé (trading réel), et états corrompus silencieux sur ~13 fichiers. Probabilité faible mais conséquence non récupérable pour `spec_positions` entre deux backups.
**Recommandation** : (a) écriture atomique sur `spec_positions.json` ; (b) le loader ÉCHOUE BRUYAMMENT sur fichier corrompu (pattern B2-05) au lieu de `[]` ; (c) généraliser le helper atomique aux autres fichiers d'état — notamment les 7 non suivis git. **Décision LEO requise** (aucune correction appliquée).

### P7-02 — Fuite possible du token dans les logs (MOYENNE)
**Constat** : `notify.py:126` → `log.error("Telegram send failed: %s", exc)` — les exceptions `requests` incluent l'URL complète, qui contient le token (`api.telegram.org/bot<TOKEN>/sendMessage`). Les logs (`logs/`, gitignorés ✓) servent aux diagnostics et peuvent être collés/partagés (cas vécu : collages dans les sessions).
**Impact** : un token compromis si un log est partagé. Pas d'exploitation sans accès aux logs.
**Recommandation** : assainir le message (masquer `/bot.*/` de `str(exc)`) + garde-fou similaire sur tout futur appel à token dans l'URL. Décision LEO.

### P7-03 — `pickle.load` sans contrôle de provenance (BASSE-MOYENNE)
**Constat** : `regime_marche.py:113` → `pickle.load(open(chemin, "rb"))` sur `history_clean.pkl`. Le format pickle EXÉCUTE du code au chargement si le fichier est piégé. Atténuations existantes : le cache est produit localement par le pipeline (`scripts/preparer_historique_propre.py`), `cache_integrity.py` contrôle les VALEURS après chargement. Mais **aucun contrôle AVANT chargement** (pas de SHA, pas de « provenance locale uniquement » documentée).
**Impact** : risque local faible (pas de source externe de .pkl), mais la règle doit être explicite pour l'avenir.
**Recommandation** : documenter « ne jamais charger un `.pkl` d'origine externe ; le cache se régénère » + (option) SHA-256 du cache vérifié avant `load`. Décision LEO.

### P7-04 — Micro-nettoyages (BASSE)
- `regime_marche.py:113` : `open()` sans context manager (descripteur maintenu jusqu'au GC) — même ligne que P7-03.
- Journal `.jsonl` : append sans verrou — une ligne peut être tronquée par un crash en pleine écriture ; à la lecture, les lignes incomplètes devraient être écartées ET signalées (vérifier `journal_alertes.py` — non fait dans cet audit).

## Doctrine rappelée
« **Un système qui échoue BRUYAMMENT est sûr ; un système qui échoue EN SILENCE est dangereux** » (lot 4). P7-01 est l'application directe : l'écriture non atomique est tolerable SI le loader crie ; ici il chuchote (`return []`).

## Recommandations priorisées (aucune appliquée — décisions LEO)
1. **Immédiat** : `spec_positions.json` → atomique + loader bruyant (P7-01a/b).
2. **Court terme** : généraliser l'atomicité aux fichiers d'état non suivis git (P7-01c) ; assainir le log token (P7-02).
3. **Documentation** : règles pickle (P7-03) et micro-nettoyages (P7-04).

## Limites de cet audit
- Greps systématiques + lectures ciblées ; pas de test d'intrusion, pas d'exécution, périmètre `src/` + `config.yaml` + `.gitignore` (les `scripts/` n'ont été couverts qu'en preuve).
- La liste d'écritures non atomiques est issue d'une analyse statique des motifs `write_text`/`json.dump` ; quelques faux négatifs/positifs sont possibles (revue ligne à ligne faite pour les 3 fichiers critiques).
