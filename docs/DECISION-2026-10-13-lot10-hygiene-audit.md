# Décision du 13/10/2026 — Lot 10 : hygiène d'audit (A-003, B2-14, B2-15, registres)

## Contexte
Dernier bloc des « quick wins » de la clôture d'audit : le seul item **P1** restant
(A-003), deux écarts d'hygiène git (B2-14, B2-15) et l'actualisation des registres
(A-001/A-002/R-001/R-002 — statuts figés sur des états périmés).

## Corrections

**A-003 (P1) — `payout_ratio(None)` levait un TypeError.** Reproduit **en réel avant
correction** (`TypeError: '<=' not supported between instances of 'NoneType' and 'int'`,
ligne 379) : un titre du noyau sans dividende connu faisait planter l'étape
« Soutenabilité ». Fix : garde `None` explicite (dps/price) + type hints élargis —
**une donnée manquante = abstention, jamais une exception**. Test : 3 assertions
ajoutées à `test_payout_ratio` (fichier vert, 43 tests).

**B2-14 (P3) — backup git fourre-tout.** `git_backup.py` faisait `git add -A` : le commit
`968998f` (25 fichiers) mêlait livrables d'audit + état + données. Fix :
`git add -A -- . ':(exclude)audit'` — les livrables d'audit se committent
**explicitement dans leur lot** (règle « un lot = un commit », architecture §9) ; le
reste du dépôt (src, scripts, tests, docs, data, racine) reste couvert. **Exclusion
vérifiée en réel** : un fichier témoin déposé dans `audit/` est resté non indexé.
*Écart assumé avec le finding* : les artefacts `data/test_*.json` **restent versionnés**
— ils fondent la chaîne de preuve (référence → sorties → documents) et la CI les lit ;
les gitignorer casserait les tests gardiens.

**B2-15 (P3) — documents personnels suivis puis poussés sur GitHub.** 30 fichiers
(`data/avis/*` = 20 : avis courtier PDF/PNG/TXT ; + `boc_2026-08-17.pdf`, `ocr_up.png`,
`palc_notation_2026.pdf`, `semc_*`, `sitab_ef2025.txt`, `snts_age_2026.pdf`,
`snts_direction.png`) retirés du **suivi** (`git rm --cached`), **conservés sur le
disque** — vérifié : aucun test ni module `src/` ne les lit, seuls `scripts/parse_avis*.py`
les lisent en local. `.gitignore` étendu : `data/avis/`, `data/*.pdf`, `data/*.png`,
`data/*.txt`. **La purge d'historique n'est PAS faite** (réécriture = décision de LEO) ;
le bundle local `D:/PROJETS/bridge-bank-*.bundle` reste à sécuriser côté disque.

## Registres actualisés (statuts réels, vérifiés)

| Item | Ancien statut | Nouveau statut |
|---|---|---|
| A-001 | RÉSOLUE 12/10 | RÉSOLUE (credential revérifié sur les pushes du 13/10 ; run hebdo du **18/10** à confirmer) |
| A-002 | « risque identifié » | **RÉSOLUE le 13/10** — livraison réparée (jobs du matin `completed`) |
| A-003 | « anomalie reproduite » | **RÉSOLUE le 13/10** (ce lot) |
| R-001 | « risque non confirmé » | **RÉSOLU le 13/10** — les 4 modules cités ont des tests |
| R-002 | « outils impossibles » | couverture **mesurée** (51 %, aucun `fail_under`) ; mutation = limite **assumée** |

## Preuves
- A-003 : reproduit → corrigé → `pytest tests/test_portfolio.py` → **43 passed**.
- B2-14 : exclusion prouvée en réel (témoin `audit/_test_exclusion.tmp` resté `??` puis supprimé).
- B2-15 : `git ls-files data/ | grep -Ei '\.(pdf|png|txt)$'` → **0** ; disque intact
  (`data/avis/` = 25 fichiers, 7 pdf/png à la racine `data/`).
- Suite complète : **511 passed** (voir rapport du lot).
