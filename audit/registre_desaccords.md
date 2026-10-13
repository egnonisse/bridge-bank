# Phase 3 — Registre des désaccords et croisement (audit à 2 familles)

**Date** : 2026-10-12 · **Livrable de la phase 3** (protocole : « deux agents indépendants sur
les points sensibles ») · Commit audité : `b810f7d` (A) / `a0836b4` (B).

## 1. Dispositif et périmètres

| Agent | Famille / modèle | Périmètre | Findings |
|---|---|---|---|
| **A** | Claude (anthropic/claude-sonnet-5.5, OpenRouter) | 3 modules sensibles : `strategie_leo.py`, `challenge_validateur.py`, `fondamentaux_historiques.py` | 13 (2 P1 · 10 P2 · 1 P3) — `phase3_agentA_claude.md` |
| **B0** | Mistral (run avorté, connexion coupée — matériel récupéré) | revue élargie (tentative) | 4 pistes récupérées — `phase3_materiel_runB_avorte.md` |
| **B1** | Mistral (mistral-large-4-0, OpenRouter) | cœur métier : alertes, portefeuille, veille spé, notifications | 15 (1 P1 · 6 P2 · 8 P3) — `phase3_agentB1_mistral.md` |
| **B2** | Mistral (mistral-large-4-0) | infrastructure & données : collecte, CLI, scripts, sécurité | 15 (1 P1 · 7 P2 · 7 P3) — `phase3_agentB2_mistral.md` |

**Total** : 47 items (43 formels + 4 récupérés). Les périmètres A / (B1+B2) sont volontairement
disjoints ; le croisement porte donc sur les **convergences thématiques**, les **vérifications
d'intégrité** et les **faux positifs**, pas sur des contradictions frontales de périmètre.

## 2. Vérifications d'intégrité (par l'auditeur principal, exécutées le 12/10)

Règle appliquée : aucun finding gobé sans contrôle. Échantillon couvrant les 2 P1 formels, les
items récupérés et les croisements structurants :

| Finding | Statut de vérification |
|---|---|
| A3-01 (TTM jamais écarté) | ✅ **CONFIRMÉ** — branche morte dans le code + 12 titres à BPA 2024==2025 dans les données réelles |
| B0-01 (parse de date spec_veille) | ✅ **CONFIRMÉ PAR EXÉCUTION** — le parse échoue systématiquement, repli sur `opened_at` |
| B1-01 (sortie persistée avant envoi) | ✅ **CONFIRMÉ** — `save_portfolio` (main.py:532) précède `notifier.send` (:539-541), retour ignoré |
| B1-03 (DRIP brut sans IRVM) | ✅ **CONFIRMÉ** — `cash = pos.dps * pos.quantity` (portfolio.py:553), aucun `(1−IRVM)` |
| B2-04 (cron faux-vert) | ✅ **CONFIRMÉ** — `daily_check.py` attrape l'exception et **sort en 0** (le `check=True` du wrapper est neutralisé) |
| B2-01 (cache PER) | ⚠️ **PARTIELLEMENT CONFIRMÉ — une erreur corrigée** (voir §4, F-01) |
| B0-02 / B1-02 (format virgule) | ✅ **CONFIRMÉ** — ~8 occurrences dans `spec_fiche.py` + chemins live de `portfolio.py`/`alerts.py` |
| B1-07 (clé de cooldown avec prix) | ✅ Confirmé par lecture du code cité |

## 3. Convergences (le même besoin vu par plusieurs angles — à traiter ensemble)

| # | Convergence | Sources croisées |
|---|---|---|
| **C1** | Le **format français** (sans virgule de milliers) n'est pas appliqué aux **messages live** : fiches spé, sorties, renforcements, alertes watchlist — alors que le helper `format_fr` et son test existent, et que l'INVARIANT E1 le demande | B0-02 + B1-02 |
| **C2** | **Vérification TLS désactivée** (`verify=False` + `disable_warnings` global à l'import) sur toutes les sources de données — y compris celles qui déclenchent les décisions | B0-03 + B2-02 |
| **C3** | **Veuille spé — le garde-fou stop-out** : date de stop extraite d'une chaîne d'affichage (échec systématique → repli sur la date d'ouverture) et « 2 stop-outs consécutifs » comptés **cumulativement** | B0-01 + B1-09 |
| **C4** | **Constantes fiscales recopiées en dur** (0,88 / 0,008 / 0,12 hors `taxation.py`) et **test gardien C4 aveugle** (ne scanne que `src/*.py` top-niveau, pas les sous-dossiers ni les littéraux en expression) | B1-06 + A3-06 (+ grep de B0) |
| **C5** | **Écritures non atomiques + lecture « vide par défaut »** : un fichier corrompu est lu comme vide puis **écrasé** — danger maximal sur `portfolio.json` et `dividendes.json` (données irremplaçables) | B1-04 + B2-13 |
| **C6** | **Deux « prix d'entrée 4 % net »** (IPS sans frais vs code avec frais, ~1,4 % d'écart) — deux valeurs dans le code, une seule dans l'IPS | B0-04 + B1-08 |
| **C7** | **Fraîcheur des fondamentaux** : cache PER sans date (et 11 valeurs absurdes), deux caches divergents tamponnés « frais » à l'écriture, dps figé à l'ouverture (prix de sortie épérimé), dividende le plus récent sans limite d'âge | B2-01 + B2-03 + B1-05 + A3-11 |
| **C8** | **Fiabilité de la délivrance** : alerte de sortie perdue sur échec d'envoi (position clôturée quand même), cron faux-vert, job value bloqué, anti-spam consommé avant livraison, cooldown watchlist inefficace | B1-01 + B1-07 + B1-13 + B2-04 + B2-07 |
| **C9** | **Historique silencieusement faux** : divisions avalées sans avertissement, replis 2 ans, dates fabriquées, 3 caches d'autorité incertaine (validation ≠ production), nettoyeur asymétrique ; en amont les look-aheads BPA/TTM biaisent les évaluations | B2-05 + B2-06 + B2-10 + B2-11 + A3-01 + A3-02 |
| **C10** | **Duplications de valeurs/seuils** qui divergent déjà : `PROFIT_DOWN_PROB` (PALC 45 vs 46), défaut 0,13 non importé, `cash_cible` de la simulation contre l'IPS | B1-12 + A3-07 + A3-06 |

## 4. Désaccords, erreurs et faux positifs (ce que le croisement corrige)

**F-01 — B2-01 « panne silencieuse depuis le 09/09 » : FAUX (erreur de lecture de date).**
Vérification directe : `stat data/per_cache.json` → **2026-10-09 09:13** (9 octobre, écrit par le
check quotidien), pas « 9 septembre » ; l'écart est de **3 jours**, pas 33. En revanche le FOND du
finding tient : 11 valeurs absurdes dans le cache (PER 0,0 ×4 ; 688 / 578 / 254 / 212 / 96,7 /
72,7 / 59,6), aucun champ de fraîcheur dans le schéma, et aucune validation à l'écriture.
**Impact direct sur le portefeuille de LEO** : les PER en cache de PALC (7,73), SGBC (12,03),
SLBC (13,34), SNTS (10,88), BICC (14,38) sont **plausibles** → pas de danger imminent sur ses
positions, mais le risque existe pour d'autres titres (ex. SIVC à 96,7 déclencherait « VENDS
TOUT » à tort s'il était détenu). **Reclassé P2** (hygiène des données) au lieu de P1.

**F-02 — Niveaux de preuve hétérogènes (à retenir pour les phases suivantes).**
L'agent A a vérifié par les données et l'exécution (doublons réels, formats de chaînes) ; les
agents B travaillent en lecture statique — leurs scénarios d'impact sont des **constructions
raisonnables, pas des reproductions** (B2 le déclare lui-même). Ne pas transformer un scénario B
en certitude avant la phase 5/8.

**F-03 — Aucun désaccord frontal entre agents** (périmètres disjoints) : le seul point où un agent
se trompe est la date de B2-01 (F-01). Le croisement apporte donc surtout des **recoupements** et
deux **regroupements** : B2-01 + B1-05 (même sinistre « vente fausse » par deux chemins), et
B1-04 + B2-13 (même classe d'écriture non sûre).

**F-04 — Le run avorté (B0) a laissé 4 pistes utiles**, dont 2 recoupées par B1/B2 (format FR,
TLS) et 1 seule orpheline confirmée (B0-01). Le protocole d'écriture incrémentale a été appliqué
aux relances — les rapports B1/B2 sont complets.

## 5. Synthèse consolidée — le TOP 10 des risques de la phase 3

Classement par (gravité × confiance de vérification × impact réel sur LEO) :

| Rang | Risque | Gravité | Preuve |
|---|---|---|---|
| 1 | **Sortie « VENDS TOUT » perdue** sur échec d'envoi — position clôturée, LEO jamais prévenu, plus aucune surveillance | P1 | Confirmé |
| 2 | **Look-aheads BPA/TTM** dans les fondamentaux historiques — biaisent les évaluations et les règles « RETENUE » du challenge | P1 | Confirmé |
| 3 | **Cache PER** : 11 valeurs absurdes, aucun champ de fraîcheur, deux caches divergents ; alimente « PER > 40 → VENDS TOUT » | P1→P2 | Confirmé (corrigé) |
| 4 | **dps figé** → prix de sortie calculé sur le dividende d'ouverture (ventes prématurées ou tardives) | P2 | Confirmé |
| 5 | **Format français non appliqué** aux messages live (invariant E1) — risque de mauvaise lecture d'un montant d'ordre | P2 | Confirmé |
| 6 | **Cron faux-vert** : le check plante → sort 0 → heartbeat ✅ — la surveillance ne voit pas ses propres pannes | P2 | Confirmé |
| 7 | **Écritures non atomiques** : `portfolio.json` / `dividendes.json` effaçables par corruption + sauvegarde inconditionnelle | P2 | Confirmé |
| 8 | **Garde-fou stop-out inopérant** (veille spé) + cooldown watchlist inefficace (spam) | P2/P3 | Confirmé |
| 9 | **TLS désactivé** sur toutes les sources de décision | P2 | Confirmé (lecture) |
| 10 | **DRIP comptabilise le brut** — dividendes surestimés de ~13,6 % à chaque versement | P2 | Confirmé |

## 6. Suites recommandées (phases 4-8)

1. **Phase 4 (tests)** : le registre de B1 donne les priorités de couverture — EX-05 (poches
   étanches), AL-05 (anti-spam), SP-02 (paliers) + **des tests de non-régression pour chaque
   correction** issue des P1/P2 ci-dessus.
2. **Phase 5 (audit financier)** : re-vérifier les P1 par exécution (recalculs indépendants) ;
   trancher C6 (une seule formule de prix d'entrée) et C7 (définir la règle de fraîcheur des
   fondamentaux) ; confronter le DRIP au relevé Bridge Bank réel.
3. **Corrections (phases 9-11)** : ordre proposé — (1) B1-01 puis B1-04/C5, (2) C1 format FR,
   (3) B2-04 cron faux-vert, (4) C7 fraîcheur, (5) C2 TLS, (6) le reste.
4. **Process** : l'écriture incrémentale est désormais la règle pour tout rapport long d'agent.

---

## 6. Statut des corrections — mise à jour du 12/10/2026 (soir)

**LOT 1 appliqué** (autorisé par LEO : « go lot 1 ») — détail : `docs/DECISION-2026-10-12-corrections-lot1.md`.

| Item | Statut | Preuve de gel |
|---|---|---|
| **B1-01** (sortie perdue si échec d'envoi) | ✅ **CORRIGÉ** | `test_sortie_non_delivree_annule_la_cloture` + `test_sortie_delivree_est_persistee` (passants) |
| **B0-01** (date de stop) | ✅ **CORRIGÉ** | `test_close_reason_porte_la_date_du_stop` (passant, ex-xfail) |
| **C1/B1-02** (format FR) | ✅ **CORRIGÉ** | gardien des sorties recapturé (0 divergence numérique) + `test_fiche_spec_sans_virgule_de_milliers` |
| **B1-04** (portfolio corrompu) | ✅ **CORRIGÉ** | `test_portfolio_corrompu_ne_redevient_pas_vide` + `test_portfolio_ecriture_atomique` |
| **B2-04** (cron faux-vert) | ✅ **CORRIGÉ** | `test_heartbeat_signale_les_echecs` + `test_heartbeat_sans_echec_garde_le_titre_vert` |
| B1-03 (DRIP brut), B1-07 (cooldown watchlist), B2-11 (nettoyeur) | ⬜ lot 2-3 | xfail actifs (3) |
| A3-01/A3-02 (look-aheads), B2-02 (TLS), C2/C5/C6/C7, B1-05/B1-13, B2-01/B2-03 | ⬜ lots 2-3 | voir §5 |

### Mise à jour du 12/10/2026 (soir) — LOT 2 APPLIQUÉ

Détail : `docs/DECISION-2026-10-12-corrections-lot2.md`. **B1-03** (DRIP net IRVM) ·
**B1-07** (clé de cooldown stable) · **B1-05** (prix de sortie recalculé au dps courant) ·
**B1-09** (stop-outs rapprochés, plus cumulatifs) · **B1-13** (anti-spam consommé à la
livraison) · **B2-01/B2-03** (PER ≤ 0 rejeté, cache daté + verrou + écriture atomique) ·
**B0-04/B1-08** (formule d'entrée unique, portfolio.json migré) → tous **CORRIGÉS et gelés**
par tests. Plus **2 découvertes d'infrastructure réparées** : BOC cassé depuis le 02/10
(pymupdf — venv projet + `--interpreter` sur les 5 jobs cron, testé en réel) et la course
sur `per_cache.json` (48 → 5 entrées, atomicité + verrou, cache restauré).

État de la suite : **356 passed, 1 xfailed** (B2-11 = lot 3). **Découvertes hors lot** :
cache historique en retard (dernières barres au 30/09) — prochain chantier candidat.

### Mise à jour du 12/10/2026 (soir) — CACHE HISTORIQUE RÉPARÉ (chantier dédié)

Détail : `docs/DECISION-2026-10-12-cache-historique.md`. **48 → 0 problème d'intégrité** :
refresh complet relancé (barres jusqu'au 09/10) + `history_clean` + profils ré-exportés ;
**fraîcheur désormais jugée sur les DONNÉES** (`_donnees_fraiches`, 4 j — auto-réparant,
fini le mtime trompeur qui a figé le cache 7 j) ; **registre des titres dormants**
(`data/titres_inactifs.json`, SEMC/SICC = source muette au 15/09 → information, pas alerte).
Suite : **361 passed, 1 xfailed** (+5 tests).

### Mise à jour du 12/10/2026 (nuit) — LOT 3 APPLIQUÉ

Détail : `docs/DECISION-2026-10-12-corrections-lot3.md`. **A3-01** (parseur BPA : colonne
TTM écartée par position, cellules vides préservées, refus si incohérent → **12 doublons
exacts → 0**, **22/47 titres recalculés**, ABJC 2024 : 121,98 → 138,84) · **A3-02**
(publication au 30/06 N+1, fini le look-ahead de 3-6 mois) · **B2-02/B0-03** (TLS :
`verify=False` retiré de 5 sources, 6 domaines testés en `verify=True` → 200 ; seul
BSTrade garde l'exception, SSLError vérifié) · **B2-11** (nettoyeur symétrique [÷5, ×5]
+ anti sur-nettoyage) · **C4/A3-06** (0,88/0,008 → `net_yield()`/`IRVM_DIVIDEND_TAX`
dans 6 modules ; test gardien **récursif** + littéraux fiscaux + `AnnAssign`) · **C10/B1-12**
(`PROFIT_DOWN_PROB` supprimé — PALC 45 vs 46 acta la divergence ; défaut 0,13 →
`regles.PROFIT_ALERT_THRESHOLD`) · **A3-07** (divergence IPS documentée dans la docstring
du moteur). Suite : **374 passed, 0 xfailed** (+13 tests ; plus aucun xfail).

### Mise à jour du 13/10/2026 (nuit) — LOT 4 · 1re partie : LIVRAISON DES JOBS AGENTS (B2-07 + radar)

**Constat en réel** : le job value (`9bf21948f66b`) échouait à CHAQUE run depuis ≥ le 07/10
(`[blocked_config:silent] delivery platform 'telegram' has no gateway credentials`) et le
radar (`e8974cd7337d`) était en `delivery: suppressed` sur TOUS ses runs — **aucun rapport
de ces 2 jobs n'atteignait LEO**. Cause : la passerelle Telegram d'Hermes n'est pas
connectée sur cette machine (s'applique la règle du 18/09 : les crons livrent par le
NOTIFIER INTERNE du projet).

**Correction** :
- `src/notify.py` : découpage des messages > 4096 caractères (limite API Telegram) aux
  frontières de lignes — un rapport long était PERDU à l'envoi (7 tests, `tests/test_notify.py`).
- `scripts/notifier_envoyer.py` : pont CLI agent → notifier interne (« envoyé »/« ÉCHEC »,
  journalisé dans `data/alertes_journal.jsonl`).
- Les 2 jobs passés en `deliver=local` + étape d'ENVOI explicite dans le prompt (+ note
  anti-conflit contre le bandeau système « do NOT deliver the output yourself »).

**Preuves (13/10 ~00h20)** : message de test reçu (299 car.) ; run value → `completed`,
réponse « ✅ Analyse value : rien de nouveau aujourd'hui. » ; run radar → `completed`,
monitor `no_change` (normal sans code L1/L2) ; plus aucun `failed`/`blocked_config`.
Suite : **468 passed, 0 xfailed**. Le premier rapport réel validera la chaîne de bout en bout.

### Mise à jour du 13/10/2026 (nuit) — LOT 4 · 2e partie : SILENCES DE LA COLLECTE (C9) + DRAPEAU + DIVIDENDE COURANT (C7)

**B2-05** (ajuster_historique avalait l'absence du fichier de divisions → historique brut
non ajusté, silencieux) : l'échec est désormais **BRUYANT** (FileNotFoundError explicite,
comme `charger()`) — classe de l'incident du 21/08 (faux drawdowns −96 %).
**B2-06** (replis et zéros silencieux) : repli d'historique **journalisé** + titres en échec
**comptés et signalés** (backtest.py) ; barre sans horodatage **écartée** (plus de date
« maintenant » fabriquée) ; valeur illisible **signalée** vs champ absent muet (bsapi.py).
**B2-12** (drapeau `*` dilué par le fonctionnement normal) : 14 fichiers d'état exclus du
calcul (caches, états de veille, snapshots suivis) ; `profit_thresholds.json`, `regles.py`,
`config.yaml` restent **surveillés** — un vrai changement de règles porte toujours l'étoile.
**A3-11** (dividende « le plus récent » sans limite d'âge) : le dividende point-in-time est
désormais (i) **PÉRIMÉ au-delà de 15 mois** → « inconnu », jamais un rendement fictif
(scénario BNBC), (ii) la **SOMME des versements de l'année écoulée** (acompte + solde ; le
payout dps/BPA redevient annuel/annuel) — le rendement d'un dividende coupé disparaît de la
sélection point-in-time.

**Preuves** : 6 nouveaux tests collecte + 2 empreinte + 6 A3-11 (15/15 du fichier) ; **rejeu
complet des chiffres publiés du 13/10 : EXIT 0 — aucun écart** (les 6 mesures de référence
sont identiques ; `git status -- data/` vide après rejeu : sorties identiques au bit près).
Suite : **474 passed, 0 xfailed**.

### Mise à jour du 13/10/2026 (nuit) — LOT 4 · 3e partie : MOTEUR A3-12 + CHIFFRES PUBLIÉS

**A3-12** (4 défauts du moteur de simulation, P2) corrigés : (a) dividendes d'une position
soldée conservés au compte-rendu (cumul moteur) ; (b) réserve de cash jamais franchie par une
tranche (montant borné par le disponible) ; (c) dividende crédité AVANT les ordres du jour —
le droit va aux détenteurs d'avant l'ex-date ; (d) plafond de ligne mesuré sur le cumul
investi (`investi_total`) — plus de réinvestissement du produit d'une vente au-delà du
plafond.

**Conséquence assumée sur les chiffres publiés** (re-mesure du 13/10, preuve
`audit/preuves/attribution_remesuree_2026-10-13.txt`) : noyau 232,2 → **233,0 %** ;
renforcement +26,2 → **+26,7 pt** ; paliers −45,4 → **−49,0 pt** ; complète −31,2 →
**−43,0 pt**. Sens intact, constat renforcé (les paliers coûtent davantage). Référence
(`chiffres_reference.json`), invariant B1 (`INVARIANTS-METIER.md`) et rapport 28 ans alignés —
jamais de réécriture silencieuse : l'ancien chiffre reste daté. Détail :
`docs/DECISION-2026-10-13-lot4-residuels.md`.

Suite : **484 passed, 0 xfailed**.

---

*Phase 3 complète. Livrables : `phase3_agentA_claude.md`, `phase3_agentB1_mistral.md`,
`phase3_agentB2_mistral.md`, `phase3_materiel_runB_avorte.md`, ce registre. Les corrections
du LOT 1 ont été appliquées le 12/10 (section 6) ; les lots 2-3 restent à autoriser.*
