# DÉCISION — achat spéculatif ONTBF, 297 actions à 2 740 F

**Date de la décision :** 16 novembre 2026
**Décisionnaire :** LEO (« soyons fous »)
**Ordre passé :** n° 987223 — Achat ONATEL BF (code BRVM `ONTBF`) — 297 actions à 2 740 F — validité 17/11/2026

---

## 1. Ce que la stratégie disait

**Aucun schéma n'était actif.** Le seul schéma à espérance positive (CASSURE) exige une clôture
au-dessus de **3 115 F** avec un volume ≥ 4 822 titres ; le cours était à 2 900 F, soit 7,4 % en
dessous. À 2 740 F, la distance au déclencheur monte à **13,7 %**.

Ce que les mesures du projet disaient des alternatives :

| Façon d'entrer | Médiane encaissée (plan complet) | Cas perdants |
|---|---:|---:|
| Acheter après une baisse (schéma PANIQUE) | **−9,4 %** | 56 % |
| Acheter la cassure (schéma CASSURE) | **+14,9 %** | 35 % |
| Acheter sans aucun signal | **aucun avantage démontré** (49 % contre le hasard) | — |

Le point de bascule de rentabilité a été calculé à **48 % de chances de hausse**. Pour un achat
sans signal, la probabilité n'est pas mesurée ; le seul indice disponible est le benchmark du
hors-période, à **49 %** — juste au-dessus du seuil.

**LEO a été informé de ces trois chiffres avant de décider.** La décision est prise en
connaissance de cause : c'est un pari assumé, hors règles de la stratégie.

## 2. Les chiffres de l'ordre

| Élément | Montant |
|---|---:|
| 297 actions × 2 740 F | **813 780 F** |
| Frais d'achat (1,4 %, minimum 1 000 F) | **11 393 F** |
| **Total débité** | **825 173 F** |

### Financement — passe de 2 361 F près

| | Montant |
|---|---:|
| Cash disponible enregistré | 742 738 F |
| Produit de cessions SLBC en attente (relevé du 12/11) | 84 796 F |
| **Total mobilisable** | **827 534 F** |
| Ordre à financer | 825 173 F |
| **Reste après achat** | **2 361 F** |

⚠️ **Sans le règlement des 84 796 F, l'ordre ne peut pas être servi** (il manque 82 435 F).
Le maximum finançable sur le seul cash disponible serait de **267 actions**.

## 3. Le plan attaché à cette position

| Niveau | Prix | Action |
|---|---:|---|
| Entrée | 2 740 F | — |
| **Stop −15 %** | **2 329 F** | vendre les 297 actions, sans discuter |
| +20 % | 3 288 F | vendre 99 actions → 325 512 F |
| +35 % | 3 699 F | vendre 99 actions → 366 201 F |
| +50 % | 4 110 F | vendre les 99 restantes → 406 890 F |

**Risque chiffré :** −122 067 F si le stop est touché, soit **14,8 % de la liquidité totale**.
**Gain maximal si les trois paliers touchent :** +406 890 F brut, avant frais de vente.
**Ratio gain maximal / perte : 3,3 pour 1.**

## 4. Les risques acceptés, explicitement

1. **Aucun signal ne couvre ce prix.** L'achat n'est adossé à aucune mesure de probabilité.
2. **Poids de 51,9 % du portefeuille** sur un seul titre, pour une poche spé plafonnée à 10 %
   par l'IPS (soit 158 922 F, dépassé de 666 251 F).
3. **Cash résiduel de 2 361 F** après exécution : aucune capacité de renforcement ni d'achat
   d'opportunité, et aucune marge si un autre titre casse son seuil.
4. **Validité de l'ordre au 17/11** : il faut une baisse de 5,5 % en une séance pour être servi.
   Le creux des 60 dernières séances est à 2 760 F — le titre n'est pas descendu sous 2 740 F
   depuis plus de trois mois. **L'exécution est peu probable avant expiration.**
5. **Concentration géographique et sectorielle** : télécoms Burkina Faso, sur un portefeuille
   déjà exposé aux télécoms via SNTS (30 actions).

## 5. Ce qui n'est PAS fait

- L'ordre **n'est pas exécuté** : quantité servie = 0 à l'instant du relevé.
- La position **n'est pas enregistrée** dans `data/spec_positions.json` tant qu'aucune action
  n'est réellement achetée. Règle du projet : « un ordre annoncé n'est pas une exécution ».
- Elle ne doit pas être comptée dans les statistiques de la veille spé : le schéma n'était pas
  actif, l'inclure fausserait les mesures de réussite du dispositif.

---

*Document produit à la demande de LEO, qui a explicitement demandé que la décision soit
documentée avec ses chiffres plutôt que re-débattue.*
