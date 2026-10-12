# Chiffres publiés — vérification de reproducibilité (12/10/2026)

**Pourquoi ce document.** Le rapport `docs/RAPPORT-VALIDATION-28-ANS.md` (08/10) cite des chiffres
qui ont **fondé des décisions** (rendre les seuils non-déclencheurs, garder le renforcement, etc.).
Or les données qu'il a utilisées (`data/*.pkl`) **ne sont pas versionnées** : l'état d'époque a
disparu. La règle adoptée est donc « **toute mesure publiée porte sa provenance** », et ces chiffres
sont re-joués ici sur les données et le code du 12/10.

**Méthode.** Les scripts qui les ont produits, rejoués **en série** (jamais en parallèle), sur le
commit `80437e0`. Sorties brutes : `audit/preuves/remesure_<script>.txt`.

---

## 1. Tableau de vérification

| # | Figure enregistrée (08/10) | Re-mesurée (12/10) | Verdict |
|---|---|---|---|
| **1** | SÉLECTION : « noyau −6,9 pt vs hasard, 11,03 %/an » | **+1,1 pt** vs hasard · **10,65 %/an** | **NON REPRODUIT** — écart de 8 pts ; la configuration d'origine n'est pas identifiée (entrées non versionnées). Défaut de traçabilité, pas erreur prouvée. |
| **2** | ENTRÉE PROGRESSIVE : « 42 480 obs · 46 titres · +0 à +0,7 pt · 52-55 % » | **43 227 obs · 47 titres · −0,5 à +0,5 pt · 52-54 %** | **VERDICT TENU** (« neutre, l'écart est négligeable »). Chiffres légèrement dérivés : le cache historique réparé apporte des observations et un titre de plus. |
| **3** | RENFORCEMENT : « 5 196 obs · **67-69 %** en année de krach » | **5 196 obs (identique)** · **63 %** (3 ans) · **67 %** (5 ans) · **69 %** (10 ans) | **TENU.** Précision à apporter : la borne basse est 63 %, pas 67 % — l'énoncé doit dire « 63-69 % » ou préciser les horizons. |
| **4** | PALIERS : « −43,1 pt · volatilité **÷3,6** · **37 514** trades » | **−45,4 pt** (attribution, §9 de `recalcul_donnees_corrigees.md`) · **÷3,64** (écart-type 82,0 % → 22,5 %) · **38 262 trades** | **TENU ET RENFORCÉ** — le coût est même plus élevé qu'enregistré, et le ÷3,6 est **confirmé au centième**. |
| **5** | REBALANCEMENT : « +4,7 à +11,6 pt (3-5 ans) · **−2 à −9 pt (10 ans)** · pire cas −10,8 % → +2,7 % » | **+3,2 à +5,8 pt** (3 ans) · **+5,4 à +7,3 pt** (5 ans) · **+8,4 à +13,8 pt (10 ans)** · pire cas **−12,2 % → −0,4 %** | **DIVERGENCE — changement de signe au 10 ans.** L'ancien verdict (« coûte à 10 ans ») est démenti : le rebalancement est **positif à tous les horizons**. La divergence va dans le sens **favorable** — aucune décision n'est renversée, le rapport est corrigé. |
| **6** | DÉTACHEMENT : « 179 cas · dividende 6,71 % · baisse −3,73 % · capture +2,98 % · 32/179 perdants (18 %) · net −0,63 % » | **182 cas** (2 aberrants écartés) · **6,63 %** · **−3,68 %** · **+2,95 %** · **34/182 (19 %)** · net ≈ **−0,66 %** | **TENU** — à un cheveu. La conclusion (« le calcul net reste négatif → jamais d'achat la veille du détachement ») est intacte. |

## 2. Ce que ces vérifications établissent

1. **Le chiffre qui portait la décision tient** : l'attribution des paliers (−43,1 → **−45,4 pt**,
   drawdowns identiques) — c'est elle qui justifie la décision du 08/10 et l'invariant B1.
2. **Cinq verdicts sur six sont confirmés** (entrée progressive neutre, renforcement gagnant en
   krach, paliers coûteux, détachement net négatif), avec des chiffres légèrement dérivés — toujours
   dans le **même sens**, jamais de quoi changer une décision.
3. **Une divergence substantielle** : le rebalancement au-delà de 5 ans. Elle **corrige** une
   conclusion défavorable à tort (le rapport disait « coûte à 10 ans ») ; la correction est
   favorable, donc conservatrice au sens de la décision.
4. **Un chiffre reste non reproductible** (la sélection) : c'est le prix de mesures publiées sans
   leurs entrées. Rien ne le remplace, et le rapport le dit maintenant.

## 3. Effets appliqués

- `docs/RAPPORT-VALIDATION-28-ANS.md` : lignes **1, 2, 3, 4 et 5** mises à jour + **encadré de
  provenance** couvrant les six mesures.
- `docs/INVARIANTS-METIER.md` : invariant **B1** aligné sur la mesure re-mesurée (−45,4 pt), comme
  l'exige la hiérarchie des sources (`décision datée > invariant > IPS > commentaire`).
- **Aucune règle du système n'a été modifiée.** Cette vérification n'ajoute pas de fonctionnalité :
  elle établit que les règles reposent sur des mesures **reproductibles**, ce qui est leur seule
  garantie durable.

## 4. Recommandation

Étendre la même règle aux autres chiffres du projet qui fondent une règle : les seuils par titre
(calibrés sur les cours, re-mesurables en une commande via `seuils_vente.calibrer`), les niveaux
d'alerte, et les profils de sortie. La re-mesure est bon marché ; c'est son absence qui coûte cher.
