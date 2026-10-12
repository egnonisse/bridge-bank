# AUDIT BRVM — Phase 8 : exécution contrôlée

**Date** : 2026-10-12 · **Autorisation** : LEO (« oui vas-y ») · **Commit audité** : `ec4f460`
**Interpréteur** : `hermes-agent/venv` (Python 3.11.15) · **Discipline** : exécuter, mesurer, rien modifier.

---

## 1. Condition préalable — gel de `data/`

L'audit avait constaté que la **production écrit dans `data/`** (check quotidien de 09h13 le 09/10 :
`per_cache.json`, `reinf_alert_state.json`, `alertes_journal.jsonl`). Avant toute exécution :

```
111 fichiers de data/ empreintes (SHA-256) -> audit/preuves/phase8_gel_data_avant.txt
```

**Après** l'exécution complète, même empreinte rejouée :

```
comparaison avant/apres : 0 modifie(s), 0 ajoute(s), 0 disparu(s)
-> AUCUNE modification : l'execution n'a pas touche data/
```

**[Fait vérifié] L'exécution contrôlée est non destructive** : la suite de tests ne touche pas un
octet des données de production. C'est la condition que j'avais posée ; elle est remplie et prouvée.

## 2. Les trois filets, avant exécution

| Filet | Résultat |
|---|---|
| `scripts/verifier_chemins.py --strict` | **0** chemin recalculé à la main |
| `scripts/auditer_constantes.py --comparer` | **215 valeurs identiques** au snapshot |
| `scripts/verifier_configuration.py` | **conforme** (instantané, config.yaml, secrets) |

## 3. Suite complète

```
$ python -m pytest -q -ra
374 passed in 148.58s (0:02:28)        code retour 0
```

**374 tests, 0 échec, 0 `xfail` résiduel, 0 ignoré** — les 6 `xfail` posés en Phase 4 comme
« cibles de correction » ont bien été retirés quand les corrections sont arrivées : le filet est
armé, pas contourné.

### Les tests de régression des corrections (lots 1-3)

```
$ python -m pytest tests/test_regressions_audit.py -v
18 passed in 49.59s
```

Ils couvrent nommément : sortie rapprochée / éloignée par un dividende, stopouts espacés,
fiche livrée ou non, `per_cache` (valeurs invalides, schéma de date, verrou libéré et orphelin purgé),
cooldown de watchlist, `close_reason` portant la date du stop, sortie non délivrée annulant la
clôture, sortie délivrée persistée.
**[Fait vérifié] Les corrections des lots 1 à 3 sont validées par exécution, pas par lecture.**

## 4. Le point grave — le filet de non-régression a été régénéré

Le filet de sorties (`tests/fixtures/sorties_reference.json`) devait prouver que les corrections
ne changeaient **rien d'autre**. Or :

```
empreinte au 09/10 (3 captures identiques) : a6d110cd5845b9f9
empreinte aujourd'hui                      : 5af60e2b8034843b
commits l'ayant modifié : 615ca9a (lot 1) · c23f9d4 (lot 2)
```

**Un filet régénéré par le code qu'il surveille ne prouve plus « rien n'a changé »** : il prouve
seulement que le code produit la référence que le code vient de produire. Sa valeur probante pour
les corrections est donc **perdue en l'état**.

### Le delta, mesuré et jugé (au lieu d'être supposé)

Comparaison du blob **d'avant corrections** (`f109329`, qui contient déjà les commandes CLI) avec
l'actuel — `audit/preuves/phase8_delta_reference_sorties.txt` et `phase8_delta_normalise.txt` :

| | Nombre |
|---|---|
| Sorties communes | 410 |
| Identiques | **287** |
| Différentes | **123** |
| dont **formatage seul** (normalisation des nombres) | **101** |
| dont **substantielles** | **22** |
| Clés déplacées (prix d'entrée) | 36 ajoutées / 36 disparues |

Les **22 substantielles**, toutes attribuées :

| Nature | Exemple | Rattaché à |
|---|---|---|
| Dividendes comptés **nets** (× 0,88) | SLBC 5600 → 4928 · SNTS 17793 → 15657,84 · SGBC 9000 → 7920 | correction **B1-03** (DRIP net), lot 2 |
| **Prix d'entrée** (−1,381 %) | SNTS 36245 → **35744,58** · PALC 7333,33 → 7232,08 · SGBC 55000 → 54240,63 | correction **B1-08**, lot 2 |
| Messages reflet (montant net, prix d'entrée) | « Dividende versé : 17793 FCFA » → « 15658 » | B1-03 |
| Typographie du zéro | « +0.0 % (+0) » → « +0.0 % (0) » | format FR, lot 1 |

Les 101 « format seul » sont la correction **format FR** du lot 1 (`-21,360 F` → `-21 360 F`).
Les 36 clés déplacées le sont du **même −1,381 %** que B1-08 : les scénarios de test sont indexés
par le prix d'entrée, qui a changé.

**[Fait vérifié] Aucune dérive inexpliquée : les 123 modifications et les 72 clés déplacées
correspondent, une à une, à des corrections décidées et documentées.** Le filet a donc joué son
rôle par un autre chemin que prévu : non pas « rien n'a changé », mais « tout ce qui a changé est
voulu, et rien d'autre n'a bougé » — 287 sorties structurelles (niveaux, décisions, alternatives,
historiques) sont restées identiques.

## 5. Trouvaille mineure — le filet peut s'éteindre en silence

`tests/test_sorties_invariables.py:26` :

```python
pytest.skip(f"référence absente : {SORTIE} (lancer scripts/capturer_sorties.py)")
```

Si la référence disparaît (mauvaise manipulation, exclusion git, clone partiel), le test
**passe en ignoré** au lieu d'échouer. Un contrôle qui peut s'éteindre sans bruit n'est pas un
contrôle — c'est la même famille de défaut que le cache pickle ignoré par git, déjà rencontré.

## 6. Verdict de la Phase 8

| Question | Réponse |
|---|---|
| La suite passe-t-elle sur l'arbre audité ? | **Oui** — 374/374, 148 s, code retour 0 |
| Les corrections des lots 1-3 sont-elles validées ? | **Oui** — 18 tests de régression verts |
| L'exécution modifie-t-elle les données ? | **Non** — 0 fichier touché sur 111 |
| Les corrections ont-elles cassé autre chose ? | **Non** — 0 dérive inexpliquée sur 410 sorties |
| Le filet de non-régression prouve-t-il encore ? | **Plus tel quel** — il a été régénéré (§4) ; son delta est désormais examiné et attribué |
| Reste-t-il des points ouverts ? | **Oui** — voir §7 |

## 7. Recommandations (aucune n'a été appliquée — elles demandent ton accord)

1. **Re-baseliner la référence** dans un commit qui dit explicitement « référence mise à jour par
   les corrections X et Y » — au lieu d'un changement silencieux enfoui dans un commit de correction.
2. **Supprimer l'échappatoire `skip`** : si la référence manque, le test doit **échouer**.
3. **Re-dériver les seuils par titre** : A3-01/A3-02 (look-aheads BPA/TTM) sont corrigés, mais les
   statistiques qui ont calibré les seuils de vente ont été calculées **sur les données biaisées**.
   Tant qu'elles ne sont pas recalculées, les seuils restent calibrés sur une base partiellement
   faussée. C'est la conséquence la plus lourde du P1, et elle n'est pas encore traitée.
4. **Ne pas laisser `cancel-in-progress` masquer des états non validés** : 7 états, dont les
   décisions Q1-Q4 et les phases 4-5, n'ont jamais été validés directement (voir
   `preuves/ci_runs_verification_2026-10-12.txt`).

## 8. Limites

- Pas d'outil de couverture disponible : « 374 tests verts » ne dit rien du **pourcentage** du code
  exercé (limite connue de l'audit, notée en Phase 10).
- Cette phase prouve que le **code** fait ce qu'on attend ; elle ne prouve pas que les **règles**
  sont rentables (c'est la Phase 5, statique et statistique) ni que le marché se comportera ainsi.
- L'exécution a eu lieu sur `ec4f460` : toute modification ultérieure invalide ces preuves.
