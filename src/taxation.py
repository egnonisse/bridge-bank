"""Fiscalité et frais BRVM (Côte d'Ivoire), appliqués aux rendements.

Source : grille tarifaire officielle Bridge Securities (Annexe II) + IRVM CI.

Frais de transaction (achat/vente), observés sur le CMP réel :
  - courtage ordre   : 0,80 % (Bridge, min 1 000 FCFA)
  - TVA (18 %)       : ~0,14 %
  - frais BRVM (DC/BR, règlement/livraison) : ~0,46 %
  - TOTAL effectif   : ~1,40 % (vérifié sur ordres réels : ex. SGBC 39 000 → CMP 39 546)
  - conservation     : 0,20 %/trimestre (min 2 500 FCFA/trim) = 0,80 %/an
  - tenue de compte  : gratuit

Fiscalité Côte d'Ivoire :
  - IRVM dividendes  : 12 % (retenue à la source libératoire, pers. physiques)

Source du taux 12 % : Bulletin Officiel de la Cote BRVM du 15/06/2026
(avis PALM CI : « IRVM applicable de 12 % »). Historique contradictoire :
10 % (2019), 15 % (janv. 2025), 12 % (BOC 2026). À re-vérifier une fois sur
un avis de paiement réel (net crédité vs brut) via Bridge Securities.
"""
from __future__ import annotations

# --- frais Bridge Securities (tarification officielle, Annexe II) -----------
BROKERAGE_RATE = 0.008       # courtage ordinaire 0,80 % (min 1 000 F, max 1 %)
BROKERAGE_MIN = 1000.0       # minimum de courtage par ordre (FCFA)
TVA_RATE = 0.18              # TVA sur le courtage
BRVM_FEES_RATE = 0.00456     # frais BRVM (DC/BR, règlement/livraison) — calibré sur CMP réels
# taux effectif total (ordre >= ~125 000 F, sans min) : 0,80 % + TVA + 0,456 % ≈ 1,40 %
BROKERAGE_FEE = BROKERAGE_RATE * (1 + TVA_RATE) + BRVM_FEES_RATE
CUSTODY_PER_QUARTER = 0.002  # conservation 0,20 %/trimestre
CUSTODY_ANNUAL = CUSTODY_PER_QUARTER * 4  # 0,80 %/an
CUSTODY_MIN_PER_QUARTER = 2500.0  # minimum par trimestre (FCFA)


def commission(montant: float) -> float:
    """Frais totaux de transaction (FCFA) pour un ordre d'un montant donné.

    Décomposition (grille Bridge Securities, Annexe II) :
      - courtage : 0,80 % (min 1 000 F par ordre)
      - TVA      : 18 % sur le courtage
      - BRVM     : 0,456 % du montant (DC/BR, règlement/livraison)

    NB : le « max 1 % » de la grille est redondant (0,80 % < 1 %) ; le min 1 000 F
    est appliqué par prudence (non observé sur l'ordre réel SGBC 117 000 F).
    """
    if montant <= 0:
        return 0.0
    courtage = max(montant * BROKERAGE_RATE, BROKERAGE_MIN)
    return courtage * (1 + TVA_RATE) + montant * BRVM_FEES_RATE

# --- fiscalité Côte d'Ivoire -------------------------------------------------
IRVM_DIVIDEND_TAX = 0.12     # impôt dividendes (IRVM), retenu à la source (12 % pers. physiques)

# --- objectifs de rendement NET (après impôt + frais) ------------------------
TARGET_NET_YIELD_ENTRY = 0.04  # rendement net visé à l'entrée (4 %)
TARGET_NET_YIELD_EXIT = 0.02   # plancher net de sortie (2 %)


def net_yield(gross_yield: float) -> float:
    """Rendement net (fraction) = brut × (1 − IRVM) − conservation annuelle."""
    return gross_yield * (1 - IRVM_DIVIDEND_TAX) - CUSTODY_ANNUAL


def gross_yield_for_net(net_yield_target: float) -> float:
    """Rendement brut (fraction) requis pour atteindre un rendement net cible."""
    return (net_yield_target + CUSTODY_ANNUAL) / (1 - IRVM_DIVIDEND_TAX)


def entry_price_for_net(dps: float, target_net: float = TARGET_NET_YIELD_ENTRY) -> float:
    """Prix d'achat max pour atteindre un rendement net cible, pour un dividende donné.

    Ex. dps=1740, cible 4 % net -> 30 812 FCFA : acheter en dessous de ce prix.
    """
    if dps <= 0:
        return 0.0
    # Divise par (1 + frais de transaction) : le prix de marché doit être plus bas
    # pour que le rendement net sur COÛT (CMP, frais inclus) atteigne la cible.
    return dps / gross_yield_for_net(target_net) / (1 + BROKERAGE_FEE)
