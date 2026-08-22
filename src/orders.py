"""Ordres limites du noyau dividende : prix d'achat pour un rendement net cible.

Pour chaque titre du noyau, calcule le prix d'entrée qui donne le rendement NET
cible (4 % par défaut, après IRVM + frais), compare au cours actuel et indique :
  - ACHETER : le cours est déjà au niveau qui offre le rendement net cible ;
  - LIMITE  : poser un ordre d'achat à ce prix et attendre.
"""
from __future__ import annotations

from .bsapi import BSApi
from .fundamentals import get_dps, get_per_brvm
from .portfolio import PAYOUT_CRITICAL, PAYOUT_TIGHT, payout_ratio
from .taxation import TARGET_NET_YIELD_ENTRY, entry_price_for_net, net_yield


def _sustainability_label(payout: float | None) -> str:
    """Libellé de soutenabilité à partir du payout ratio (garde-fou anti value-trap)."""
    if payout is None:
        return "n/a"
    if payout > PAYOUT_CRITICAL:
        return "🔴 NON COUVERT"
    if payout > PAYOUT_TIGHT:
        return "🟠 TENDU"
    return "✅ sain"


def build_limit_orders(
    api: BSApi, codes: list[str], target_net: float = TARGET_NET_YIELD_ENTRY
) -> list[dict]:
    """Retourne les ordres limites du noyau, triés ACHETER d'abord puis rendement décroissant.

    Chaque ordre inclut le payout ratio (soutenabilité) : un dividende non couvert
    (> 100 %) dégrade l'action en « ⚠️ VALUE TRAP » même si le cours est attractif.
    """
    snap = api.market_snapshot()
    orders: list[dict] = []
    for code in codes:
        code = code.strip().upper()
        quote = snap.by_code(code)
        if quote is None or quote.last <= 0:
            orders.append({"code": code, "error": "introuvable ou sans cotation"})
            continue
        dps = get_dps(code)
        if not dps or dps <= 0:
            orders.append({"code": code, "name": quote.name, "last": quote.last, "error": "dividende indisponible"})
            continue
        per = get_per_brvm(code)
        entry = entry_price_for_net(dps, target_net)
        net = net_yield(dps / quote.last) * 100
        payout = payout_ratio(dps, quote.last, per)
        action = "ACHETER" if quote.last <= entry else "LIMITE"
        if payout is not None and payout > PAYOUT_CRITICAL:
            action = "⚠️ VALUE TRAP"
        orders.append({
            "code": code,
            "name": quote.name,
            "last": quote.last,
            "dps": dps,
            "per": per,
            "payout": round(payout * 100) if payout is not None else None,
            "entry_price": round(entry, 2),
            "net_yield": round(net, 2),
            "action": action,
            "sustainability": _sustainability_label(payout),
        })
    orders.sort(key=lambda o: (0 if o.get("action") == "ACHETER" else 1, -o.get("net_yield", 0.0)))
    return orders
