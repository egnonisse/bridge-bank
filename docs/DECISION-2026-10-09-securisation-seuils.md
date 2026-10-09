# Décision — sécuriser les seuils avant toute refonte

**Date :** 9 octobre 2026
**Statut :** implémentée — **309 tests verts**, 189 valeurs effectives identiques au snapshot,
`verifier_chemins.py --strict` = 0
**Origine :** demande LEO du 09/10/2026 — « sécuriser les seuils avant toute refonte »
**Portée :** `src/schema_seuils.py` (nouveau), `src/seuils_vente.py`, `src/portfolio.py`,
`scripts/rafraichir_stats_seuils.py`, `scripts/migrer_seuils_mode.py`

---

## 1. Les deux trous, mesurés dans le code réel

**a) Un fichier mal formé devenait un système sans seuils, en silence.**

`charger()` faisait :

```python
except (OSError, json.JSONDecodeError):
    return {}
```

Un fichier tronqué renvoyait donc « aucun seuil calibré » : `pour()` retombait sur la table de
départ, `mode_pour` classait tout en `informatif` — **plus aucune vente proposée** — et rien ne
le signalait. Un incident de disque changeait une décision d'investissement sans un mot.

**b) Rien n'empêchait un calibrage automatique d'écraser une décision.**

`enregistrer()` écrivait le dictionnaire reçu (`write_text`, sans validation, sans écriture
atomique). Rien ne distinguait un ajout légitime d'un écrasement.

## 2. Deux contrats, parce que lire et écrire n'ont pas le même risque

| | LIRE | ÉCRIRE |
|---|---|---|
| **Exigence** | seul `threshold` est indispensable | tous les champs : `code`, `threshold`, `down_prob`, `borne_basse`, `episodes`, `significatif`, `mode` |
| **Pourquoi** | un seuil calibré **avant** l'introduction du mode n'a ni `mode` ni `borne_basse` ; `mode_pour` sait le classer prudemment en `informatif`. Refuser de le lire **supprimerait** une décision existante au lieu de la protéger | ce que le système produit doit être complet et cohérent, sinon la qualité de demain dépend de ce qui traînait hier |

**Dans les deux cas, un champ PRÉSENT mais invalide est refusé.** Tolérer un champ *absent*
n'est pas tolérer une valeur *inconnue* : un `mode: "peut-être"` retomberait en `informatif` et
une vente disparaîtrait sans un mot.

## 3. Ce qui est protégé

| Protection | Déclencheur |
|---|---|
| **Implicite** | `mode: declencheur` — ce seuil propose de VENDRE : c'est une décision en vigueur, pas une mesure à rafraîchir |
| **Explicite** | `protege: true` — geler un seuil qu'on ne veut pas voir bouger |

Une écriture **automatique** (`origine` par défaut) ne peut pas :

- changer `threshold` ou `mode` d'une entrée protégée ;
- **supprimer** une entrée protégée ;
- **créer** un `declencheur` — activer une vente ne se fait pas tout seul.

Elle peut : **ajouter** un titre non calibré (le travail de `calibrate_missing_thresholds`) et
**rafraîchir des mesures** (le travail de `rafraichir_stats_seuils.py`) — « une mesure se
remesure, une décision ne s'efface pas ».

`autorise_protege=True` déclare l'autorisation explicite : c'est le geste manuel, jamais le
recalcul.

## 4. Garanties vérifiables

- **Le refus est atomique** : validation complète, puis écriture via fichier temporaire et
  `os.replace`. Un refus laisse le fichier **octet pour octet identique** — c'est ce que
  vérifient les tests, pas seulement le code de retour.
- **Le refus est journalisé** avant d'être levé (`seuils_journal.jsonl`, append-only, avec
  `origine` et la valeur tentée dans le motif). Un refus silencieux serait aussi grave que
  l'écrasement qu'il évite.
- **On ne détruit pas ce qu'on ne sait pas relire** : si le fichier courant est corrompu,
  l'écriture est refusée au lieu de l'écraser.
- **42 tests dédiés** (`tests/test_schema_seuils.py`) : clé manquante, type invalide, unité
  fausse (13 pour 0.13), champ inconnu, code incohérent, mode inconnu, cohérence
  `significatif`/`mode`, suppression et écrasement d'un protégé, création automatique d'un
  déclencheur, fichier corrompu, et **non-régression sur le fichier de production réel**.

## 5. Ce que la sécurisation a changé dans le comportement

- `charger()` **lève** au lieu de renvoyer `{}` : un fichier illisible arrête la lecture au
  lieu de dégrader en silence. Le check quotidien échoue **bruyamment** si le fichier est
  corrompu — c'est voulu.
- `rafraichir_stats_seuils.py` peut désormais être **refusé** : si remesurer affaiblit la
  preuve d'un `declencheur` (borne basse sous 50 %), l'écriture n'a pas lieu et le script le
  dit (`exit 1`), au lieu de produire un déclencheur incohérent. La décision doit être revue à
  la main.
- `enregistrer()` n'écrit que si quelque chose a changé (`calibrate_missing_thresholds`).

## 6. Ce que cette décision ne couvre PAS

- **Le fichier de production ne contient aujourd'hui aucune entrée protégée** : les 4 seuils
  sont `informatif`. La protection est un filet pour le jour où un titre deviendra
  `declencheur` — le trou réellement béant aujourd'hui était le point 1 (le silence).
- Aucune protection du **journal** lui-même : il est append-only, mais rien ne l'empêche d'être
  supprimé. Une sauvegarde par le versionnage (il est suivi par git) est la seule garantie.
- La validation ne juge pas la **pertinence économique** d'un seuil : elle garantit qu'il est
  lisible, complet et cohérent — pas qu'il est bon.

## 7. Un bug attrapé par les tests négatifs eux-mêmes

Le contrôle de cohérence comparait `borne_basse` (49, un pourcentage) à `BORNE_BASSE_MIN`
(0.50, une fraction) : il ne se déclenchait **jamais** — un garde-fou décoratif. C'est
exactement le piège d'unité que le projet documente (`FRAIS = 0.028` contre
`FRAIS_PAR_SENS = 0.014`). La conversion est désormais explicite et **verrouillée par un test
dédié** (`test_la_borne_minimale_est_comparee_dans_la_bonne_unite`).
