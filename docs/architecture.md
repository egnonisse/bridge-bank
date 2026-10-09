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

**`src/infrastructure/paths.py`** : une source unique pour tous les chemins. Chaque module écrit
`from .infrastructure.paths import DATA_DIR`, ce qui reste vrai **quelle que soit sa profondeur**.
Le module porte aussi les noms de fichiers (`REVERSAL_PROFILES`, `PROFIT_THRESHOLDS`,
`SEUILS_JOURNAL`…) et `chemin_data(nom)` — aucun nom de fichier n'a besoin d'être recopié ailleurs.

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
| **`collecte/`** | `bsapi.py` · `live.py` · `dividend_history.py` · `backtest.py` (chargement) · `cache_integrity.py` · `fundamentals.py` · `dividends.py` · `divisions_officielles.py` · `nettoyage_aberrantes.py` | 9 | ✅ lot 4 |
| **`analyse/`** | `fondamentaux_historiques.py` · `screener.py` · `screening.py` · `bonds.py` · `boc.py` · `news.py` · `radar.py` | 7 | ✅ lot 3 |
| **`strategie/`** | `strategie_leo.py` · `noyau_check.py` · `orders.py` · `speculation.py` · `spec_profiles.py` · `paliers_sortie.py` · `spec_fiche.py` · `spec_veille.py` | 8 | ✅ lot 4 |
| **`calibration/`** | `seuils_vente.py` · `regime_marche.py` · `schema_seuils.py` (**42e module**, né après la carte) | 3 | ✅ lot 3 |
| **`portefeuille/`** | `portfolio.py` (positions, cash) · `alerts.py` · `report.py` · `format_fr.py` | 4 |
| **`alertes/`** | `notify.py` (transport Telegram, utilisé par `alerts` et `report`) + extrait de `portfolio.py` : `_profit_info_alert`, `_msg_regime`, `reinforcement_messages` | 1 + extrait |
| **`backtesting/`** | `backtest_noyau.py` · `challenge_validateur.py` · `challenge_schema.py` · `challenge_indicateurs.py` | 4 | ✅ lot 3 |
| **`cli/`** | `main.py` (**1 310 lignes, 25 commandes**) · `ajustement.py` | 2 |
| **`infrastructure/`** | `paths.py` (puis la plomberie : `cache.py`, `http.py`) | 1 |

**Total : 41 / 41** — chaque module de `src/` a un domaine, aucun n'est compté deux fois
(vérifié par script, pas à l'œil).

**+ 1 module né APRÈS la carte** : `schema_seuils.py` (durcissement des seuils du 09/10) →
`calibration/`. **Total réel : 42.** La carte avait été établie sur l'état du 09/10 au matin ; le
durcissement des seuils du même jour a ajouté un module, que le lot 3 a rattaché en même temps que
`seuils_vente` (c'est son vocabulaire).

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
- **Aucun paquet ne doit porter le nom d'un module existant** : Python résout le **dossier**
  d'abord, donc `src/backtest/` masquait `src/backtest.py`. Mesuré au lot 1 : 7 erreurs de
  collecte en test, et le contrôle des constantes en échec (il lit en important les modules).
  D'où `backtesting/` — et c'est la seule collision de la carte.

**La carte reste indicative** : plusieurs modules sont à **découper**, pas seulement à déplacer
(`portfolio.py`, `main.py`, `backtest.py`).

## 5. Ordre d'exécution — six étapes, chacune vérifiable seule

**Règle : une étape = un commit = un `pytest` complet + `--comparer` identique.**

| Lot | Action | Vérification | État |
|---|---|---|---|
| **0** | Migrer les 19 chemins vers `src/paths.py` | `verifier_chemins.py --strict` → 0 | ✅ **fait le 09/10** |
| **1** | Créer les dossiers décidés (§4) + `__init__.py` | `pytest` inchangé | ✅ **fait le 09/10** — 10 paquets, aucun fichier déplacé, 309 tests inchangés |
| **2** | Déplacer les modules **feuilles** (aucun dépendant interne) : `format_fr`, `paths`, `models` (`enums.py`, cité dans la première version, n'existe pas) | `pytest` + `--comparer` | ✅ **fait le 09/10** — 3 modules déplacés, 35 fichiers d'imports réécrits, 309 tests, snapshot 202 → 202 (16 clés renommées, **0 valeur modifiée**) |
| **3** | Déplacer `calibration/`, `analyse/`, `backtesting/` | idem | ✅ **fait le 09/10** — 14 modules, 108 imports recalculés dans 53 fichiers + 16 cibles de `monkeypatch` (voir ci-dessous), 309 tests, snapshot 202 → 202 (**61 clés renommées, 0 valeur modifiée**) |
| **4** | Déplacer `collecte/`, `strategie/` | idem | ✅ **fait le 09/10** — 17 modules, 149 imports recalculés dans 67 fichiers + 37 cibles de `monkeypatch`, 333 tests, snapshot 210 → 210 (**60 clés renommées, 0 valeur modifiée**) |
| **5** | **Découper** `portfolio.py` (calibrage → `calibration/`, alertes → `alertes/`, modèle → `domaine/`) puis `main.py` | idem + relecture | à faire — **⚠ déplacer `regles.py` et `taxation.py` oblige à corriger `MODULE_REGLES`/`MODULE_TAXATION` dans `src/infrastructure/paths.py`** (l'empreinte des alertes les surveille ; `tests/test_empreinte.py` échoue si elles pointent dans le vide). **Étape 5a (référence de sorties) ✅ faite le 09/10** — voir ci-dessous ; le découpage lui-même n'est pas commencé |

**Le lot 0 était obligatoire avant tout déplacement** — c'est lui qui rend les autres sûrs.

**Le lot 1 a figé les noms de dossiers** (09/10) — les deux questions de §3 étaient bien à
trancher AVANT lui. Deux enseignements du lot, tous les deux mesurés :

1. le dossier de simulation s'appelle **`backtesting/`** : un paquet `backtest/` **masquait**
   `src/backtest.py` (7 erreurs de collecte en test, contrôle des constantes en échec) ;
2. l'auditeur des constantes marche désormais **dans les sous-dossiers** (`SRC.rglob` + noms
   pointés) — sans quoi il aurait cessé de surveiller chaque module déplacé, sans le dire.

**Le lot 2 a déplacé les trois modules feuilles** (09/10) : `paths.py` → `infrastructure/`,
`models.py` → `domaine/`, `format_fr.py` → `portefeuille/`. Trois enseignements :

1. **Le lot 0 a payé exactement comme prévu** : un seul fichier à corriger pour le calcul de
   chemin (`paths.py` lui-même, passé de `parent.parent` à `parents[2]`), et **zéro** module à
   reprendre côté données — les 22 modules qui l'importent continuent de lire le bon dossier.
2. **Un cache `pickle` porte le CHEMIN DE CLASSE de ses objets.** `data/history_clean.pkl` (et
   les deux autres) contenaient des `src.models.HistoryBar` : les déballer après le déplacement
   levait `ModuleNotFoundError: No module named 'src.models'` — un test est tombé pour cette
   raison exacte. Les trois caches ont été **convertis sur place** (valeurs comparées avant/après
   champ par champ : identiques), plutôt que d'ajouter un module de compatibilité qui aurait
   survécu des années.
3. **La CI ne peut PAS voir cette panne** : le cache est ignoré par git et le test qui l'exerce
   est protégé par `skipif` quand il est absent. Conséquence : le contrôle côté serveur peut être
   vert alors qu'une machine de travail est cassée. Piste durable à trancher : stocker des
   **données simples** (dicts) dans le cache au lieu d'instances de classes — un cache ne devrait
   pas dépendre de l'emplacement d'une classe.

**Le lot 3 a déplacé `calibration/`, `analyse/` et `backtesting/`** (09/10) : 14 modules, 108
imports recalculés dans 53 fichiers, 309 tests, snapshot 202 → 202 (61 clés renommées, 0 valeur
modifiée). Quatre enseignements, dont deux payés par des tests rouges :

1. **Il y a DEUX populations à recalculer, pas une** : les importeurs des modules déplacés **et
   les modules déplacés EUX-MÊMES** — ces derniers importent aussi des modules qui ne bougent pas
   (`from .regles import X` visait `src.regles` ; depuis `src/analyse/`, la même ligne viserait
   `src.analyse.regles`). Traiter la seconde population est ce qui sépare « ça importe » de « ça
   importe le bon fichier ».
2. **Un import sans point initial n'est JAMAIS relatif.** Le premier essai à blanc a proposé
   `from ..datetime import date` dans les modules déplacés : sans garde-fou, une quarantaine
   d'imports de bibliothèque standard auraient été corrompus. *L'essai à blanc n'est pas une
   précaution, c'est le contrôle qui a trouvé le bug.*
3. **Les cibles sous forme de CHAÎNE ne sont pas des `import`** : les tests patchaient
   `monkeypatch.setattr("src.screener.X", …)`, qui importe la cible depuis la chaîne. Tous les
   `import` étaient justes, et **13 tests sont tombés** pour cette seule raison. Un déplacement
   doit traiter les deux formes.
4. **Le filet des constantes a suivi tout seul** (`rglob` + noms pointés, acquis au lot 1) : il a
   renommé les 61 clés sans intervention. En revanche le script de preuve écrit pour l'occasion
   était faux (clé reconstruite sans le nom du module, donc « 0 paire » au lieu de 61) — un
   contrôle qu'on écrit à la main doit être vérifié lui aussi, sinon il rassure à tort.

**Découverte de périmètre** : la carte annonçait 41 modules, il y en avait **42** —
`schema_seuils.py` était né le jour même, après la rédaction de la carte (§4 corrigé).

Le lot 4 peut commencer : `collecte/` (9 modules) et `strategie/` (8 modules).

**Le lot 4 a déplacé `collecte/` et `strategie/`** (09/10) : 17 modules, 149 imports recalculés
dans 67 fichiers, 37 cibles de `monkeypatch` corrigées, 333 tests, snapshot 210 → 210 (60 clés
renommées, 0 valeur modifiée). Deux enseignements :

1. **L'outil de déplacement est devenu GÉNÉRIQUE** (la carte du lot est un fichier
   `{module: domaine}` à côté de lui) : les lots 3, 4 et 5 utilisent le même outil, seule la carte
   change. Un déplacement de 17 modules n'a plus rien de nouveau à apprendre — c'est ce qui rend
   la progression par lots tenable.
2. **Un contrôle dont le résultat doit être interprété est un mauvais contrôle.** Le repérage des
   « imports restants vers les anciens emplacements » a listé des formes légitimes de MÊME domaine
   (`src/strategie/spec_veille.py → from .spec_fiche import …`) : la même ligne peut être correcte
   ou non selon le domaine. La vérification qui ne s'interprète pas est : **tous les modules du
   paquet s'importent** (`pkgutil` + `import_module`, 54 modules, 0 échec) puis la suite complète.
3. Le noyau `regles.py` / `taxation.py` **reste à la racine** volontairement : l'empreinte des
   alertes les surveille par des constantes déclarées (§ lot 5).

Le lot 5 peut commencer : découper `portfolio.py` (le risque n'est plus le déplacement mais le
DÉCOUPAGE) — et il exige une comparaison des SORTIES avant/après, pas seulement des constantes.

**Le lot 5 est un découpage, pas un déplacement** : c'est le plus risqué, et il vient en
dernier, quand l'arborescence est stable.

### Étape 5a — la référence de sorties (faite le 09/10, AVANT tout découpage)

Un déplacement se vérifie par les constantes et les tests. Un **découpage**, non : les mêmes
valeurs peuvent produire des messages différents si une fonction est recopiée de travers. D'où une
troisième nature de filet, demandée explicitement : **comparer les SORTIES avant/après**.

- `scripts/capturer_sorties.py` fige **398 sorties réelles** de `portfolio.py` : les messages des
  5 constructeurs d'alertes, `status_level`, les lignes « 📜 LES AUTRES FOIS », les 4 niveaux du
  verrou de concentration × 3 régimes de marché, le modèle de position, `record_dividend`, le
  cooldown, les formats — et **8 sorties de commandes** (`portf status/check/open/dividend/close`,
  `sustain`) plus le résumé quotidien.
- `tests/fixtures/sorties_reference.json` porte la référence (versionnée) ;
  `tests/test_sorties_invariables.py` recalcule et **nomme** les sorties changées.
- **Reproductible à l'octet** : horloge figée, seuils et profils de retournement en fixtures. Une
  référence qui casse quand LEO change un seuil ne serait pas une référence de code.
- **Le contrôle a été testé** : une phrase modifiée dans `portfolio.py` fait échouer le filet en
  signalant 6 sorties ; puis tout repasse. Un filet qui ne peut pas échouer ne prouve rien.
- Périmètre vérifié dans le code, pas supposé : sur les 6 commandes candidates, **seules `portf` et
  `sustain` traversent `portfolio.py`** (`report`, `filet` et `limits` passent à côté).

**Le découpage proprement dit reste à faire** : modèle → `domaine/`, calibrage → `calibration/`,
messages → `alertes/`, positions/cash → `portefeuille/`, en commits séparés, la référence verte à
chaque étape.

## 6. Non-régression — les quatre filets

| Filet | Ce qu'il attrape | Valeur de référence (09/10, après le lot 4 + 5a) |
|---|---|---|
| **les tests** | le comportement | ✅ **336 verts** |
| **`auditer_constantes.py --comparer`** | toute valeur effective modifiée | ✅ **210 valeurs** identiques au snapshot |
| **`verifier_chemins.py --strict`** | tout chemin recalculé à la main | ✅ **0** |
| **`test_sorties_invariables.py`** | toute SORTIE modifiée (message, niveau, texte) | ✅ **398 sorties** identiques à la référence |

Les quatre doivent être **identiques** après chaque lot. Un écart sur les deux derniers est une
décision (à relire et à documenter) ; un écart sur les deux premiers est une régression.

Le quatrième n'existait pas dans le plan d'origine : il a été ajouté pour le lot 5, parce qu'un
**découpage** peut changer un message sans changer une seule valeur. Les trois premiers
n'auraient rien vu.

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
| CI | ✅ **créée le 09/10** — `.github/workflows/ci.yml` : chemins, configuration, constantes, `pytest`. Python 3.11, `actions/checkout@v7`. Premier run vert : `37877120841` |
| Blocage de la fusion | ⚠️ **pas côté serveur** : GitHub refuse protection de branche et rulesets sur un dépôt privé en compte gratuit (403). **Crochet local `.githooks/pre-push`** à la place — voir `docs/DECISION-2026-10-09-ci-et-controle-des-constantes.md` §3. Activer par clone : `git config core.hooksPath .githooks` |
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

### ✅ Sauvegarde distante rétablie (09/10/2026) — sauf pour le cron

**Cause réelle, en deux temps :**

1. **Mauvais compte** : le credential git par défaut de ce poste appartient à `aiwatch-ci`, qui n'a
   aucun droit sur ce dépôt. Tant que le dépôt était **privé**, GitHub masquait tout derrière
   « Repository not found » — indiscernable d'une suppression, d'où un premier diagnostic erroné.
2. **« Your repository is disabled »** au premier essai, juste après la bascule de visibilité :
   **transitoire**. L'API montrait déjà `disabled = false`, `private = true`,
   `permissions.push = true`, et le second essai a poussé sans erreur. Aucun des 13 dépôts du
   compte n'est désactivé.

**Fait le 09/10 :**

- dépôt repassé **en privé** — le passage en public exposait les avis courtier et rendait
  indexables les positions, le cash et les snapshots ;
- `git push` avec le jeton **egnonisse** du `.env` Hermes (fine-grained, expiration 07/01/2027) :
  `4d1f21d..5349d09 main -> main` — vérifié, `origin/main` = `HEAD` ;
- les **13 commits locaux** (30/09 → 09/10) sont enfin sauvegardés à distance.

**Règle de diagnostic, à réutiliser :** GitHub répond la *même* chose pour un dépôt privé
inaccessible et pour un dépôt supprimé. Ne jamais conclure « dépôt supprimé » — ni « identifiants
valides » — sans savoir **quel compte** s'authentifie :

```bash
printf 'protocol=https\nhost=github.com\n\n' | git credential fill | grep '^username='
```

Un témoin « ça marche ailleurs » n'est valable que s'il est **privé** et testé **sans** credential
(`git -c credential.helper= ls-remote <url>`) : un dépôt public répond sans authentification et ne
prouve rien.

**Reste à régler — le cron :** `git_backup.py` pousse avec le credential **par défaut** du poste,
toujours celui d'`aiwatch-ci` → `BridgeBank backup git hebdo` **échouera encore dimanche 09h**.
Trois voies :

- ajouter `aiwatch-ci` en collaborateur *write* sur le dépôt — le credential déjà stocké suffit ;
- enregistrer le jeton `egnonisse` dans le gestionnaire de credentials Windows (⚠️ il remplace
  alors celui d'`aiwatch-ci` pour tout `github.com` sur ce poste) ;
- faire lire le jeton du `.env` par `git_backup.py` (auto-contenu, mais couple le projet à un
  fichier Hermes).

**À trancher avant dimanche** — c'est la cause du prochain échec.

Filet conservé par prudence : `D:/PROJETS/bridge-bank-2026-10-09.bundle` (histoire complète
vérifiée, ~27 Mo) — désormais redondant avec le distant.
