# Cas d'étude — ETIT (Ecobank / ETI Togo)

Opération réelle de LEO (2026), documentée comme **référence de la règle de sortie
value** : un bon achat value gâché par une sortie de type spéculatif.

## Les transactions

| Date | Opération | Quantité | Prix | Montant |
|---|---|---|---|---|
| 24/04/2026 | Achat | 6 500 | 28 F | 182 000 F |
| 18/05/2026 | Achat | 3 401 | 29 F | 98 629 F |
| **Total achat** | | **9 901** | PMP 28,34 F | **280 629 F** |
| 01/07/2026 | Vente | 9 901 | 43 F | 425 743 F |

## Les chiffres clés

- **Gain réalisé** : 145 114 F = **+51,7 %** en 68 jours.
- **PER à l'achat** : ≈ 1,6 (BPA ≈ 17,66 F — source PER 3,51 à 62 F sur brvm.org).
- **PER à la vente (43 F)** : ≈ 2,4.
- **PER au pic (≈ 62 F, août 2026)** : ≈ 3,5.

## La leçon

1. **La value gagne.** Achat à PER ≈ 1,6 (sous-évaluation extrême) → le marché a
   réévalué. C'est la mécanique que le noyau dividende cherche à exploiter.
2. **La sortie était prématurée.** Vendu à 43 F alors que la thèse value
   (« le titre est sous-évalué ») était encore intacte : PER ≈ 2,4, encore très
   bas. Le titre a continué jusqu'à ~62 F (PER 3,5).
   - **Gain manqué** : 188 119 F (plus que le gain réalisé).
   - **Scénario value** (garder jusqu'à 62 F) : **+119 %** au lieu de +51,7 %.

## Le piège : mélanger deux logiques de sortie

| Logique | Règle de sortie | Encodée dans |
|---|---|---|
| **Value** (noyau) | sur la **thèse** : PER revient à sa juste valeur, dividende coupé | `portf` — sortie sur fondamentaux, JAMAIS sur un % de gain |
| **Spéculative** (poche) | sur le **prix** : stop −15 %, +20 %, +35 %, +50 % | `spec` — sortie mécanique par pourcentage |

Ici : **achat value** (PER 1,6) mais **sortie spéculative** (+51 % arbitraire).
Résultat : 1,5× au lieu de 2,5×.

## Règle de sortie value — actionnable

Sortir du noyau uniquement quand **un de ces déclencheurs fondamentaux** se produit :

1. **Dividende coupé > 50 %** ou suspendu (la thèse « revenu » est morte) ;
2. **PER explose > 40** (décote résorbée ou bénéfices en chute) ;
3. **Prix de sortie atteint** (rendement net tombé à 2 %).

Une simple hausse du cours **n'est pas** un déclencheur de sortie value.
