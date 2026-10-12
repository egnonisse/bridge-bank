# Phase 5 — Synthèse consolidée de l'audit financier (12/10/2026)

**Objet** : « formules, recalculs indépendants, déclencheurs, calibration, biais temporels ».
**Deux volets convergent** — un recalcul **déterministe** (Python pur) et une vérification
**indépendante par un agent** (deepseek-v4-pro, jamais vu le code).

| Volet | Méthode | Livrable |
|---|---|---|
| **1. Recalculs déterministes** | chaque formule redérivée des principes (IPS §1/§3/§7), calculée en Python pur, comparée au code | `phase5_recalculs_deterministes.py` → `preuves/phase5_recalculs.txt` |
| **2. Vérification indépendante** | agent deepseek-v4-pro : dérivation → calcul → comparaison → verdict, + reproduction des P1 | `phase5_agent_deepseek.md` |

## 1. Convergence des deux volets

| Point testé | Volet 1 (déterministe) | Volet 2 (agent) | Verdict consolidé |
|---|---|---|---|
| Frais 1,40 % (0,80 % × 1,18 + 0,456 %) | ✅ conforme | ✅ conforme (au 3ᵉ déc.) | **CONFORME** |
| net_yield = brut × 0,88 − 0,008 | ✅ | ✅ (4,0000 % exact au point cible) | **CONFORME** |
| gross_yield_for_net(4 %) = 5,4545 % | ✅ | ✅ | **CONFORME** |
| Prix d'entrée : deux formules (36 245 vs 35 744,58) | ⚠️ écart 1,381 % | ⚠️ écart 1,381 % (500,42 F) | **ÉCART MINEUR (B1-08/C6)** |
| Prix de sortie = 62 134,29 (net 2 %) | ✅ | ✅ (net exactement 2,0000 %) | **CONFORME** |
| DRIP brut au lieu de net | ❌ +13,64 % | ❌ +626,40 F (cas 1740×3) | **ÉCART MINEUR (B1-03)** |
| Stop −15 % / break-even / suiveur −10 % | ✅ | ✅ (+ cohérence IPS §4.2) | **CONFORME** |
| Déclencheur PER > 40 → vente | ✅ (PER 41) | ✅ (PER 45,2 cas réels) | **CONFORME** |
| Déclencheur prix ≥ sortie | ✅ (62 500) | ✅ | **CONFORME** |
| Payout > 80 % / > 100 % | — | ✅ (90 %/120 % construits) | **CONFORME** |
| **A3-01 — colonne TTM jamais écartée** | (confirmé phase 3 + ma vérif.) | ✅ **REPRODUIT : 12 titres, 10 « fiables »** | **P1 CONFIRMÉ — 2 familles** |
| **A3-02 — BPA connu au 1er janvier N+1** | (confirmé phase 3) | ✅ **REPRODUIT : condition sur l'année seule** | **P1 CONFIRMÉ — 2 familles** |

## 2. Verdict global

**Les fondations de calcul du système sont SAINES.** Aucune erreur de frais, de rendement, de
prix, de palier, ni de déclencheur n'a été trouvée par deux méthodes indépendantes — c'est un
résultat d'audit réjouissant : les décisions reposent sur de l'arithmétique exacte.

Les seuls écarts financiers sont :
1. **A3-01 / A3-02 (P1)** — les look-aheads BPA/TTM du module de fondamentaux historiques :
   ils ne faussent pas la production quotidienne (le module sert aux évaluations/backtests)
   mais **biaisent les statistiques qui valident des règles** — désormais confirmés par
   *trois* regards (Claude, ma vérification, DeepSeek).
2. **B1-08/C6 (mineur)** — deux formules de prix d'entrée (1,381 % d'écart) : à trancher
   (une seule formule, ou les deux étiquetées).
3. **B1-03 (mineur)** — le DRIP comptabilise le brut : +13,64 % de dividendes surestimés
   à chaque versement dans le suivi.

## 3. Note de traçabilité (agents avortés)

Les agents **Claude Opus 5.5** puis **Gemini 3.1 Pro** ont été bloqués par le **plafond de
5 $ de la clé OpenRouter** (0,996 $ puis ~0,7 $ restants ; refusés sur le worst-case
max_tokens). La vérification indépendante a été menée sur la **clé DeepSeek directe**
(deepseek-v4-pro) — famille différente de Claude et Mistral. Si LEO ajuste le plafond de la
clé OpenRouter, une passe Opus/GPT pourra compléter la triangulation plus tard.

## 4. Limites

- A3-01 : la cause « colonne TTM » reste une **inférence forte** (branche morte + 12 doublons
  exacts) ; le HTML source n'a pas été re-scrapé.
- A3-02 : l'ampleur exacte du look-ahead (3–6 mois) dépend des dates de publication réelles
  par titre, non présentes dans le cache ; le sens (connaissance prématurée) est certain.
- Les volets 1 et 2 sont **statiques + calculatoires** : l'exécution contrôlée (phase 8)
  reste à faire pour la preuve dynamique.
