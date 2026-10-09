# Centralisation des règles métier — catalogue unique et vérifiable

**Date :** 8 octobre 2026
**Statut :** implémentée, **non-régression prouvée**, 231 tests verts

---

## 1. Le problème, mesuré

Un audit automatique (`scripts/auditer_constantes.py`) a trouvé **194 définitions de
constantes pour 159 notions**, réparties sur 39 fichiers. Certaines règles étaient
recopiées :

| Règle | Endroits | Fois |
|---|---|---|
| PER maximum | `backtest_noyau` · `noyau_check` · `portfolio` · `screener` | **4** |
| Payout max | `backtest_noyau` · `noyau_check` · `portfolio` | **3** |
| IRVM | `backtest_noyau.IRVM` · `taxation.IRVM_DIVIDEND_TAX` | 2 noms |
| Rendement d'entrée | `backtest_noyau.RENDEMENT_NET_MIN` · `taxation.TARGET_NET_YIELD_ENTRY` | 2 |
| Frais de courtage | `challenge_validateur` · `paliers_sortie` · `spec_profiles` · `strategie_leo` | **4** |

**Deux cas concrets, pas théoriques :**

- **« Combien de cas faut-il pour valider un seuil ? » avait DEUX réponses** (`6` dans
  `portfolio.py`, `8` dans `seuils_vente.py`). Un seuil à 6 cas passait un filtre et se
  faisait rejeter par l'autre.
- **`FRAIS = 0.028` (aller-retour) et `FRAIS_PAR_SENS = 0.014`** portent le **même mot**
  avec des **sens opposés**. Les confondre **double les frais, en silence** : le calcul
  tourne, le résultat est faux.

## 2. Ce qui a été fait — et ce qui n'a PAS été fait

**Créé** : `src/regles.py` — un **catalogue**, pas une usine. Il ne contient que des
valeurs, aucune logique, et n'importe que `taxation` (lui-même sans dépendance), donc
aucun cycle d'import possible.

**Il ne redéfinit pas la fiscalité** : `taxation.py` en était déjà la source correcte
(taux de courtage, TVA, frais BRVM, conservation). Le catalogue la **réexporte**.

```
IRVM               = IRVM_DIVIDEND_TAX        # 0,12
FRAIS_PAR_SENS     = BROKERAGE_FEE            # 0,014 — courtage + TVA + BRVM
FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_SENS       # 0,028 — DÉRIVÉ, jamais recopié
```

**Découverte au passage** : `strategie_leo.FRAIS_PAR_SENS = 0.014` n'était pas une valeur
arbitraire — c'est **exactement** `BROKERAGE_FEE` (0,008 × 1,18 + 0,00456). C'était une
copie d'un calcul réel.

**Pas fait, volontairement** :
- ❌ Aucun fichier déplacé, aucun dossier créé
- ❌ Aucune constante technique touchée (`STATE_FILE`, `CACHE_FILE`, URLs) — leur
  divergence entre modules est **normale**
- ❌ Aucune logique déplacée — la séparation par domaines viendra **après**

Les modules existants **gardent leurs noms locaux** par alias, ce qui évite de toucher
leur logique :

```python
from .regles import PER_MAX as PER_MAX_NOYAU
```

## 3. La preuve de non-régression

Avant toute modification, `scripts/auditer_constantes.py` a capturé la **valeur effective**
de chaque constante — lue en **important réellement les modules**, pas en analysant le
texte, parce que c'est la valeur effective qui compte.

Après la centralisation :

```
$ python scripts/auditer_constantes.py --comparer
1 VALEUR(S) MODIFIEE(S) :
  src.portfolio.PROFIT_MIN_EPISODES : 6 -> 8
```

**193 valeurs identiques, une seule modifiée** — et c'est celle qu'on a **décidée** :
`MIN_EPISODES` passe à 8, pour qu'il n'y ait plus qu'une réponse à la question. C'est
exactement ce que le snapshot doit produire : **un changement explicite, jamais silencieux.**

## 4. Le garde-fou contre le retour de la duplication

Une charte se perd à la première réécriture. Un test, non :
`tests/test_regles_centralisees.py` (7 tests) refuse la **réapparition d'une valeur
littérale** pour une règle cataloguée, dans n'importe quel module.

Il autorise l'import, l'alias et la dérivation ; il refuse la copie — **même avec la
bonne valeur**, parce que c'est la copie qui divergera.

Il verrouille en plus trois cohérences : le rapport exact de 2 entre `FRAIS_PAR_SENS` et
`FRAIS_ALLER_RETOUR`, le fait que les frais viennent du courtage réel, et l'unicité de la
réponse au nombre de cas requis.

## 5. Résultat

| Avant | Après |
|---|---|
| 194 définitions | **189** |
| 4 définitions du PER max | **1** (catalogue) |
| 2 réponses à « combien de cas » | **1** (8) |
| Duplication non détectable | **7 tests qui la refusent** |
| Aucun moyen de prouver l'absence d'effet de bord | **`--comparer` sur 189 valeurs** |

## 6. Ce qui reste à faire (étape suivante, séparée)

1. **Séparation par domaines** (achats / sorties / fiscalité / données) — à faire
   **après**, quand la centralisation aura montré qu'elle tient dans le temps.
2. **Point d'attention détecté** : `COMPANY_HINTS` existe en **deux versions divergentes**
   (`src/boc.py` utilise des soulignés `societe_generale`, `src/news.py` des espaces
   `societe generale`, et `news` connaît en plus `sgb` et `palmci`). Chaque module traite
   un format d'entrée différent — ce n'est pas un bug, mais deux tables qui résolvent la
   même chose finiront par diverger. À unifier quand la séparation par domaines arrivera.
3. **Le reste du système utilise encore `:,.0f`** (format anglais) dans ses messages —
   l'extension de `format_fr` à toutes les alertes reste à faire.
