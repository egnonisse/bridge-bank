# Décision du 13/10/2026 — Lot 7 : provenance du cache historique (P6-02, P6-04, P7-03)

## Contexte
Les **3 derniers items** de l'audit phases 6-7, après le feu vert de LEO. Objectif : fermer
la famille « le cache historique change → des calculs silencieusement faux » (incident 21/08).

## P7-03 — le cache porte son empreinte
`src/collecte/history_io.py` *(nouveau)* :
- `ecrire_cache()` : pickle écrit **atomiquement** (`.tmp` + `replace`) **puis** sidecar
  `<cache>.sha256` (atomique aussi) ;
- `charger_cache()` : si le sidecar existe et que **l'empreinte diverge** → **`CacheHistoriqueAltere`**
  avec la commande de régénération. Sidecar absent → toléré (ancien cache).
- Écrivain unique migré : `scripts/preparer_historique_propre.py`. Lecteurs migrés :
  `regime_marche.charger_series_quotidiennes` et `challenge_validateur.charger_historique`.
- **Limite assumée** : un sidecar protège d'une altération ACCIDENTELLE. Contre un adversaire qui
  réécrit les deux fichiers, la défense reste la règle de provenance + `cache_integrity`.

## P6-04 — lecture unique + signature dans les dérivés
- **Une seule lecture** (`charger_cache`) — fin des lectures dispersées (3 → 1).
- `regime_marche.json` porte désormais `_cache_sha` : un « régime du jour » calculé sur un cache
  de cours DIFFÉRENT n'est **pas réutilisé** — il est recalculé (auto-réparant, cf. fraîcheur jugée
  sur les données). `reversal_profiles.json` portait déjà sa signature (mécanisme existant).
- Constat corrigé : `fondamentaux_historiques.json` n'est **pas** un dérivé du cache de cours
  (vérifié — l'audit le citait à tort) ; hors périmètre.

## P6-02 — cycle `portfolio ⇄ speculation` : verrouillé par tests
Les 2 imports locaux (« évite la circularité ») sont **déjà couverts par 4 tests**
(`tests/test_poches_etanches.py` : blocage dans les 2 sens + les 2 cas légitimes) : tout
déplacement qui casserait les imports ferait **échouer le build**. Commentaires enrichis en ce
sens. La découpe propre (module `domaine/` portant les 2 loaders) reste au plan de réorganisation
(`docs/architecture.md`) — dette assumée, pas un risque silencieux.

## Preuves
- Suite complète : **495 tests verts** (5 nouveaux : 4 `history_io` + 2 régime − dont 1 remplace un
  ancien… voir suite) ; ciblé : 63 verts.
- **Cache réel** chargé avec vérification en place : **48 titres** via `charger_cache()`.
- Tests de l'invalidation : régime « POISON » recalculé (empreinte différente) ; régime « SENTINELLE »
  servi tel quel (empreinte identique).
- `lire_sha` du cache réel = `None` aujourd'hui (sidecar créé au prochain passage du pipeline) →
  aucun risque de panne : le sidecar absent est toléré.

## État final de l'audit phases 6-7
| Item | État |
|---|---|
| P6-01, P6-03, P6-05 | ✅ lot 6 |
| P6-02 | Assumé + verrouillé par tests |
| P6-04 | ✅ lot 7 |
| P7-01, P7-01c, P7-02, P7-04 | ✅ lots 5-6 |
| P7-03 | ✅ lot 7 |

**Aucun item d'audit restant.** Restent les décisions hors audit de LEO (clé Anthropic, garde-fous,
plafond OpenRouter, backup du dimanche).

## Fichiers touchés (lot 7)
`src/collecte/history_io.py` *(neuf)* · `src/calibration/regime_marche.py` ·
`src/backtesting/challenge_validateur.py` · `scripts/preparer_historique_propre.py` ·
`src/strategie/speculation.py` *(commentaire)* · `src/portfolio.py` *(commentaire)* ·
`tests/test_history_io.py` *(neuf)* · `tests/test_regime_marche.py`.
