# Décision du 12/10/2026 — Corrections du LOT 1 (suite de l'audit technique)

**Contexte** : l'audit technique (phases 0-5, 47 items) a produit un plan de corrections ordonné.
Le **LOT 1** regroupe les 5 corrections critiques touchant la **livraison des alertes** et
l'**intégrité des données**. Périmètre validé par LEO le 12/10/2026 (« go lot 1 »).

**Protocole appliqué** (décidé le 08/10) : corriger → le test `xfail` passe en XPASS →
geler le test (retirer le marqueur) → commit atomique. Rien sans test, rien sans preuve.

## Corrections appliquées

| Réf | Problème (source) | Correction (valeur AVANT → APRÈS) | Tests de gel |
|---|---|---|---|
| **B1-01** | `cmd_portf check` clôturait la position **avant** l'envoi Telegram ; le retour d'envoi était ignoré → échec d'envoi = sortie perdue, position orpheline | AVANT : persistance puis envoi (retour ignoré). APRÈS : l'envoi précède la persistance ; si l'envoi échoue (notifier actif), la clôture est **annulée en mémoire** et re-tentée au prochain run | `test_sortie_non_delivree_annule_la_cloture`, `test_sortie_delivree_est_persistee` |
| **B0-01** | `close_reason` ne contenait aucune date (parse échouait → repli sur `opened_at`) → cooldown « 30 j après stop-out » **inopérant** | AVANT : champ aucun. APRÈS : nouveau champ `SpecPosition.closed_at` horodaté à chaque clôture (stop −15 % et palier +50 %) ; `spec_veille` lit `closed_at` en priorité | `test_close_reason_porte_la_date_du_stop` |
| **C1 / B1-02** | Format US (virgule de milliers : `39,200`) dans les **messages live** alors que l'invariant E1 impose le format français | AVANT : `{x:,.0f}` partout. APRÈS : helper `fcfa()` / `nombre()` — patches manuels (`portfolio.py`, `spec_fiche.py`, `alerts.py`) + passe mécanique vérifiée (`main.py`, `report.py`, `speculation.py`, `noyau_check.py`, `cache_integrity.py`), 158 remplacements, unités « FCFA » redondantes nettoyées | Test gardien des sorties recapturé, `test_fiche_spec_sans_virgule_de_milliers` |
| **B1-04** | `load_portfolio` retournait `[]` en silence sur fichier corrompu → le cron sauvegardait ensuite et **effaçait** les données ; écriture non atomique | AVANT : `return []` sur OSError/JSONDecodeError. APRÈS : exception bruyante `PortfolioInvalide` (aucune écriture ne suit) + écriture **atomique** (fichier `.tmp` puis `replace`) | `test_portfolio_corrompu_ne_redevient_pas_vide`, `test_portfolio_ecriture_atomique` |
| **B2-04** | `daily_check.py` avalait les exceptions et sortait en code 0 ; le heartbeat affichait « ✅ » même si une étape plantait | AVANT : `except: traceback` + exit 0. APRÈS : `sys.exit(1)` en cas d'échec ; heartbeat dont le titre passe « ⚠️ N étape(s) en ÉCHEC » et chaque étape en échec est marquée « ❌ ÉCHEC (voir logs/daily.log) » | `test_heartbeat_signale_les_echecs`, `test_heartbeat_sans_echec_garde_le_titre_vert` |

## Preuves d'exécution

- Suite complète : **346 passed, 3 xfailed** (12/10/2026). Les 3 `xfail` restants =
  corrections des lots 2-3, non encore appliquées : DRIP net d'IRVM (B1-03), cooldown
  watchlist (B1-07), nettoyeur symétrique (B2-11).
- Recapture du **gardien des sorties** (`tests/fixtures/sorties_reference.json`) :
  115 clés changées (passe manuelle) puis 3 (passe mécanique) — contrôle automatique par
  extraction de **tous** les nombres : **0 divergence numérique** (pur changement de format).
- Vérification live : `portf status` affiche « 38 967 F » (format FR) — portefeuille
  chargé, API OK.
- Script de la passe mécanique conservé : `scripts/corriger_format_fr.py` (dry-run par défaut).

## Effets attendus (ce que ça change pour LEO)

1. Une alerte de sortie (« VENDS TOUT ») **ne peut plus être perdue en silence** : en cas
   d'échec d'envoi, elle est re-tentée au prochain check quotidien.
2. Un `portfolio.json` corrompu **arrête** le check au lieu d'être écrasé (re-tenté après
   correction manuelle).
3. Le check quotidien **signale visiblement** ses échecs (code de sortie + heartbeat).
4. Tous les montants visibles (Telegram **et** CLI) sont au format français.

## Limites connues (honnêteté)

- `spec_veille` : le repli sur `opened_at` subsiste pour les clôtures **antérieures** au
  12/10 (l'historique n'a pas de `closed_at`) — la correction est effective pour toutes
  les clôtures futures.
- L'annulation de clôture (B1-01) ne s'applique que si le notifier est **actif** : s'il est
  désactivé par configuration, la clôture est persistée sans envoi (comportement historique
  voulu : le mode CLI sans Telegram reste utilisable).
- La passe mécanique C1 ne couvre pas les scripts d'étude (`scripts/tester_*.py`,
  `scripts/analyser_trades_reels.py`) — outils internes de recherche, pas des messages.
