# AUDIT BRVM — Phase 2 : registre des exigences (définition du comportement attendu)

**Date** : 2026-10-12 · **Commit audité** : `b810f7d` (inchangé — l'audit n'a rien modifié)
**Livrables** : `audit/matrice_exigences_tests.csv` (43 exigences) · `audit/preuves/phase2_tests_cites.txt`
**Statut de l'audit** : phases 0, 1 et 2 faites. Aucun test exécuté, aucune correction.

---

## 1. Méthode et sources examinées

Le protocole interdit de prendre le comportement du code pour la règle officielle. J'ai donc
construit le registre **à partir des sources écrites**, puis confronté chacune au code.

| Source | Volume | Ce qu'elle apporte |
|---|---|---|
| `docs/IPS.md` (v1.2, 18/08/2026) | 218 lignes | la politique d'investissement : entrées, sorties, alertes, allocations, fiscalité |
| `docs/INVARIANTS-METIER.md` | 100 lignes | **23 invariants** (A1-E3) avec, pour chacun, le test qui le protège |
| 5 documents de décision (08 et 09/10) | 616 lignes | les évolutions datées et **motivées** (seuils, centralisation, CI, empreinte, unification) |
| 1 document d'anomalie (09/10) | 153 lignes | le seuil « 13 » écrit en dur — cas réel de divergence documentaire |
| 2 rapports de validation | 481 lignes | les mesures statistiques (28 ans, challenge multi-modèles) |
| `data/constantes_snapshot.json`, `config.yaml` | 210 valeurs | **le comportement effectif du code**, valeur par valeur |

**Règle appliquée** : chaque ligne du registre porte l'exigence, sa **source exacte**, les modules
concernés, le comportement attendu, la condition de réussite, le test associé et un **statut**.
Là où les sources divergent, je documente le conflit — **je ne tranche pas**.

---

## 2. Le registre en chiffres

**43 exigences** réparties en 13 familles : Alerte (7) · Données (7) · Entrée (5) · Sortie (4) ·
Fiscalité (4) · Traçabilité (4) · Concentration (3) · Spéculation (3) · Architecture (2) ·
Soutenabilité (1) · Obligations (1) · Allocation (1) · Lecture (1).

| Statut | Nombre | Signification |
|---|---|---|
| **concordant** | **28** + 1 vérifié en production = **29** | le document et le code disent la même chose (valeur constatée à l'appui ; le +1 est DE-04, le journal des envois, déjà vérifié en production) |
| **conflit** | **4** | deux sources se contredisent — voir §3 (au REGISTRE ; **CONFLIT-05 est hors registre** : documentation interne au code, sans impact sur les calculs) |
| **non testé** | **6** | la règle existe, aucun test ciblé ne la protège — les 9 exigences sans test ciblé de §5 se répartissent ainsi : ces 6 + SP-01/02/03 (statuts « conflit » et « à vérifier ») |
| **à vérifier** | **4** | vérification prévue en Phase 4/5 (exécution, contrat, forme du message) |

---

## 3. Les conflits documentés — **TOUS TRAITÉS le 12/10/2026**

> **Mise à jour du 12/10/2026 :** les 4 questions ci-dessous ont été décidées par LEO et les
> corrections sont exécutées (code, IPS, tests) — voir
> `docs/DECISION-2026-10-12-hierarchie-sources-et-questions-audit.md`. Le récit ci-dessous est
> conservé tel qu'établi en phase 2 (traçabilité de l'audit) ; les statuts courants : CONFLIT-01
> résolu, CONFLIT-02 résolu, CONFLIT-03 résolu, CONFLIT-04 résolu (décision Q3), CONFLIT-05 résolu.

### CONFLIT-01 — Trois allocations différentes dans le même document
- **Source A** : `IPS.md` §2 — « Noyau dividende **70 %** · Liquidités **30 %** » (mise à jour du 03/09).
- **Source B** : `IPS.md` §3, titre — « Noyau dividende (**60 %**) ».
- **Source C** : `IPS.md` §6, titre — « Liquidités (**15 %**) ».
- **Impact** : une allocation cible est la base de tout dimensionnement de position. Trois valeurs
  rendent impossible de dire si le système conseille une taille conforme à l'IPS.
- **Ce qu'il faut** : une décision de LEO sur la valeur de référence, puis une mise à jour du
  document. **L'audit ne choisit pas.**

### CONFLIT-02 — La poche obligataire est supprimée en §2 et toujours décrite en §5
- **Source A** : `IPS.md` §2 — « ~~Obligations~~ **0 %** — RETIRÉES (03/09/2026) ».
- **Source B** : `IPS.md` §5 — « Obligations UEMOA (**15 %**) », avec trois lignes et un critère de
  sélection (coupon ≥ 6 %, buy & hold).
- **Code** : `src/analyse/bonds.py` existe et fonctionne (`bond` en CLI, hors stratégie).
- **Impact** : un lecteur du §5 conclurait qu'une poche de 15 % est visée. Le code, lui, ne
  l'alloue pas — mais la coexistence des deux descriptions invite à la réintroduire par erreur.
- **Ce qu'il faut** : archiver la §5 (décision déjà prise le 03/09) ou la marquer comme historique.

### CONFLIT-03 — Le déclencheur de vente « +13 % » de l'IPS contredit la décision du 08/10
- **Source A** : `IPS.md` §3.4 et son tableau des niveaux — « plus-value ≥ **+13 %** → VENDS 1/3 ».
- **Source B** : `docs/DECISION-2026-10-08-seuils-vente.md` — **aucune borne basse n'atteint 50 %**,
  donc les 4 seuils passent en `mode: informatif` **et n'appellent plus de vente**. Le seuil est
  **par titre** (13 % SNTS, 10 % SGBC, 5 % SLBC, 5 % PALC), pas unique.
- **Code** : `portfolio.py` applique `est_declencheur(info)` → les 4 seuils en vigueur sont
  `informatif` (constaté dans `data/profit_thresholds.json`), donc le message est une information,
  pas une consigne.
- **Anomalie liée** : `docs/ANOMALIE-2026-10-09-seuil-13-en-dur.md` documente que la ligne
  « LES AUTRES FOIS » affichait « après une hausse de 13 % » **en dur**, donc faux pour SLBC (5 %).
- **Impact** : un lecteur de l'IPS croirait que le système vend à +13 %. **Le code est cohérent avec la
  DÉCISION DATÉE du 08/10** (seuils par titre — source la plus récente, cf. Q1) ; l'IPS a vieilli.
  C'est un constat que je documente, **pas un arbitrage** : la hiérarchie des sources est justement
  la question ouverte Q1.

### CONFLIT-04 — Le signal de volume en spéculation : mesuré placebo, toujours compté
- **Source A** : `IPS.md` §4.1 — « **Déclencheur (obligatoire, les deux conditions)** : breakout
  20j **ET** volume ≥ 2× la moyenne 20j — sans volume, faux breakout ».
- **Source B** : `docs/CHALLENGE-MULTI-MODELES.md` et le constat du 26/08 — « volume ≥ 2× = placebo
  prédictif (**p = 0,44**) » ; c'est l'une des raisons de la suspension de la spéculation.
- **Code** : `speculation.py` — `MIN_SIGNALS = 3` et le volume figure toujours parmi les signaux
  qui comptent pour la confluence.
- **Impact** : la documentation et le code continuent de traiter comme déclencheur un critère dont
  la mesure dit qu'il n'apporte rien. Ce n'est pas une divergence de valeur : c'est un **désaccord
  de fond** entre la mesure et l'implémentation, sur une poche dont LEO peut se servir.
- **Ce qu'il faut** : décision de LEO (retirer le volume du décompte, le garder en information, ou
  documenter pourquoi il reste). **Question ouverte Q3.**

### CONFLIT-05 (documentation interne au code — **hors du compte des 4 conflits du registre**) — L'IRVM « 15 % » et le « 5,65 % brut » sont périmés
- **Source** : `src/portfolio.py` ligne 5 — « après IRVM **15 %** + frais de conservation » ;
  ligne 53 — « 4 % net -> **≈ 5,65 % brut** » ; `src/analyse/screener.py` ligne 32 — « ≈ 5,65 % brut ».
- **Réalité constatée** : `IRVM = IRVM_DIVIDEND_TAX = **0,12**` (catalogue + `taxation.py`) et
  `DIV_YIELD_ENTRY = **0,05454545454545455**` — c'est-à-dire exactement `gross_yield_for_net(0,04)`
  avec un IRVM de 12 %, conforme à l'IPS §3.1 (brut ≥ 5,45 %) et à l'invariant A3.
- **Impact** : **aucun sur les calculs** (les valeurs effectives sont bonnes, et le snapshot des
  constantes le prouve). L'impact est sur la **confiance** : un commentaire faux sur la fiscalité
  fait douter du reste, et c'est exactement ce que l'invariant A3 (« l'IRVM est identique partout »)
  cherche à prévenir. Le tout premier commentaire du module le plus sensible du projet est faux.

### Cas particulier — une règle qui n'existe QUE dans le code
`MAX_BUY_WEIGHT = **0,40**` (`src/regles.py`) : c'est le plafond de poids d'achat appliqué lors d'un
renforcement « limité », et il **détermine un nombre d'actions conseillé** (`max_qty`, affiché dans
l'alerte). Recherche faite : il n'apparaît dans **aucun** document d'exigence — seulement dans le
catalogue de constantes et dans le rapport auto-généré des constantes.
**C'est précisément le cas que le protocole demande de ne pas promouvoir en règle officielle sans
validation humaine. Question ouverte Q4.**

---

## 4. Traçabilité exigence → test : le contrôle, et ses deux faux positifs

`docs/INVARIANTS-METIER.md` cite 45 fonctions de test. Vérification statique (les tests cités
existent-ils réellement ?) :

```
fichiers de test présents      : 38+1   (38 test_*.py + conftest.py = 39 fichiers .py, cf. Phase 0)
fonctions de test définies     : 335    (336 collectés par pytest)
noms cités par les documents   : 53  → 8 fichiers · 45 fonctions
cités mais INTROUVABLES        : 0
```

**Aucune référence documentaire ne pointe vers un test inexistant** — c'est une qualité réelle de
ce corpus, et elle est elle-même protégée par `tests/test_invariants_documentes.py`.

**Deux défauts de MON contrôle, corrigés avant publication** (un audit qui produit de fausses
anomalies est pire qu'un audit muet) :

1. **8 faux « introuvables »** : les documents citent aussi bien un **fichier** (`tests/test_portfolio.py`)
   qu'une **fonction** (`test_grand_montant`). Mon contrôle confondait les deux.
2. **45 faux « introuvables »** : le générateur `glob` était consommé une première fois puis
   réitéré — il renvoyait zéro fichier, et donc *tous* les tests cités paraissaient absents.
   Correctif : matérialiser la liste avant de l'itérer.

**290 tests sur 335 ne sont cités par aucun document.** Ce n'est pas un défaut en soi (un test
protège un chemin de code, pas forcément une exigence écrite), mais cela **borne la portée du
registre** : il couvre ce que les documents déclarent, pas la totalité du comportement du système.

---

## 5. Les exigences sans aucun test ciblé (9 exigences — dont 6 au statut « non testé »)

Les **6 premières lignes** ci-dessous sont au statut « non testé » du registre ; **SP-01** est au
statut « conflit » et **SP-02/03** au statut « à vérifier » — d'où l'écart apparent avec le chiffre
de 6 du §2 : les trois exigences de spéculation sont bien sans test ciblé, mais classées autrement
dans la matrice.

| Réf. | Exigence | Gravité si elle casse |
|---|---|---|
| **EX-05** | **poches étanches** (portf ↔ spec, refus croisé) | **élevée** — règle structurante, appliquée par une `ValueError` dans `portfolio.py` |
| AL-03 | moins-value ≥ 10 % → CONSERVE chiffré | moyenne |
| AL-04 | échéance 3 ans → réévaluation, jamais clôture | moyenne |
| AL-05 | anti-spam 7 jours, sorties toujours envoyées | moyenne |
| AL-06 | niveau 1 en console seulement, 2-3 sur Telegram | faible |
| EX-03 | exclusions d'entrée (rendement > 30 %, PER > 50) | moyenne |
| SP-01/02/03 | spéculation (volume placebo — SP-01 statut « conflit » ; paliers mécaniques et rappel d'analyse — SP-02/03 statuts « à vérifier ») | selon l'usage de la poche |

**Proposition pour la Phase 4** : couvrir en priorité **EX-05** (poches étanches), **AL-05**
(anti-spam, car une régression ferait du bruit ou ferait taire une sortie) et **SP-02** (paliers
mécaniques, où une régression coûte de l'argent).

---

## 6. Questions ouvertes — décision humaine nécessaire

| # | Question | Pourquoi je ne peux pas trancher |
|---|---|---|
| **Q1** | **Hiérarchie des sources** : en cas de contradiction entre `IPS.md`, `INVARIANTS-METIER.md`, les décisions datées et le code, **qui fait autorité** ? | Le protocole interdit de choisir arbitrairement. Mon avis technique (à valider) : décision datée > invariant > IPS > commentaire de code — mais c'est une convention à entériner. |
| **Q2** | L'IPS doit-il être mis à jour (CONFLIT-01, 02, 03) ? Par qui ? | C'est de la politique d'investissement : elle appartient à LEO, pas à l'audit. |
| **Q3** | Le signal de **volume** en spéculation : retiré du décompte, conservé en information, ou maintenu ? | Désaccord entre une mesure (p = 0,44) et l'implémentation. |
| **Q4** | `MAX_BUY_WEIGHT = 0,40` : confirmé, ou à corriger ? | Règle **absente de toute source écrite**, qui produit pourtant un nombre d'actions conseillé. |

**Avis du contrôle externe (12/10)** : consignés dans `audit/manifest.json` →
`revue_qualite_du_2026-10-12` et `phase2_resume.questions_ouvertes_pour_decision_humaine`.
**DÉCISIONS DE LEO DU 12/10/2026 — TOUTES TRANCHÉES ET EXÉCUTÉES** (Q1 : hiérarchie inscrite en
tête de l'IPS ; Q2 : IPS mise à jour — conflits 01/02/03/05 corrigés ; Q3 : volume en
information, implémenté dans le code + CLI + tests ; Q4 : `MAX_BUY_WEIGHT = 0,40` confirmé,
inscrit dans l'IPS §3.4 avec test). Détail complet :
`docs/DECISION-2026-10-12-hierarchie-sources-et-questions-audit.md`.

---

## 7. Limites de cette phase

- Le registre est **la lecture d'une personne** : une règle implicite dans le code peut m'avoir
  échappé. Il ne prétend pas à l'exhaustivité du comportement (voir les 290 tests non référencés).
- Les **conditions de réussite** ne sont pas encore *exécutées* : c'est la Phase 4 (puis la Phase 8
  pour la suite complète).
- Les valeurs du code sont constatées via le snapshot des constantes ; **le snapshot peut être
  périmé** si une constante a changé sans régénération — la Phase 4 le vérifiera par exécution.
- Je n'ai pas encore confronté ces exigences à la **performance** (Phase 5) : « correct » n'est pas
  « rentable », et le protocole demande de distinguer les deux jusqu'au bout.
