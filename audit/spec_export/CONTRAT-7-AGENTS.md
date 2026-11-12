# Contrat partagé — audit de la veille spéculative (12/11/2026)

Sept chantiers tournent en parallèle. Ce document est la source commune : **lis-le en entier
avant de produire**, et n'écris QUE dans les fichiers qui te sont attribués.

## Faits ÉTABLIS — ne pas les re-mesurer, ils sont prouvés

1. **Univers de données** : `charger_historique_propre()` (cache PROPRE, divisions ajustées)
   est la SEULE source valide pour backtester. `load_all_history(BSApi())` renvoie
   `HISTORY_BRUT` — les cours NON ajustés : une division 10:1 y apparaît comme une chute de
   −90 %, ce qui crée de faux signaux PANIQUE. **37 titres sur 48 diffèrent**, facteurs ×2 à ×100.
   Le calibrage a été corrigé le 12/11 : il lit désormais le cache propre.

2. **Les cas publiés** (cache propre, espacement 60 séances par titre ET par schéma) :
   - CASSURE **267** cas · EVEIL **934** · PANIQUE **414** (total 1 615)
   - Export déjà produit dans `audit/spec_export/cas_*.csv` + `resume.json`

3. **Les règles du signal** (`src/strategie/spec_profiles.py`, `detect_schemas`) :
   - CASSURE : `closes[-1] > max(closes[-251:-1])` + volume ≥ médiane 60 séances (si volumes fournis)
   - EVEIL : `closes[-1] / min(closes[-61:-1]) - 1 >= 0.10` + même filtre volume
   - PANIQUE : RSI 14 < 30
   - `zone_of()` = **position min-max** dans la fenêtre 5 ans, PAS un percentile de rang

4. **LA mesure qui compte** : un palier (+20/+35/+50 %) doit être atteint **AVANT** le stop
   −15 %, sinon le plan est invalide. Mesuré sur les cas exportés :
   - PANIQUE : +20 % touché 59 % brut → **46 % avant le stop** ; stop touché dans 56 % des cas
   - EVEIL : 61 % → **52 %** · CASSURE : 69 % → **62 %**

5. **`SEUIL_CAS_ZONE = 10`** : sous 10 cas, aucune conclusion chiffrée n'est tirée (affichage ⚪).
   La couleur d'un verdict est dérivée du taux mesuré : ≥60 % ✅ · 50-60 % 🟡 · <50 % 🔴.

6. **Frais** : 1,4 % par sens (courtage 0,80 % + TVA 18 % + BRVM 0,456 %), **minimum 1 000 F
   par ordre** — sous 125 000 F le taux effectif dépasse 1,4 % (20 % sur 5 000 F).

## Règles du dépôt — non négociables

1. **Aucun test ne touche le réseau.** Un appel HTTP dans un test fait passer la suite de 8 s
   à plusieurs minutes quand le site ne répond pas.
2. **Aucun commit, aucun push, aucune branche** : le parent commite après vérification.
3. **Ne jamais inventer un chiffre.** Donnée absente = « non disponible », jamais une valeur plausible.
4. **Un chiffre CALIBRÉ ne se fige jamais dans un test** : le test compare à la source, pas à une constante.
5. Python du projet (le seul avec les dépendances) :
   `C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python`
6. Bash MSYS : binaires natifs refusent `/c/...` → utiliser `C:/...`.
7. `write_file` refuse de réécrire un fichier non relu dans la session → `read_file` d'abord,
   ou `patch` pour une modification ciblée.
8. **Preuve par exécution** : colle la sortie réelle (tests, script) dans ton rapport final.

## Répartition des fichiers — UN SEUL écrivain par fichier

| Agent | Fichiers que TU écris | Interdits |
|---|---|---|
| **P2** | `audit/spec_export/SPECIFICATION-SIGNAL.md` | tout le reste |
| **P3** | `scripts/reconcilier_boc.py` + `audit/spec_export/RECONCILIATION-BOC.md` | tout le reste |
| **P4** | `scripts/exporter_cas_spec.py` (patch) + les CSV de `audit/spec_export/` | les autres .md de spec_export |
| **P5** | `scripts/rejouer_plan_complet.py` + `audit/spec_export/PLAN-COMPLET.md` | tout le reste |
| **P6** | `scripts/valider_hors_periode.py` + `audit/spec_export/HORS-PERIODE.md` | tout le reste |
| **TEST** | `tests/test_spec_audit.py` (nouveau fichier) | tout le reste |
| **CHALLENGE** | `audit/spec_export/CHALLENGE.md` | tout le reste |

**Ne lis pas les fichiers des autres agents pour t'en inspirer** : ils n'existent pas encore
ou sont en cours d'écriture. Travaille sur le code et les données du dépôt.

## Vocabulaire imposé

- `cas` : un épisode de signal (titre + date + schéma), espacement 60 séances par titre/schéma.
- `palier avant stop` : le palier est atteint à une séance STRICTEMENT antérieure au stop.
- `zone_minmax` : position 0-1 dans la fourchette 5 ans (la convention du backtest).
- `percentile_rang` : part des séances sous le cours (le vrai percentile, pour comparaison).
