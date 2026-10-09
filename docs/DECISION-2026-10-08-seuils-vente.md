# Décision — les seuils de vente sur plus-value ne déclenchent plus de vente

**Date :** 8 octobre 2026
**Portée :** `src/portfolio.py`, `src/seuils_vente.py`, `src/regime_marche.py`, `src/report.py`
**Statut :** implémentée, testée (216 tests), 6 points de contrôle validés

---

## 1. Le problème

Le système auto-calibrait un seuil de vente par titre et proposait « VENDS 1/3 » dès que
le cours le franchissait. Mesure d'attribution : **les paliers coûtent −43,1 points de
rendement ajusté à l'exposition** (variante D contre noyau passif), et le challenge
multi-modèles a trouvé la même chose par un chemin indépendant.

## 2. La cause — un défaut de conception, pas un mauvais réglage

`calibrate_profit_threshold` retenait le seuil dont la **probabilité ponctuelle** de
baisse était la plus haute. Deux conséquences mécaniques :

- cette probabilité monte avec le seuil (on n'exige +X % que si le titre a déjà monté) ;
- le nombre de cas, lui, **diminue**.

Le seuil gagnant est donc structurellement celui qui a **le moins de cas**. Sur SNTS :
86 % de baisses… mesurées sur **7 cas**. Intervalle de confiance (Wilson) : **49 % – 97 %**.
La borne basse est sous 50 % — le chiffre est réel mais **non concluant**.

| Titre | Seuil | Cas | Prob. | Borne basse | IC 95 % |
|---|---|---|---|---|---|
| SNTS | 13 % | 7 | 86 % | **49 %** | 49-97 % |
| SGBC | 10 % | 30 | 63 % | **46 %** | 46-78 % |
| SLBC | 5 % | 41 | 51 % | **36 %** | 36-66 % |
| PALC | 5 % | 56 | 46 % | **34 %** | 34-59 % |

**Aucune borne basse n'atteint 50 %.** Aucun de ces seuils n'est distinguable du hasard.

Cause de la pauvreté en cas chez SNTS : c'est le titre **le plus calme** du portefeuille
(volatilité 1,37 %/jour contre 2,86 % pour PALC) — atteindre +13 % en 20 séances y est
rare par nature. Son historique est pourtant le plus long (2 346 barres, aucune division
non corrigée) : le problème n'est pas la donnée, c'est la méthode de sélection.

---

## 3. Ce qui a été décidé

**Un seuil de vente sur gain ne déclenche une consigne que si sa borne basse d'intervalle
de confiance atteint 50 %.** Sinon il reste **visible mais informatif**.

- Les 4 seuils existants sont **conservés** (aucune suppression) et passés en
  `mode: "informatif"`.
- Tout nouveau seuil calé automatiquement reçoit son mode par le test de Wilson.
- Le **mode déclencheur reste implémenté** : si un titre présentait un jour un signal
  fondé, le message de vente d'origine partirait.

## 4. Ce qui a été ajouté au-delà du strict correctif

- **Régime de marché** dans les alertes de renforcement. Indicateur explicitement défini :
  indice médian des titres suivis (buy & hold, base 100), comparé à sa moyenne 200 séances.
  Motif : le renforcement gagne **67-69 %** du temps en entrant en année de krach contre
  **42-49 %** en marché haussier. Conformément à la règle « **ne bloque pas** », l'alerte
  **part toujours** — elle est simplement documentée par le régime.
- **Alerte de trésorerie dormante** : informative, après 3 relevés consécutifs au-dessus de
  35 % (cible 30 %). **Aucun investissement n'est déclenché, aucun ordre proposé.**

## 5. Les 6 points de contrôle impératifs — vérifiés

| # | Point | Vérification |
|---|---|---|
| 1 | Les 4 seuils restent visibles en informatif, l'auto-calibrage respecte le mode | `test_les_quatre_seuils_historiques_sont_conserves`, `test_les_quatre_seuils_sont_informatifs`, `test_mode_explicite_est_respecte` |
| 2 | Wilson bloque les seuils non significatifs **sans effacer** les historiques | `test_petit_echantillon_non_significatif`, `test_echantillon_insuffisant_bloque_meme_avec_100_pourcent` ; migration avec sauvegarde `.bak-avant-mode` |
| 3 | Le renforcement dépend d'un indicateur **défini et calculé** | `test_indice_median_est_en_buy_and_hold`, `test_etat_marche_est_traçable`, `test_indice_reel_monte_et_creuse_en_2020` |
| 4 | L'alerte trésorerie est informative, aucun investissement automatique | `test_alerte_tresorerie_est_informative`, `test_alerte_tresorerie_nappelle_aucune_fonction_dinvestissement` (garde-fou structurel sur le code source) |
| 5 | Sorties fondamentales, rebalancement, poche spé **inchangés** | `test_dividende_coupe_declenche_toujours_la_vente_totale`, `test_per_explose_declenche_toujours_la_vente_totale`, `test_prix_de_sortie_declenche_toujours_la_vente_totale` ; `speculation.py` ne référence aucune de ces constantes ; le rebalancement n'existe pas dans le code |
| 6 | pytest et non-régression | **216 passés, 0 échec** |

## 6. Deux pièges rencontrés pendant l'implémentation

**(a) Modifier la table du code n'aurait rien changé.** `profit_threshold_for` lit
**d'abord** `data/profit_thresholds.json`, et la table `PROFIT_THRESHOLDS` seulement en
repli. Pire : `calibrate_missing_thresholds`, appelé chaque matin, **recalcule tout titre
absent du fichier** — supprimer une entrée l'aurait fait revenir le lendemain. La
modification devait donc porter sur la **logique** (un champ `mode`), pas sur les données.

**(b) L'indicateur de marché était faux au premier jet.** La version initiale cumulait
`(1 + médiane des variations quotidiennes)` : c'est un indice à **rebalancement
quotidien**, qui subit le *volatility drag*. Il affichait **−43 %** sur 2017-2026 là où le
marché montait. Corrigé en buy & hold (médiane des séries normalisées) → **+60,9 %**, avec
les creux attendus (33,9 en mars 2020, 44,6 en décembre 2018). *Un indicateur de régime
qui se trompe de sens est pire que pas d'indicateur.*

**Bonus :** le contrôle croisé de la migration a révélé que le fichier de calibration
était **périmé** — SLBC y était stocké à 54 % alors que l'historique corrigé donne 51 %.

## 7. Effet attendu

Le système cesse de proposer des ventes sur un signal de bruit — **+43,1 points** de
rendement ajusté mesurés sur la période 2022-2026, sans rien retirer d'autre. Les sorties
fondamentales (dividende coupé, PER > 40, rendement net ≤ 2 %) restent le seul déclencheur
de vente totale, conformément à la doctrine déjà en place.

**Réserve honnête :** cette décision s'appuie sur 4 titres et 9 ans d'historique. Elle ne
prouve pas qu'aucun signal de vente n'existe — elle établit qu'**aucun de ceux testés
n'est distinguable du hasard**, ce qui est une raison suffisante pour ne pas vendre sur
cette base.
