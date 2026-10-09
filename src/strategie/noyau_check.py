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

import json
from pathlib import Path

from ..collecte.fundamentals import get_fundamentals
from ..taxation import TARGET_NET_YIELD_ENTRY, entry_price_for_net, net_yield

# Filtres d'entrée : définis dans src/regles.py (catalogue unique).
from ..regles import PAYOUT_TIGHT, PER_MAX  # noqa: E402
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)
NET_MAX = 0.10          # borne haute anti-mirage (décision 25/09) : net ≤ 10 %
REFERENCE_AMOUNT = 100_000.0  # taille standard de ligne noyau (pour le calcul d'exemple)

PREP_WATCH_FILE = DATA_DIR / "prep_watch_state.json"  # *_state.json exclu par .gitignore
PREP_REALERT_DOWN_PCT = 0.03  # re-alerte si le prix s'améliore de ≥ 3 % sous la limite


def load_prep_watchlist() -> dict:
    """{code: {"limit": prix_limite, "name": libellé, "alerted_at": date|None}}."""
    try:
        return json.loads(PREP_WATCH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_prep_watchlist(watch: dict) -> None:
    PREP_WATCH_FILE.write_text(json.dumps(watch, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate_noyau_candidate(code: str, price: float, name: str = "",
                             hist: dict | None = None) -> dict | None:
    """Évalue un candidat contre les filtres noyau. None = rien à faire.

    Filtres (décision 25/09, challenge croisé 3 IA) :
      1. dividende > 0 · 2. net ≥ 4 % · 3. PER ≤ 14 · 4. payout ≤ 80 %
      5. net ≤ 10 % (borne haute anti-mirage)
      6. régularité ≥ 4/5 ans · 7. croissance ≥ −10 %/an · 8. liquidité ≥ 5 M F/j
    hist : cache {code: bars} pour la liquidité (None = non vérifiée).
    """
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
    if net > NET_MAX:
        return None  # rendement mirage (FTSC 93 %) : jamais d'alerte d'achat
    entry = entry_price_for_net(dps)
    label = name or code

    # nouveaux filtres (régularité, croissance, liquidité) — décision LEO 25/09
    from ..collecte.dividend_history import dividend_filters

    extra = dividend_filters(code, hist)
    extra_lines = "\n".join(f"      • {n}" for n in extra["notes"]) if extra["notes"] else ""
    if not extra["ok"]:
        # filtres ratés : log local (le radar reste de la veille), jamais d'alerte
        print(f"[noyau-check] {code} rejeté par les filtres de fiabilité : "
              f"{'; '.join(extra['reasons'])}")
        return None

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
            f"   • Dividende : {dps:,.0f} F brut/action\n"
            f"   • Fiabilité :\n{extra_lines}\n\n"
            f"📋 Ordre : ACHAT {code} ≤ {entry:,.0f} F\n"
            f"   → {qty} action(s) ≈ {qty*price:,.0f} F · dividende net ≈ {net_annual:,.0f} F/an\n\n"
            f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
        )
        return {"verdict": "opportunity", "message": msg}

    payout_note = f" (payout {payout*100:.0f} %)" if payout > 0.75 else ""
    extra_txt = f"\n   • Fiabilité :\n{extra_lines}" if extra_lines else ""
    msg = (
        f"📉 À PRÉPARER — {code} ({label})\n\n"
        f"💰 Cours : {price:,.0f} F — rendement net actuel {net*100:.1f} % (< 4 %)\n\n"
        f"✅ Fondamentaux : PER {per:.1f} (≤ 14), dividende {dps:,.0f} F brut{payout_note}{extra_txt}\n\n"
        f"📋 Ordre limite à poser : ≤ {entry:,.0f} F (dps×0,88 ÷ 0,048)\n"
        f"   → si le titre revient dans ta zone : ≥ 4 % net COUVERT\n"
        f"   → sinon : tu l'as regardé passer, sans perdre un franc.\n\n"
        f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
    )
    return {"verdict": "limit", "message": msg, "limit_price": entry}


def prep_watch_alerts(watch: dict, price_of) -> tuple[list[str], dict]:
    """Surveille les ordres limites « À PRÉPARER ». Retourne (alertes, watch mise à jour).

    Alerte UNE fois quand le prix passe sous la limite (« 🎯 TON ORDRE LIMITE EST PRÊT »),
    puis re-alerte si le prix s'améliore encore de ≥ 3 % sous le prix déjà signalé.
    Les candidats au-dessus de leur limite restent silencieux.
    """
    from datetime import datetime

    alerts: list[str] = []
    today = datetime.now().isoformat()
    for code, info in list(watch.items()):
        limit = info.get("limit", 0.0)
        price = price_of(code)
        if not price or price <= 0 or price > limit:
            continue
        last = info.get("alerted_price")
        if last is None or price <= last * (1 - PREP_REALERT_DOWN_PCT):
            info["alerted_at"] = today
            info["alerted_price"] = price
            alerts.append(
                f"🎯 TON ORDRE LIMITE EST PRÊT — {code} ({info.get('name', '')})\n\n"
                f"💰 Cours : {price:,.0f} F — sous ta limite de {limit:,.0f} F.\n"
                f"→ À ce prix, ton loyer garanti est ≥ 4 % net par an.\n"
                f"→ Si tu veux profiter : passe l'ordre ACHAT {code} ≤ {limit:,.0f} F.\n"
                f"→ Sinon : tu laisses courir, l'ordre limite reste en veille.\n\n"
                f"🚫 Rappel : décision LEO — l'outil ne passe jamais d'ordre."
            )
    return alerts, watch
