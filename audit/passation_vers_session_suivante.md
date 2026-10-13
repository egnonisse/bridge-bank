# Passation — suite de l'audit Bridge Bank

**À lire par la session qui reprend le travail.** Rédigé le 12/10/2026 à la fin de la session
`20261009_015303_6c45b6` ; **mis à jour le 13/10/2026 après le LOT 4 et le rejeu de confirmation.**

## 1. État exact

| | |
|---|---|
| Dépôt | `C:\Users\LEO\projects\Bridge Bank` · branche `main` · **HEAD `2974ad7`** (rejeu de confirmation du 13/10 : EXIT 0, aucun écart) |
| Interpréteur des tests | `C:\Users\LEO\AppData\Local\hermes\hermes-agent\venv\Scripts\python` (le `python` du PATH n'a pas les dépendances) |
| Tests | **484 verts**, 0 xfail (+ le rejeu marqué `preuve`, exclu par défaut : `pytest -m preuve -s`) |
| CI | `.github/workflows/ci.yml` — dernier état vérifié par LEO : 24 verts / 25 runs (12/10). **Vérifier le run du SOMMET `2974ad7`** (l'assistant n'a pas accès au repo privé) |
| Couverture | **51 % global** (aucun `fail_under`) ; moteurs de preuve : `strategie_leo` 94 %, `paliers_sortie` 96 %, `backtest_noyau` 87 %, `divisions_officielles` 84 % |
| Arbre de travail | attendu : 4 fichiers `data/` écrits par la production (`alertes_journal`, `per_cache`, `spec_seen_state`, `value_new_state`) + `audit/etat_des_lieux/` non commité (livrables pour LEO) |
| Dossier d'audit | `audit/` — `manifest.json` = état officiel, `preuves/` = preuves brutes ; `audit/etat_des_lieux/` = inventaire agents + vérifications V1-V8 (13/10) |

## 2. Ce qui est fait — ne pas refaire

- **Audit phases 0 → 5 et 8** (exécution contrôlée) : `audit/phase0_capacites.md`, `phase1_cartographie.md`,
  `phase2_exigences.md`, `phase3_agent*.md`, `matrice_tests_phase4.md`, `phase5_synthese.md`,
  `registre_desaccords.md`, `phase8_execution_controlee.md`.
- **Corrections des LOTS 1, 2, 3** (12/10) **et 4** (13/10) appliquées et validées par exécution :
  - **LOT 4** (doc : `docs/DECISION-2026-10-13-lot4-residuels.md`) : **B2-07** les jobs agents value+radar livrent par le **notifier interne** (découpage > 4096 car. inclus) — le gateway Telegram supprimait en silence ; **B2-05/06/12** silences de collecte (divisions bruyantes, replis journalisés) + drapeau d'empreinte (C9) ; **A3-11** dividende point-in-time (péremption 15 mois + cumul annuel, C7) ; **A3-12** 4 défauts du moteur de simulation (dividendes d'une position soldée conservés, achat borné au disponible, dividende crédité avant les ordres du jour, plafond sur l'investi cumulé).
- **Tests des moteurs de preuve + non-régression des chiffres publiés** (`4f3e59d`) : couverture `strategie_leo` 0→94 %, `paliers_sortie` 0→96 %, `backtest_noyau` 28→87 %, `divisions_officielles` 0→84 %. Référence gelée `audit/preuves/chiffres_reference.json` + rejeu `scripts/verifier_chiffres_publies.py` (exit 1 à tout écart) + tests gardiens (dont un `preuve` exclu par défaut — **le casser volontairement pour vérifier qu'il échoue**).
- **Chiffres publiés re-mesurés** (`chiffres_publies_verifies.md`) : 5 sur 6 tiennent. L'attribution a été **re-mesurée le 13/10 après le LOT 4** (paliers −45,4 → **−49,0 pt** ; noyau 232,2 → **233,0 %** ; renforcement +26,7 ; bilan −43,0) ; **rejeu de confirmation EXIT 0** (`2974ad7`) ; docs alignés (INVARIANTS-METIER, RAPPORT-VALIDATION-28-ANS). Le rebalancement à 10 ans **change de signe** (en faveur). La sélection (−6,9 pt) reste **non reproductible** (entrées non versionnées).
- **État des lieux agents + vérification V1-V8** (13/10, `audit/etat_des_lieux/`) : inventaire recadré Bridge Bank (9 agents, 6 jobs, 10 écarts, 0 élevé) ; vérification des 8 points (2 corrections au rapport d'inventaire : **clé Anthropic INVALIDE**, écart OpenRouter ; skill brvm chargé à la demande confirmé). `providers.default` **aligné sur deepseek** ; mémoire Hermes consolidée ; skill `brvm-value-investing` **découpé** (987 → 133 lignes, archive intégrale dans `references/_archive-skill-md-2026-10-13.md`).

## 3. À faire, par ordre de valeur

1. **Décisions sur l'audit phases 6-7 (FAITES le 13/10)** — `audit/phase6_contrats_modules.md` (5 items, 0 sévérité haute : P6-01 redéfinitions de chemins ×6, P6-02 cycle portfolio⇄speculation, P6-03 portfolio.json vs portfolio_state.json, P6-04 format implicite de history_clean.pkl, P6-05 règle de centralisation non écrite) et `audit/phase7_securite_integrite.md` (4 items, **P7-01 HAUTE** : spec_positions.json non atomique + loader qui avale la corruption ; P7-02 token dans les logs d'erreur ; P7-03 pickle sans garde ; P7-04 micro). **Aucune correction appliquée — tout attend une décision de LEO.** ✅ Exception : **LOTS 5-6 (13/10) — P7-01, P6-01, P6-03, P6-05, P7-01c, P7-02, P7-04 CORRIGÉS** : atomicité généralisée (17 sites + test statique `test_atomicite_etat.py`), 8 redéfinitions de chemins migrées vers `paths.py`, `verifier_chemins.py` étendu à 2 contrôles (chemins + noms recopiés, les deux prouvés capables d'échouer), logs Telegram assainis (`_sans_token`) ; suite **490 verts**. Docs : `docs/DECISION-2026-10-13-p7-01-atomicite-et-lecture-stricte.md` + `docs/DECISION-2026-10-13-lot6-integrite-etat.md`. Découverte au passage : 2 tests gardiens cassés depuis le LOT 4 (référence −49,0 vs tests −45,4) — corrigés + procédure du skill mise à jour.
**Restes ouverts : AUCUN item P6/P7.** ✅ **LOT 7 (13/10)** : P6-04 (lecture unique du cache + signature `_cache_sha` dans le régime — auto-invalidation) et P7-03 (`history_io.py` : sidecar `.sha256` du cache vérifié au chargement) **CORRIGÉS** ; P6-02 = dette ASSUMÉE, verrouillée par 4 tests (`test_poches_etanches`) ; docs : `docs/DECISION-2026-10-13-lot7-signature-cache.md`. ✅ **LOT 8 (13/10) — chantier A3, le JUGE** : durci (J+1, p=(1+#≥)/(1+N) sur 1 000 tirages, baseline conditionnelle durées+dates, avantage par moitié, Bonferroni), **8 tests créés** (le juge n'en avait aucun — R-001), **6 règles re-jugées : 1/6** (H3 seule) ; **bug d'affichage** du script de re-validation corrigé (`res`→`apres`). **RESTE (chantier A3)** : **A3-08** — moteur `strategie_leo` (attribution des composants : capital équitable par titre, paramètres morts, titres achetés imprimés) → re-mesure des 4 chiffres publiés attendue. Docs : `docs/DECISION-2026-10-13-lot8-chantier-challenge.md`. ✅ **LOT 9 (13/10) — chantier A3 (moteur) TERMINÉ** : plafond de ligne dynamique (`capital × (1−cash)/n_titres` — toutes les variantes achètent le MÊME univers), 5 paramètres morts retirés, `titres_achetes` publiés, exécution J+1 (garde-fous re-vérifiés, ordre non exécuté jamais appliqué), 6 tests (32 au total) ; **attribution RE-MESURÉE** : noyau 203,0 %/87,3 % ; **renforcement −16,1 pt (LA CONCLUSION CHANGE DE SIGNE : l'ancien +26,7 était un artefact de composition)** ; paliers −42,9 ; complète −54,4 — référence, invariants B1 (42,9 pt), rapport 28 ans et tests gardiens alignés. **Le chantier A3 est COMPLET** (juge lot 8 + moteur lot 9). Docs : `docs/DECISION-2026-10-13-lot9-moteur-equitable.md`. ✅ **LOT 10 (13/10) — HYGIÈNE D'AUDIT** : **A-003 corrigé** (P1 : `payout_ratio(None)` levait un TypeError — reproduit en réel avant correction, garde `None` + 3 assertions) ; **B2-14** (backup : `git add -A -- . ':(exclude)audit'` — exclusion vérifiée en réel ; les artefacts `data/test_*.json` restent versionnés, écart assumé) ; **B2-15** (30 documents personnels retirés du suivi git — `data/avis/` + 10 fichiers racine, disque intact, `.gitignore` étendu ; purge d'historique = décision LEO) ; **registres actualisés** (A-001/A-002/A-003/R-001/R-002 → statuts réels vérifiés). Docs : `docs/DECISION-2026-10-13-lot10-hygiene-audit.md`. **Restent (P2/P3, à décider)** : B1-10/B1-11/B1-14/B1-15 (veille spé — fallback silencieux, stop bas de fourchette, close_price, alerte brute), B2-08 (6 wrappers hors dépôt), R-002 (mutation, assumé). Décisions LEO : SPHC, SNTS 26/10, backup dim 18/10, ANTHROPIC_BASE_URL, curator adopt.
2. **Décisions de LEO en attente** : clé Anthropic invalide + son doublon dans `.env` ; garde-fous durs Hermes ; plafond OpenRouter ; vérifier que le backup git de dimanche passe (1 échec + 1 interrompu ces 2 dernières semaines, credential corrigé le 12/10).
3. **Constats moteur en attente de décision** (documentés, non corrigés) : `backtest_noyau` ne compte AUCUN frais (absolus optimistes, relatifs valables) ; le renfort de `strategie_leo` n'a de marge que si les tranches sont rabotées par le cash. Doc : `docs/DECISION-2026-10-12-tests-moteurs-de-preuve.md`.

**Le constat qui commande cet ordre** : *les chiffres qui fondent les décisions sont produits par le
code le moins couvert du projet.* C'est pourquoi la réparation du cache historique a pu déplacer
l'attribution de −43,1 à −45,4 pt et inverser le signe du rebalancement **sans qu'aucune alerte ne
se déclenche**. Rien n'était cassé — mais rien ne veillait. (Depuis : les 4 moteurs sont couverts et un rejeu garde la référence.)

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

"$PY" -m pytest -q                                  # la suite (496 tests)
"$PY" -m pytest -q --cov --cov-report=term-missing  # + la couverture
"$PY" scripts/verifier_chemins.py --strict          # filet 1 (2 contrôles : chemins recalculés + noms recopiés)
"$PY" scripts/auditer_constantes.py --comparer      # filet 2 (217 valeurs)
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

## 6. ⏰ ÉVÉNEMENT DATÉ — fractionnement SNTS ×10 (26/10/2026)

**Faits** (communiqué SONATEL du 12/10, lu le 13/10 — PDF scanné, lu par vision) : AGE du 08/10 →
**10 nouvelles pour 1 ancienne** ; nominal 500 → 50 F (100 M → 1 Md titres) ; dernière cote ancienne
base **ven. 23/10** ; base fractionnée à l'ouverture du **lun. 26/10** (positions traitées
automatiquement par le DC/BR, sans frais ; cours de référence publié au BOC).

**Impact portefeuille** (position SNTS **3 @ 32 436**) : → **30 titres @ 3 243,60** (valeur inchangée) ;
`dps` 1 977 → 197,70 ; `exit_price` 62 134,29 → 6 213,429 ; `entry_price_ref` 35 744,58 → 3 574,458.

**Checklist (le 26/10, ou le 27/10 AVANT 09h — sinon le check crie « cassure SNTS », à raison)** :
1. `data/divisions_officielles.json`, clé `divisions` : ajouter
   `{"code": "SNTS", "date": "2026-10-26", "nouvelles": 10, "anciennes": 1, "facteur": 10.0, "type": "division", "sens": "10 nouvelles pour 1 ancienne(s)"}`
2. Ré-export du cache : `"$PY" scripts/preparer_historique_propre.py` (barres ≤ 23/10 ÷10 ;
   vérifier le cours de référence SNTS au BOC).
3. Migration `data/portfolio.json` (SNTS) : `quantity` ×10 ; `entry_price`, `dps`, `exit_price`,
   `entry_price_ref` ÷10.
4. Contrôle : `"$PY" -m src.main integrity` (0 problème) ; re-export `reversal_profiles` si prévu.
5. ⚠️ **NE PAS ajouter l'entrée AVANT le 26/10** : les barres du cache (base 32 000) seraient ÷10
   face à une API encore en base 32 000 → incohérence signalée à tort pendant 10 jours.
