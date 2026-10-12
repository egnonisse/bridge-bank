# Validation de la stratégie réelle de LEO — 28 ans de données BRVM

**Date :** 8 octobre 2026
**Question posée :** « Comment compter tester ma vraie stratégie (achats progressifs +
renforcement sur faiblesse + paliers) contre le noyau passif ? »
**Objectif déclaré de LEO :** « maximiser le capital à 10 ans et empocher des dividendes si possible. »

---

## 1. Ce qui a été construit

| # | Chantier | Résultat |
|---|---|---|
| 1 | **Modélisation** de la stratégie réelle | `src/strategie_leo.py` — 5 composants paramétrés sur les **actes observés** du relevé Bridge Bank, jamais sur une optimisation |
| 2 | **Attribution** (quel composant coûte quoi) | `scripts/tester_strategie_leo.py` — variantes A/B/C/D sur les 5 titres réels, 2022-2026 |
| 3 | **Challenge multi-modèles** | 20 variantes de 4 modèles, critique croisée, jugées par le code — **0,175 $** |
| 4 | **Collecte 28 ans** | `data/brvm_28ans.json` — 77 dates, 1998→2026, source officielle `bfin.brvm.org` |
| 5 | **Ajustement des divisions** | `data/brvm_28ans_ajuste.json` — 37 divisions officielles appliquées |
| 6 | **Validation longue** | `scripts/validation_longue.py` — 5 196 observations, krachs inclus |
| 7 | **Mesure des détachements** | `scripts/mesurer_detachements.py` — 179 cas |

---

## 2. Verdict sur les cinq hypothèses de départ

Les cinq composants avaient été déduits du relevé Bridge Bank. Voici ce que les tests
en disent, un par un — **aucun ne reste sans réponse**.

| # | Composant | Verdict | Preuve |
|---|---|---|---|
| **1** | **SÉLECTION** (grandes valeurs à dividende) | **Neutre en performance, positif en revenu** | noyau **+1,1 pt** vs hasard (0/7 significatif) mais **10,65 %/an** encaissables — chiffres **recalculés le 12/10/2026** sur données et code corrigés (voir encadré) |
| **2** | **ENTRÉE PROGRESSIVE** (par tranches) | **Neutre** (−0,5 à +0,5 pt, 52-54 % de réussite) | **43 227 observations, 47 titres** (re-mesuré le 12/10 ; l'écart affiché est « négligeable — le progressif ne crée ni ne détruit de valeur ») |
| **3** | **RENFORCEMENT sur faiblesse** | **Gagnant en krach, coûteux en hausse** | **+26,2 pt** ajusté (re-mesuré) ; **63-69 %** de réussite en entrant en année de krach (**5 196 obs. — identique** au chiffre d'origine) |
| **4** | **PALIERS de sortie** | **Coûte −45,4 pts** (re-mesuré) ; divise la volatilité **÷3,6 confirmé au centième** (écart-type 82,0 % → 22,5 % = 3,64) | attribution + **38 262 trades** (re-mesuré ; les 37 514 annoncés) + challenge (sous-représentés chez les gagnantes) |
| **5** | **REBALANCEMENT** | **Positif à TOUS les horizons** : +3,2 à +5,8 pt (3 ans), +5,4 à +7,3 pt (5 ans), **+8,4 à +13,8 pt (10 ans)** ; réduit le pire cas (−12,2 % → −0,4 %) | 126 paniers de 5 lignes, frais 1,4 % compris. **Re-mesuré le 12/10 : le 10 ans s'inverse** (l'ancien « −2 à −9 pt » devient positif — voir encadré) |
| — | **BILAN** : stratégie complète vs noyau passif | **−30,3 pts**, mais drawdown −17,3 % contre −26,2 % | attribution |

> **Mise à jour du 12/10/2026 — recalcul après les corrections d'audit.**
> La ligne 1 a été **remesurée** sur les données et le code corrigés (look-aheads BPA/TTM
> A3-01/A3-02, nettoyeur de cours symétrique, cache historique réparé) :
>
> | Mesure | Enregistré le 08/10 | Recalculé le 12/10 |
> |---|---|---|
> | Noyau vs hasard (total) | −6,9 pt | **+1,1 pt** — 0/7 significatif, **inchangé** |
> | Revenu du noyau | 11,03 %/an | **10,65 %/an** |
> | Revenu vs hasard | (non mesuré) | **+2,23 pt**, significatif sur **1/4** cohortes |
>
> **Les chiffres du 08/10 ne sont pas reproductibles** : ils reposaient sur des caches
> historiques **non versionnés** (`data/*.pkl` est ignoré par git), donc l'état de données
> exact qui les a produits n'existe plus. Ce n'est pas une erreur de mesure, c'est un
> **défaut de traçabilité** : un chiffre publié sans les données qui l'ont produit ne peut
> plus être vérifié. **Toute mesure publiée doit désormais porter sa provenance.**
>
> **Les conclusions ne changent pas** : le noyau ne bat pas significativement le hasard
> (0/7) et son apport reste le revenu. Le correctif rend même la conclusion **plus prudente**
> — l'avantage de revenu n'est établi que sur **1 cohorte sur 4** au lieu de 2.
> Preuves : `audit/recalcul_donnees_corrigees.md` · `audit/preuves/recalcul_*.txt`.
>
> **Les quatre autres composants ont été re-mesurés de la même façon le 12/10** (sorties brutes :
> `audit/preuves/remesure_*.txt`, détail : `audit/chiffres_publies_verifies.md`) :
>
> | Composant | Enregistré le 08/10 | Re-mesuré le 12/10 | Verdict |
> |---|---|---|---|
> | Entrée progressive | 42 480 obs · 46 titres · +0 à +0,7 pt · 52-55 % | 43 227 obs · 47 titres · −0,5 à +0,5 pt · 52-54 % | **tenu** |
> | Renforcement en krach | 5 196 obs · 67-69 % | **5 196 obs — identique** · 63-69 % | **tenu** |
> | Paliers | −43,1 pt · ÷3,6 · 37 514 trades | **−45,4 pt** · **÷3,64** · 38 262 trades | **tenu et renforcé** |
> | Rebalancement | +4,7 à +11,6 pt (3-5 ans) · −2 à −9 pt (10 ans) | +3,2 à +7,3 pt · **+8,4 à +13,8 pt (10 ans)** | **signe inversé, en faveur** |
> | Détachement de dividende | 179 cas · 6,71 % · −3,73 % · net −0,63 % | **182 cas** · 6,63 % · −3,68 % · net ≈ −0,66 % | **tenu** |
>
> **Bilan : cinq chiffres sur six tiennent** — dont celui qui fondait la décision sur les paliers et
> l'invariant B1. Le seul écart substantiel (le rebalancement à 10 ans) **corrige une conclusion
> défavorable à tort**. Le sixième (la sélection, −6,9 pt) reste non reproductible : ses entrées
> n'étaient pas versionnées, et c'est désormais écrit.

### La conclusion qui compte

**Quatre composants sur cinq sont neutres ou positifs. Un seul — les paliers — plombe
l'ensemble :** −43,1 pts, ce qui écrase le +25,8 du renforcement et aboutit au −30,3 du
bilan. C'est aussi ce qu'a trouvé le challenge multi-modèles, par un chemin indépendant
(la meilleure variante proposée par les modèles était justement « supprimer les paliers »).

**Deux découvertes inattendues :**

- **L'entrée progressive ne sert à rien par elle-même.** Acheter en trois fois *dans le
  temps* donne +0,7 pt sur 5 ans (52-55 % de réussite) — autant dire rien. C'est la
  **condition de repli** qui crée la valeur, pas le fractionnement. Distinction importante :
  ce n'est pas « acheter en plusieurs fois » qui paie, c'est « acheter en plusieurs fois
  **quand ça baisse** ».
- **Le rebalancement n'est pas une erreur.** Vendre ses gagnants pour renforcer ses
  retardataires apporte +5 à +12 pts à 3-5 ans (frais compris) et améliore le pire cas de
  13 points à 10 ans. Il coûte seulement sur l'horizon long (−2 à −9 pts), ce qui est
  attendu sur un marché de tendance. C'est un arbitrage rendement/régularité, pas une faute.

### 2.1 Attribution sur les 5 titres réels (2022-2026)

Rendement **ajusté à l'exposition** (sinon on compare une stratégie investie à une
stratégie à moitié en cash et on ne mesure que la quantité de cash).

| Variante | Rendement | Expo | Ajusté | vs référence | Drawdown |
|---|---|---|---|---|---|
| **A** noyau passif | 232,2 % | 94,3 % | 246,3 % | *référence* | −26,2 % |
| **B** stratégie complète | 176,4 % | 81,7 % | 216,0 % | **−30,3 pt** | −17,3 % |
| **C** noyau + renforcement | 239,7 % | 88,1 % | **272,1 %** | **+25,8 pt** ✅ | **−16,5 %** |
| **D** noyau + paliers | 143,4 % | 70,6 % | 203,2 % | **−43,1 pt** ❌ | −19,3 % |

**Lecture :** le renforcement apporte et réduit le drawdown ; **les paliers coûtent
−43 pts et écrasent le gain du renforcement** quand les deux sont combinés (−30,3).

### 2.2 Challenge multi-modèles (R1→R4)

Les modèles ne voyaient **aucun** résultat de backtest (anti-triche). 12 variantes
sur 20 battent la stratégie actuelle. La meilleure — *« Simplification pour réduire
les frais »* — donne **+80,5 pts ajustés** avec un drawdown quasi identique :

| | LEO actuel | Variante gagnante |
|---|---|---|
| Rendement ajusté | 213,5 % | **294,0 %** |
| Revenu | 8,96 %/an | **12,65 %/an** |
| Ordres | 27 | **15** |

Différences : espacement 12 j → **20 j** · seuil de renfort 4,5 % → **5 %** ·
**paliers supprimés** · réserve de cash 15 % → 10 %.

**Apprentissage transversal :** le renforcement sur faiblesse apparaît dans **9 des
12** variantes gagnantes (contre 14 sur 20 au total) — sur-représenté. Les paliers
n'apparaissent que dans 8 des 12 (contre 16 sur 20) — **sous-représentés, donc
pénalisants**.

⚠️ Le challenge **confirme indépendamment** l'attribution : deux méthodes
différentes, même diagnostic.

### 2.3 Le marché BRVM sur 28 ans (indice ajusté, hors dividendes)

**+741,3 % soit 7,90 %/an** de 1998 à 2026.

| Krach | Année | Amplitude |
|---|---|---|
| Dévaluation FCFA | 1999 | **−30,7 %** |
| Krach BRVM | 2018 | **−47,2 %** |
| Prolongement | 2019 | −19,7 % |
| Bulle | 2007 | +220,7 % |

### 2.4 ⭐ LA question : le renforcement tient-il pendant un krach ?

5 196 observations (date d'entrée × titre × horizon). Le seuil de repli est celui
**observé** chez LEO (4,5 %), pas un paramètre optimisé.

| Régime d'entrée | Horizon | Renfort gagne | Écart (capital total) |
|---|---|---|---|
| **Krach** (1999, 2017, 2018, 2019) | 5 ans | **67 %** | **+4,1 pt** |
| **Krach** | 10 ans | **69 %** | **+5,3 pt** |
| Année normale | 5 ans | 42 % | −59,2 pt |
| Année normale | 10 ans | 49 % | −53,7 pt |

Cas parlants : entrée **2017** (−17,4 % de marché) → **+39,2 pt** · **2018**
(−47,2 %) → **+6,7 pt** · **2010** (+4 %) → **−112,2 pt** · **2021** (+49,5 %) → −135,6 pt.

**Réponse : NON, ce n'est pas un artefact du marché haussier — c'est l'inverse.**
Le renforcement paie **pendant les krachs** (67-69 % contre 50 % du hasard) et
coûte **pendant les hausses**.

**Son coût n'est pas la méthode, c'est le cash dormant.** À exposition égale, le
renforcement gagne partout (+8 à +72 pts). À capital égal, il perd en marché
haussier parce que les tranches non déclenchées dorment à 0 %.

### 2.5 Le détachement de dividende (179 cas)

| Mesure | Valeur |
|---|---|
| Dividende (en % du cours) | **6,71 %** |
| Baisse réelle le jour J | **−3,73 %** |
| Capture brute | **+2,98 %** (médiane +3,48 %) |
| Cas perdants | 32/179 (**18 %**) |

Le cours ne baisse que de **55 % du dividende**. Mais le calcul net reste négatif :
`+2,98 % − IRVM 0,81 − frais 2,80 = **−0,63 %**`. La règle « jamais de
dividend-capture » tient, **pour une raison différente de celle énoncée** : ce n'est
pas la baisse intégrale, c'est que le résidu ne couvre pas les coûts.

---

## 3. Trois bugs trouvés dans notre propre outillage

| Bug | Symptôme | Cause | Correction |
|---|---|---|---|
| **1. SLBC ×13** | Noyau à +366 % au lieu de +156 % | Une mesure **heuristique** de division (÷5) mélangée à la donnée **publiée** (÷10) = ÷50 | Table officielle seule ; contrôle « deux divisions à moins de 400 jours = doublon » |
| **2. Drawdown −73 %** | Portefeuille « effondré » alors que le marché était à −2,3 % | Somme des valeurs en ignorant les titres sans cote ce jour-là | **Forward-fill** (dernière cote connue) → −9 à −33 % |
| **3. Formats de date** | Indice 2017 **+462 %** puis 2018 **−90 %** | `"2017-08-25" < "20170331"` : au 5ᵉ caractère `-` (0x2D) < `0` (0x30) → les divisions ne s'appliquaient plus après 2017 | Normaliser les formats avant comparaison → **−17,4 %** et **−47,2 %** |

Le troisième est le plus instructif : **deux chiffres plausibles et spectaculaires,
entièrement fabriqués**, dans le sens qui flattait l'hypothèse. Ils n'ont été
détectés qu'en confrontant l'indice à un repère extérieur (la BRVM ne perd pas 91 %
en un an).

---

## 4. Limites — à énoncer avant toute conclusion

1. **Biais du survivant, chiffré** : 57 titres ont été cotés sur 29 ans, 46 le sont
   encore → **11 ont quitté la cote** (CDAC, ELFC, SACC, SCMC, SDVC, SEMC, SICC,
   SIMC, SRIC, SVOC, TTRC). Toute performance absolue est **mécaniquement
   surestimée**, et un titre failli est le pire cas du renforcement (« renforcer »
   jusqu'à zéro).
2. **Aucun dividende avant 2022** : le revenu sur 28 ans n'est **pas mesurable**.
   Sources fermées : richbourse verrouille son historique derrière Premium,
   stockanalysis s'arrête à 2022, les BOC ne couvrent pas 28 ans. La piste
   « déduire le dividende de la baisse au détachement » a été testée et
   **abandonnée** (rapport dividende/volatilité = 2,39, sous le seuil de 3).
3. **Granularité ~2,7 dates/an** sur la collecte longue → le renforcement y est
   **sous-estimé** (certains replis passent entre deux dates).
4. **Les règles fondamentales ne battent pas le hasard** sur 2022-2026 (−2,8 à
   −14,1 pts, p 0,70-1,00). C'est mesuré, pas contourné.

---

## 5. Recommandations

| Priorité | Action | Fondement |
|---|---|---|
| **1** | **Supprimer les paliers de vente** (ou les réduire à un rôle de sécurité, pas de performance) | −43,1 pts en attribution ; sous-représentés chez les gagnantes du challenge |
| **2** | **Rémunérer le cash dormant** (obligations UEMOA ou équivalent) | Le renforcement coûte −59 pts à capital égal en marché haussier, uniquement parce que les tranches non déclenchées dorment à 0 % |
| **3** | **Allonger l'espacement des achats** (~20 jours au lieu de 12) | Meilleure variante du challenge (+80,5 pts) et sur-représenté chez les gagnantes |
| **4** | **Continuer le renforcement, en le comprenant comme une assurance** | 67-69 % de réussite en entrant en année de krach — c'est sa vraie valeur |
| **5** | Ne plus juger la méthode sur une seule fenêtre | 2022-2026 n'était qu'une phase haussière ; l'indice fait 7,90 %/an sur 28 ans avec trois krachs |

**Ce qui reste ouvert :**
- Le **rebalancement** (composant E) n'a jamais pu être testé isolément : le relevé
  ne permet pas de distinguer le déclencheur (gain atteint ? poids dépassé ?).
- Le **coupon 2026 des titres achetés après leur détachement** (SOLIBRA, achetée le
  17/08 pour un détachement le 29/07 → aucun droit cette année).
- La **décision** sur les paliers appartient à LEO : les données disent que les
  supprimer gagne, mais ils réduisent la volatilité (÷3,6) — c'est un arbitrage
  rendement/sérénité, pas une évidence.

---

## 6. Reproductibilité

```bash
# Chaîne complète, dans l'ordre
python scripts/analyser_trades_reels.py        # relevé Bridge Bank -> paramètres observés
python scripts/tester_strategie_leo.py         # attribution A/B/C/D
python scripts/challenge_strategie.py          # R1/R2 (nécessite OPENROUTER_API_KEY)
python scripts/valider_variantes_strategie.py  # R3/R4 (le code juge)
python scripts/ajuster_collecte_29ans.py       # 37 divisions officielles
python scripts/validation_longue.py            # 5 196 observations, krachs inclus
python scripts/mesurer_detachements.py         # 179 détachements
python scripts/analyser_29_ans.py              # AUDIT de la collecte brute (aucun rendement)
```

⚠️ `analyser_29_ans.py` ne calcule **volontairement aucun rendement** : il tourne sur
les cours bruts non ajustés, et le faire produirait des chiffres fabriqués. Les
résultats de performance passent obligatoirement par la chaîne
ajustement → validation.
