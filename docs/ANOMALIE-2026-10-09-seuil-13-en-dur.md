# Anomalie — le seuil « 13 % » est écrit en dur dans l'alerte

**Découvert :** 9 octobre 2026, en vérifiant le rendu réel de l'alerte après le chantier de
traçabilité.
**Statut :** ✅ **intégralement résolu** — problème n°1 corrigé par l'option A (09/10/2026),
problème n°2 résolu par l'**option B** (09/10/2026).
**Voir** : `docs/DECISION-2026-10-09-unification-definition-retournement.md`
**Sévérité :** moyenne. Le message n'est pas faux en soi, mais il **affirmait un seuil qui
n'est pas celui du titre**, et il affichait **deux statistiques contradictoires** dans le
même message.

---

## ✅ RÉSOLU — les deux problèmes

### Problème n°1 (option A) — le seuil écrit en dur
`_history_line()` ne contient plus de littéral : le seuil de référence est **lu dans la
donnée**, jamais recopié dans le code.

### Problème n°2 (option B) — deux définitions, deux chiffres
Le profil est désormais mesuré **au seuil de chaque titre**, avec **la même définition
d'épisode** que le seuil de vente. Les deux chiffres **ne peuvent plus diverger** :

| Titre | Seuil | Profil avant | Profil après |
|---|---|---|---|
| SNTS | 86 % sur 7 cas | 90 % sur 10 cas ❌ | **86 % sur 7 cas** ✅ |
| SGBC | 63 % sur 30 cas | 62 % sur 26 cas ❌ | **63 % sur 30 cas** ✅ |
| SLBC | 54 % sur 41 cas | **39 % sur 38 cas** ❌ | **54 % sur 41 cas** ✅ |
| PALC | 46 % sur 56 cas | 37 % sur 51 cas ❌ | **46 % sur 56 cas** ✅ |

**Le cas SLBC est le plus parlant** : le message affichait 39 % (mesuré à +13 %) alors que
son propre seuil de 5 % donne 54 % — il annonçait une statistique qui disait **l'inverse**
de sa réalité.

**Et le taux n'est affiché que s'il est statistiquement fondé** : sur peu de cas, « 86 % » se
lit comme une probabilité de baisse future. Le profil ne délivre alors que le délai et la
profondeur du repli — ce qu'il sait vraiment.

---

## Détail du problème (analyse d'origine conservée)



`src/portfolio.py`, fonction `_history_line()`, ligne 218 :

```python
f"\n   📜 LES AUTRES FOIS (9 ans de recul) : après une hausse de 13 % en\n"
```

Le **« 13 % » est un littéral**, pas `profit_threshold_for(pos.code)`.

Or `scripts/export_reversal_profiles.py` calcule **tous** les profils sur +13 % :

```python
LO, HI = 0.13, 0.65        # ligne 21
...
"_meta": {"seuil_pct": 13, ...}
```

## Ce que ça produit, mesuré

| Titre | Seuil réel du titre | Le message affirme | Statistique mesurée sur |
|---|---|---|---|
| SNTS | 13 % | « hausse de 13 % » ✅ | 13 % ✅ |
| SGBC | **10 %** | « hausse de **13 %** » ❌ | 13 % ❌ |
| SLBC | **5 %** | « hausse de **13 %** » ❌ | 13 % ❌ |
| PALC | **5 %** | « hausse de **13 %** » ❌ | 13 % ❌ |

Trois titres sur quatre reçoivent donc l'affirmation d'un seuil qui n'est pas le leur.

## Le second problème, plus gênant : deux chiffres contradictoires

Sur SNTS — le seul titre où le seuil **est** 13 % — le message affiche :

```
   Pourquoi je ne te propose pas de vendre :
      sur 7 cas passés où le prix avait monté comme ça, il est
      rebaissé 6 fois (86 %). C'est trop proche du pile ou face
      (50 %) pour en faire une règle.
   (seuil 13 % — 86 % de baisse sur 7 cas · manuelle, 2026-10-09)
   ...
   📜 LES AUTRES FOIS (9 ans de recul) : après une hausse de 13 % en
      un mois, le prix a REBAISSÉ dans 90 % des cas.
```

**86 % puis 90 %, pour la même question, dans le même message.** Le lecteur ne peut pas
savoir lequel croire — et le premier dit « c'est du hasard », le second dit « 90 % des cas ».

### Pourquoi ils diffèrent

Deux sources mesurent la même chose avec des règles différentes :

| Source | Fichier | Fenêtre | Filtre | SNTS |
|---|---|---|---|---|
| Seuil de vente | `profit_thresholds.json` | +13 % en 20 séances | 5 candidats, dédoublonné `i += 20` | **86 %** sur 7 cas |
| Profil de retournement | `reversal_profiles.json` | +13 % à +65 % en 20 séances | borne haute 65 %, dédoublonnage propre | **90 %** |

Les épisodes ne sont pas les mêmes : le profil écarte les hausses au-delà de +65 %, le seuil
ne les écarte pas. **Deux mesures de la même notion → deux chiffres.**

C'est exactement le défaut que le chantier de centralisation vient de corriger ailleurs
(« combien de cas pour valider un seuil » avait deux réponses). **Il en reste un ici.**

## Correctifs possibles

### A. Minimal — rendre le texte honnête (30 min)

Remplacer le littéral par le seuil réel du titre :

```python
seuil_pct = profit_threshold_for(pos.code) * 100
line = f"\n   📜 LES AUTRES FOIS (9 ans de recul) : après une hausse de {seuil_pct:.0f} % en\n"
```

**Effet** : le message n'affirme plus un faux seuil.
**Limite** : la statistique reste mesurée sur 13 %. Il faut alors **renommer la ligne** pour
dire sur quoi elle porte : « après une hausse de 13 % (toutes actions confondues) », ce qui
est honnête mais moins pertinent pour son titre.

### B. Complète — une seule source (2 h)

Générer les profils de retournement **au seuil du titre**, comme le calibrage le fait déjà.
`reversal_profiles.json` contiendrait alors, par titre, les statistiques mesurées **sur son
propre seuil**. Le message devient :

```
   (seuil 10 % — 62 % de baisse sur 30 cas · manuelle, 2026-10-09)
   📜 LES AUTRES FOIS : après une hausse de 10 % en un mois, ...
```

**Effet** : une seule mesure, un seul chiffre, aucune contradiction possible.
**Coût** : regénérer le fichier (script déjà écrit, à paramétrer par titre).
**Risque** : sur un seuil bas (5 %), les épisodes sont plus nombreux → statistiques plus
fiables qu'à 13 %. C'est un **gain**, pas une perte.

### C. Retirer la ligne (5 min)

Supprimer « 📜 LES AUTRES FOIS » : le bloc `explication()` porte déjà l'information, sourcée
et tracée.

**Effet** : plus de contradiction.
**Limite** : on perd le contexte historique long (9 ans) et le délai de retournement
(« 2 à 4 semaines »), qui est utile.

## Recommandation

**B**, en deux temps : d'abord **A** (30 min) pour arrêter d'afficher un faux seuil dès
demain, puis **B** quand le prochain calibrage tournera — la structure du journal est déjà
en place pour tracer le changement.

**Ne pas laisser en l'état** : le message affirme aujourd'hui un seuil que trois titres sur
quatre n'ont pas.
