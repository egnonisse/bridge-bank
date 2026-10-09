# Décision — une seule définition pour le retournement après hausse

**Date :** 9 octobre 2026
**Statut :** implémentée, **267 tests verts**, aucune décision de portefeuille modifiée
**Origine :** anomalie `docs/ANOMALIE-2026-10-09-seuil-13-en-dur.md`, option B

---

## 1. Le problème

Le seuil de vente et le profil de retournement mesuraient **le même phénomène** — « le prix
a monté, que fait-il ensuite ? » — avec **deux définitions différentes** :

| | Profil (avant) | Seuil de vente |
|---|---|---|
| **Hausse retenue** | entre **13 % et 65 %** | **≥ seuil du titre**, sans plafond |
| **Dédoublonnage** | espacement de **10 séances** | saut de **20 séances** |
| **Seuil de mesure** | **13 % pour tous les titres** | celui **du titre** |

D'où deux chiffres pour une même notion. Sur SNTS : « 86 % sur 7 cas » (seuil) puis
« 90 % sur 10 cas » (profil). Sur SLBC : le message affichait **39 %**, mesuré à +13 %,
alors que **son** seuil de 5 % donne **54 %** — il disait l'inverse de sa propre réalité.

## 2. La mesure qui a décidé

Avant de choisir, chaque règle a été isolée (`scripts/comparer_definitions_episodes.py`) :

| Définition | SNTS | SGBC | SLBC | PALC |
|---|---|---|---|---|
| espace 20, sans borne (**= le seuil**) | 7 cas, 86 % | 30, 63 % | 41, 54 % | 56, 46 % |
| espace 10, borne 65 % (profil d'origine) | **10** cas, 90 % | **42**, 57 % | **67**, 46 % | **87**, 45 % |
| espace 10, sans borne | 10, 90 % | 42, 57 % | 67, 46 % | 88, 44 % |
| espace 20, sans borne, horizon 60 | **6**, **100 %** | 30, 63 % | 40, 52 % | 54, 44 % |

**Deux conclusions :**

1. **La borne haute à 65 % ne changeait rien** (10/10, 42/42, 67/67, 87/88). Elle est
   supprimée — sans perte.

2. **Le dédoublonnage à 10 gonflait les effectifs** (SNTS 7 → 10, SLBC 41 → 67). ⚠️ **Plus de
   cas n'est pas une meilleure preuve** : deux épisodes espacés de 10 séances partagent la
   moitié de leur fenêtre, donc ne sont pas indépendants.

3. 🚨 **Le piège évité** : combiner « espace 20 » avec un recul de 60 séances donnait pour
   SNTS **100 % sur 6 cas**, borne basse 61 % → étiqueté « fiable ». Un 100 % sur 6 cas
   présenté comme concluant, à côté d'un seuil à « 86 % sur 7 cas » : **pire qu'avant**.
   La définition retenue est celle du **seuil**, horizon de décision compris (20 séances).

## 3. Ce qui a été implémenté

**Une seule définition, dans `src/seuils_vente.py`** (elle qui décide) :

```python
def indices_episodes(closes, seuil) -> list[int]:
    """hausse >= seuil sur 20 séances, fenêtres disjointes (saut de 20)"""
```

`episodes()` en **dérive** — elle ne peut plus diverger.

**L'export paramétré par titre** (`scripts/export_reversal_profiles.py`) :

- mesure chaque titre **à son propre seuil** ;
- publie le **nombre de cas**, la **borne basse de Wilson** et un drapeau `significatif` ;
- **deux seuils distincts** : `PUBLICATION` (5 cas — de quoi décrire un creux) et
  `SIGNIFICATIVITÉ` (8 cas **et** borne ≥ 50 %). Les confondre privait SNTS de toute
  description alors que son creux médian est utile.

**L'affichage** (`src/portfolio.py`) :

- le **taux n'est montré que s'il est fondé** (`significatif`) — condition de transparence ;
- sinon, seuls le délai et la profondeur du repli sont donnés : **c'est ce que le profil
  sait vraiment** ;
- deux motifs de non-significativité, **deux phrases** : « trop peu de cas » (n < 8) et « pas
  assez nette » (assez de cas, signal flou). Confondre les deux produisait un message faux
  (« 30 cas — trop peu »).

**Les statistiques des seuils rafraîchies** (`scripts/rafraichir_stats_seuils.py`) :
`down_prob`, `borne_basse`, `episodes`, `significatif` remesurés. **`threshold` et `mode`
jamais touchés** — ce sont des décisions, pas des mesures.

## 4. Résultat — SNTS affiche UN seul chiffre

| Titre | Seuil | Profil (avant) | Profil (après) |
|---|---|---|---|
| SNTS | 86 % sur 7 cas | 90 % sur 10 cas ❌ | **86 % sur 7 cas** ✅ |
| SGBC | 63 % sur 30 cas | 62 % sur 26 cas ❌ | **63 % sur 30 cas** ✅ |
| SLBC | 54 % sur 41 cas | **39 % sur 38 cas** ❌ | **54 % sur 41 cas** ✅ |
| PALC | 46 % sur 56 cas | 37 % sur 51 cas ❌ | **46 % sur 56 cas** ✅ |

Et le message final pour SNTS :

```
   (seuil 13 % — 86 % de baisse sur 7 cas, non concluant · manuelle, 2026-10-09)
   📜 LES AUTRES FOIS (7 cas — trop peu pour une fréquence fiable) :
      après une hausse de 13 % en un mois, voici comment ça s'est terminé.
      En moyenne : -3,1 % un mois plus tard,
      avec un point bas vers 46 jours de bourse
      (-12,4 %).
```

**Le taux n'apparaît qu'une fois, et il est étiqueté.** Le profil apporte le descriptif que
le seuil ne peut pas donner : le délai et la profondeur du repli.

## 5. Condition n° 4 — absence de régression, vérifiée

| Contrôle | Résultat |
|---|---|
| Seuils de vente | **inchangés** — SNTS 0,13 · SGBC 0,10 · SLBC 0,05 · PALC 0,05 |
| Modes | **inchangés** — les 4 restent `informatif` |
| Valeurs effectives | **189 identiques** au snapshot (`--comparer`) |
| Sorties fondamentales | **inchangées** (testées) |
| Suite complète | **267 tests**, 0 échec |

## 6. Traçabilité

Le changement de statistique de SLBC est **au journal** (`data/seuils_journal.jsonl`) :

```json
{"horodatage": "2026-10-09T01:17:…", "titre": "SLBC", "avant": 51, "apres": 54,
 "motif": "unification de la definition d'episode (fenetres disjointes de 20 seances, sans borne haute)",
 "origine": "automatique",
 "methode": "recalcul sur l'historique au seuil inchange du titre"}
```

## 7. Ce que ça ne prouve PAS

🎯 **Un taux plus élevé n'est pas un signal plus exploitable.** SLBC passe de 39 % à 54 % :
le chiffre est **plus juste**, il n'est pas **plus prédictif**. Pour que le seuil propose une
vente, il faudrait que la **borne basse atteigne 50 %** — elle est à 39 %. Le mode reste
`informatif`, et c'est correct.

Mesurer juste ne rend pas un signal rentable : c'était l'objet des cinq épreuves de
validation, et aucune n'a trouvé de déclencheur battant le hasard net de frais.

## 8. Tests ajoutés

| Fichier | Ce qu'il verrouille |
|---|---|
| `tests/test_unification_definition.py` (11) | profil et seuil donnent **le même chiffre** · fenêtres disjointes · pas de borne haute · `significatif` = 8 cas **et** borne ≥ 50 % · chaque profil porte son seuil · **aucun profil du fichier ne porte le seuil d'un autre titre** |
| `tests/test_history_line_seuil.py` (7) | le seuil affiché est celui du titre · le taux non fondé n'est **pas** affiché · deux motifs de non-significativité, deux phrases · pas de jargon |
| `tests/test_portfolio.py` (+2) | profil significatif → taux affiché · profil non significatif → descriptif seul |
