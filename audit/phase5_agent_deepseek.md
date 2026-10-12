# Phase 5 — Audit financier par recalcul indépendant (Agent DeepSeek)

**Agent** : DeepSeek (deepseek-v4-pro) — sous-agent indépendant, jamais vu ce code
**Date** : 2026-10-12 · **Périmètre** : frais/taxation, net_yield, prix d'entrée/sortie,
DRIP, paliers/stops, déclencheurs, biais temporels (A3-01/A3-02)
**Méthode** : dérivation posée → calcul en mémoire (`python -c`) → comparaison au code →
verdict CONFIRMÉ / ÉCART (ampleur). Aucune écriture disque hors ce rapport, aucun appel
réseau, aucune modification du projet.

---

## Synthèse — écarts classés par sévérité

| Sévérité | Finding | Ampleur vérifiée |
|---|---|---|
| **MAJEUR (P1)** | A3-01 — colonne TTM jamais écartée (branche morte) → BPA décalés d'un an | 12/47 titres BPA 2024==2025, dont 10 `bpa_fiable=True` |
| **MAJEUR (P1)** | A3-02 — BPA « connu » au 1ᵉʳ janvier N+1, pas ~avril | look-ahead 3–6 mois sur tous les PER/payout |
| **MINEUR** | B1-08 / C6 — deux formules de prix d'entrée (÷1,014 vs sans frais) | 1,381 % d'écart (500,42 F sur SNTS) |
| **MINEUR** | B1-03 — DRIP comptabilise le dividende BRUT (sans IRVM) | 626,40 F surestimés (dps 1740 × 3 actions) |

**Conforme sans écart** : frais 1,40 % · net_yield = brut×0,88−0,008 · gross_yield_for_net(4 %)
= 5,4545 % · paliers/stops −15/+20/+35/+50/suiveur −10 % · PER>40 → vente · prix de sortie
= net 2 % · payout >80/>100 %.

---

## 1. Frais & taxation — CONFIRMÉ

**(a) Dérivation.** Courtage 0,80 % + TVA 18 % sur le courtage + frais BRVM 0,456 %.
Total par sens = 0,008 × (1 + 0,18) + 0,00456.

**(b) Calcul.**
```
0,008 × 1,18   = 0,00944
+ 0,00456      = 0,014000  = 1,40 %
```

**(c) Comparaison au code.** `taxation.py:29` : `BROKERAGE_FEE = BROKERAGE_RATE * (1 + TVA_RATE) + BRVM_FEES_RATE`
= 0,008 × 1,18 + 0,00456 = 0,014. `regles.py:56` : `FRAIS_PAR_SENS = BROKERAGE_FEE  # 0,014`.
L'aller-retour dérivé `FRAIS_ALLER_RETOUR = 2 × FRAIS_PAR_SENS = 0,028` est cohérent.

**(d) Verdict : CONFIRMÉ conforme.** Le total annoncé « ~1,40 % » est exact au 3ᵉ chiffre décimal.

---

## 2. net_yield et gross_yield_for_net — CONFIRMÉ

**(a) Dérivation.** Rendement net = brut × (1 − IRVM 12 %) − conservation 0,80 %/an.
Pour un net cible n, le brut requis = (n + 0,008) / (1 − 0,12) = (n + 0,008) / 0,88.

**(b) Calcul.**
```
net_yield(0,0545454…) = 0,0545454 × 0,88 − 0,008 = 0,048 − 0,008 = 0,040000 ✓
gross_yield_for_net(0,04) = 0,048 / 0,88 = 0,05454545… = 5,4545 % ✓ (l'énoncé « 5,4545 % »)
gross_yield_for_net(0,02) = 0,028 / 0,88 = 0,031818… = 3,1818 %
```

**(c) Comparaison au code.** `taxation.py:59-66` : `net_yield(g) = g*(1-IRVM) − CUSTODY_ANNUAL`
(avec `CUSTODY_ANNUAL = 0,002×4 = 0,008`), `gross_yield_for_net(n) = (n+CUSTODY_ANNUAL)/(1-IRVM)`.
IPS §7 : « Rendement net = brut × 0,88 − 0,80 % » et §3.1 « brut ≥ 5,45 % » — identiques.

**(d) Verdict : CONFIRMÉ conforme.** net_yield(5,4545 %) = 4,0000 % exact ; le 0,88 = 1−12 %
et le « −0,80 pt » = conservation annuelle. Aucune erreur de signe ni d'unité.

---

## 3. Prix d'entrée/sortie — ÉCART (deux formules, 1,381 %)

**(a) Dérivation.** Deux formules coexistent dans le code :
- `entry_price_ref` (portfolio.py:162) = dps / DIV_YIELD_ENTRY = dps / gross_yield_for_net(4 %)
  → **sans** frais de transaction. C'est la formule de l'IPS §3.2.
- `entry_price_for_net` (taxation.py:78) = dps / gross_yield_for_net(4 %) **÷ (1 + BROKERAGE_FEE)**
  → **avec** frais (÷ 1,014). Utilisée par `orders.py:48`, `noyau_check.py:67`, `portfolio.py:679`.

**(b) Calcul (SNTS, dps = 1977).**
```
entry_price_ref      = 1977 / 0,05454545 = 36 245,00 F   (= table IPS « SNTS 36 245 »)
entry_price_for_net  = 36 245 / 1,014    = 35 744,58 F
écart                = 500,42 F = 1,381 %  (= 1 − 1/1,014)
```

**(c) Comparaison au code.** Confirmé : `DividendPosition.__post_init__` (portfolio.py:161-162)
calcule `entry_price_ref = dps/DIV_YIELD_ENTRY` SANS division par (1+0,014), alors que
`entry_price_for_net` divise par (1+BROKERAGE_FEE). Deux valeurs, une seule notion.

**(d) Verdict : ÉCART MINEUR confirmé** (finding B1-08/C6). Ampleur exacte 1,381 %, dans le
sens « la formule avec frais donne un prix d'entrée plus bas ». Impact limité : les deux
servent de seuil indicatif « acheter en dessous », jamais d'ordre automatique. C'est une
incohérence documentaire/duplication (C6), pas un biais de décision.

---

## 4. DRIP — ÉCART (dividende brut comptabilisé, +626,40 F)

**(a) Dérivation.** `record_dividend` (portfolio.py:546-559) : `cash = pos.dps * pos.quantity`
— le montant BRUT. Un dividende réel est crédité NET d'IRVM 12 % : net = dps × qty × 0,88.

**(b) Calcul (cas demandé : dps 1740, 3 actions, IRVM 12 %).**
```
cash brut comptabilisé = 1740 × 3 = 5 220,00 F
cash net réel          = 5 220 × 0,88 = 4 593,60 F
écart                  = 626,40 F   (= 12 % de 5 220)
```

**(c) Comparaison au code.** portfolio.py:553 : `cash = pos.dps * pos.quantity` — aucun
`(1 − IRVM_DIVIDEND_TAX)`. `pos.dividends_earned += cash` (l.556) accumule donc le brut.

**(d) Verdict : ÉCART MINEUR confirmé** (finding B1-03). L'écart attendu de **626,40 F** est
reproduit exactement. Conséquence : `dividends_earned` surestime le revenu de 13,64 %
(= 0,12/0,88) à chaque versement. Le réinvestissement (`new_shares = cash // price`) achète
aussi trop d'actions. Le solde de cash et la valeur finale du portefeuille simulé sont
surévalués.

---

## 5. Paliers & stops — CONFIRMÉ

**(a) Dérivation.** Lecture directe des constantes de `src/strategie/speculation.py:37-41`.

**(b)/(c) Comparaison au code.**

| Constante | Code | Valeur | IPS §4.2 |
|---|---|---|---|
| Stop-loss initial | `STOP_LOSS = 0.15` | −15 % | −15 % ✓ |
| Palier 1 | `TAKE_1 = 0.20` | +20 % → vendre ⅓, stop→break-even (entry) | +20 % ✓ |
| Palier 2 | `TAKE_2 = 0.35` | +35 % → vendre ⅓, stop suiveur −10 % du plus haut | +35 % ✓ |
| Palier 3 | `TAKE_3 = 0.50` | +50 % → clôture finale | +50 % ✓ |
| Suiveur | `TRAILING = 0.10` | −10 % du plus haut | −10 % ✓ |

Vérifications de logique : `check_position` (l.194) `price >= entry*(1+TAKE_1)` → `stop_loss = entry_price`
(break-even). l.202 : après +35 %, `stop_loss = highest*(1−TRAILING)`. l.206 : `>= entry*1.50` → clôture.
`remaining` (l.160-166) : 1/3 vendu à +20, 1/3 à +35, dernier tiers à +50. Cohérent.

**(d) Verdict : CONFIRMÉ conforme.** Aucune inversion, aucun seuil fantôme. La fraction
vendue `SELL_FRACTION = 1/3` (regles.py:87) correspond au « ⅓ » de l'IPS.

---

## 6. Déclencheurs de sortie — CONFIRMÉ (2 cas numériques)

**(a) Dérivation.** Trois sorties fondamentales (portfolio.py:488-509) + soutenabilité
(portfolio.py:376-405), confrontées à IPS §3.4.

**Cas n°1 — PER explose (PER > 40 → VENDS TOUT).**
- Code (portfolio.py:500-503) : `if current_per > PER_EXPLODE` avec `PER_EXPLODE = 40.0` (l.55).
- Cas : SNTS, `current_per = 45` → `45 > 40` ⇒ `pos.closed = True`, `close_reason = "PER 45.0 > 40"`.
- IPS §3.4.2 : « PER > 40 → sortir ». **CONFORME.**

**Cas n°2 — prix de sortie (net ≤ 2 %) + payout.**
- `exit_price = dps / DIV_YIELD_EXIT` (portfolio.py:160), `DIV_YIELD_EXIT = gross_yield_for_net(0,02) = 0,031818`.
- Cas SNTS : `exit_price = 1977 / 0,03181818 = 62 134,29 F`. À ce prix, `net_yield(1977/62134,29) = 0,031818×0,88 − 0,008 = 2,0000 %`.
  ⇒ déclenchement `current_price >= 62 134` ⇔ net ≤ 2 %. IPS §3.4.3 « rendement net ≤ 2 % → vendre ». **CONFORME.**
- Payout (`payout_ratio = dps × per / price`, l.366-373) : cas dps 1000, cours 10 000, PER 12
  → payout 1,20 = 120 % > 1,00 ⇒ « non couvert » ; PER 9 → payout 0,90 = 90 % > 0,80 ⇒ « tendu ».
  Seuils `PAYOUT_CRITICAL = 1,00` / `PAYOUT_TIGHT = 0,80` (regles.py:68-69). IPS §3.4 niveau 3 :
  « payout > 80 % (tendu) / > 100 % (non couvert) ». **CONFORME.**

**(d) Verdict : CONFIRMÉ conforme.** Les trois déclencheurs et les deux seuils de payout sont
exactement ceux de l'IPS, sans dérive de seuil ni condition inversée.

---

## 7. Biais temporels — reproduction des P1 A3-01 / A3-02

### A3-01 — colonne TTM jamais écartée : **CONFIRMÉ (majeur)**

**(a) Dérivation.** `extraire_bpa` (fondamentaux_historiques.py:198-219) lit les cellules
numériques de la ligne « Earnings Per Share » en s'arrêtant dès que
`len(valeurs) >= len(ordre)`. Le test censé écarter le TTM exige ensuite
`len(valeurs) == len(ordre) + 1` — condition **mathématiquement impossible** après ce `break`.

**(b) Calcul / démonstration.** La boucle `break` dès que `len(valeurs) == len(ordre)` ;
donc à la sortie, `len(valeurs) ≤ len(ordre)`, jamais `len(ordre) + 1`. La branche
`if len(valeurs) == len(ordre) + 1: valeurs = valeurs[1:]` (l.218-219) est du **code mort**.
Si la ligne commence par une colonne TTM, chaque valeur est associée à l'année +1 et la
dernière année est perdue.

**(c) Preuve par les données** (`data/fondamentaux_historiques.json`, lecture seule) :
12 titres sur 47 ont **BPA 2024 == BPA 2025 au centime** — signature TTM(=dernier FY) + FY2025
lus comme deux exercices :

| Titre | BPA (2024=2025) | bpa_fiable |
|---|---|---|
| ABJC | 121,98 | ✅ |
| BOAB | 496,00 | ✅ |
| CABC | 287,91 | ✅ |
| CFAC | 46,40 | ✅ |
| CIEC | 233,93 | ✅ |
| ORAC | 857,10 | ✅ |
| PALC | 1003,19 | ✅ |
| SIVC | 20,53 | ✅ |
| SOGC | 578,31 | ✅ |
| TTLS | 208,09 | ✅ |
| NTLC | 16698,29 | ❌ |
| SAFC | 2158,25 | ❌ |

**10 déclarés `bpa_fiable=True`** — identique à la liste et au décompte du finding A3-01.
Une égalité stricte entre deux exercices consécutifs n'est pas plausible naturellement ;
c'est le décalage d'un an annoncé. Le contrôle croisé `valider_bpa` ne le détecte pas (il ne
compare que la colonne la plus récente à un PER actuel, tolérance 40 %).

**(d) Verdict : CONFIRMÉ, P1.** Le module censé supprimer le look-ahead le réintroduit :
les BPA de 10 titres « fiables » sont étiquetés un an en avance.

### A3-02 — publication supposée au 1ᵉʳ janvier N+1 : **CONFIRMÉ (majeur)**

**(a) Dérivation.** `bpa_connu` (l.317-336) : `annee = int(date[:4])`, puis
`if a + DECALAGE_PUBLICATION_BPA <= annee` avec `DECALAGE_PUBLICATION_BPA = 1` (l.56).

**(b) Calcul.** Un BPA d'exercice 2024 (a=2024) est accepté dès que
`2024 + 1 <= annee`, soit `annee >= 2025` — donc dès le **2025-01-01**, alors que la
docstring (l.55-56) et le module annoncent « publié vers avril N+1 » (voire après l'AG,
mai-juillet d'après les ex-dates de dividendes du cache).

**(c) Comparaison.** La condition est sur l'**année seule**, pas sur une date (aucun
`date >= f"{a+1}-06-30"`). Un titre évalué en janvier-mars utilise un BPA inconnu du marché.

**(d) Verdict : CONFIRMÉ, P1.** Look-ahead de 3 à 6 mois sur tous les PER/payout du
challenge ; cumulé avec A3-01 (années décalées), l'information employée peut avoir
~1 an et 3 mois d'avance. Le docstring « Sans ces règles, on remplace un look-ahead par
un autre » décrit exactement le défaut que le code commet.

---

## Confirmé conforme (récapitulatif)

1. Frais par sens : 0,80 % + TVA 18 % + BRVM 0,456 % = **1,40 %** exact.
2. `net_yield` = brut × 0,88 − 0,008 ; IPS §7 identique.
3. `gross_yield_for_net(4 %)` = **5,4545 %** (et 3,1818 % pour la sortie).
4. Paliers/stops −15 % / +20 / +35 / +50 % / suiveur −10 % — conformes à IPS §4.2.
5. PER > 40 → vente totale — conforme IPS §3.4.
6. Prix de sortie = net 2 % (62 134 F pour SNTS, rendement net exactement 2,0000 %).
7. Payout > 80 % (tendu) / > 100 % (non couvert) — conforme IPS §3.4.

---

## Limites

- **Aucun test lancé, aucune exécution du code projet** (interdit par la mission) : verdicts
  de lecture + calculs indépendants en mémoire.
- **A3-01** : la preuve « colonne TTM décale les années » repose sur la branche morte (lecture
  statique) et sur 12 doublons exacts de BPA ; le HTML source de stockanalysis.com n'a pas été
  re-scrapé (réseau interdit) — l'hypothèse « TTM » reste une inférence forte, corroborée par
  les données.
- **A3-02** : l'ampleur exacte (3 vs 6 mois) dépend de la date réelle de publication/AG par
  titre, non disponible dans le cache ; le sens du biais (connaissance prématurée) est certain.
- Les frais « 1,40 % » sont vérifiés arithmétiquement ; leur calibration sur les CMP réels
  (ex. SGBC) relève du relevé Bridge Bank, hors de ce recalcul.
- Le plancher de courtage 1 000 F et le « max 1 % » de la grille ne sont pas re-vérifiés ici
  (aucun ordre réel consultable).

---

**Bilan** : 2 écarts majeurs (A3-01, A3-02) · 2 écarts mineurs (B1-08/C6, B1-03) ·
7 points conformes.
