# Décision — une empreinte de version sur chaque alerte

**Date** : 09/10/2026 · **Portée** : traçabilité des alertes (`src/notify.py`,
`src/infrastructure/empreinte.py`, `src/alertes/journal_alertes.py`) · **Origine** : point 3 de
l'audit du 09/10 (« les alertes doivent porter l'identifiant de version du code, l'empreinte de la
configuration des seuils et la date de génération »).

## Le problème, mesuré

Le journal des seuils (`data/seuils_journal.jsonl`) dit **ce qui a changé** dans les décisions. Il
ne dit pas dans quel **état** était le système quand une alerte est partie. Et surtout : **le texte
des alertes n'était conservé nulle part.**

Vérifié avant d'écrire une ligne : les 18 appels à `notifier.send(...)` (`src/main.py` ×15,
`src/alerts.py`, `src/speculation.py`, `scripts/close_check.py`) partaient vers Telegram et
disparaissaient. Le seul fichier conservé, `data/alerts_state.json`, ne contient que des
horodatages anti-doublon — ni le message, ni les règles utilisées.

Conséquence concrète : une alerte reçue il y a trois semaines est inexplicable. Quatre causes
distinctes produisent pourtant le même effet « l'alerte a changé » :

1. le **code** a changé (règle réécrite, correction) ;
2. les **règles** métier ont changé (PER max, payout, fiscalité) ;
3. les **seuils calibrés** ont changé (une décision, journalisée) ;
4. la **configuration** a changé (watchlist, noyau, cadence).

## Ce qui est décidé

**1. Un journal des envois, append-only** : `data/alertes_journal.jsonl`, une ligne par message
sortant, clés en français — mêmes conventions que le journal des seuils (objet JSON par ligne,
jamais édité, **versionné** avec le dépôt pour survivre à la machine).

    horodatage   date et heure de l'envoi (heure locale, secondes)
    origine      module ayant demandé l'envoi (« src.main ») — lu dans la pile d'appels
    envoye       vrai/faux : un envoi qui a ÉCHOUÉ est une information, pas une ligne à perdre
    empreinte    code · regles · seuils · config
    message      le texte de l'alerte

**2. L'empreinte porte quatre valeurs, pas une** — parce que les quatre causes ci-dessus n'ont pas
la même explication et qu'il faut pouvoir les distinguer :

| Champ | Ce qu'il mesure | Comment |
|---|---|---|
| `code` | la version du code | SHA court du commit, suffixé `*` si l'arbre de travail est modifié |
| `regles` | les règles métier | SHA-256 du contenu de `regles.py` + `taxation.py` |
| `seuils` | les seuils calibrés | SHA-256 du contenu de `profit_thresholds.json` |
| `config` | la configuration | SHA-256 du contenu de `config.yaml` |

**Le `*` est le point le plus important.** Un paramètre peut être modifié sur le disque entre deux
exécutions **sans qu'aucun commit n'apparaisse** : le SHA du commit seul ne le verrait jamais.
L'empreinte du contenu, elle, le voit toujours. Les journaux append-only sont exclus du calcul du
drapeau : un journal qui s'allonge n'est pas un changement de règles (sinon chaque alerte
marquerait l'arbre comme modifié *à cause de sa propre trace*).

**3. L'empreinte est posée au POINT DE PASSAGE UNIQUE**, pas dans les 18 appelants :
`TelegramNotifier.send()`. Un appelant oublié rendrait la traçabilité partielle **sans que personne
ne s'en aperçoive** — exactement le défaut qu'on cherche à supprimer. Aucun producteur d'alerte n'a
été modifié.

**4. Le transport reste transparent par défaut.** Le texte envoyé est **inchangé** ; le rappel
visible (`— v4434c8a* · seuils e4fe39cdb73c`) s'active par un réglage :
`alerts.empreinte_dans_message: true` dans `config.yaml`. La trace, elle, est **toujours** inscrite.

**5. La traçabilité ne peut jamais empêcher une alerte de partir.** `enregistrer()` attrape ses
propres erreurs (disque, permissions, objet non sérialisable) et l'appel est de nouveau protégé dans
`send()`. Règle : *une trace manquante est moins grave qu'une alerte perdue.*

## Le défaut trouvé en vérifiant (et le garde ajouté)

La première version de `empreinte.py` pointait `regles.py` et `taxation.py` vers `src/domaine/` —
leur destination prévue par le plan, mais **pas leur emplacement actuel** : ils sont encore à la
racine de `src/` (le lot 5 les déplacera). Le calcul lisait donc deux fichiers inexistants et
produisait une empreinte **constante** (`be5fcd9f07db`), parfaitement crédible, qui n'aurait jamais
signalé un changement de règle.

C'est la panne silencieuse type de ce projet, et elle n'a été vue que par une **exécution réelle**,
pas par les tests unitaires — ceux-ci passaient tous.

Correctifs :

- les chemins sont déclarés dans `src/infrastructure/paths.py` (`MODULE_REGLES`, `MODULE_TAXATION`),
  conformément à la règle « un chemin vit à un seul endroit » ;
- `tests/test_empreinte.py::test_les_fichiers_surveilles_existent_vraiment` **échoue bruyamment** si
  l'un des fichiers surveillés n'existe plus. C'est ce test qui protège le lot 5 : il faudra mettre
  ces deux constantes à jour, sinon la CI refuse.
- empreinte corrigée : `1b9873e0b707` (au lieu de `be5fcd9f07db`), et elle change bien quand une
  valeur de règle change (vérifié : `PER_MAX = 14` → `13` change l'empreinte).

## Limite assumée

L'empreinte est lue **au moment de l'envoi**, pas au moment du calcul de l'alerte. Un changement
survenu entre les deux serait attribué à cet envoi. Le distinguer exigerait de transporter l'état
dans tout le pipeline — disproportionné au regard du risque (une exécution dure quelques minutes).

## Vérifications

| Contrôle | Résultat |
|---|---|
| `pytest` | **333 passed** (309 + 24 nouveaux) |
| Envoi réel de bout en bout | journal créé, ligne relue, `envoye: false` (Telegram non configuré) |
| Empreinte des règles suit le contenu | oui (modification de `PER_MAX` → empreinte différente) |
| `verifier_chemins.py --strict` / configuration | 0 / conforme |
| Snapshot des constantes | 202 → 210 (**8 ajoutées, 0 modifiée**) |

Ligne de journal produite par la vérification de bout en bout (retirée ensuite : le journal doit
naître de la première alerte **réelle**, une trace qui commence par des entrées de test n'est plus
une trace) :

```json
{"horodatage": "2026-10-09T06:36:12", "origine": "__main__", "envoye": false,
 "empreinte": {"code": "4434c8a*", "regles": "1b9873e0b707", "seuils": "e4fe39cdb73c",
               "config": "6b8dd4727a0e"},
 "message": "🔔 ALERTE de vérification — mise en place de la traçabilité"}
```

## Conséquences pour la suite

- **Lot 5 du plan** : déplacer `regles.py` et `taxation.py` vers `domaine/` **oblige** à corriger
  `MODULE_REGLES` / `MODULE_TAXATION` dans `paths.py` (le test le dira).
- Lire la trace : `src.alertes.journal_alertes.lire()` / `.derniere()` / `.compter()`.
- Le journal s'allongera d'une ligne par message sortant (y compris le battement quotidien) : c'est
  voulu, c'est la trace de ce qui est sorti.
