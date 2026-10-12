# RECALCUL SUR DONNÉES CORRIGÉES — seuils, backtest du noyau, challenge

**Date** : 2026-10-12 · **Demande** : LEO — « recalcul des seuils sur données corrigées »
**Conclusion en une ligne** : **les seuils de vente ne sont PAS concernés** (mon affirmation était
fausse, preuve au §1). Les statistiques réellement concernées sont le **backtest du noyau** et le
**challenge** ; le recalcul est **fait** (§3) et il **ne renverse aucune conclusion** — il en rend
une plus prudente.

---

## 1. Ce que j'ai affirmé, et pourquoi c'était faux

J'avais écrit : « les statistiques qui ont calibré tes seuils de vente par titre ont été calculées
sur les données biaisées ». **C'est faux, et la vérification est immédiate :**

```
src/calibration/seuils_vente.py  imports : json · datetime · Path · paths.DATA_DIR · regles · schema_seuils
                                  AUCUN import de fondamentaux
signature du calibrage           : calibrer(code: str, closes: list[float])
                                   ^^^^ les ÉPISODES sont mesurés sur les COURS seuls
```

Les seuils par titre (13 SNTS · 10 SGBC · 5 SLBC · 5 PALC) sont calibrés sur la **distribution des
baisses après une hausse**, c'est-à-dire sur des **prix**. Les look-aheads A3-01/A3-02 vivaient dans
le module de **fondamentaux historiques** : ils ne peuvent pas les toucher.
**[Fait vérifié] Il n'y avait rien à recalculer de ce côté.** Mon assertion était une inférence non
vérifiée — exactement ce que le protocole interdit.

## 2. Les vrais consommateurs du module biaisé

Cartographie (grep exhaustif de `fondamentaux_historiques`) :

| Module | Usage | Conséquence du biais |
|---|---|---|
| `src/backtesting/backtest_noyau.py` (2 appels) | sélection point-in-time du noyau + paniers aléatoires | la sélection « croyait connaître » des comptes 3-6 mois avant le marché |
| `src/backtesting/challenge_indicateurs.py` (2 appels) | challenge point-in-time des indicateurs fondamentaux | verdicts sur des indicateurs partiellement devinés |
| `src/calibration/seuils_vente.py` | **aucun** | **aucune** |

Le docstring du backtest promettait noir sur blanc « **Aucun regard sur le futur
(fondamentaux_a_la_date)** » : cette promesse n'était pas tenue jusqu'au 12/10. Elle l'est
maintenant.

## 3. Les données étaient-elles à corriger ?

Réponse mesurée : **non, elles l'étaient déjà.** J'ai reconstruit le cache avec l'extracteur corrigé
(`scripts/construire_fondamentaux_historiques.py`, 48 titres, sortie `data/fondamentaux_historiques.json`) :

```
titres avant : 47  ·  apres : 47        titres dont les donnees changent : 0 / 47
ABJC  bpa 2024 : 138.84 dans la sauvegarde 18h09  ET  dans le cache reconstruit
doublons d'exercices consecutifs identiques : 0  (le correctif annonce « 12 -> 0 »)
```

Le cache de 18h09 contenait **déjà** les valeurs corrigées : il avait été régénéré juste avant le
commit du code (18h19). **La reconstruction était donc un no-op — et c'est la preuve que la donnée
est saine.** Sauvegarde conservée : `preuves/fondamentaux_avant_recollecte.json`.

## 4. Le recalcul, avec isolation de cause

Méthode : **mêmes données** (le cache actuel, copié à l'identique), **seul le code diffère**. Le
« avant » est exécuté dans un worktree de `b810f7d` (état d'avant correctif), hors du dépôt de LEO,
pour ne rien perturber. Les deux scripts sont déterministes (tirages à graine fixe) : les chiffres
sont reproductibles.

### `scripts/tester_noyau.py` — noyau contre 100 paniers aléatoires (2022-2026)

| | Avant correctif | Après correctif |
|---|---|---|
| Moyenne noyau | +185,8 % | **+187,0 %** |
| Moyenne hasard | +185,1 % | +185,8 % |
| Avantage | **+0,8 pt** | **+1,1 pt** |
| Cohortes significatives | **0/7** | **0/7** |
| Revenu annuel encaissé | 10,57 % | **10,65 %** |

### `scripts/tester_revenu_vs_hasard.py` — revenu contre 100 paniers aléatoires

| | Avant correctif | Après correctif |
|---|---|---|
| Noyau | 10,20 %/an | **10,35 %/an** |
| Hasard (médiane 100 tirages) | 8,06 %/an | 8,12 %/an |
| Écart | +2,14 pt | **+2,23 pt** |
| **Cohortes significatives (p<0,05)** | **2/4** | **1/4** |

## 5. Lecture

1. **Aucune conclusion ne se renverse.** Le verdict central tient : **le noyau ne bat pas
   significativement le hasard** (0/7 sur le total), et son intérêt reste **le revenu** (10,35 %/an
   contre 8,12 %).
2. **Le correctif rend une conclusion PLUS PRUDENTE** : l'avantage de revenu passe de significatif
   sur 2 cohortes à **1 seule**. C'est le sens attendu — retirer une information future ne peut pas
   créer un avantage. Le look-ahead fournissait donc une **petite part** de l'edge apparent.
3. L'ampleur est faible (+0,3 pt sur le total, +0,09 pt sur le revenu) : les conclusions de l'étude
   28 ans ne reposaient pas sur le biais. **Elles sont robustes au correctif.**

## 6. Deux défauts trouvés en chemin

1. **`tester_revenu_vs_hasard.py` conclut contre ses propres chiffres** : il affiche « +2,23 pt »
   d'avance du noyau puis termine par « ❌ le hasard apporte plus de revenu ». La ligne de verdict
   ne suit pas les données affichées — un lecteur pressé en tire la conclusion inverse.
2. **Le chiffre enregistré ne se reproduit pas** : `docs/RAPPORT-VALIDATION-28-ANS.md` annonce
   « noyau **−6,9 pt** vs hasard » et « 11,03 %/an ». Mes deux exécutions (avant ET après correctif)
   donnent +0,8 et +1,1 pt, et 10,57 / 10,65 %/an. L'écart ne vient donc pas du correctif : la
   configuration exacte qui a produit ce chiffre n'est pas identifiée. **À clarifier avant de citer
   −6,9 pt comme référence.**

## 7. Recommandations — ÉTAT

1. **✅ APPLIQUÉE (12/10)** — `scripts/tester_revenu_vs_hasard.py` : le verdict est extrait en
   fonction pure `verdict_revenu()` à quatre branches honnêtes (écart notable × avantage établi).
   Avant : sur les chiffres réels (+2,23 pt, significatif sur 1/4), l'ancien `else` imprimait
   « ❌ le hasard apporte plus de revenu » — le contraire de ses propres chiffres. Après :
   « 🟡 LE NOYAU APPORTE PLUS DE REVENU (+2,23 pt), MAIS L'AVANTAGE N'EST PAS ÉTABLI
   (significatif sur 1/4 cohortes seulement) ». Cinq tests le figent
   (`tests/test_verdict_revenu.py`), dont un qui interdit nommément la conclusion menteuse.
2. **✅ APPLIQUÉE (12/10)** — `docs/RAPPORT-VALIDATION-28-ANS.md` : ligne 1 remesurée
   (+1,1 pt · 10,65 %/an · revenu +2,23 pt sur 1/4) et **encadré de provenance** ajouté.
   **Le −6,9 pt / 11,03 %/an du 08/10 reste NON REPRODUIT** : il reposait sur des caches
   historiques **non versionnés** (`.gitignore:27 → data/*.pkl`), donc l'état de données exact
   n'existe plus. Ce n'est pas une erreur de mesure : c'est un **défaut de traçabilité**, et
   c'est désormais écrit dans le rapport.
3. **✅ SANS OBJET (par conception)** — les seuils par titre ne sont pas concernés (§1) :
   aucun recalibrage n'a été fait, et aucun ne doit l'être.

**Conséquence durable** : la règle « toute mesure publiée porte sa provenance » entre au rapport
28 ans. Sans elle, un chiffre devient invérifiable dès que ses données disparaissent.

## 8. Limites

- L'isolation porte sur le **code de lecture** et la **donnée** ; les autres corrections du lot 3
  (nettoyeur symétrique des cours, taux fiscaux centralisés, TLS strict) sont **présentes dans le
  « après »** et leurs effets ne sont pas isolés séparément. Le delta mesuré est donc celui de
  **l'ensemble du lot 3**, pas du seul correctif des look-aheads.
- Ces tests portent sur 2022-2026 (4-7 cohortes) : petits effectifs, ce que le 1/4 et le 0/7
  traduisent.
- Le worktree d'avant correctif a été retiré après usage ; les sorties brutes restent dans
  `preuves/`.

---

## 9. L'attribution qui justifie une décision — RE-MESURÉE (12/10)

Le chiffre « les paliers coûtent −43,1 points » ne décore pas : il justifie la **décision du
08/10** (rendre les seuils de vente non-déclencheurs) et il est inscrit dans l'**invariant B1**
(`docs/INVARIANTS-METIER.md`), qui prime sur l'IPS par la hiérarchie adoptée (Q1). Il venait de
`scripts/tester_strategie_leo.py` — réexécutable, lui. Re-mesuré le 12/10 sur les données et le
code corrigés (`preuves/attribution_remesuree_2026-10-12.txt`) :

| Variante | Enregistré le 08/10 | Re-mesuré le 12/10 | Écart |
|---|---|---|---|
| **A** noyau passif | référence | 232,2 % · DD −26,2 % | — |
| **C** noyau + renforcement | 239,7 % · 88,1 % · 272,1 % · **+25,8 pt** · DD −16,5 % | 239,7 % · 88,5 % · 270,9 % · **+26,2 pt** · DD −16,5 % | **+0,4 pt** |
| **D** noyau + paliers | 143,4 % · 70,6 % · 203,2 % · **−43,1 pt** · DD −19,3 % | 143,4 % · 71,9 % · 199,3 % · **−45,4 pt** · DD −19,3 % | **−2,3 pt** |
| **B** stratégie complète | **−30,3 pt** | **−31,2 pt** | −0,9 pt |

**Lecture** : l'attribution est **reproductible** et elle **résiste** aux corrections des lots 1-3.
Les écarts vont de 0,4 à 2,3 points, même signe, même ampleur ; les drawdowns sont identiques au
dixième. Le coût des paliers est même **un peu plus élevé** qu'enregistré (−45,4 contre −43,1) :
la décision de les rendre non-déclencheurs est donc **mieux justifiée encore**.

**Ce que cela change pour la gouvernance** : le trou de traçabilité du §6 ne touche pas le chiffre
qui portait la décision. Il touchait « noyau −6,9 pt vs hasard » — une mesure **descriptive** du
rapport 28 ans, pas un fondement de règle. La règle « toute mesure publiée porte sa provenance »
reste utile, mais le risque réel était plus faible que craint.
