# Mesure des taux de réussite par ZONE — poche spéculative BRVM

- **Objet** : vérifier sur les données réelles les taux de réussite par ZONE
  (position du prix dans la fourchette des ~5 ans) codés en dur dans
  `src/strategie/spec_fiche.py` (`ZONE_LABELS`) : FORCE 83 %, BAS_SOLIDE 80 %,
  HAUT_FRAGILE « 0 gagnant sur 4 », BAS_ECRASE 50 %.
- **Script reproductible** : `scripts/mesurer_zones_spec.py`
- **Mesuré le** : 2026-11-09 (fichier nommé `-2026-11-02` car il clôt le chantier
  « prix des alertes spé » du 02/11/2026).
- **Source** : `data/history_clean.pkl` (cache canonique, ajusté des divisions et
  nettoyé), lu via `history_io.charger_cache` (empreinte SHA-256 vérifiée).
  Aucun accès réseau.

## Méthode — réutilisation de la machinerie existante

Le script rejoue exactement le calcul des fréquences historiques de
`scripts/calibrate_spec_profiles.py` et y ajoute la dimension ZONE :

- détection des schémas par `spec_profiles.detect_schemas` (sans volumes, comme
  le calibrate) → CASSURE / EVEIL / PANIQUE ;
- zone par `spec_profiles.zone_of(closes[:i+1])` puis `zone_label` ;
- rendement net à 12 mois (252 séances), frais aller-retour 2,8 % déduits ;
- pic maximal sur l'horizon pour les paliers +20 % / +50 % ;
- espacement anti-recouvrement de 60 séances par schéma ;
- séries d'au moins 500 barres, première barre > 0.

**Important** : en production, la fiche exige en plus la confirmation par le
volume pour CASSURE et EVEIL — les signaux réellement déclenchés sont donc un
sous-ensemble de ceux comptés ici. Les totaux par schéma re-mesurés ici
(5 / 28 / 18) sont identiques à ceux qu'on obtient en rejouant la même
agrégation sur le cache **brut** courant, preuve que la lecture du cache propre
ne biaise pas la comparaison.

**Seuil de suffisance** : 10 cas par cellule. En dessous, la cellule est
marquée INSUFFISANT et aucune conclusion n'en est tirée.

## Totaux par schéma (toutes zones confondues)

| Schéma | Cas | % finissant plus haut à 12 m | Gain net médian | vs `spec_profiles.json` |
|---|---|---|---|---|
| CASSURE | 5 | 80 % (4/5) | +105,4 % | json : n=10 — **stale** (voir limites) |
| EVEIL | 28 | 61 % (17/28) | +21,4 % | json : n=28 ✅ identique |
| PANIQUE | 18 | 50 % (9/18) | +2,0 % | json : n=16 — **stale** (voir limites) |
| **Total** | **51** | 59 % (30/51) | +21,4 % | |

## Résultat détaillé par schéma × zone

Colonnes : `n` cas · `% hausse 12 m` (part finissant plus haut) · `médian`
(gain net) · `+20 %` / `+50 %` (part des cas ayant touché le palier) ·
`codé dur` (taux de la zone dans ZONE_LABELS) · suffisance (seuil 10).

### CASSURE (total 5 cas)

| Zone | n | % hausse 12 m | médian net | +20 % | +50 % | codé dur | échantillon |
|---|---|---|---|---|---|---|---|
| 0-20 | 1 | 100 % | +185,5 % | 100 % | 100 % | 50 % | INSUFFISANT |
| 20-40 | 2 | 100 % | +89,0 % | 100 % | 100 % | 80 % | INSUFFISANT |
| 40-60 | 0 | — | — | — | — | neutre | aucun cas |
| 60-80 | 2 | 50 % | +81,2 % | 50 % | 50 % | 0 % | INSUFFISANT |
| 80-100 | 0 | — | — | — | — | 83 % | aucun cas |

### EVEIL (total 28 cas)

| Zone | n | % hausse 12 m | médian net | +20 % | +50 % | codé dur | échantillon |
|---|---|---|---|---|---|---|---|
| 0-20 | 11 | 55 % | +56,8 % | 73 % | 64 % | 50 % | suffisant |
| 20-40 | 5 | 100 % | +94,8 % | 100 % | 100 % | 80 % | INSUFFISANT |
| 40-60 | 9 | 67 % | +11,2 % | 100 % | 44 % | neutre | INSUFFISANT |
| 60-80 | 3 | 0 % | −34,7 % | 0 % | 0 % | 0 % | INSUFFISANT |
| 80-100 | 0 | — | — | — | — | 83 % | aucun cas |

### PANIQUE (total 18 cas)

| Zone | n | % hausse 12 m | médian net | +20 % | +50 % | codé dur | échantillon |
|---|---|---|---|---|---|---|---|
| 0-20 | 7 | 43 % | −14,7 % | 71 % | 43 % | 50 % | INSUFFISANT |
| 20-40 | 3 | 100 % | +6,9 % | 67 % | 67 % | 80 % | INSUFFISANT |
| 40-60 | 4 | 50 % | +10,5 % | 100 % | 25 % | neutre | INSUFFISANT |
| 60-80 | 2 | 0 % | −36,5 % | 50 % | 0 % | 0 % | INSUFFISANT |
| 80-100 | 2 | 50 % | +13,4 % | 100 % | 50 % | 83 % | INSUFFISANT |

## Comparaison par zone (schémas confondus) vs taux codés en dur

| Zone | n | mesuré | médian net | codé dur | écart | verdict |
|---|---|---|---|---|---|---|
| 0-20 (BAS_ECRASE) | 19 | 53 % | +56,8 % | 50 % | +3 pt | **compatible** |
| 20-40 (BAS_SOLIDE) | 10 | 100 % | +87,9 % | 80 % | +20 pt | **dépasse le codé dur** (mais n=10, juste au seuil) |
| 40-60 (MILIEU) | 13 | 62 % | +11,2 % | — (neutre) | — | aucun taux codé |
| 60-80 (HAUT_FRAGILE) | 7 | 14 % | −32,9 % | 0 % | +14 pt | **non mesurable** (< 10 cas) |
| 80-100 (FORCE) | 2 | 50 % | +13,4 % | 83 % | −33 pt | **non mesurable** (< 10 cas) |

## Avertissement : biais de survie

Les 48 titres du cache sont ceux encore présents dans la source de données ;
**les titres radiés sont absents**. Tout taux mesuré ici est donc optimiste : un
titre qui s'est effondré puis a été radié (rendement ≈ −100 %) n'apparaît jamais
dans l'échantillon. Ce biais frappe surtout les zones du bas et du haut de la
fourchette, précisément celles où un titre peut disparaître (BAS_ECRASE = titres
écrasés, HAUT_FRAGILE = « anciens champions qui s'essoufflent »). Les pourcentages
sont des **fréquences observées, pas des probabilités** — les perdants existent.

## Conclusion : les taux 83 / 80 / 50 / « 0-sur-4 » sont-ils confirmés ?

- **50 % (BAS_ECRASE, 0-20) — CONFIRMÉ.** 19 cas, 53 % finissent plus haut :
  l'ordre de grandeur est exact. Nuance : le gain net médian mesuré (+56,8 %)
  est tiré par des extrêmes (CASSURE +185 %, EVEIL +89 % sur des microsamples) ;
  pour le schéma PANIQUE seul, la zone 0-20 est bien médiocre (43 %, médian
  −14,7 %) — « pas cher ne paie pas » reste vrai pour le rachat de panique.
- **80 % (BAS_SOLIDE, 20-40) — CONFIRMÉ (au minimum).** 10 cas, 10 gagnants
  (100 %), médian +87,9 % : la zone 20-40 ressort comme la meilleure mesurée.
  Mais n=10 est exactement le seuil : c'est un ordre de grandeur confirmé, pas
  une loi. La valeur codée 80 % n'est pas contredite (elle est même dépassée).
- **83 % (FORCE, 80-100) — NON MESURABLE.** 2 cas seulement (1 gagnant, 50 %).
  Le 83 % ne peut être ni confirmé ni infirmé sur un tel échantillon. La zone
  FORCE n'a quasiment jamais coïncidé avec un signal de ces trois schémas sur
  les 10 dernières années.
- **« 0 gagnant sur 4 » (HAUT_FRAGILE, 60-80) — NON MESURABLE au sens strict,
  mais direction confirmée.** 7 cas, 1 gagnant (14 %), médian −32,9 % : le
  « 0 sur 4 » n'est pas reproduit à l'identique (on trouve 1 gagnant sur 7),
  et 7 cas < 10 interdit toute conclusion chiffrée. En revanche la zone 60-80 a
  le **pire profil de toutes les zones** (14 % de réussite, médian négatif) :
  le verdict « NON » que la fiche oppose à cette zone est soutenu par la mesure,
  même si le chiffre exact « 0 sur 4 » n'est pas reproductible.

**En résumé** : sur les quatre taux affichés, **un seul est solidement confirmé
(50 %)** ; un est **confirmé a minima (80 %)**, un est **non mesurable (83 %)**
et le dernier (**« 0 sur 4 »**) est **non mesurable tel quel mais va dans le
bon sens**. Aucun taux n'est *infirmé*. Le message d'ensemble de la fiche — les
zones 20-40 sont bonnes, le bas (0-20) ne paie pas pour la panique, et 60-80
est une zone à fuir — est cohérent avec la mesure réelle.

## Limites

- **`spec_profiles.json` est périmé par rapport au cache courant.** Le fichier
  affiche CASSURE n=10 et PANIQUE n=16 ; rejouer la même agrégation sur le cache
  actuel (propre comme brut) donne 5 et 18. Les fréquences affichées dans les
  fiches reposent donc sur un calibrage plus ancien que les données — à
  re-calibrer (hors périmètre de cette tâche, qui ne modifie aucune donnée de
  production).
- **Détection sans volume** (fidèle au calibrate) : les vrais signaux filtrés
  par le volume en production sont moins nombreux encore que les échantillons
  ci-dessus.
- **Échantillons par cellule très petits** : 9 cellules sur 15 sont INSUFFISANTES
  (< 10 cas). C'est la limite structurelle de toute statistique par zone sur la
  BRVM (48 titres, 10 ans).

## Preuve (sortie réelle du script)

```
$ PYTHONPATH= "C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python" scripts/mesurer_zones_spec.py
...
── CASSURE ──
zone        n  % hausse   médian   % +20   % +50  codé dur  échantillon
0-20        1      100%   185.5%    100%    100%      50 %  INSUFFISANT
20-40       2      100%    89.0%    100%    100%      80 %  INSUFFISANT
40-60       —         —        —       —       —         —    aucun cas
60-80       2       50%    81.2%     50%     50%       0 %  INSUFFISANT
80-100      —         —        —       —       —      83 %    aucun cas
TOTAL           5           80%      105.4%

── EVEIL ──
zone        n  % hausse   médian   % +20   % +50  codé dur  échantillon
0-20       11       55%    56.8%     73%     64%      50 %    suffisant
20-40       5      100%    94.8%    100%    100%      80 %  INSUFFISANT
40-60       9       67%    11.2%    100%     44%         —  INSUFFISANT
60-80       3        0%   -34.7%      0%      0%       0 %  INSUFFISANT
80-100      —         —        —       —       —      83 %    aucun cas
TOTAL          28           61%       21.4%

── PANIQUE ──
zone        n  % hausse   médian   % +20   % +50  codé dur  échantillon
0-20        7       43%   -14.7%     71%     43%      50 %  INSUFFISANT
20-40       3      100%     6.9%     67%     67%      80 %  INSUFFISANT
40-60       4       50%    10.5%    100%     25%         —  INSUFFISANT
60-80       2        0%   -36.5%     50%      0%       0 %  INSUFFISANT
80-100      2       50%    13.4%    100%     50%      83 %  INSUFFISANT
TOTAL          18           50%        2.0%

── PAR ZONE (schémas confondus) vs taux codés en dur dans ZONE_LABELS ──
zone        n   mesuré   médian    codé dur    écart  verdict
0-20       19      53%    56.8%        50 %    +3 pt  compatible
20-40      10     100%    87.9%        80 %   +20 pt  dépasse le codé dur
40-60      13      62%    11.2%  — (neutre)        —  aucun taux codé
60-80       7      14%   -32.9%         0 %   +14 pt  NON MESURABLE (<10 cas)
80-100      2      50%    13.4%        83 %   -33 pt  NON MESURABLE (<10 cas)
```
