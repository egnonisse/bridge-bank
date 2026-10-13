# Décision du 13/10/2026 — Lot 8 : le chantier du JUGE (audit A3-03/04/05/09/10/13)

## Contexte
Les items « challenge » du chantier 3 (§3). Le juge (`challenge_validateur.py`) était
le dernier module majeur **sans aucun test** (R-001) et le plus permissif. Son
durcissement **change des chiffres publiés** — assumé, mesuré et daté ici.

## Corrections appliquées

**A3-10 — exécution à J+1.** Un signal lu au close de la séance `i` est exécuté au
close de `i+1`, **entrées ET sorties** (`simuler`). Sur une place au fixing, on ne
trade pas le close qu'on vient de lire : sans ce décalage, une règle de réaction
courte mesure un avantage que la baseline n'a pas.

**A3-05 — p-value honnête + baseline corrigée.**
- `p = (1 + #≥) / (1 + N)` — jamais 0,0000 ; `NB_TIRAGES_ALEATOIRES` 100 → **1000** ;
- la baseline **ne tire plus avant `SEANCES_MIN_INDICATEURS`** (l'ancien tirage
  pouvait commencer à la séance 0, où la règle n'a pas le droit d'agir) ;
- **durées rééchantillonnées** sur celles des trades réels (plus de durée figée) ;
- **bootstrap conditionnel** : dates de départ tirées DANS les dates de la règle —
  la corrélation entre trades d'un même jour ne sous-estime plus la variance ;
- `seuil_p` déclaré par l'appelant : les orchestrateurs passent `0,05 / nb_hypothèses`
  (**Bonferroni**) — 20 tests à 0,05 laissaient attendre ≈ 1 faux positif.

**A3-03 — robustesse par l'AVANTAGE.** Baseline recalculée **séparément par moitié** ;
le verdict exige `avantage_in > 0` ET `avantage_out > 0` (l'ancien test portait sur le
rendement ABSOLU, quasi toujours positif dans un marché à +145 %). Coupure **figée** :
`DATE_COUPURE_DEFAUT = "2022-01-01"` (jamais choisie après avoir vu les résultats).

**A3-04 — dividendes des deux côtés.** Appelants corrigés (`challenge_multi_modeles`,
`tester_le_juge`) ; `evaluer_hypothese` **SIGNALE** l'absence d'`historique_fond`.

**A3-09 — `resume()` robuste** : 0 trade, baseline absente, moitiés absentes — plus
de `TypeError` (un formatage `n/d` partout).

**A3-13 (validateur)** : bloc `indicateurs()` local **supprimé** (code mort dupliquant
`challenge_indicateurs.precalculer`, ZÉRO appelant) ; `charger_fondamentaux` ne masque
plus ses replis (dataset/cache illisibles = message).

**BUG découvert et corrigé pendant la re-mesure** : `scripts/revalider_regles_challenge.py`
affichait `res.verdict` (variable de la DERNIÈRE règle évaluée) pour TOUTES les lignes —
bilan faussé (« 0/6 » annoncé ; 1/6 réel). **Les bilans antérieurs de ce script sont à
relire avec méfiance.**

## Tests (R-001) — `tests/test_challenge_validateur.py` (8 tests)
`resume` robuste · baseline bornée à la fenêtre éligible (preuve par série piégée) ·
p=(1+#≥)/(1+N) (baselines patchées) · bootstrap conditionnel (tous les paniers partent
de la date donnée) · exécution J+1 (prix d'entrée = close i+1, PAS le prix du signal) ·
verdict par avantage/moitié (+ repli non régressif) · signalement hf ·
AUCUN SIGNAL protégé.

## RÉSULTAT — les 6 règles retenues, re-jugées par le juge durci

| Règle | trades | net | hasard | avantage | p (seuil 0,0083) | verdict |
|---|---|---|---|---|---|---|
| claude-haiku-5-H1 | 269 | 20,35 % | 14,17 % | +6,18 pt | 0,154 | NON CONCLUANTE |
| gpt-5.6-luna-p-H1 | 909 | 5,70 % | 4,21 % | +1,49 pt | 0,104 | NON CONCLUANTE |
| gpt-5.6-luna-p-H2 | 983 | 4,25 % | 3,43 % | +0,82 pt | 0,237 | NON CONCLUANTE |
| gpt-5.6-luna-p-H4 | 420 | 5,68 % | 3,45 % | +2,23 pt | 0,159 | NON CONCLUANTE |
| **gemini-2.5-fla-H3** | 1576 | 2,36 % | 0,29 % | **+2,07 pt** | **0,005** | **RETENUE** (moitiés +3,21/+1,59) |
| gemini-2.5-fla-H4 | 225 | 1,91 % | 5,15 % | −3,24 pt | 0,919 | NON CONCLUANTE |

**1/6 TIENT.** Avant le durcissement, la référence publiée était « **6/6 tiennent
(+5 à +19,5 pts, p = 0,000)** » — obtenue avec des p-values non ajustées, une baseline
optimiste (durée figée, dates indépendantes, fenêtre dès la séance 0) et une exécution
au close du signal. Le durcissement ne « casse » pas les règles : il révèle que
**5 des 6 étaient dans le bruit du marché**. La phrase-socle du skill — « aucun
déclencheur testé ne bat le hasard net de frais » — en sort **renforcée**, et la
suspension de la spéculation confortée.

## Mises à jour de traçabilité
- Skill `brvm-value-investing` : tableau des mesures + note du durcissement.
- `scripts/revalider_regles_challenge.py` : bug d'affichage corrigé + seuil Bonferroni.
- `CHALLENGE-MULTI-MODELES.md` (doc du projet) : addendum daté.

## Preuves
- Suite complète : **504 passed** (496 + 8 du juge).
- Re-mesure : `C:\Users\LEO\AppData\Local\Temp\revalidation_finale.txt` (« 1/6 »).
- **Déterminisme vérifié** : H3 évaluée 3× (seule, ×2, après H1) → avantages identiques
  au bit (3.211016248765991 / 1.5939697853561474) — la contradiction apparente
  « 0/6 puis 1/6 » venait du bug d'affichage du script, pas du juge.
- `data/` : md5 identiques avant/après la re-mesure (48 fichiers OK).
