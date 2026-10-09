# Décision — intégration continue et fiabilité des filets

**Date :** 9 octobre 2026
**Statut :** CI en place et **verte sur GitHub** — quatre filets à chaque poussée
**Origine :** demande LEO du 09/10/2026 — « automatiser les contrôles avec la CI »
**Portée :** `.github/workflows/ci.yml` (nouveau), `requirements.txt`, `requirements-dev.txt`,
`scripts/verifier_configuration.py` (nouveau), `scripts/auditer_constantes.py`,
`data/constantes_snapshot.json`

---

## 1. Ce que la CI exécute

À chaque poussée sur `main`, à chaque proposition de fusion, et à la demande — dans l'ordre
du moins coûteux au plus coûteux (le retour le plus rapide d'abord) :

| # | Étape | Ce qu'elle attrape |
|---|---|---|
| 1 | `scripts/verifier_chemins.py --strict` | un chemin de données recalculé à la main (le prérequis au déplacement de fichiers) |
| 2 | `scripts/verifier_configuration.py` | seuils non conformes, instantané absent, `config.yaml` cassé, **secret versionné** |
| 3 | `scripts/auditer_constantes.py --comparer` | toute valeur effective de constante qui a bougé |
| 4 | `pytest -q` | le comportement (309 tests) |

**Python 3.11** — la version qui fait tourner le système et les tests en local : une CI sur une
autre version découvrirait des pannes qui n'existent pas en production.
`actions/checkout@v7` et `actions/setup-python@v7` (majeures en cours au 09/10), `cache: pip`,
une seule exécution par branche, `timeout-minutes: 15`.

**Première exécution vérifiée** : run [37877120841](https://github.com/egnonisse/bridge-bank/actions/runs/37877120841)
sur le commit `b6691b9` — `completed/success`, les quatre étapes vertes.

## 2. Deux défauts trouvés en rendant les filets portables

**a) Le filet des constantes annonçait une couverture qu'il n'avait pas.**

`lire_valeur_effective()` confondait « import impossible » et « valeur `None` », et **les deux**
usages sautaient la ligne (`if courante is None: continue`). Mesure : sur un interpréteur sans
les dépendances, le contrôle affichait

```
OK — 189 valeurs effectives identiques au snapshot
```

alors que **109 d'entre elles n'étaient même pas lues** (`ModuleNotFoundError: urllib3`). Un
filet qui se raccourcit en silence est pire qu'un filet absent : il rassure.

Correction : une sentinelle `ILLISIBLE` distincte de `None`. Le contrôle **échoue** en nommant
la cause et affiche la couverture réelle (`le controle n'a verifie que X/Y valeurs`), et un
instantané **partiel ne peut plus être écrit** — sinon la comparaison suivante porterait sur ce
qui restait lisible, et annoncerait « OK ».

**b) L'instantané n'était pas portable.**

Quatre constantes stockaient le chemin du dossier projet en clair (`<Path Bridge Bank>`) : sur
toute autre machine — clone, CI — la comparaison signalait un écart qui n'existe pas. Un faux
écart est le meilleur moyen d'apprendre à ignorer une alerte. `src/paths.py::RACINE` est
désormais normalisé (`<Path .>`).

Instantané régénéré : **202 valeurs**. 22 entrées disparues = vestiges d'avant le lot 0
(`RACINE` est maintenant importé de `src/paths.py`), 35 ajoutées (`src.paths`,
`src.schema_seuils`, `src.seuils_vente`). **Aucune valeur existante modifiée.**

**c) `requirements.txt` était incomplet** — la CI aurait échoué dessus : `pymupdf` (importé par
`src/boc.py`) et `urllib3` (importé par `bsapi`, `dividend_history`, `fondamentaux_historiques`)
n'étaient pas déclarés.

## 3. Blocage de la fusion : impossible sur un dépôt privé en compte gratuit

Demandé, testé, refusé par GitHub :

```
PUT /repos/egnonisse/bridge-bank/branches/main/protection
→ 403 « Upgrade to GitHub Pro or make this repository public to enable this feature »
GET /repos/egnonisse/bridge-bank/rulesets
→ 403 (même message)
```

Plan du compte : **free**. Les deux mécanismes de blocage côté serveur (protection de branche
*et* rulesets) sont donc hors de portée sans payer.

**Décision du 09/10 : crochet git `pre-push` local** (gratuit). Il bloque la poussée depuis ce
poste quand un filet rapide est rouge — là où le travail se fait réellement.

`.githooks/pre-push` exécute, en quelques secondes :

| Contrôle | Ce qu'il bloque |
|---|---|
| `verifier_chemins.py --strict` | un chemin de données recalculé à la main |
| `verifier_configuration.py` | seuils non conformes, secret versionné, `config.yaml` cassé |
| `auditer_constantes.py --comparer` | une valeur effective de constante qui a bougé |

`pytest` est **volontairement absent** : 90 s à chaque poussée découragerait de pousser, donc de
committer — le remède serait pire que le mal. Il reste dans la CI.

**Quel interpréteur ?** Il en faut un qui ait les dépendances, sinon le contrôle des constantes
échoue pour une mauvaise raison. Ordre : `$BRIDGE_PYTHON`, puis `git config bridge.python`
(réglage **par machine**, non versionné — le chemin d'un interpréteur n'a rien à faire dans le
dépôt), puis `python3`/`python` s'ils passent la sonde.

**Si l'environnement est cassé, on NE bloque PAS : on prévient.** Bloquer une poussée parce
qu'une dépendance manque ne protège rien (la CI rattrapera), alors que perdre une poussée de
sauvegarde serait pire que l'intégrer rouge.

**Activation** (une fois par clone) : `git config core.hooksPath .githooks`

**Comportement vérifié**, pas supposé :

```
état sain                           -> exit 0, « ✓ filets verts »
chemin recalculé réintroduit        -> exit 1, « ✗ POUSSÉE BLOQUÉE » (1 occurrence détectée)
secret dans config.yaml             -> exit 1, « telegram.bot_token est RENSEIGNÉ et le
                                              fichier est versionné »
```

⚠️ **La sauvegarde hebdomadaire ne doit jamais être bloquée** par un filet rouge :
`scripts/git_backup.py` pousse un état *de travail* — le perdre serait pire que de l'intégrer
rouge. Elle passe donc explicitement en `git push --no-verify`, avec le commentaire qui dit
pourquoi.

**Si le blocage côté serveur devient souhaitable plus tard** (une poussée depuis une autre
machine ne passerait pas par le crochet), la seule voie reste GitHub Pro (~4 $/mois) : la
configuration à poser est décrite dans l'historique de cette décision.

## 4. Ce que cette décision ne fait pas

- Elle ne remplace pas la relecture : un test vert prouve qu'on n'a rien cassé de **connu**.
- Elle ne couvre pas le réseau : deux tests appellent `stockanalysis.com` (avertissement
  `InsecureRequestWarning`) — ils passent en CI *parce que* le coureur a un accès réseau ; sur
  un réseau filtré, ils échoueraient sans que le code soit en cause.
- Le filet des constantes reste **descriptif** : il détecte un changement de valeur, il ne dit
  pas si le changement était voulu. C'est l'affaire du journal (`seuils_journal.jsonl`) et du
  message de commit.
