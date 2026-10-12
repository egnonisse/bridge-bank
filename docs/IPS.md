# IPS — Politique d'Investissement (Bridge Bank)

**Investisseur :** LEO (Egnonisse Léonard) · **Marché :** BRVM (UEMOA) · **Devise :** FCFA
**Version :** 1.2 · **Date :** 2026-08-18 · **Horizon :** ≥ 3 ans

> Ce document est la référence. Toute décision d'achat/vente doit pouvoir être
> rattachée à une règle ci-dessous. Il prime sur l'émotion et l'actualité.

> **Hiérarchie des sources (décision du 12/10/2026, à la suite de l'audit)** — en cas de
> contradiction entre documents : **1) décision datée · 2) invariant (`docs/INVARIANTS-METIER.md`)
> · 3) cette IPS · 4) commentaire de code**. Une contradiction constatée oblige à mettre à jour
> la source perdante — deux versions ne cohabitent jamais (décisions : `docs/DECISION-2026-10-12-hierarchie-sources-et-questions-audit.md`).

---

## 1. Objectifs & profil

| Critère | Valeur |
|---|---|
| Horizon | **≥ 3 ans**, pas de retrait avant l'échéance |
| Objectif | **Revenu dividende réinvesti** (DRIP) + croissance du capital |
| Capital initial | ≈ 1 000 000 FCFA |
| Tolérance au risque | −30 % supportable, mais **garde-fou global −25 % → revue complète** |
| Philosophie | Value + dividende (Graham / Buffett / Greenblatt adapté) |
| Exigence | ≥ 3 sources de valorisation croisées, **aucun chiffre inventé** |

**Principe fondamental :** le rendement se mesure en **NET** (après impôt + frais).
Le « rendement » affiché par les sources brutes ne suffit pas.

---

## 2. Allocation cible

| Poche | Part | Montant (1 M FCFA) | Rôle |
|---|---|---|---|
| **Noyau dividende (actions)** | 70 % | 700 000 (7 × 100 000) | revenu récurrent réinvesti |
| **Liquidités** | 30 % | 300 000 | échelonnage des achats + soldes de marché |
| ~~Obligations~~ | **0 %** | — | **RETIRÉES (03/09/2026)** — stratégie actions uniquement |
| ~~Spéculative~~ | **≤ 10 %** | — | **AUTORISÉE EN CONSCIENCE (03/09/2026)** — alertes néophytes avec analyse toujours en tête + proposition de plafond |

> **Décision du 03/09/2026 — obligations retirées.** LEO se concentre uniquement
> sur les actions : l'objectif de rendement (viser plus haut que le YTM ~6,6 %)
> passe par la sélection d'actions value+dividende et l'attente des soldes, pas
> par la poche obligataire. Le module `bond` reste disponible en manuel
> (`python -m src.main bond ...`), hors stratégie.

> **Décision du 03/09/2026 — spéculation « en conscience ».** Après la suspension du
> 26/08 (H2 volume placebo, H4 frais), LEO a choisi de RÉACTIVER les alertes
> spéculatives AVEC garde-fous : chaque alerte est néophyte-compréhensible,
> l'analyse des 9 ans de données figure TOUJOURS en tête (le signal ne prédit
> rien, le pari est perdant en moyenne à 70 000 F, gagnant à ≥ 150 000 F), et le
> système PROPOSE un plafond de poche (~10 % du portefeuille) — la décision de
> jouer et le montant restent à LEO. Règle d'or exécutoire : un pari perdant ne
> devient jamais un investissement. Conditions de réactivation données le 26/08
> (position ≥ 150 000 F + déclencheur prédictif) documentées mais non bloquantes :
> LEO joue en connaissance de cause.

**Règle :** les poches sont étanches. Un spéculatif perdant ne devient **jamais**
un investissement long terme (et inversement). Appliquée par l'outil :
`portf open` et `spec open` refusent un titre déjà ouvert dans l'autre poche
(une position clôturée ne bloque pas — la vente d'abord, le rachat ensuite).

---

## 3. Noyau dividende (70 %)

> Titre corrigé le 12/10/2026 (audit, CONFLIT-01) : 70 % conformément à la décision
> d'allocation du 03/09/2026 en §2 — les mentions « 60 % » étaient des restes d'édition.

### 3.1 Critères d'entrée
- **Rendement net ≥ 4 %** (soit **brut ≥ 5,45 %** : après IRVM 12 % + conservation 0,80 %/an).
- **PER ≤ 14**.
- Exclusions automatiques : rendement > 30 % (dividende exceptionnel suspect), PER > 50 (bénéfice quasi nul).
- **Compléments de fiabilité (encodés dans `noyau-check` depuis le 25/09/2026)** :
  régularité du dividende ≥ 4 années sur 5, croissance du dividende ≥ −10 %/an,
  liquidité ≥ 5 M F/j, borne haute du rendement net ≤ 10 % (anti-dividende exceptionnel).

### 3.2 Prix d'entrée et de sortie
- **Prix d'entrée** = `dps × (1 − 12 %) / (4 % + 0,80 %)` → acheter en dessous.
- **Prix de sortie** = rendement net tombé à **2 %**.

### 3.3 Titres retenus (exercice 2025, dps officiels brvm.org)

| Code | Société | DPS brut | Cours | Net | Entrée (4 % net) |
|---|---|---|---|---|---|
| SOGC | SOGB (caoutchouc) | 570 | 7 915 | 5,54 % | 10 450 |
| SGBC | SocGen CI | 2 606 | 39 000 | 5,08 % | 47 777 |
| BOAS | BOA Sénégal | 511 | 7 700 | 5,04 % | 9 368 |
| SNTS | Sonatel | 1 977 | 32 000 | 4,64 % | 36 245 |
| SLBC | Solibra | 2 127 | 37 400 | 4,20 % | 38 995 |
| PALC | PalmCI | 502 | 8 980 | 4,12 % | 9 196 |

**Exclus du noyau (value traps confirmés)** : STBC / FTSC — dividende exceptionnel
non récurrent + bénéfices en chute.

**Soutenabilité (payout) — garde-fou systématique** : vérifiée à chaque décision via
`limits` (colonne payout) et `sustain` (alerte), plus le cron quotidien. État actuel :
**SOGC = payout 105 % → value trap, à écarter** ; **BOAS = 84 % → tendu, surveiller** ;
SGBC/SLBC/SNTS/PALC sains. Un payout > 100 % signifie un dividende non couvert par les
bénéfices → risque de coupe, même si le rendement affiché paraît élevé.

### 3.4 Sortie & gestion de position

**Sorties fondamentales (vente totale)** — la thèse « revenu » est morte :
1. **Dividende coupé > 50 %** ou suspendu → sortir.
2. **PER > 40** → sortir (décote résorbée ou bénéfices en chute).
3. **Prix de sortie atteint** (rendement net ≤ 2 %) → vendre.

Une simple baisse de cours **n'est pas** un déclencheur de sortie.
Voir le contre-exemple documenté : [cas-value-etit.md](cas-value-etit.md).

**Alertes hiérarchisées (pas de vente automatique, sauf sortie)** :

| Niveau | Déclencheur | Action |
|---|---|---|
| **1 — Information** | variation modérée | « rien à faire » (console uniquement) |
| **2 — Décisionnel** | plus-value ≥ **seuil par titre** (13 % SNTS · 10 % SGBC · 5 % SLBC · 5 % PALC — mode **informatif**) · moins-value ≥ −10 % · échéance 3 ans | info chiffrée (les seuils de vente n'appellent plus de vente tant qu'aucune borne basse n'atteint 50 % — `docs/DECISION-2026-10-08-seuils-vente.md`) ou CONSERVE, chiffré |
| **3 — Fondamental** | payout > 80 % (tendu) / > 100 % (non couvert) | RISQUE DE COUPE DU DIVIDENDE — surveillance renforcée |

> Mis à jour le 12/10/2026 (audit, CONFLIT-03) : le « +13 % » unique a été remplacé par les
> **seuils par titre** de la décision du 08/10 (`data/profit_thresholds.json`), tous en mode
> **informatif** — le code et la décision datée concordent ; cette IPS suivait l'ancienne règle.

- **Soutenabilité (garde-fou anti value-trap)** : payout = dividende ÷ BPA
  (BPA = prix ÷ PER). > 80 % = tendu, > 100 % = non couvert par les bénéfices
  → risque de coupe. Détecte le value trap *avant* la coupe, car la baisse du
  cours la précède souvent.
- **Plus-value ≥ seuil par titre** (13 % SNTS · 10 % SGBC · 5 % SLBC · 5 % PALC) :
  mode **informatif** — bénéfice net après courtage affiché, ou CONSERVE pour le dividende
  net/an. Reco : rendement net ≥ 4 % → conserver (décision 08/10, cf. ci-dessus).
- **Moins-value ≥ −10 %** : CONSERVE — perte couverte en ~N ans de dividendes nets.
- **Échéance 3 ans** → réévaluer la thèse (alerte, pas clôture auto).

Structure de chaque alerte : TITRE → PERFORMANCE → ACTION (avec ordre limite précis :
« vends à ≥ X F » / « renforce à ≤ X F ») → CHIFFRES → ALTERNATIVE → PROCHAINE
VÉRIFICATION. Telegram reçoit les niveaux 2-3 + sorties ; le niveau 1 reste en
console. Anti-spam : 7 jours/position (sorties toujours envoyées).

**Renforcement & plafonds de poids (décision du 12/10/2026 — question Q4 de l'audit)**
- Un renforcement « limité » plafonne le poids d'**ACHAT** à `MAX_BUY_WEIGHT = 0,40`
  (40 % du portefeuille) : c'est lui qui détermine le **nombre d'actions conseillé**
  (`max_qty`) affiché dans l'alerte.
- Poids marché : `MAX_POSITION_WEIGHT = 0,35` (informe, gradué au-delà) ·
  `MAX_MARKET_WEIGHT = 0,50` (ligne Buffett : jamais plus de la moitié dans un seul titre,
  avertissement final). Ces trois valeurs sont **confirmées** et protégées par un test
  (`tests/test_regles_centralisees.py::test_max_buy_weight_confirme_et_inscrit_dans_l_ips`).

---

## 4. Poche spéculative (10 %)

### 4.1 Signaux d'entrée (breakout = déclencheur)

**Déclencheur (obligatoire) :**
1. **Breakout 20j** : cours au-dessus du plus haut des 20 derniers jours.

**Confirmations (confluence totale ≥ 3 signaux) :**
- momentum (20j > +10 % ou 60j > +20 %)
- RSI 50–70
- golden cross (EMA20 > EMA50) — **confirmation de tendance, PAS déclencheur**.

**Volume ≥ 2× la moyenne 20j — INFORMATION seule (décision du 12/10/2026, Q3 de l'audit)** :
il n'est **plus** un déclencheur requis ni un point de confluence — la mesure
(`docs/CHALLENGE-MULTI-MODELES.md`, p = 0,44) montre qu'il n'apporte rien. Il reste
**affiché** dans `spec screen` (mention « [info: …] ») pour la lecture humaine, jamais compté.
*(Pour la veille spé « durée », un filtre volume distinct existe : séance ≥ médiane
60 jours à la cassure — décision du 25/09.)*

**Pourquoi le golden cross n'est plus un déclencheur :** c'est un signal
*tardif* — la moyenne courte met des semaines à rattraper la moyenne longue, donc
il constate une hausse déjà largement faite. Le breakout détecte le *début* du
mouvement. Backtest (17/08) : BICB détecté à 5 720 F le 10/06 via breakout, contre
~8 000 F via golden cross. Le golden cross est conservé comme simple confirmation.

### 4.2 Sortie (MÉCANIQUE, par pourcentage — non négociable)
- **Stop-loss initial : −15 %**.
- **+20 %** → vendre ⅓, stop → **break-even**.
- **+35 %** → vendre ⅓, stop suiveur → **−10 % du plus haut**.
- **+50 %** → clôture finale.

---

## 5. Obligations UEMOA — **ARCHIVÉ** (poche retirée le 03/09/2026)

> ⚠️ **Section HISTORIQUE — ne plus s'y référer pour une décision.** La poche obligataire a
> été retirée le 03/09/2026 (voir la décision en §2 : stratégie actions uniquement). Le
> contenu ci-dessous est conservé pour mémoire (audit, CONFLIT-02). Le module `bond` reste
> disponible en manuel, hors stratégie.

Critère : coupon ≥ 6 %, émetteur souverain solide, au pair ou en décote, échéance ≤ 3 ans.

| Code | Émetteur | Coupon | Échéance | Cours |
|---|---|---|---|---|
| SNTS.O2 | Sonatel | 6,50 % | 2027 | 100 |
| EOS.O15 | État Sénégal | 6,25 % | 2029 | 100 |
| TPCI.O34 | État Côte d'Ivoire | 6,00 % | 2029 | 98 |

Évités : primes fortes (> 110), Mali/Burkina (risque politique). **Buy & hold jusqu'à échéance.**

---

## 6. Liquidités (30 %)

> Titre corrigé le 12/10/2026 (audit, CONFLIT-01) : 30 % conformément à la décision
> du 03/09/2026 en §2 — « 15 % » était un reste de l'allocation d'avant la suppression
> de la poche obligataire.

Réserve pour **échelonner** les achats du noyau via ordres limites (remplir le
portefeuille sur 3–6 mois, pas en un jour) et saisir les opportunités value.

---

## 7. Fiscalité & frais (Côte d'Ivoire)

| Poste | Taux |
|---|---|
| IRVM dividendes (retenue à la source) | 12 % (pers. physiques) |
| Courtage Bridge Securities | 0,80 %/ordre (min 1 000 FCFA) |
| Conservation | 0,20 %/trimestre = 0,80 %/an (min 2 500 FCFA/trim) |

**Rendement net = brut × 0,88 − 0,80 %.**

L'IRVM 12 % est confirmé par le BOC BRVM du 15/06/2026 (« IRVM applicable de
12 % »). Historique : 10 % (2019) → 15 % (début 2025) → 12 % (2026). À re-vérifier
sur un avis de paiement réel (net vs brut) via Bridge Securities.

---

## 8. Suivi & automatisation

- **Cron quotidien 09:00** (`BridgeBank check quotidien`) : annonces BRVM du noyau,
  sorties fondamentales + alertes de gestion (soutenabilité, plus/moins-value),
  candidats d'entrée spéculative, stops.
- **Alertes Telegram** (`@Bridgebank91Bot`) : uniquement en cas d'événement (silencieux sinon).
- Sources de vérité : **avis officiels brvm.org** (dividendes) > afx.kwayisi.org (fallback).
- Logs : `logs/daily.log` ; états persistés dans `data/`.

---

## 9. Gouvernance & révision

- **Décisions finales : LEO.** L'outil conseille, n'exécute pas d'ordre.
- **Révision trimestrielle** de l'IPS (allocation, seuils, titres).
- **Révision immédiate** si : garde-fou global **−25 %** atteint, changement de
  fiscalité, ou un titre du noyau déclenche une sortie fondamentale.
- Les dps officiels sont à **mettre à jour à chaque avis de dividende** brvm.org
  (actuellement exercice 2025).

---

## 10. Risques & limites (esquisse — à compléter)

- **Concentration UEMOA / FCFA** : 100 % du portefeuille en FCFA, corrélé à la zone.
- **Risque de change** : FCFA arrimé à l'EUR ; toute dévaluation UEMOA affecte tout.
- **Liquidité BRVM** : faible, surtout sur les petites capitalisations.
- **Survivorship bias** du backtest (seuls les titres encore cotés sont testés).

*Section à compléter dans la tâche dédiée « risque pays/change ».*
