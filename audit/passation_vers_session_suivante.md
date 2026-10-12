# Passation — suite de l'audit Bridge Bank

**À lire par la session qui reprend le travail.** Rédigé le 12/10/2026, à la fin de la session
`20261009_015303_6c45b6`. État vérifié, pas d'intention.

## 1. État exact

| | |
|---|---|
| Dépôt | `C:\Users\LEO\projects\Bridge Bank` · branche `main` · **HEAD `2b8438d`** |
| Interpréteur des tests | `C:\Users\LEO\AppData\Local\hermes\hermes-agent\venv\Scripts\python` (le `python` du PATH n'a pas les dépendances) |
| Tests | **379 verts**, 0 xfail (139-158 s) |
| CI | `.github/workflows/ci.yml` — **run #28 vert** sur `2b8438d`, vérifié par l'API |
| Couverture | **51 %** (`pytest-cov` déclaré dans `requirements-dev.txt`, config `pyproject.toml`, **aucun `fail_under`**) |
| Arbre de travail | propre, sauf `data/titres_inactifs.json` (non suivi, régénéré à chaque refresh) |
| Dossier d'audit | `audit/` — `manifest.json` = état officiel, `preuves/` = preuves brutes |

## 2. Ce qui est fait — ne pas refaire

- **Audit phases 0 → 5 et 8** (exécution contrôlée) : `audit/phase0_capacites.md`, `phase1_cartographie.md`,
  `phase2_exigences.md`, `phase3_agent*.md`, `matrice_tests_phase4.md`, `phase5_synthese.md`,
  `registre_desaccords.md`, `phase8_execution_controlee.md`.
- **Corrections des lots 1 à 3** appliquées et validées par exécution (18 tests de régression).
- **Référence des sorties** : le delta a été mesuré et **entièrement attribué** aux corrections
  voulues (101 différences de format + 22 substantielles, cf. `phase8_execution_controlee.md` §4).
- **Chiffres publiés re-mesurés** (`chiffres_publies_verifies.md`) : **5 sur 6 tiennent**, dont
  l'attribution des paliers (−45,4 pt, fondement de la décision du 08/10 et de l'invariant B1).
  Le rebalancement à 10 ans **change de signe** (en faveur). La sélection (−6,9 pt) reste
  **non reproductible** (entrées non versionnées).
- **Couverture mesurée** (`couverture_tests.md`).

## 3. À faire, par ordre de valeur

1. **Tests des moteurs de preuve** — c'est le prolongement direct du constat ci-dessous :
   - `src/strategie/strategie_leo.py` (**0 %**, vrai code : `MoteurLeo`) ;
   - `src/strategie/paliers_sortie.py` (**0 %**, `simuler_paliers`/`comparer_modes`) ;
   - `src/backtesting/backtest_noyau.py` (**28 %**).
   Et **un test de non-régression par chiffre publié** : le script rejoué (à graine fixe) doit
   produire une valeur connue, et tout écart doit **faire échouer le test**. C'est la version
   automatisée de la vérification manuelle du 12/10.
2. **Test de lecture minimal sur `src/collecte/divisions_officielles.py`** (**0 %**, vrai code) :
   une erreur de division fausse silencieusement **tous** les rendements longs.
3. Phases 6-7 de l'audit (contrats inter-modules, sécurité) — valeur réelle, rendement plus faible
   sur ce projet (pas de serveur, pas d'utilisateur, pas de base de données).

**Le constat qui commande cet ordre** : *les chiffres qui fondent les décisions sont produits par le
code le moins couvert du projet.* C'est pourquoi la réparation du cache historique a pu déplacer
l'attribution de −43,1 à −45,4 pt et inverser le signe du rebalancement **sans qu'aucune alerte ne
se déclenche**. Rien n'était cassé — mais rien ne veillait.

## 4. Règles non négociables

- **Geler `data/` avant toute exécution de tests** (empreinte SHA-256 avant/après). La **production
  écrit dans `data/`** : un check quotidien tourne vers 09h13. Un test qui lit un état mouvant ne
  prouve rien.
- **Toute mesure publiée porte sa provenance** : script, données, date. Jamais de réécriture
  silencieuse d'un chiffre — on l'**encadre** (« enregistré le X / recalculé le Y », corrections
  concernées, renvoi vers les preuves brutes).
- **Un chiffre qui ne se reproduit pas n'est pas « faux »** : on écrit que la configuration d'origine
  n'est pas identifiée (défaut de traçabilité) et on passe au suivant.
- **Un contrôle qui ne peut pas échouer ne prouve rien** : le casser volontairement pour vérifier
  qu'il échoue (fait pour la référence de sorties et pour le verdict de revenu).
- **Aucun `fail_under`** sur la couverture : 51 % est une mesure de départ, pas un objectif. Un seuil
  posé maintenant s'atteindrait par des tests faciles.
- **Aucune règle métier modifiée sans décision explicite de LEO.** Hiérarchie des sources :
  décision datée > invariant > IPS > commentaire de code.
- **CI : vérifier le run DU SOMMET** par l'API (`cancel-in-progress: true` annule les runs
  intermédiaires — un run vert ne couvre pas forcément un commit intermédiaire).

## 5. Commandes utiles

```bash
PY="C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python"
cd "C:/Users/LEO/projects/Bridge Bank"

"$PY" -m pytest -q                                  # la suite (379 tests)
"$PY" -m pytest -q --cov --cov-report=term-missing  # + la couverture
"$PY" scripts/verifier_chemins.py --strict          # filet 1
"$PY" scripts/auditer_constantes.py --comparer      # filet 2 (215 valeurs)
"$PY" scripts/verifier_configuration.py             # filet 3

# les 5 mesures du rapport 28 ans (en SÉRIE, jamais en parallèle ; ~15 min au total)
for s in validation_longue tester_entree_progressive tester_rebalancement tester_paliers \
         mesurer_detachements; do "$PY" scripts/$s.py; done
```

Le crochet **pre-push** rejoue les filets et bloque une poussée cassée. Les 5 sorties brutes de la
re-mesure sont dans `audit/preuves/remesure_*.txt` — elles servent de valeurs de référence.

⚠️ **Ces mesures ÉCRIVENT dans `data/`** — c'est vérifié, ne le découvre pas en cassant quelque
chose : `tester_rebalancement.py`, `tester_entree_progressive.py`, `mesurer_detachements.py`,
`validation_longue.py` et `tester_paliers.py` déposent leurs résultats dans des fichiers **suivis**
par git (`data/test_rebalancement.json`, `data/test_entree_progressive.json`,
`data/mesure_detachements.json`, `data/validation_longue.json`…). Conséquence pratique :
**prendre l'empreinte de `data/` AVANT de les lancer**, puis committer les nouveaux résultats
explicitement (« re-mesuré le … sur données et code corrigés ») — jamais les laisser en modification
silencieuse. Les valeurs précédentes restent récupérables (`git show HEAD:data/<fichier>.json`),
contrairement aux caches `data/*.pkl` qui, eux, ne sont pas versionnés.
