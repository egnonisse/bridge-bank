# Décision — Tests des moteurs de preuve + non-régression des chiffres publiés (12/10/2026)

**Origine :** passation `audit/passation_vers_session_suivante.md` §3 — « les chiffres qui fondent
les décisions sont produits par le code le moins couvert du projet ». Priorités 1 et 2 : couvrir
`strategie_leo.py` (0 %), `paliers_sortie.py` (0 %), `backtest_noyau.py` (28 %),
`divisions_officielles.py` (0 %), et automatiser la re-vérification des chiffres publiés.

**Règles suivies (§4 de la passation) :** `data/` gelé avant toute exécution (empreinte SHA-256 de
111 fichiers) · provenance de chaque chiffre · aucun `fail_under` · aucune règle métier modifiée ·
un contrôle qui ne peut pas échouer ne prouve rien (cassé volontairement, voir §3).

## 1. Couverture des moteurs de preuve — mesurée

| Module | Avant | Après | Tests ajoutés |
|---|---|---|---|
| `src/strategie/strategie_leo.py` | **0 %** | **94 %** | `tests/test_strategie_leo.py` (21) |
| `src/strategie/paliers_sortie.py` | **0 %** | **96 %** | `tests/test_paliers_sortie.py` (22) |
| `src/backtesting/backtest_noyau.py` | 28 % | **87 %** | `tests/test_backtest_noyau.py` (15) |
| `src/collecte/divisions_officielles.py` | **0 %** | **84 %** | `tests/test_divisions_officielles.py` (15) |

Suite complète : **452 passed** en 2 min 23 (avant : 379 ; +73 tests). Aucun `fail_under` ajouté.

## 2. Dispositif de non-régression des chiffres publiés

Trois pièces, chaînées :

1. **`audit/preuves/chiffres_reference.json`** — les valeurs gelées (re-mesurées le 12/10), chacune
   avec SON script et SA sortie. Toute re-mesure doit y être actée, jamais silencieuse.
2. **`scripts/verifier_chiffres_publies.py`** — rejoue les 6 scripts de mesure EN SÉRIE (~15 min),
   compare aux valeurs de référence et sort en 1 à tout écart. **Version automatisée de la
   vérification manuelle du 12/10.** Écrit un rapport daté dans `audit/preuves/`.
3. **`tests/test_preuves_publies.py`** — 7 tests rapides (dans la suite standard) qui verrouillent
   la chaîne : référence → sorties versionnées → documents (invariant B1 qui cite « 45,4 pt »,
   rapport et doc de vérification qui citent les mêmes chiffres) ; + 1 test **marqué `preuve`**
   (le rejeu complet), **exclu par défaut** (`addopts = -m 'not preuve'` dans `pyproject.toml`) —
   la suite standard reste à ~2,5 min, la CI inchangée. Le lancer : `pytest -m preuve -s`.

## 3. Preuves d'exécution (les contrôles échouent quand ils doivent échouer)

- **Casse volontaire de la sortie** : `observations` 43 227 → 99 999 dans
  `data/test_entree_progressive.json` → le test rapide **échoue** ; restauration → il repasse. ✓
- **Casse volontaire de la référence** : le rejeu complet **détecte et sort en code 1** —
  et il a signalé **DEUX écarts, dont un défaut réel de son propre parser** : la ligne
  « A noyau passif » existe dans DEUX tableaux (RÉSULTATS puis NORMALISATION) et le parser
  lisait le revenu/an (10,76 %) au lieu de l'exposition (94,9 %) ; les écarts C/D étaient
  sauvés par l'ordre du texte, pas par le code. **Corrigé** (lecture du seul bloc
  NORMALISATION) puis validé sur la sortie réelle : 232,2 · 94,9 · +26,2 · −45,4 = référence
  exacte. Preuve du test de casse : `audit/preuves/verification_chiffres_2026-10-12_test_de_casse.txt`.
  C'est la démonstration que le dispositif attrape de VRAIES erreurs, pas seulement celles
  qu'on a semées.
- **Rejeu sur l'état sain** : toutes les valeurs rejouées correspondent à la référence → code 0
  (`audit/preuves/verification_chiffres_2026-10-12.txt`) ; `git diff data/` VIDE après le rejeu
  (les scripts réécrivent leurs sorties : mêmes valeurs = preuve de non-régression). ✓
- Suite complète lancée **après gel de `data/`** : vérification d'intégrité à l'issue (0 modifié).

## 4. Constats découverts EN ÉCRIVANT les tests (à remonter, aucune correction sans décision de LEO)

1. **`backtest_noyau` ne compte AUCUN frais** : `simuler_position` fait `actions = capital / cours`
   — pas de 1,4 % à l'achat, pas de minimum de 1 000 F sur les réinvestissements. Les écarts
   RELATIFS noyau vs panier aléatoire restent valables (mêmes hypothèses des deux côtés), mais les
   rendements ABSOLUS publiés de ce module sont optimistes. Non corrigé : décision de LEO requise.
2. **`strategie_leo` — renfort quasi inatteignable par défaut** : les `nb_tranches` achats
   consomment exactement `budget_max_ligne` (tranche = plafond / nb_tranches), donc « reste » vaut 0
   et la condition du renfort (`reste > tranche/2` ET cash > `tranche/2`) n'est réunie que si les
   tranches ont été RABOTÉES par le cash (cas réel : cash contraint, dividendes/ventes qui
   rechargent). Comportement du plafond, pas un bug — verrouillé par tests (dont un scénario de
   déclenchement réel).
3. **`simuler_paliers` sans garde d'entrée** : une liste de barres vide lève `IndexError` (les
   appelants filtrent ; verrouillé en l'état, à trancher si un nouvel appelant arrive).
4. **`simuler_paliers` — un seul palier par séance** : un cours qui saute à +36 % ne déclenche que
   le +20 % ce jour-là ; le +35 % attend une séance suivante au-dessus du seuil. Verrouillé tel quel.
5. **Rapport 28 ans §2.1** : son tableau d'attribution (valeurs du 08/10) n'avait PAS d'encadré de
   provenance — la règle §4 l'exige. **Corrigé :** encadré « enregistré le 08/10 / re-mesuré le
   12/10 » avec renvoi aux preuves, valeurs conservées (jamais de réécriture silencieuse).

## 5. Fichiers

- Tests : `tests/test_strategie_leo.py`, `test_paliers_sortie.py`, `test_backtest_noyau.py`,
  `test_divisions_officielles.py`, `test_preuves_publiees.py`
- Dispositif : `audit/preuves/chiffres_reference.json`, `scripts/verifier_chiffres_publies.py`
- Config : `pyproject.toml` (marqueur `preuve` + exclusion par défaut)
- Documents : `docs/RAPPORT-VALIDATION-28-ANS.md` (encadré §2.1)
