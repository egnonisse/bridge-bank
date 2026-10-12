# Couverture des tests — la carte réelle (12/10/2026)

**Pourquoi.** L'audit avait constaté en Phase 0 qu'**aucun outil de couverture** n'était disponible
et s'était refusé à publier un taux inventé. La mesure existe maintenant : elle remplace « on pense
que c'est testé » par une carte.

**Méthode.** `pytest-cov 7.1.0` / `coverage 7.16.2`, déclaré dans `requirements-dev.txt` (que la CI
installe déjà) et configuré dans `pyproject.toml` (`source = ["src"]`, **aucun `fail_under`** : un
seuil se fixe après avoir vu la mesure). Suite exécutée **après gel de `data/`** — vérification
d'intégrité après coup : **0 modifié, 0 ajouté, 0 disparu sur 111 fichiers**. Preuve brute :
`audit/preuves/couverture_tests_2026-10-12.txt`.

```
379 passed in 158.57s (0:02:38)
TOTAL   5956 statements   2947 missed   51%
```

## 1. Par couche

| Couche | Couverture | Lecture |
|---|---|---|
| **Règles et décisions** (ce qui DÉCIDE) | `regles` **100 %** · `empreinte` **100 %** · `format_fr` **100 %** · `seuils_vente` **98 %** · `taxation` **96 %** · `schema_seuils` **95 %** · `models` **95 %** · `notify` **88 %** · `noyau_check` **88 %** · `portfolio` **87 %** | **Solide.** La logique qui produit une alerte ou un refus est exercée. |
| **Collecte et données** | `cache_integrity` 89 % · `live` 92 % · `dividends` 92 % · `fundamentals` 70 % · `dividend_history` 72 % · `nettoyage_aberrantes` 39 % · `bsapi` **27 %** | Mitigé — le réseau et le nettoyage sont peu testés (attendu, mais à savoir). |
| **Analyse** | `bonds` 93 % · `news` 93 % · `radar` 80 % · `screener` 71 % · `boc` 65 % · `fondamentaux_historiques` **53 %** · `screening` **50 %** | Faible — dont le module des fondamentaux historiques, **celui qui portait le biais A3-01/A3-02**. |
| **Preuves et statistiques** (ce qui MESURE) | `challenge_validateur` **20 %** · `challenge_schema` **20 %** · `challenge_indicateurs` **12 %** · `backtest_noyau` **28 %** · `report` 59 % | **Le trou principal.** Les scripts qui fondent les chiffres publiés ne sont pas couverts. |
| **Interface** | `main.py` **21 %** (995 instructions, 783 non exercées) | La CLI s'exécute à la main, pas par les tests. |

## 2. Trois modules à **0 %** — vérifiés, et ce ne sont pas des tables

Un module à 0 % peut être une simple table de données : ce serait alors un faux trou. Vérification
faite, ici c'est **du code, avec de la logique** :

| Module | Contenu | Pourquoi ça compte |
|---|---|---|
| `src/strategie/strategie_leo.py` | 18 def/class, 75 instructions de contrôle (classe `MoteurLeo`, `variante_noyau_passif`) | **C'est le moteur qui a produit les chiffres d'attribution** (−43,1 / +25,8 puis −45,4 / +26,2) **que j'ai re-mesurés aujourd'hui.** Il n'a **aucun test**. |
| `src/strategie/paliers_sortie.py` | 8 def/class, 38 instructions (`simuler_paliers`, `comparer_modes`) | Le simulateur des paliers de sortie — la règle la plus coûteuse du système (−45,4 pt). |
| `src/collecte/divisions_officielles.py` | 11 def/class, 40 instructions (`charger`, `appliquer`, `utiles`) | Les divisions officielles : une erreur ici fausse **tous** les rendements longs. |

## 3. Le lien avec ce que l'audit a trouvé

Les deux constats se rejoignent et s'expliquent :

> **Les chiffres qui fondent les décisions sont produits par le code le moins couvert du projet.**

C'est exactement pourquoi la réparation du cache historique (12/10) a pu déplacer l'attribution de
−43,1 à −45,4 pt, et **inverser le signe du rebalancement à 10 ans**, sans qu'aucune alerte ne se
déclenche : ces mesures vivent dans des scripts à exécution manuelle, dont les modules ne sont pas
exercés par la suite. Rien n'était cassé — mais rien ne veillait.

## 4. Recommandations (aucune appliquée sans accord)

1. **Couvrir d'abord les moteurs de preuve**, pas le pourcentage : `strategie_leo.py`,
   `paliers_sortie.py`, puis `backtest_noyau.py`. Ce sont eux qui produisent les chiffres sur
   lesquels reposent des règles.
2. **Un test de non-régression par chiffre publié** : le script rejoué doit produire une valeur
   connue (à graine fixe), et l'écart doit faire échouer le test. C'est la version automatisée de la
   vérification manuelle faite aujourd'hui.
3. **Ne pas fixer de `fail_under`** pour l'instant : 51 % n'est pas un objectif, c'est une mesure de
   départ. Un seuil posé maintenant se ferait atteindre par des tests faciles, pas utiles.
4. `divisions_officielles.py` : au minimum un test de lecture, car une erreur de division fausse
   tous les rendements — c'est un point de défaillance silencieux.

## 5. Limites

- **Couverture d'instructions** (`branch = false`) : une ligne exécutée n'est pas une ligne vérifiée,
  et une branche non prise ne se voit pas. 51 % est un **plancher**, pas une garantie.
- Les lignes exclues (`pragma: no cover`, `__main__`) sont celles déclarées telles — elles ne sont
  pas mesurées.
- La mesure est datée : elle vaut pour le commit `bfc0d6f` + ce commit.
