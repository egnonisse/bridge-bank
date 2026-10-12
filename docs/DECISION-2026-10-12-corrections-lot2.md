# Décision du 12/10/2026 — Corrections du LOT 2 (suite de l'audit technique)

**Contexte** : après le LOT 1 (livraison des alertes + intégrité), le **LOT 2** traite les
7 corrections de justesse des calculs et de la fiabilité des données. Validé par LEO
(« go lot 2 »). Protocole inchangé : corriger → XPASS → geler le test → commit.

## A. Les 7 corrections du lot

| Réf | Problème (AVANT) | Correction (APRÈS) | Tests de gel |
|---|---|---|---|
| **B1-03** | `record_dividend` comptabilisait le dividende **BRUT** — l'IRVM 12 % (retenue à la source) n'était jamais déduite → cash, actions rachetées et `dividends_earned` surestimés de ~13,6 % | `cash = dps × (1 − IRVM) × quantité` — le cash RÉELLEMENT reçu | `test_drip_comptabilise_le_net_apres_irvm` (gelé) + 3 tests DRIP réécrits (valeurs nettes) |
| **B1-07** | La clé de cooldown de la watchlist contenait le **prix** (`code:« Prix atteint 45 200 »`) → clé différente à chaque tick → re-notification malgré le cooldown 30 min | Clé stable `code:type:seuil` (`_check_rules` retourne `(clé, message)`) | `test_cooldown_watchlist_ne_repete_pas` (gelé) |
| **B1-05** | Le prix de sortie (net 2 %) restait figé au **dps d'ouverture** — un dividende en hausse sortait trop tôt, un dividende réduit laissait attendre un niveau qui ne reviendrait plus | `exit_ref` recalculé au **dps courant** quand il est connu (`current_dps / DIV_YIELD_EXIT`) ; repli sur `exit_price` figé sinon | `test_sortie_rapprochee_par_un_dividende_reduit`, `test_sortie_eloignee_par_un_dividende_en_hausse` |
| **B1-09** | Les stop-outs étaient comptés **cumulativement** — deux stop-outs espacés de deux ans déclenchaient la suspension de 60 j | Seuls les stop-outs **RAPPROCHÉS** (dans la fenêtre de 60 j précédant le dernier) comptent : ≥ 2 = suspension, sinon cooldown 30 j. Fonction testable extraite : `stopout_cooldowns()` | `test_stopouts_espaces_ne_suspendent_pas` |
| **B1-13** | L'anti-spam 7 j des fiches spé était consommé à la **génération** : un envoi Telegram en échec = fiche perdue 7 jours ; une fiche écartée par le plafond 3/j = perdue aussi | `scan()` ne marque plus les fiches décidables (seules les NON le sont) ; `mark_delivered(keys)` est appelé **après livraison réussie** (échec d'envoi → reproposée demain ; plafond 3/j → non marquée) | `test_fiche_non_livree_reste_disponible`, `test_fiche_livree_est_marquee` |
| **B2-01** | Un PER ≤ 0 était servi comme valeur : brvm.org affiche « 0.00 » quand le PER n'est pas calculable → payout calculé à 0 % = **fausse sécurité** (cache : STAC/SICC/SCRC/UNXC à 0.0) | PER ≤ 0 traité comme **INDISPONIBLE** (jamais caché, jamais servi) ; scrape et cache filtrés | `test_per_cache_rejette_les_valeurs_invalides` |
| **B2-03** | Cache PER sans date (fraîcheur inconnue) ; écriture **non atomique** ; deux lectures divergentes possibles | Schéma `{code: {"per": …, "date": ISO}}` (rétro-compatible ancien format plat) ; écriture atomique tmp+replace ; `per_date` exposé par `get_fundamentals` | `test_per_cache_schema_date_et_pas_de_residu` |
| **B0-04/B1-08** | DEUX formules de prix d'entrée (~1,4 % d'écart) : `entry_price_ref` (IPS pur, sans frais) vs `entry_price_for_net` (frais inclus) — la valeur affichée pouvait faire acheter à un prix qui ne tient pas le net 4 % | **Formule unique** : `entry_price_ref = entry_price_for_net(dps)` (frais inclus). Docstring, note du noyau-check (« dps ÷ 5,45 % ÷ 1,014 — frais inclus ») et `portfolio.json` migrés (SNTS 36 245 → **35 744,58**) | `test_exit_and_entry_prices`, `test_open_dividend_position` (mis à jour) |

## B. Deux découvertes d'infrastructure (réparées dans la foulée)

### B-infra-1 — Le BOC échouait depuis le 02/10 (pymupdf absent du python du cron)
- **Symptôme** (rendu VISIBLE par la correction B2-04 du lot 1) : chaque run du check
  quotidien affichait « ⚠ échec : No module named 'pymupdf' » sur l'étape BOC — donc
  **10 jours sans veille des bulletins officiels** (dividendes, convocations).
- **Cause** : les scripts cron de Hermes tournent sur un python qui n'embarque pas les
  dépendances du projet (pymupdf, ajouté au requirements le 09/08).
- **Correction officielle** : `hermes cron edit <id> --interpreter …` (option prévue
  exactement pour ça : « so it can import packages Hermes does not ship »). Création d'un
  **venv projet dédié** `C:\Users\LEO\projects\Bridge Bank\.venv` (uv, Python 3.12,
  `requirements.txt` + pytest) et branchement des **5 jobs** BridgeBank dessus
  (daily, rapport mensuel, backup, radar, veille spé).
- **Preuve** : run réel déclenché le 12/10 à 17h03 via le runner → « BOC 09/10/2026 (brvm) :
  aucun événement dividende sur le noyau » + heartbeat « ✅ Check quotidien » 9 étapes/9.

### B-infra-2 — Course de données sur `per_cache.json` (48 → 5 entrées)
- **Symptôme** : le cache PER a été écrasé de 48 à 5 entrées pendant que le check quotidien
  (screener, 3 threads) tournait en même temps qu'un autre accès.
- **Cause** : `get_per_brvm` faisait load → modif → save **sans atomicité ni verrou** ;
  un thread lisait le fichier pendant qu'un autre l'écrivait (JSON tronqué → `{}` →
  sauvegarde d'une entrée → écrasement en cascade).
- **Correction** : écriture atomique (tmp + replace) **et verrou inter-processus** (fichier
  `O_EXCL` avec purge d'un verrou orphelin > 60 s, timeout 15 s non bloquant).
- **Preuve** : `test_verrou_cache_libere_et_orphelin_purge` ; cache reconstruit
  (44 entrées datées du 12/10, les 4 « 0.00 » de brvm.org correctement absents).

## C. Preuves d'exécution

- **356 passed, 1 xfailed** (le seul xfail restant = B2-11, lot 3). Suite lancée avec le
  venv projet (`.venv`).
- **Gardien des sorties** recapturé : 10 clés changées, contrôle automatique — **10/10 sont
  des transformations attendues** (×0,88 IRVM : DRIP + commande dividende ; ÷1,014 frais :
  prix d'entrée unique). Zéro changement inexpliqué.
- **Migration `portfolio.json`** : entry_price_ref SGBC 47 776,67 → 47 117,03 ; SLBC 38 995 →
  38 456,61 ; SNTS 36 245 → 35 744,58 ; PALC 9 195,93 → 9 068,96.
- **Cache PER restauré et daté** : 44 entrées `{per, date: 2026-10-12}`.
- Run réel du check 17h03 via le runner : BOC ✅, tout vert sauf « Intégrité des données »
  (cache historique en retard — voir Limites).

## D. Limites connues (honnêteté)

- **Cache historique en retard** : la dernière barre du cache est au **30/09/2026** (48 titres
  signalés par l'étape Intégrité à chaque run). Les analyses techniques récentes tournent
  donc sur des barres de fin septembre (les cours LIVE sont utilisés là où c'est prévu).
  **Prochain chantier candidat** : diagnostiquer le refresh historique puis relancer.
- `spec_veille` : le repli sur `opened_at` subsiste pour les stop-outs dont l'horodatage
  (`closed_at` ou date dans `close_reason`) est illisible — aucun cas réel concerné aujourd'hui.
- La passe mécanique C1 (lot 1) ne couvre pas les scripts d'étude — inchangé.
- Le python du runner Hermes n'a pas été modifié : les jobs futurs (nouveaux scripts du
  projet) devront aussi recevoir `--interpreter <venv projet>` à leur création.
