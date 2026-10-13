# Décision du 13/10/2026 — P7-01 : écriture atomique + lecture stricte des positions

## Contexte
Audit **phase 7** (13/10), item **P7-01 (sévérité HAUTE)** : `data/spec_positions.json` — les positions de **trading RÉEL** de la poche spéculative — était écrit par `write_text` DIRECT (`speculation.py`) et son loader avalait toute corruption **en silence** (`return []`) : un crash pendant l'écriture, ou un fichier tronqué, aurait fait croire à « aucune position » sans la moindre alerte. Même défaut sur `bonds_positions.json`.

## Correction (lot 5)
1. **Nouveau module `src/infrastructure/ecriture.py`** :
   - `ecrire_json_atomique(chemin, donnees)` — `.tmp` + `replace()` (atomique ; le motif inline existant, centralisé) ;
   - `lire_json_strict(chemin)` — absent → `None` (premier lancement, légitime) ; présent mais illisible → lève **`FichierEtatIllisible`** (doctrine lot 4 : échouer BRUYAMMENT).
2. **`speculation.py`** : `save_positions` → atomique ; `load_positions` → bruyant sur JSON invalide ou schéma incompatible.
3. **`bonds.py`** : idem (`save_bond_positions`, `load_bond_positions`).
4. **4 tests ajoutés** : absent → `[]` · corrompu → lève · écriture sans résidu `.tmp` + relisible (spec) · structure inattendue → lève (bonds).

## Découverte corrigée au passage — régression du LOT 4
La suite standard laissait **2 tests gardiens cassés depuis le lot 4** : `chiffres_reference.json` avait été alignée (paliers **−49,0**, provenance **13/10**) mais `tests/test_preuves_publiees.py` figait encore −45,4 et la date 12/10 — le rejeu `-m preuve` ne les couvre pas. Corrigés : assertions alignées sur la référence, motifs `49,0` / `+26,7` ajoutés aux documents gardés, 2 docstrings périmés rafraîchis (`test_paliers_sortie`, `test_strategie_leo`).
**LEÇON (procédure mise à jour)** : « quand la référence des chiffres publiés change, aligner les TESTS GARDIENS **et les docstrings** dans le MÊME commit » — ajouté à la procédure du skill `brvm-value-investing`.

## Preuves
- Suite complète : **488 passed, 0 failed** (`EXIT=0`, 152 s) ; 4 nouveaux tests.
- Données réelles relues après migration : `spec_positions.json` → **BICC + SMBC** ; `bonds_positions.json` → 0.
- Filets : chemins OK · **217 constantes identiques au snapshot** · config OK.

## Hors périmètre (en attente de décision LEO)
Les ~11 autres fichiers d'état non atomiques (reconstructibles — sévérité moindre) ; les items P6-01..05 et P7-02..04 de l'audit phase 6-7.

## Fichiers touchés
`src/infrastructure/ecriture.py` *(nouveau)* · `src/strategie/speculation.py` · `src/analyse/bonds.py` · `tests/test_speculation.py` · `tests/test_bonds.py` · `tests/test_preuves_publiees.py` · `tests/test_paliers_sortie.py` *(docstring)* · `tests/test_strategie_leo.py` *(docstring)*.
