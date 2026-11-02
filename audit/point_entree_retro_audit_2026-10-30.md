# Point d'entrée : rétro-audit des 4 positions (30/10/2026)

**Question de LEO** : « ce manque de vigilance m'a fait acheter trop cher — pourquoi ? »
**Origine** : alerte 💪 RENFORCE PALC (cours 7 360 F) ; l'alerte ne disait rien de la
position du prix dans l'historique du titre.

## Ce que le contrôle d'achat vérifiait (constat dans le code)

`evaluate_noyau_candidate()` appliquait 8 filtres : dividende > 0 · net ≥ 4 % · PER ≤ 14 ·
payout ≤ 80 % · net ≤ 10 % · régularité ≥ 4/5 ans · croissance du dividende ≥ −10 %/an ·
liquidité ≥ 5 M F/j.

**Tous portent sur le DIVIDENDE. Aucun ne regarde le PRIX dans son histoire.** La brique
existait pourtant (`spec_profiles.zone_of` : position dans la fourchette 5 ans), mais elle
n'était branchée que sur la poche spéculative.

## Les 4 positions au crible de leur propre historique

| Titre | CMP | Percentile | Médiane | Bas | ATH | Loyer payé | Tendance | Verdict |
|---|---|---|---|---|---|---|---|---|
| SGBC | 38 967 | 98e | 13 495 | 6 200 | 40 000 | 5,09 % | **+11,2 %/an** | normal (croissance) |
| SLBC | 38 124 | 94e | 13 000 | 2 950 | 44 505 | 4,11 % | **+9,4 %/an** | normal (croissance) |
| SNTS | 3 244 | 99e | 1 720 | 1 050 | 4 700 | 4,56 % | **+6,0 %/an** | normal (croissance) |
| **PALC** | **8 641** | **78e** | **6 200** | 890 | 13 100 | 4,31 % | **+1,3 %/an** | **moyen-haut** |

**Lecture** : sur un titre en CROISSANCE (≥ 6 %/an), un prix au 94-99e percentile est
**normal** — c'est la signature d'un titre qui monte. Le percentile brut seul aurait fait
condamner les trois meilleures lignes du portefeuille.

Sur PALC (plat/cyclique, **−44 % sous son ATH**), le 78e percentile est un **vrai signal** :
le prix est haut dans une distribution qui ne monte pas.

## Coût mesuré du point d'entrée (PALC)

| | Valeur |
|---|---|
| Capital investi | 224 666 F |
| Actions achetées | 26 à 8 641 F |
| Dividende net/an | 11 477 F (4,31 %) |
| Au prix **médian** (6 200 F), même capital | **36,2 actions** → 15 995 F/an (6,32 %) |
| **Loyer annuel manqué** | **+4 518 F/an (+39 %)** |

## Correctif appliqué (commit du 30/10/2026)

Bloc « 📍 POINT D'ENTRÉE » ajouté aux **deux** alertes d'achat du noyau (OPPORTUNITÉ et
À PRÉPARER) : percentile, médiane, ATH, tendance annualisée, écart au prix médian, verdict
(`📍 normal` / `🟡 prude` / `🚩 cher`).

- Seuils dans `src/regles.py` (§6) — **informatifs**, jamais bloquants (doctrine 11/09).
- **Piège évité** : le bloc n'affiche PAS « le loyer au prix médian » (ce calcul appliquait
  le dps d'aujourd'hui à un prix de 2018 : SGBC affichait un « loyer » fictif de 16,2 %).
  Il affiche l'**écart au prix médian**.
- Tests : `tests/test_point_entree.py` (5 tests, dont le garde-fou « titre en croissance
  reste normal » et « historique trop court = aucun verdict »).
- Snapshot des constantes : 230 valeurs (3 nouvelles), `--comparer` OK.

## Limite assumée

Le percentile historique **n'est pas** un critère de cherté absolu : il ne remplace pas une
comparaison du rendement du dividende à son propre historique (indisponible avant 2022 sur
la BRVM). Il répond à une seule question : *ce prix est-il haut dans la distribution de CE
titre, et ce titre monte-t-il ?*
