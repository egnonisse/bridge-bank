# Phase 4 — Matrice de tests (établie le 12/10/2026)

**Suite** : 344 tests — **338 passés + 6 xfail** (cibles de correction de la phase 3, échecs
attendus) + 0 échec · **data/ intact** pendant l'exécution (47 fichiers, md5 identiques —
`preuves/phase4_journal.txt`).
**Références** : 43 exigences (`phase2_exigences.md`), 47 findings (`registre_desaccords.md`),
23 invariants (`docs/INVARIANTS-METIER.md`).

## 1. Types de tests couverts

| Type | Définition | Convention |
|---|---|---|
| **Nominal** | le chemin heureux documenté | test direct |
| **Limites** | seuils (exactement 4 %, exactement −15 %, 0 action) | valeurs frontières |
| **Invalides** | entrées/sorties malformées (fichier corrompu, dps None, quantité 0) | exceptions ou repli explicite |
| **Adversarial** | cas construits pour casser la règle (faux breakout, print illiquide, prix absurde) | garde-fous |
| **Robustesse** | pannes (réseau, corruption, coupure) — jamais de faux-vert | xfail si non couvert aujourd'hui |

**Convention xfail** (nouveau, `tests/test_regressions_audit.py`) : un test qui décrit une
correction à venir est marqué `xfail(strict=False)`. Quand la correction est appliquée il passe en
**XPASS** → retirer le marqueur et geler la correction.

## 2. Matrice par zone

| Zone | Nominal | Limites | Invalides | Adversarial | Robustesse | Trous prioritaires |
|---|---|---|---|---|---|---|
| **Entrées noyau** (`noyau_check`, filtres) | ✅ | ✅ | ⚠️ partiel | ⚠️ partiel | ⚠️ | EX-03 (exclusions 30 %/PER 50) : valeurs cataloguées, pas de test de comportement |
| **Sorties fondamentales** | ✅ | ✅ | ⚠️ | ⚠️ | **❌ B1-01** | test « échec d'envoi ⇒ pas de clôture silencieuse » — à créer AVEC la correction |
| **Alertes & niveaux 1-3** | ✅ | ✅ | ⚠️ | ⚠️ | **❌ B2-04** | cron faux-vert (sortie ≠ 0 sur échec) ; AL-04 (échéance 3 ans) non testé |
| **Anti-spam / cooldowns** | ✅ | ✅ | ✅ | **❌ B1-07 xfail** | ⚠️ | clé de cooldown watchlist (xfail posé) ; AL-05 partiellement couvert (renforcements) |
| **DRIP** | ✅ | ✅ | ⚠️ | **❌ B1-03 xfail** | ⚠️ | net d'IRVM (xfail posé) |
| **Poches étanches (EX-05)** | ✅✅ | ✅ | ✅ | ✅ | ✅ | **en fait TESTÉ** (4 tests, `test_poches_etanches.py`) — voir §3 |
| **Veille spé** (schémas, fiches, stop-out) | ✅ | ✅ | **❌ B1-04 xfail** | ✅ (live ±50 %, volume) | **❌ B0-01 xfail** | date du stop structurée (xfail posé) ; anti-spam consommé à l'envoi (B1-13) |
| **Fiche spé — format FR** | — | — | **❌ B1-02 xfail** | ✅ | — | virgule de milliers (xfail posé) |
| **Collecte & données** | ✅ | ⚠️ | ⚠️ | **❌ B2-11 xfail** | **❌ B2-05/06** | nettoyeur symétrique (xfail posé) ; repli 2 ans silencieux, divisions avalées |
| **Caches de fondamentaux** | ✅ | ❌ | ❌ | **❌ B2-01** | ❌ | fraîcheur (pas de date), valeurs absurdes, deux caches divergents |
| **Crons & notification** | ✅ | ⚠️ | ⚠️ | ⚠️ | **❌ B2-04** | le faux-vert ; le job value bloqué (B2-07) |
| **Sécurité** | — | — | ⚠️ | **❌ B2-02** | ⚠️ | TLS désactivé (verify=False) partout ; secrets ✅ (hors dépôt, testés par la CI) |

Légende : ✅ couvert · ⚠️ partiel · ❌ manquant (id de finding si applicable).

## 3. Corrections apportées à la phase 2 (constats de la phase 4)

- **EX-05 « non testé » était FAUX** : 4 tests existent (`test_poches_etanches.py` — refus croisé
  noyau↔spec dans les deux sens + cas légitime après clôture). Le statut passe à **couvert**.
- **AL-05 / AL-06 « non testés » : partiellement couverts** — `test_portfolio.py` vérifie le
  cooldown des renforcements et référence les niveaux `LEVEL_*` ; le trou réel est l'anti-spam
  de la veille spé (B1-13).
- **AL-04 (échéance 3 ans) : non testé confirmé** (aucune occurrence).
- Ces écarts s'ajoutent au registre : la phase 2 sous-estimait la couverture existante par
  contrôle statique (elle ne cherchait pas les tests par comportement).

## 4. Tests créés en phase 4 (6 xfail — cibles des corrections)

| Test | Finding | Comportement cible |
|---|---|---|
| `test_drip_comptabilise_le_net_apres_irvm` | B1-03 | cash = dps × 0,88 × quantité |
| `test_portfolio_corrompu_ne_redevient_pas_vide` | B1-04 | fichier illisible ⇒ bruyant, jamais écrasé |
| `test_fiche_spec_sans_virgule_de_milliers` | B1-02 | format FR (espaces) dans les fiches |
| `test_nettoyeur_detecte_les_artefacts_bas` | B2-11 | détection symétrique des outliers |
| `test_cooldown_watchlist_ne_repete_pas` | B1-07 | clé de cooldown sans le prix |
| `test_close_reason_porte_la_date_du_stop` | B0-01 | date du stop dans `close_reason`/`closed_at` |

## 5. Tests à créer AVEC les corrections (phases 9-11)

1. **B1-01** — « échec d'envoi ⇒ la position n'est pas clôturée / l'alerte est réémise »
   (nécessite le refactor send-before-save : test au niveau `cmd_portf check` mocké).
2. **B2-04** — `daily_check` doit sortir ≠ 0 quand une étape lève (test en subprocess).
3. **B2-01/B2-03** — cache de fondamentaux : refus d'une valeur non plausible + fraîcheur
   obligatoire (schéma `{per, scraped_at, source}`).
4. **B2-05/06** — divisions absentes ⇒ erreur explicite ; repli de collecte ⇒ compteur journalisé.
5. **B1-05** — prix de sortie recalculé sur le dps courant.
6. **B1-13** — anti-spam consommé à l'envoi (fiche non envoyée ⇒ non marquée vue).
7. **C6 (B1-08/B0-04)** — une seule formule de prix d'entrée (ou les deux étiquetées).
8. **B1-12** — extension du test gardien C4 aux sous-dossiers + littéraux en expressions.

## 6. Priorités pour la phase 8 (exécution contrôlée étendue)

- Convertir les 6 xfail en tests fermés au fil des corrections (passer `strict=True` pour
  transformer tout XPASS futur en signal visible).
- Compléter par la couverture de code (outil `coverage` à installer — autorisation requise).
- Rejouer la suite complète avec gel de `data/` (relevé avant/après — le mécanisme du
  `phase4_journal.txt` est réutilisable).
