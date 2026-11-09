# DÉCISION — 09/11/2026 — Renforcement PALC de 26 actions à 7 300 F

**Décision de LEO** : ordre d'achat **26 actions PALM CI (PALC) à 7 300 F**, déposé le
09/11/2026 (ordre n° 980998), **toujours actif** à la clôture de cette session.
Motif donné par LEO : *« Je pense avoir payé cette action trop cher, je voudrais ramener son
CMP à sa valeur réelle »*, puis précisé : *« si on arrive à faire baisser le CMP, atteindre
la plus-value est plus probable quand une hausse est constatée »* → *« Je veux bien prendre
le risque. »*

**Statut des données** : quantité exécutée **0** / prix exécuté **0** au moment de la
décision. **Aucune position n'est enregistrée dans `portfolio.json`** — règle du dépôt
(leçon BICC 25/09 : une annonce d'ordre n'est pas une exécution). La mise à jour se fera
quand une ligne montrera une quantité exécutée > 0.

## Ce que la décision fait, chiffré

| | Avant | Après exécution |
|---|---|---|
| Actions PALC | 26 | **52** |
| CMP | 8 641 F | **8 022 F** |
| Capital engagé | 224 666 F | **417 123 F** |
| Coût de l'ordre | — | **192 457 F** (1,4 % de frais inclus) |
| Cash restant | 198 238 F | **5 781 F** (97 % du cash consommé) |
| Poids de la ligne (total) | 19,1 % | **38,1 %** |
| Poids des actions seules | 23,6 % | **47,2 %** |
| Loyer au CMP | 4,31 % net | **4,70 % net** |
| Seuil de vente à l'équilibre | 8 762 F (+16,8 %) | **8 134 F (+8,5 %)** |

## La thèse de LEO, et sa validation mesurée

Sur l'historique complet de PALC (2 265 séances, 2017 → 2026) :

| Horizon | Le cours atteint +7,1 % (seuil des 52) | Le cours atteint +16,8 % (seuil des 26) |
|---|---|---|
| 6 mois | **64,9 %** | 51,6 % |
| **12 mois** | **75,3 %** | 63,0 % |
| 24 mois | **81,1 %** | 70,9 % |

⇒ **La thèse est exacte** : renforcer abaisse le seuil de moitié ET le seuil bas est atteint
plus souvent. Ce n'est pas un sophisme, c'est de l'arithmétique et une fréquence mesurée.

## Le risque accepté, chiffré

Fréquences de baisse observées sur les mêmes 12 mois (n = 2 015 fenêtres) :
−20 % dans **60,5 %** des cas · −30 % dans **48,8 %** · −44 % dans **22,5 %**.

| Cours atteint | 26 actions | **52 actions** |
|---|---|---|
| 4 200 F (−44 %) | −115 466 F | **−198 723 F** |
| 6 000 F (−20 %) | −68 666 F | **−105 123 F** |
| 7 500 F (aujourd'hui) | −29 666 F | −27 123 F |
| 8 250 F (+10 %) | −10 166 F | **+11 877 F** |
| 9 000 F (+20 %) | +9 334 F | **+50 877 F** |

**Le point décisif énoncé avant la décision** : le gain au seuil est comparable dans les
deux cas (≈ +36 000 F, car le pourcentage plus faible s'applique à une base plus grande),
mais la perte augmente de 53 % à −20 % et de 72 % à −44 %. Le renfort est un **levier**, pas
un avantage : il accélère le retour au gain en amplifiant aussi les pertes.

**Alternative proposée et écartée par LEO** : 13 actions (96 229 F) → seuil +11,2 %, poids
35,4 %, cash conservé 102 009 F.

## Points de vigilance à la prochaine session

1. **Si l'ordre s'exécute** → `portfolio.json` : `quantity` 26 → 52, `entry_price` → 8 022 F,
   et vérifier que `entry_price_ref` (seuil de renfort) reste cohérent.
2. **Cash à 5 781 F** : plus aucune marge. Les alertes d'achat continueront de partir
   (règle : l'alerte ne dépend jamais du cash, décision LEO 08/09) — la logistique est
   séparée de l'alerte.
3. **Concentration** : 47,2 % des actions sur un titre qui a perdu −44 % en décembre 2024.
   Le plafond informatif de 35 % est dépassé sciemment.
4. **Date de fin de l'ordre : 09/11/2026** — s'il n'est pas exécuté à la clôture, il expire.
   Dans ce cas, la décision devra être rejouée (l'ordre ne se re-crée pas tout seul).

## Traçabilité

Décision prise après exposé contradictoire chiffré dans la session du 09/11/2026.
Scripts de mesure : `cmp_illusion.py` et `cmp_probabilite.py` (scratch de session),
résultats reproduits dans ce document. Hiérarchie des sources respectée : cette décision
datée prime sur les commentaires de code et sur l'IPS.
