# Décision du 13/10/2026 — Lots 5-6 : intégrité des données d'état (audit phases 6-7)

## Contexte
Suite des corrections d'audit (phase 6 « contrats entre modules », phase 7 « sécurité/intégrité »).
Le **lot 5** (`6d8d958`) a traité l'item HAUTE P7-01 ; le **lot 6** traite le reste des items
corrigibles. Conservateur par construction : **aucune règle métier changée, aucun chiffre recalculé.**

## Lot 5 — P7-01 : les positions de trading réel
- `src/infrastructure/ecriture.py` *(nouveau)* : `ecrire_json_atomique()` (`.tmp` + `replace()`) et
  `lire_json_strict()` (absent → `None` ; présent mais illisible → **`FichierEtatIllisible`**).
  Un fichier d'état corrompu ne donne JAMAIS un résultat vide silencieux.
- `spec_positions.json` + `bonds_positions.json` : écriture atomique + lecture bruyante. 4 tests.
  Données réelles relues après migration : BICC + SMBC.
- **Découverte corrigée** : 2 tests gardiens cassés depuis le LOT 4 (référence −49,0/13-10 vs tests
  −45,4/12-10) → alignés + 2 docstrings rafraîchis. **Procédure du skill mise à jour** : « quand la
  référence des chiffres publiés change, aligner les TESTS GARDIENS dans le même commit ».

## Lot 6 — P6-01/03/05 + P7-01c/02/04
**1. Atomicité généralisée (P7-01c).** 17 sites d'écriture d'état migrés vers `ecrire_json_atomique`
(18 fichiers : alerts, boc, fondamentaux_historiques, news, radar ×2, screener ×2, regime_marche,
dividends, main, portfolio ×2, report, noyau_check, spec_veille, spec_candidates). Les 3 motifs
atomiques inline existants (schema_seuils, backtest, fundamentals) sont inchangés (même garantie).
- **Contrôle anti-régression** : `tests/test_atomicite_etat.py` — tout `X.write_text(json.dumps(...))`
  hors temporaire fait échouer la suite. **Épreuve réelle** : une écriture directe réintroduite en
  probe → test ROUGE nommant le fichier et la ligne ; probe retirée → vert. Le contrôle n'est pas vide.

**2. Chemins (P6-01/03/05).** **8 redéfinitions locales migrées** : les 6 signalées + 2 découvertes
pendant la correction (`report.py` → `portfolio_state.json` ; `portfolio.py` → `reversal_profiles.json`).
Nouvelles constantes dans `paths.py` : `PORTFOLIO_FILE`, `SPEC_POSITIONS`, `RADAR_ALERT_STATE`,
`RADAR_SEEN_STATE`, `REGIME_MARCHE` (+ commentaire distinguant `portfolio.json` de `portfolio_state.json`,
P6-03). **Règle de centralisation ÉCRITE** dans `docs/architecture.md` §6 (P6-05).
- `scripts/verifier_chemins.py` porte désormais **2 contrôles** : (1) chemins recalculés à la main ;
  (2) **noms de fichiers recopiés** — liste dérivée de `paths.py` lui-même. **Épreuve réelle** : une
  recopie réintroduite en probe → signalée, exit 1. Résultat courant : **0 + 0**.

**3. Logs (P7-02).** `_sans_token()` dans `notify.py` : les exceptions `requests` (qui contiennent le
token dans l'URL) sont assainies avant d'être journalisées. Test dédié.

**4. Micro-nettoyages (P7-04).** `pickle.load(open(...))` → context manager (`regime_marche.py`).
Journal `.jsonl` : **aucun lecteur dans `src/`** (constaté — lecteurs = scripts ad hoc) → rien à
durcir côté code ; l'écriture append-only reste sûre par conception.

**5. P7-03 (pickle).** Règle écrite près de `HISTORY_CACHE` (`paths.py`) : « provenance locale
uniquement ; jamais de `.pkl` d'origine externe ; le cache se régénère ». Le SHA pré-chargement n'est
**pas retenu** : qui peut altérer le `.pkl` peut altérer son `.sha` — la défense utile est la règle +
`cache_integrity`. Réévaluable sur demande.

## Preuves
- Suite complète : **490 passed, 0 failed** (`EXIT=0`) — dont les 5 nouveaux tests des lots 5-6.
- `verifier_chemins.py --strict` : **0 chemin + 0 nom** (exit 0) ; les 2 contrôles prouvés capables d'échouer.
- Compilation + imports réels : 18 fichiers OK ; données réelles relues (spec_positions, portfolio).

## Restes ouverts (décision LEO)
- **P6-02** : cycle `portfolio ⇄ speculation` — dette assumée (la voie propre = module domaine, plan de réorg).
- **P6-04** : garde de format/signature des dérivés du cache (fondamentaux, regime_marche) — non fait.
- **P7-03** : option SHA si le besoin apparaît.
- `scripts/` : chemins directs tolérés (outillage d'enquête) — documenté §6.

## Fichiers touchés (lot 6)
`src/infrastructure/paths.py` · `src/infrastructure/ecriture.py` *(lot 5)* · 18 modules d'état ·
`src/notify.py` · `src/report.py` · `scripts/verifier_chemins.py` · `tests/test_atomicite_etat.py` *(neuf)* ·
`tests/test_notify.py` · `docs/architecture.md` · `audit/phase6_contrats_modules.md` · `audit/phase7_securite_integrite.md`.
