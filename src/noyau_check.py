"""Filtres noyau appliqués à un candidat — verdict + alerte d'achat QUALIFIÉE.

Pipeline d'achat légitime : radar (mouvement) → veille (pourquoi) → CES FILTRES.
Aucune alerte d'achat sans les 4 filtres : dividende officiel > 0, PER ≤ 14,
payout ≤ 80 %, rendement net ≥ 4 % (sinon ordre limite au prix d'entrée).

Verdicts :
  'opportunity' : tous les filtres passent AU COURS ACTUEL → alerte d'achat.
  'limit'       : fondamentaux sains mais cours trop haut → ordre limite au repli.
  None          : filtres ratés → silence total (le radar reste de la veille).
"""
from __future__ import annotations

from .fundamentals import get_fundamentals
from .taxation import TARGET_NET_YIELD_ENTRY, entry_price_for_net, net_yield

PER_MAX = 14.0          # IPS : PER ≤ 14
PAYOUT_TIGHT = 0.80     # payout > 80 % : tendu → pas d'alerte d'achat
REFERENCE_AMOUNT = 100_000.0  # taille standard de ligne noyau (pour le calcul d'exemple)


def evaluate_noyau_candidate(code: str, price: float, name: str = "") -> dict | None:
    """Évalue un candidat contre les filtres noyau. None = rien à faire."""
    code = code.upper()
    if price <= 0:
        return None
    fund = get_fundamentals(code)
    dps = fund.get("dps")
    per = fund.get("per")
    if not dps or dps <= 0 or not per or per <= 0 or per > PER_MAX:
        return None
    payout = dps * per / price
    if payout > PAYOUT_TIGHT:
        return None  # dividende tendu : jamais d'alerte d'achat
    gross = dps / price
    net = net_yield(gross)
    entry = entry_price_for_net(dps)
    label = name or code

    if net >= TARGET_NET_YIELD_ENTRY:
        margin = (entry / price - 1) * 100 if price > 0 else 0.0
        qty = max(1, int(REFERENCE_AMOUNT // price))
        net_annual = qty * dps * 0.88
        payout_note = ""
        if payout > 0.75:
            payout_note = f" ⚠️ frontière (limite 80 %) — re-vérifier au prochain résultat"
        msg = (
            f"🎯 OPPORTUNITÉ NOYAU — {code} ({label})\n\n"
            f"💰 Cours : {price:,.0f} F — marge vs seuil d'achat ({entry:,.0f} F) : {margin:+.1f} %\n\n"
            f"✅ Filtres noyau :\n"
            f"   • Rendement net : {net*100:.1f} % (exigé ≥ 4 %)\n"
            f"   • PER : {per:.1f} (limite 14)\n"
            f"   • Payout : {payout*100:.0f} %{payout_note}\n"
            f"   • Dividende : {dps:,.0f} F brut/action\n\n"
            f"📋 Ordre : ACHAT {code} ≤ {entry:,.0f} F\n"
            f"   → {qty} action(s) ≈ {qty*price:,.0f} F · dividende net ≈ {net_annual:,.0f} F/an\n\n"
            f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
        )
        return {"verdict": "opportunity", "message": msg}

    payout_note = f" (payout {payout*100:.0f} %)" if payout > 0.75 else ""
    msg = (
        f"📉 À PRÉPARER — {code} ({label})\n\n"
        f"💰 Cours : {price:,.0f} F — rendement net actuel {net*100:.1f} % (< 4 %)\n\n"
        f"✅ Fondamentaux : PER {per:.1f} (≤ 14), dividende {dps:,.0f} F brut{payout_note}\n\n"
        f"📋 Ordre limite à poser : ≤ {entry:,.0f} F (dps×0,88 ÷ 0,048)\n"
        f"   → si le titre revient dans ta zone : ≥ 4 % net garanti\n"
        f"   → sinon : tu l'as regardé passer, sans perdre un franc.\n\n"
        f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
    )
    return {"verdict": "limit", "message": msg}
