# Architecture — organisation cible et plan de migration

**État :** lot 0 **terminé** le 09/10/2026. **Aucun fichier n'a encore été déplacé** : le lot 1
commence.
**Décisions du 09/10 :** modules du **métier en français**, plomberie en anglais ; domaine de
collecte nommé **`src/collecte/`**, `data/` réservé aux données (§3). Carte complète :
**41 modules sur 41** (§4).

---

## 1. Pourquoi ce chantier n'a pas été lancé directement

La restructuration demandée est **la bonne cible**. Mais trois mesures montrent qu'elle ne
peut pas être la première étape :

| Mesure | Valeur (avant migration) |
|---|---|
| Modules dans `src/` | **41** |
| Scripts | **86** |
| Tests | **35** |
| Chemins calculés à la main (`__file__`) | **100** |
| Imports relatifs | **143** |

Ces valeurs décrivent l'état **avant** le lot 0 : elles justifient l'ordre, ce ne sont pas les
chiffres du jour. Ne pas confondre les deux comptages de `__file__` qui circulent : **100** =
tous les usages du dépôt (105 aujourd'hui : 5 dans `src/`, 91 dans `scripts/`, 9 dans `tests/`) ;
**19** = le seul idiome de chemin de données, celui que traque `verifier_chemins.py`
(**0** depuis le lot 0).

**Le piège n'est pas le nombre, c'est le calcul de chemin.** Chaque module faisait :

```python
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
```

Ce calcul dépend de la **profondeur** du fichier. Déplacer `src/portfolio.py` vers
`src/portefeuille/positions.py` fait passer `parent.parent` de la **racine** à `src/` — et
**tous les chargements de données échouent en silence** : un `load()` qui ne trouve pas son
fichier renvoie une valeur par défaut, le programme continue avec des données vides.

**Aucun test de valeur ne détecte ça.** Le snapshot des constantes lit des valeurs, pas des
chemins. Une restructuration faite sans ce prérequis produirait un système **qui tourne mais
qui lit du vide** — le pire des états.

## 2. Prérequis — fait, migration terminée le 09/10

**`src/paths.py`** : une source unique pour tous les chemins. Chaque module écrit
`from .paths import DATA_DIR`, ce qui reste vrai **quelle que soit sa profondeur**. Le module
porte aussi les noms de fichiers (`REVERSAL_PROFILES`, `PROFIT_THRESHOLDS`, `SEUILS_JOURNAL`…)
et `chemin_data(nom)` — aucun nom de fichier n'a besoin d'être recopié ailleurs.

**`scripts/verifier_chemins.py`** : liste les chemins encore calculés à la main.

```
$ python scripts/verifier_chemins.py --strict
  src/     :   0 occurrence(s)
  scripts/ :   0 occurrence(s)
  tests/   :   0 occurrence(s)
  TOTAL    :   0
  → code de sortie 0
```

Migration faite : **22 modules de `src/`**, plus `tests/test_unification_definition.py` et
`scripts/sika_download_cotations.py`. `--strict` sort en code 1 dès qu'un chemin réapparaît :
le contrôle peut donc devenir un test de non-régression.

**Le contrôle avait lui-même un défaut — corrigé ici.** Il comptait le motif **cité dans une
docstring**, notamment celle de `scripts/migrer_chemins.py` qui documente l'idiome à remplacer :
`--strict` ne pouvait donc **jamais** revenir à zéro, le filet était insatisfiable. Il ignore
désormais le texte (docstrings, commentaires, messages) via `tokenize`, en ne comptant que les
littéraux qui **ouvrent** la ligne, et il ne dispense plus aucun fichier par exception — la
liste `EXCLUS` a disparu : un contrôle qui s'exempte lui-même ne prouve rien.

## 3. Avant/après sur la structure proposée

### Ce qui est juste

- **Séparation par domaine métier** — c'est ce qui manque le plus. Aujourd'hui `portfolio.py`
  (849 lignes) contient le calibrage, le modèle de position **et** la rédaction des alertes.
- **`docs/decisions/`** — existe déjà sous forme de `DECISION-*.md` à la racine de `docs/`.
  Les déplacer est trivial et rend la chronologie lisible.
- **`tests/regression/`** — correspond exactement à ce que fait `auditer_constantes.py`.
  Une catégorie explicite rend le filet de sécurité visible au lieu de le laisser implicite.
- **`data/market/` séparé de `data/portfolio/`** — utile : les données de marché sont
  **retéléchargeables**, les positions sont **irremplaçables**. Les confondre dans un même
  dossier invite à écraser les secondes en rafraîchissant les premières.

### Ce qui est tranché (09/10/2026)

**a) Français ou anglais pour les noms de modules ? → le métier en français, la plomberie en
anglais.**

Le projet était mixte : `regles.py`, `nettoyage_aberrantes.py`, `divisions_officielles.py` en
français ; `portfolio.py`, `report.py`, `backtest.py` en anglais ; `format_fr.py`,
`seuils_vente.py`, `regime_marche.py` mélangeaient. La structure proposée au départ était anglaise
(`rules.py`, `models.py`, `enums.py`) et aurait **renommé `regles.py`** — le catalogue qu'on vient
de créer, tester et documenter.

Décision : **`regles.py`, `seuils.py`, `marche.py`, `positions.py` côté métier ; `paths.py`,
`cache.py`, `http.py`, `cli.py` côté plomberie.** Conséquence importante : **aucun module existant
n'est renommé** — les lots 1 à 5 sont des déplacements et des découpages, pas des renommages.
Les noms de dossier suivent la même règle : `domaine/`, `collecte/`, `analyse/`, `strategie/`,
`portefeuille/`, `alertes/` (métier) ; `cli/`, `infrastructure/` (plomberie) ; `calibration/` et
`backtest/` sont des termes techniques employés tels quels.

**b) `src/data/` (code) contre `data/` (données) ? → `src/collecte/`.**

`from src.data import ...` aurait été confondu avec `DATA_DIR` par tout le monde, y compris dans
six mois. Le domaine de code s'appelle **`collecte/`** ; **`data/` reste aux données seules**.

## 4. Carte de migration — 41 modules vers 10 domaines (9 métier + la plomberie)

| Domaine cible | Modules actuels | Nb |
|---|---|---|
| **`domaine/`** — règles et modèles | `regles.py` · `taxation.py` · `models.py` (cotation, barre OHLCV, analyse — et **modèle de position** à extraire de `portfolio.py`) | 3 |
| **`collecte/`** | `bsapi.py` · `live.py` · `dividend_history.py` · `backtest.py` (chargement) · `cache_integrity.py` · `fundamentals.py` · `dividends.py` · `divisions_officielles.py` · `nettoyage_aberrantes.py` | 9 |
| **`analyse/`** | `fondamentaux_historiques.py` · `screener.py` · `screening.py` · `bonds.py` · `boc.py` · `news.py` · `radar.py` | 7 |
| **`strategie/`** | `strategie_leo.py` · `noyau_check.py` · `orders.py` · `speculation.py` · `spec_profiles.py` · `paliers_sortie.py` · `spec_fiche.py` · `spec_veille.py` | 8 |
| **`calibration/`** | `seuils_vente.py` · `regime_marche.py` | 2 |
| **`portefeuille/`** | `portfolio.py` (positions, cash) · `alerts.py` · `report.py` · `format_fr.py` | 4 |
| **`alertes/`** | `notify.py` (transport Telegram, utilisé par `alerts` et `report`) + extrait de `portfolio.py` : `_profit_info_alert`, `_msg_regime`, `reinforcement_messages` | 1 + extrait |
| **`backtest/`** | `backtest_noyau.py` · `challenge_validateur.py` · `challenge_schema.py` · `challenge_indicateurs.py` | 4 |
| **`cli/`** | `main.py` (**1 310 lignes, 25 commandes**) · `ajustement.py` | 2 |
| **`infrastructure/`** | `paths.py` (puis la plomberie : `cache.py`, `http.py`) | 1 |

**Total : 41 / 41** — chaque module de `src/` a un domaine, aucun n'est compté deux fois
(vérifié par script, pas à l'œil).

Corrections apportées à la première version de cette carte :

- **8 modules n'avaient aucun domaine** : `live.py` et `dividend_history.py` (→ `collecte/`),
  `screening.py` et `radar.py` (→ `analyse/`), `orders.py`, `spec_fiche.py`, `spec_veille.py`
  (→ `strategie/`), `notify.py` (→ `alertes/`).
- **2 modules cités n'existent pas** dans `src/` : `richbourse.py` et `sika.py`. Les collecteurs
  correspondants vivent dans `scripts/` (ex. `sika_download_cotations.py`) et écrivent dans `data/`.
- **`models.py` existe déjà** (cotation, barre OHLCV, analyse) : c'est lui qui accueille le
  modèle de position extrait de `portfolio.py` — il n'y a rien à créer.
- Le compte était faux : **9 domaines métier** (et non 8) **+ `infrastructure/`** pour la
  plomberie — `alertes/` est distinct de `portefeuille/`.
- **`screener.py` et `screening.py` se recouvrent** (indicateurs techniques, RSI/EMA/momentum) :
  à fusionner au lot 3, sinon la duplication de règles revient par la porte de derrière.

**La carte reste indicative** : plusieurs modules sont à **découper**, pas seulement à déplacer
(`portfolio.py`, `main.py`, `backtest.py`).

## 5. Ordre d'exécution — six étapes, chacune vérifiable seule

**Règle : une étape = un commit = un `pytest` complet + `--comparer` identique.**

| Lot | Action | Vérification | État |
|---|---|---|---|
| **0** | Migrer les 19 chemins vers `src/paths.py` | `verifier_chemins.py --strict` → 0 | ✅ **fait le 09/10** |
| **1** | Créer les dossiers décidés (§4) + `__init__.py` | `pytest` inchangé | à faire |
| **2** | Déplacer les modules **feuilles** (aucun dépendant interne) : `format_fr`, `paths`, `models` (`enums.py`, cité dans la première version, n'existe pas) | `pytest` + `--comparer` | à faire |
| **3** | Déplacer `calibration/`, `analyse/`, `backtest/` | idem | à faire |
| **4** | Déplacer `collecte/`, `strategie/` | idem | à faire |
| **5** | **Découper** `portfolio.py` (calibrage → `calibration/`, alertes → `alertes/`, modèle → `domaine/`) puis `main.py` | idem + relecture | à faire |

**Le lot 0 était obligatoire avant tout déplacement** — c'est lui qui rend les autres sûrs.

**Le lot 1 fige les noms de dossiers** : c'est pour ça que les deux questions de §3 devaient être
tranchées avant lui. Elles le sont (09/10) — il n'y a plus d'attente.

**Le lot 5 est un découpage, pas un déplacement** : c'est le plus risqué, et il vient en
dernier, quand l'arborescence est stable.

## 6. Non-régression — les trois filets

| Filet | Ce qu'il attrape | Après le lot 0 (09/10) |
|---|---|---|
| **267 tests** | le comportement | ✅ 267 verts |
| **`auditer_constantes.py --comparer`** | toute valeur effective modifiée | ✅ 189 valeurs identiques au snapshot |
| **`verifier_chemins.py --strict`** | tout chemin recalculé à la main | ✅ 0 |

Les trois doivent être **identiques** après chaque lot. Un écart sur le deuxième est une
décision ; un écart sur les deux autres est une régression.

## 7. Ce que la restructuration ne réglera PAS

- **`main.py`** : 25 commandes dans un fichier de 1 310 lignes. Le déplacer dans `cli/` le
  rend plus lisible **sans le rendre plus court** — le découpage est un travail distinct.
- **La performance de la stratégie** : aucun gain. C'est de l'hygiène — nécessaire (un
  chiffre faux coûte de l'argent), pas suffisante.

## 8. Fichiers racine

| Fichier | État |
|---|---|
| `pyproject.toml` | ✅ existe — config pytest : `pythonpath = ["."]`, `testpaths = ["tests"]` |
| `README.md` | ✅ existe (20 Ko) |
| `tests/conftest.py` | ✅ existe (fixture partagée `make_bars`) |
| `CHANGELOG.md` | à créer |
| CI | à créer — doit lancer les **trois** filets : `pytest`, `verifier_chemins.py --strict`, `auditer_constantes.py --comparer` |
| `LICENSE` | à créer si publication |

## 9. Versionnage — état après le tri du 09/10

Le dépôt était **très en retard sur le disque** : 165 fichiers suivis contre plus de 100
**non suivis**, dont des **modules entiers de `src/`** (`regles.py`, `seuils_vente.py`,
`strategie_leo.py`, `paliers_sortie.py`, `format_fr.py`, `paths.py`…), la moitié des `scripts/`
d'analyse, 9 tests et 6 documents de `docs/`. Le prérequis du lot 0 (`paths.py`) n'était même pas
committé : un `git clean` l'aurait effacé.

Tri effectué le 09/10 : commits séparés par famille (unification du retournement, lot 0 chemins,
puis modules `src/`, tests, scripts, documents, données), et `.gitignore` complété pour les
artefacts — `data/*.pkl` (~7 Mo chacun), les pages HTML brutes des collecteurs, les sauvegardes
locales `data/*.bak-avant-*`.

**Règle pour la suite :** `scripts/git_backup.py` fait **`git add -A`** chaque dimanche 09h. Un
arbre non trié le jour du cron part donc dans un **commit fourre-tout** — trier les familles
avant le dimanche, et garder le réflexe « un lot = un commit ».

### ⚠ Sauvegarde distante en échec depuis le 05/10 — cause à trancher

`origin` = `https://github.com/egnonisse/bridge-bank` → **« Repository not found »**, sans
redirection de renommage. **Ce qui est établi :**

- le run du cron du 05/10 a échoué : `⚠️ Backup Bridge Bank ÉCHOUÉ : remote: Repository not found.` ;
- dernier commit présent sur `origin/main` : `4d1f21d` (29/09) → les **12 commits suivants ne sont
  sauvegardés qu'en local** ;
- le credential git stocké sur cette machine appartient au compte **`aiwatch-ci`**, pas à
  `egnonisse` (`git credential fill` → `username=aiwatch-ci`).

**Deux causes restent possibles, et rien ici ne les sépare :** GitHub répond *exactement* la même
chose pour un dépôt privé auquel le compte n'a pas accès que pour un dépôt supprimé.

⚠️ **Fausse piste écartée** (erreur de raisonnement commise puis corrigée le 09/10) :
`egnonisse/PharmaScan` répond sans aucun credential — ce dépôt est **public**, il ne prouve donc
rien sur l'authentification. En tirer « les identifiants ne sont pas en cause » était abusif :
le seul credential disponible est celui d'un **autre compte** que le propriétaire du dépôt.

**À trancher par LEO** : le dépôt existe-t-il toujours sous `egnonisse/bridge-bank` ?

- **oui** → ajouter `aiwatch-ci` comme collaborateur (*write*) : le credential déjà présent suffit,
  ou s'authentifier en tant qu'`egnonisse` ;
- **non** → le recréer (privé) et pousser.

Filet en attendant : `D:/PROJETS/bridge-bank-2026-10-09.bundle` — histoire complète vérifiée
(`git bundle verify` : *complete history*), ~27 Mo, clonable pour restaurer.
