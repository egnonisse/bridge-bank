# DÉCISION — 12/10/2026 — Hiérarchie des sources & questions de l'audit (Q1-Q4)

**Décideur :** LEO · **Contexte :** audit technique BRVM (phases 0-2, voir `audit/manifest.json`)
— quatre questions ouvertes (Q1-Q4) attendaient une décision humaine ; les quatre ont été
tranchées le 12/10/2026 et sont **exécutées dans ce commit**.

---

## Q1 — Hiérarchie des sources en cas de contradiction → DÉCIDÉE

**Règle adoptée :** en cas de contradiction entre documents :

```
1. Décision datée        (docs/DECISION-*.md — la plus récente gagne)
2. Invariant             (docs/INVARIANTS-METIER.md)
3. IPS                   (docs/IPS.md)
4. Commentaire de code   (jamais une source de règle)
```

**Règle complémentaire (exigée par le contrôle) :** **toute contradiction constatée oblige à
mettre à jour la source perdante.** Deux versions d'une même règle ne cohabitent jamais :
c'est exactement l'écart qui a produit les CONFLIT-01 à 05.

**Inscription :** en tête de `docs/IPS.md` (bloc « Hiérarchie des sources »).

---

## Q2 — Mise à jour de l'IPS (CONFLIT-01, 02, 03) → FAITE

| Conflit | Correction appliquée dans `docs/IPS.md` |
|---|---|
| CONFLIT-01 (allocations 70 vs 60 vs 15) | §3 → « Noyau dividende (**70 %**) », §6 → « Liquidités (**30 %**) », conformes à la décision du 03/09 en §2 — mentions historiques annotées |
| CONFLIT-02 (obligations retirées mais décrites) | §5 → titre « **ARCHIVÉ** (retirée le 03/09/2026) » + avertissement « historique, ne plus s'y référer » |
| CONFLIT-03 (+13 % contre seuils par titre) | §3.4 → seuils **par titre** (13 SNTS · 10 SGBC · 5 SLBC · 5 PALC), mode **informatif**, renvoi à `DECISION-2026-10-08-seuils-vente.md` |
| CONFLIT-05 (IRVM 15 % / 5,65 % dans les docstrings) | Corrigé (règle Q1 : la source perdante est mise à jour) : `src/portfolio.py` (IRVM **12 %**, ≈ **5,45 %** entrée / ≈ **3,18 %** sortie) et `src/analyse/screener.py` (≈ 5,45 %) |

---

## Q3 — Signal de volume en spéculation → DÉCIDÉE et IMPLÉMENTÉE

**Décision :** le volume ≥ 2× n'est **plus un déclencheur requis ni un point de confluence**
(mesure : placebo, p = 0,44 — `docs/CHALLENGE-MULTI-MODELES.md`). Il reste **affiché en
information** pour la lecture humaine, et le choix est documenté.

**Implémentation :**
- `src/strategie/speculation.py` : `detect_signals()` ne contient plus le volume ;
  nouvelle fonction `volume_info()` (affichage seul) ; `screen_speculation()` exige
  uniquement le breakout 20j + confluence ≥ 3 signaux.
- `src/main.py` (`spec screen`) : le volume apparaît en « [info: …] », hors décompte.
- `docs/IPS.md` §4.1 mis à jour.
- Tests : `tests/test_speculation.py` (le volume ne compte pas ; il s'affiche).

**Note :** la poche spé reste suspendue pour le noyau ; cette correction assainit le code
pour l'usage « en conscience ». La veille spé « durée » garde son filtre volume distinct
(séance ≥ médiane 60 j à la cassure — obligation d'exécution, décision du 25/09).

---

## Q4 — `MAX_BUY_WEIGHT = 0,40` → CONFIRMÉ et INSCRIT

**Décision :** la valeur **0,40 est confirmée** (elle plafonne le poids d'ACHAT d'un
renforcement « limité » et détermine le `max_qty` conseillé dans l'alerte).

**Inscription + test :**
- `docs/IPS.md` §3.4 — bloc « Renforcement & plafonds de poids » (0,35 / 0,40 / 0,50).
- `tests/test_regles_centralisees.py::test_max_buy_weight_confirme_et_inscrit_dans_l_ips` —
  verrouille la valeur ET sa présence dans l'IPS.

---

## Conséquences pour l'audit

- Les 4 questions ouvertes du registre (`audit/phase2_exigences.md` §6) sont **tranchées** ;
  le manifest est mis à jour (statut « décidée »).
- Les CONFLIT-01/02/03/05 sont **résolus** ; CONFLIT-04 est **résolu par la décision Q3**.
- Phase 4 (conditions de réussite) pourra vérifier ces corrections par exécution.
