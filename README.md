# BS Trade Analyzer — BRVM

Outil local de **screening** et **alertes personnalisées** pour la Bourse Régionale
des Valeurs Mobilières (BRVM), basé sur l'API publique de la plateforme
[BS Trade](https://bstrade.bridge-securities.com/) (Bridge Securities).

✅ **Aucun compte requis** : les données de marché (cours temps réel, historique,
volumes) sont publiques via l'API interne `BSTradeServer/MarketDetails.aspx`.

## Installation

```bash
cd "C:\Users\LEO\projects\Bridge Bank"
python -m pip install -r requirements.txt
```

Python 3.11+ requis.

## Commandes

| Commande | Description |
|---|---|
| `python -m src.main top` | Top hausses / baisses du jour |
| `python -m src.main screen --top 15` | Screening complet : score par titre (tendance, RSI, momentum, volumes) |
| `python -m src.main analyze SIVC` | Fiche détaillée d'un titre (indicateurs + signaux) |
| `python -m src.main watch add SIVC --max 2600 --min 2200 --var 5` | Surveiller un titre (seuil haut / bas / variation %) |
| `python -m src.main watch list` / `watch remove CODE` | Gérer la watchlist |
| `python -m src.main alert --once` | Vérifier les alertes une fois |
| `python -m src.main alert --loop --interval 300` | Boucle continue (toutes les 5 min) |
| `python -m src.main radar` | Radar de veille « sortie de fond » — détection précoce, ZÉRO trading |

Exemples de codes : `SIVC` (Air Liquide), `UNLC` (Unilever), `BOAC` (Bank of Africa CI),
`NTLC` (Nestlé), `SGBC` (Société Générale), `SNTS` (Sonatel), `PALC` (Palmafrique)…

## Alertes Telegram

1. Dans Telegram, ouvrez **@BotFather** → `/newbot` → choisissez un nom → notez le **token**.
2. Envoyez un message à votre nouveau bot (n'importe quoi).
3. Récupérez votre **chat_id** :
   ```bash
   python -c "import requests; print(requests.get(f'https://api.telegram.org/bot<TOKEN>/getUpdates').json())"
   ```
   → le `chat.id` dans le premier message.
4. Configurez dans `config.yaml` (ou créez `.env` depuis `.env.example`) :
   ```yaml
   telegram:
     bot_token: "123456:ABC-..."
     chat_id: "123456789"
   ```
5. Testez : `python -m src.main alert --once` (déclenchez un seuil volontairement).

## Spéculation (poche à risque, 10 % du capital)

Détecte les signaux d'entrée techniques et gère les positions avec sortie mécanique.

| Commande | Description |
|---|---|
| `python -m src.main spec screen --min 3` | Candidats spéculatifs (breakout 20j + volume requis) — MANUEL, poche suspendue |
| `python -m src.main spec alert --min 3` | Nouveaux candidats (entrée) + alerte Telegram — MANUEL |
| `python -m src.main spec open NSBC --amount 100000` | Ouvrir une position (stop défini auto) — MANUEL |
| `python -m src.main spec status` | Positions ouvertes, stop, performance |
| `python -m src.main spec check` | Vérifier stops/paliers + notif Telegram |
| `python -m src.main spec close NSBC` | Clôture manuelle |

**Règle IPS appliquée** : les poches sont étanches. `spec open` refuse un titre
déjà détenu dans le noyau dividende, et `portf open` refuse un titre détenu en
spéculation (sauf si la position de l'autre poche est déjà clôturée).

**⛔ Spéculation SUSPENDUE le 26/08/2026 (décision LEO).** L'épreuve des points morts
a démontré : (H2) le volume ≥ 2× est un placebo prédictif (p = 0,44 sur 6 612
breakouts) ; (H4) les frais réels (min 1 000 F/ordre) rendent le net médian NÉGATIF
sous 150 000 F/position (balayage : 70 000 F → −0,7 % ; 150 000 F → +1,1 % ;
`scripts/spec_size_sweep.py`). La poche 10 % (~70 000 F) étant structurellement sous
le seuil, les alertes spéculation sont retirées du check quotidien et le cron 16h
supprimé. **Réactivation** : position ≥ 150 000 F ET déclencheur réellement
prédictif. Les modules restent disponibles en CLI manuelle.

**Détection d'entrée** — déclencheur obligatoire + confirmations :

- **Déclencheur (obligatoire)** : **breakout 20j** (cours au-dessus du plus haut des
  20 derniers jours) **+ volume ≥ 2×** la moyenne (valide la cassure — sans
  volume, c'est un faux breakout).
- **Confirmations (≥ 1 requise)** : momentum (+10 %/20j ou +20 %/60j), RSI 50-70,
  golden cross (EMA20 > EMA50).

Le **golden cross ne déclenche plus l'entrée** : c'est un signal *tardif* (il
constate une hausse déjà faite). Le breakout détecte le *début* du mouvement —
backtest : BICB détecté à 5 720 F (10/06) contre ~8 000 F via golden cross.

**Règles de sortie mécaniques (non négociables)** :
- stop-loss initial **−15 %**
- **+20 %** → vendre ⅓, stop → break-even
- **+35 %** → vendre ⅓, stop suiveur → −10 % du plus haut
- **+50 %** → clôture finale

**Zone morte (ni +20 % ni −15 % atteints)** — validée par backtest 9 ans
(1 519 entrées simulées) : **pas de clôture automatique** — les inertes à J+60
montent ensuite dans 62 % des cas en régime récent 2023-2026 (médiane nette
+4,4 % après frais, vs −1,4 % sur 2017-2022 : la conservation est neutre à
positive, la revue régulière reste justifiée).
Mention d'info dans `spec status` dès 60 séances ; alerte « 🔍 REVUE » unique à
~120 séances (~6 mois) pour vérifier que le setup reste valide (clôture
manuelle possible : `spec close CODE`).

**Frais et rendements NETS (validation out-of-sample, 21/08)** : la simulation
complète de la règle (frais 1,4 % par ordre) donne, sur 702 entrées 2023-2026,
un rendement net médian de **+1,4 %** (moyen +3,6 %, 52 % gagnants) — contre
−2,8 % médian sur 2017-2022. La stratégie spéculation a une espérance nette
légèrement positive en régime récent, jamais un jackpot : son rôle est le
contrôle du risque (stop −15 %), d'où le plafond de poche à 10 %.
Les paliers affichés (+20/+35/+50 %, stop −15 %) sont des DÉCLENCHEURS BRUTS ;
nets de frais ils valent ≈ +18,6/+33,6/+48,4 % et −16,4 %.

**⚠️ Frais réels des petits ordres (épreuve 21/08)** : Bridge facture un MINIMUM
de 1 000 F/ordre. Sur une poche de 70 000 F, l'entrée paie 2,1 % et chaque vente
⅓ (23 333 F) paie **5,5 %** → l'espérance nette de la spéculation tombe à ≈ 0
(médiane −0,3 % sur 2023-2026, −4,3 % sur 2017-2022). Pour que la structure
« 3 ventes de ⅓ » reste rentable, les positions doivent faire ≥ 100-150 000 F.
Sous 70 000 F, la spéculation est un apprentissage, pas un moteur de rendement.

**Check de clôture 16h** (ajouté 21/08) : `scripts/close_check.py` + cron Hermes
`5 16 * * 1-5` — détecte les candidats validés à la clôture du jour et alerte
« à jouer demain à l'ouverture » (un setup spéculatif vit ~24h ; le check de 09h
voit la veille et peut rater les signaux du jour). **Suspendu le 26/08 avec la
poche spéculation** (cron supprimé).

**Radar de veille « sortie de fond »** (ajouté 01/09, `src/radar.py`) : les 65
triplements BRVM de 9 ans partent d'un fond (distance ATH médiane −94 %) et le
signal +30 %/120j les précède de ~76 séances. Le radar détecte deux niveaux
(SORTIE DE FOND : r60 ≥ +15 % ET r120 ≥ +30 % ET ATH ≤ −80 % ; ACCUMULATION :
r60 ≥ +10 % ET r120 ≥ +20 % ET ATH ≤ −50 %). **Veille fondamentale uniquement,
jamais un ordre** — l'épreuve du momentum extrême a démontré que suivre ces
mouvements net de frais ne bat pas le hasard.

Les positions sont persistées dans `data/spec_positions.json`.

## Noyau dividende (60 % du capital)

| Commande | Description |
|---|---|
| `python -m src.main portf open SNTS --dps 1740 --per 7.74` | Ouvrir une position (prix entrée/sortie auto) |
| `python -m src.main portf status` | Positions, rendement, prix de sortie, durée |
| `python -m src.main portf check` | Sorties fondamentales + alertes plus/moins-value + notif Telegram |
| `python -m src.main portf dividend SNTS` | Verser + réinvestir le dividende (DRIP) |
| `python -m src.main portf close SNTS` | Clôture manuelle |
| `python -m src.main limits` | Ordres limites + payout (prix d'achat net 4 %, anti value-trap) |
| `python -m src.main sustain` | Soutenabilité des dividendes (payout) + alerte Telegram |
| `python -m src.main news` | Annonces officielles BRVM sur le noyau (dividendes, AG, dirigeants) |
| `python -m src.main news --check` | Détecter les nouveautés + alerte Telegram |

Règles : prix d'entrée (rendement **net** 4 %) et de sortie (**net** 2 %) calculés
depuis le dividende, net d'IRVM 12 % et des frais de conservation 0,80 %/an
(→ seuil brut ≈ 5,45 % à l'entrée). Durée 3 ans minimum. Dividendes réinvestis (DRIP).

**Sorties fondamentales (vente totale)** — la thèse « revenu » est morte :
dividende coupé > 50 % ou suspendu, PER > 40, prix de sortie atteint
(rendement net ≤ 2 %). Jamais de vente sur une simple baisse de cours.

**3 niveaux d'alerte hiérarchisés** — `portf check` émet :

| Niveau | Déclencheur | Action |
|---|---|---|
| **1 — Information** | variation modérée | « rien à faire » (console `portf status` uniquement) |
| **2 — Décisionnel** | plus-value ≥ +13 % · moins-value ≥ −10 % · échéance 3 ans | VENDS 1/3 (33 %) ou CONSERVE, chiffré |
| **3 — Fondamental** | payout > 80 % (tendu) / > 100 % (non couvert) | RISQUE DE COUPE DU DIVIDENDE — surveillance renforcée |
| **Sortie** | dividende coupé/suspendu · PER > 40 · net ≤ 2 % | 🔴 VENDS TOUT |

Structure de chaque alerte : TITRE → PERFORMANCE → ACTION (avec ordre limite précis :
« vends à ≥ X F » / « renforce à ≤ X F ») → CHIFFRES → ALTERNATIVE → 📜 HISTOIRE
(profil de retournement du titre sur 9 ans : % de baisse, creux, fenêtre de manœuvre —
si ≥ 8 épisodes fiables dans `data/reversal_profiles.json`) → PROCHAINE
VÉRIFICATION. Telegram reçoit les niveaux 2-3 + sorties ; le niveau 1 reste en
console. Anti-spam : 7 jours/position (sorties toujours envoyées).

## Obligations (15 % du capital)

Les obligations d'État UEMOA cotent à la BRVM avec un **nominal de 10 000 FCFA/titre**
et des cours en **% du nominal** (100 = au pair) — accessible au particulier,
contrairement à certaines émissions structurées (ex. BEFI-ALIOS, nominal ~20,8 M F).
(Établi le 20/08 à partir du carnet d'ordres BSTrade ; nominal à faire confirmer
par Bridge Securities avant le premier ordre.)

| Commande | Description |
|---|---|
| `python -m src.main bond` | Lignes achetables (offre vendeur) triées par rendement actuariel (YTM) |
| `python -m src.main bond ytm TPCI.O87 [--price 98]` | Rendement courant + actuariel d'une ligne |
| `python -m src.main bond buy TPCI.O87 --qty 10 --price 98` | Enregistrer un achat (positions dans `data/bonds_positions.json`) |
| `python -m src.main bond show` | Positions détenues, valeur, coupons annuels attendus |

- Référentiel du carnet : `data/bonds_market.json` (70 lignes, séance du 20/08/2026).
- **YTM** = coupon + gain/perte au remboursement (ex. TPCI 5,90 % achetée 98 → ~6,6 % ;
  achetée au-dessus de 100 → YTM négatif possible, ex. Pétro Ivoire à 130 → −2,7 %).
- Risque émetteur qualitatif (faible : CI/Sénégal/Bénin, institutions régionales ;
  élevé : Mali/Burkina/Niger).
- Positions intégrées au rapport mensuel (valeur + coupons/an) ; elles remplacent
  le montant forfaitaire hérité si des positions existent.
- **À vérifier avant ordre** : nominal exact, montant minimum, frais applicables,
  fiscalité des intérêts (les coupons d'emprunts d'État sont souvent exonérés,
  contrairement à l'IRVM 12 % des dividendes).

## Fiscalité & frais (Côte d'Ivoire)

Appliqués aux rendements dans tout l'outil (`src/taxation.py`) :

| Poste | Taux |
|---|---|
| IRVM dividendes (retenue à la source) | 12 % (pers. physiques) |
| Courtage Bridge Securities | 0,80 %/ordre (min 1 000 FCFA) |
| TVA (18 %) + frais BRVM (DC/BR) | ~0,60 %/ordre |
| **Total transaction** | **~1,40 %/ordre** (mesuré sur CMP réels) |
| Conservation | 0,20 %/trimestre = 0,80 %/an (min 2 500 FCFA/trim) |

Un rendement **net** de 4 % exige donc ≈ 5,45 % de rendement brut.

`src/taxation.py` expose `commission(montant)` : frais totaux décomposés
(courtage 0,80 % min 1 000 F + TVA 18 % + frais BRVM 0,456 %). Sur un ordre
moyen (≥ ~125 000 F), le taux effectif ≈ 1,40 % ; sur un petit ordre, le min
1 000 F fait grimper les frais (ex. 50 000 F → ~2,8 %).

**IRVM (12 %)** : confirmé par le BOC BRVM du 15/06/2026 (« IRVM applicable de
12 % »). Historique : 10 % (2019) → 15 % (début 2025) → 12 % (2026). À re-vérifier
sur un avis de paiement réel (net vs brut) via Bridge Securities.

**Plus-values de cession** : exonérées ou plafonnées à ~7 % selon la directive
02/2010/CM/UEMOA (application variable selon les pays). Le « bénéfice net » des
alertes de vente ne déduit que le courtage 0,8 % ; l'impôt éventuel sur la
plus-value n'est pas déduit (à confirmer selon le pays de résidence).

## Suivi des annonces BRVM

Le prix ne dit pas *quand* un dividende est annoncé ou coupé. Les **déclencheurs
fondamentaux** (dividende, AG, changement de dirigeants, notation) sont publiés
sur `brvm.org` sous forme de **PDF au nom normalisé** (`<date>_-_<type>_-_<societe>.pdf`).

`src/news.py` scrape les 5 pages d'annonces, mappe chaque société vers son code
BRVM, filtre sur le noyau et détecte les nouveautés (état persisté dans
`data/news_state.json`).

### BOC (Bulletin Officiel de la Cote) — source complète

Les pages ESV brvm.org ne listent pas les **rectificatifs** (ex. SERVAIR
124 → 229 F). Le **BOC** quotidien, relayé par les SGI (nsiacapital.com), contient
TOUTES les annonces, y compris les rectificatifs. `src/boc.py` télécharge le BOC
du jour, parse la section « Opérations en cours » (dividendes : émetteur, montant,
date) et détecte les **annonces** et **rectifications** sur le noyau (état dans
`data/boc_state.json`).

| Commande | Description |
|---|---|
| `python -m src.main boc` | Vérifie le BOC du jour et alerte (dividende annoncé/rectifié) |

Le BOC est la première étape du check quotidien (cron).

### Suivi des encaissements réels (avis BSTrade)

Les dividendes sont aussi **tracés réellement** (montant net crédité sur le
compte, lu sur l'« avis d'encaissement de dividendes » de BSTrade) pour
confirmer l'IRVM (12 % attendu) et piloter le DRIP. `src/dividends.py` →
`data/dividendes.json`.

| Commande | Description |
|---|---|
| `python -m src.main div add SGBC --amount 6880 --actions 3` | Enregistrer un net encaissé (calcule l'imposition implicite) |
| `python -m src.main div` | Lister les encaissements + total |

## Horaires de séance & délais d'exécution (Bridge Securities)

| Paramètre | Valeur | Source |
|---|---|---|
| Séance BRVM | **09h00 → 15h00** (Abidjan, GMT) | API BSTrade mode=1 |
| Ordre via BSTrade (le jour même) | jusqu'à **13h30** | Note @ORDERS |
| Ordre par courriel (@orders) | jusqu'à **11h** (après → J+1) | Note @ORDERS |
| Annulation d'ordre | sous **5 min**, par courriel, motivée | Note @ORDERS |
| Règlement / Livraison | **T+3** jours ouvrés (titres et espèces) | Note @ORDERS |
| Versement espèces | comptabilisé **J+1** | Procédure d'approvisionnement |

**Cours temps réel** : l'API BSTrade renvoie la clôture de la veille ; la source
publique en direct est brvm.org (page cours-actions), scrapée par `src/live.py`.

| Commande | Description |
|---|---|
| `python -m src.main live` | Cours temps réel de toutes les actions + état de la séance + variation vs veille |

## Automatisation quotidienne

Un cron Hermes (`BridgeBank check quotidien`) exécute chaque jour à 09:00 le
check complet : annonces + soutenabilité + **nouvelles opportunités
value+dividende** + sorties noyau + intégrité des données (spéculation suspendue
le 26/08/2026, ses étapes sont retirées) :
`scripts/bridgebank_daily.py` → `scripts/daily_check.py`, qui journalise dans
`logs/daily.log` et envoie les alertes Telegram en cas d'événement.

La détection value quotidienne signale un titre uniquement quand il **entre**
dans les critères (PER ≤ 14 + rendement net ≥ 4 %) par rapport au run
précédent (état `data/value_state.json`). Voir aussi
`python -m src.main fund value --alert` (manuel) et
`python scripts/refresh_history.py` (re-télécharge l'historique complet,
utile après l'admission de nouveaux titres à la cote).

| Commande | Description |
|---|---|
| `python -m src.main daily` | Check complet (annonces + déclencheurs de sortie + stops) |
| `python scripts/daily_check.py` | Idem, journalisé dans `logs/daily.log` (pour le cron) |

Alternative indépendante de Hermes : créer une tâche du Planificateur de tâches
Windows (nécessite un compte admin) pointant vers `scripts/daily_check.py`.

## Rapport mensuel (check-up, indépendant des alertes)

Un cron Hermes (`BridgeBank rapport mensuel`) exécute le **1ᵉʳ de chaque mois à
09:00** un bilan complet du portefeuille — même si aucune alerte n'a été
déclenchée : valeur totale, plus/moins-value, rendement net et payout par titre,
allocation vs cible IPS (avec alerte de concentration), spéculation, dividendes
perçus. L'évolution est comparée au snapshot précédent (stocké dans
`data/portfolio_state.json`).

| Commande | Description |
|---|---|
| `python -m src.main report` | Génère et envoie le rapport mensuel sur Telegram |
| `python -m src.main report cash --amount 118261` | Met à jour le solde de liquidités |
| `python scripts/report_check.py` | Idem, journalisé dans `logs/report.log` (pour le cron) |

Le solde de liquidités est la seule donnée non dérivable des positions : le
mettre à jour après chaque achat/vente (`report cash --amount X`) ou coller
l'écran BSTrade une fois par mois.

## Configuration

`config.yaml` :
- **watchlist** : seuils par titre (`max`, `min`, `change_pct`)
- **alerts** : `interval_seconds` (défaut 300), `cooldown_minutes` (30),
  `session_only` (alerter seulement en séance lun-ven 08h30-16h)

L'état des alertes déclenchées est persisté dans `data/alerts_state.json`
(évite les notifications en boucle pendant le cooldown).

## Architecture

```
src/
├── bsapi.py        → client API BS Trade (snapshot, historique)
├── models.py       → dataclasses (Quote, Snapshot, Analysis…)
├── screening.py    → indicateurs (RSI, EMA, momentum) + scoring + screening
├── fundamentals.py → scraping PER (brvm.org) + dividende/action (afx.kwayisi.org)
├── screener.py     → value+dividende, Magic Formula, value traps
├── portfolio.py    → noyau dividende (positions, sortie, DRIP)
├── orders.py       → ordres limites (prix d'achat pour un rendement net cible)
├── taxation.py     → fiscalité + frais BRVM (IRVM, courtage, conservation)
├── speculation.py  → poche spéculative (signaux, stops)
├── report.py       → rapport mensuel de santé (valeur, allocation, concentration)
├── alerts.py       → moteur d'alertes (watchlist, cooldown, séance)
├── notify.py       → envoi Telegram
└── main.py         → CLI
```

## Tests

Suite permanente (pytest) qui protège la logique critique contre les régressions :

```bash
python -m pytest
```

- `tests/test_speculation.py` : logique de sortie (stop, paliers, stop suiveur, persistance)
- `tests/test_screening.py` : indicateurs techniques + score

Dépendance de dev : `pytest` (installer via `uv pip install pytest`).

## Documentation

- `docs/IPS.md` — politique d'investissement (allocation, seuils, règles de sortie)
- `docs/cas-value-etit.md` — cas d'étude : achat value ETIT, sortie prématurée
- `docs/API-BSTrade.md` — carte des endpoints de l'API BS Trade

## Limites

- Données de marché (prix/volumes) via l'API publique BS Trade ; les fondamentaux
  (PER, dividende) sont scrapés depuis brvm.org et afx.kwayisi.org (lent, mis en cache).
- SSL du serveur BS Trade invalide → `verify=False` (données publiques, risque faible).
- Les alertes ne tournent que quand le script est lancé (`--loop`). Pour du
  24/7, lancer sur le VPS ou planifier avec le Planificateur de tâches Windows.
