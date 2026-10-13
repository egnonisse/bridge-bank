# Décision du 13/10/2026 — Lot 9 : le moteur équitable (audit A3-08, A3-10-moteur, A3-13)

## Contexte
Dernier bloc du chantier 3. Le finding A3-08 démontrait que **le comparatif d'attribution
était biaisé par la composition** : la variante passive engageait `300 000 F` par titre,
la complète `100 000` — elles ne détenaient PAS les mêmes titres et le résultat dépendait
de l'ordre du dict `univers`. Cinq paramètres déclarés n'étaient **jamais lus**. A3-10
(exécution au close du signal) s'appliquait aussi au moteur. A3-13 : 4 constats mineurs.

## Corrections appliquées

**A3-08 — plafond de ligne équitable + hygiène de l'API.**
- `budget_max_ligne` par défaut = **None → plafond DYNAMIQUE** : `capital × (1 − cash) / n_titres`
  (`n_titres` = titres de l'univers simulé) ; `tranche = plafond / nb_tranches`. Chaque
  variante engage la même PART de son capital investissable sur **chaque** titre : elles
  ouvrent le MÊME univers, seule la répartition dans le temps change. Un plafond explicite
  reste prioritaire (tests de non-régression).
- **5 paramètres morts retirés** : `budget_ligne`, `max_tranches_renforcement`,
  `duree_max_seances`, `rebalancement_actif`, `seuil_rebalancement` — un paramètre qu'on
  peut régler SANS EFFET est un mensonge de l'API. Le composant « rebalancement » n'est pas
  modélisé par ce moteur (mesuré séparément, `scripts/tester_rebalancement.py`).
- **`ResultatStrategie.titres_achetes`** : les titres réellement achetés (même revendus en
  totalité) sont publiés et **imprimés par les deux scripts** d'attribution. On ne suppose
  plus l'univers comparé : on le vérifie.

**A3-10 (moteur) — exécution à J+1.** Toute décision prise sur le close de la séance `d`
est exécutée à la séance SUIVANTE DU TITRE, au close (file d'ordres pendants). Les
garde-fous (réserve de cash, plafond de ligne) sont **re-vérifiés à l'exécution** ; un
ordre dont le garde-fou retombe est annulé. Un titre qui cesse de coter attend sa prochaine
cote ; **un ordre non exécuté à la fin de la fenêtre n'est PAS appliqué**.

**A3-13 (mineurs).**
- (a) fractions des paliers sur les actions RESTANTES : comportement conservé, docstring corrigée ;
- (b) drawdown mesuré aussi APRÈS la dernière séance ;
- (c) avertissement bruyant si une position n'a aucun cours final (avant : omission silencieuse) ;
- (d) revenu annuel en **jours réels** (l'écart de mois entiers biaisait la durée).

## Tests — `tests/test_strategie_leo.py` (26 → 32)
Nouveaux : plafond auto ouvre les 5 titres ET ignore l'ordre de l'univers (la preuve du
fix A3-08) · paramètres morts absents (`hasattr`) · plafond explicite respecté ·
exécution au cours de J+1 (CMP calculé sur le close suivant) · ordre en fin de fenêtre non
appliqué · titres achetés même revendus. Adaptés : rangs J+1 ([1, 14, 27]), exposition
95 %, ex-date, réserve vs tranche surdimensionnée (+ cas plafond auto).

## RE-MESURE — les chiffres d'attribution CHANGENT (et une conclusion S'INVERSE)

Preuve brute : `audit/preuves/attribution_remesuree_2026-10-13_lot9.txt`.

| Mesure (5 titres réels, 2022-2026) | 13/10 (lot 4) | **13/10 (lot 9)** |
|---|---|---|
| Noyau passif (A) | 233,0 % · expo 94,9 % | **203,0 % · expo 87,3 %** |
| Renforcement (C) | +26,7 pt | **−16,1 pt** — LA CONCLUSION CHANGE DE SIGNE |
| Paliers (D) | −49,0 pt | **−42,9 pt** |
| Stratégie complète (B) | −43,0 pt | **−54,4 pt** |

**Lecture.** L'avantage apparent du renforcement (+26,7 pt) était un **artefact de
composition** : la variante « renforcement » était simplement PLUS INVESTIE (300 k F/titre
contre 100 k). Avec le plafond équitable, **le renforcement coûte** (−16,1 pt) et le
**noyau passif reste la meilleure base** (232,6 % ajusté à l'exposition). Le coût des
paliers reste majeur (−42,9 pt) ; la complète coûte le plus (−54,4 pt). Cela **conforte la
doctrine du projet** (noyau buy & hold, paliers = coût documenté) — et illustre pourquoi
l'audit A3 exigeait de neutraliser la composition avant de conclure sur les habitudes.

## Traçabilité (chaîne complète)
- `audit/preuves/chiffres_reference.json` : attribution mise à jour (+ `_historique` daté
  12/10 et 13/10-lot 4) ; provenance étendue à la preuve lot 9.
- `docs/INVARIANTS-METIER.md` (B1) : « 40 à 50 points » + mesure **42,9 pt** (lot 9).
- `docs/RAPPORT-VALIDATION-28-ANS.md` : tableau §3 (lignes 3, 4, bilan), encadré §2.1,
  recommandation n°1.
- `audit/chiffres_publies_verifies.md` : nouvelle section de re-mesure lot 9.
- `tests/test_preuves_publiees.py` : B1 → 42,9 pt ; motifs des documents étendus (les
  anciens chiffres restent exigés — l'historique daté ne disparaît pas).
- `tests/test_strategie_leo.py`, docstrings moteur/scripts : alignés.

## Limites assumées
- Le plafond auto égalise la PART investissable, pas l'exposition TOTALE (la variante
  passive reste 100 % investie contre 85 % pour la complète) : c'est pourquoi
  `exposition_moyenne_pct` et le rendement AJUSTÉ restent les seules comparaisons publiées.
- Les dividendes ne sont PAS réinvestis par le moteur (le cash les accumule) — la
  docstring de `valider_variantes_strategie.py` disait le contraire, corrigée.
- Le composant « rebalancement » reste non modélisé (décision LEO si on l'ajoute).
