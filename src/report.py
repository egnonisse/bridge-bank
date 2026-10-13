"""Rapport mensuel de santé du portefeuille Bridge Bank.

Génère un bilan complet (valeur, performance, noyau dividende, allocation vs
cible IPS, spéculation, dividendes perçus) à partir des positions persistées,
des cours en direct et d'un état de trésorerie (cash + obligations) alimenté
par l'utilisateur (`report cash --amount X`).

Le rapport compare la valeur totale au snapshot précédent (historique dans
`data/portfolio_state.json`) pour tracer l'évolution mois par mois.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .collecte.bsapi import BSApi
from .analyse.bonds import NOMINAL, load_bond_positions, market_line, ytm
from .collecte.dividends import total_encaissé
from .strategie.orders import build_limit_orders
from .portfolio import load_portfolio
from .strategie.speculation import load_positions
from .infrastructure.paths import DATA_DIR, PORTFOLIO_STATE  # chemins centralisés (lot 0 du plan docs/architecture.md)
from .infrastructure.ecriture import ecrire_json_atomique  # P7-01 : ecriture atomique
from .portefeuille.format_fr import fcfa, nombre  # format FR (invariant E1, correction C1)

STATE_FILE = PORTFOLIO_STATE  # défini dans paths.py (P6-01 : plus de redéfinition locale)

# Allocation cible (IPS §2) en % — actions uniquement (obligations retirées 03/09/2026)
TARGET_STOCKS = 70.0
TARGET_BONDS = 0.0
TARGET_CASH = 30.0
TARGET_SPEC = 0.0  # poche spéculation suspendue (26/08/2026)

# Seuil de concentration : un titre > 30 % du portefeuille = risque concentré
CONCENTRATION_WARN = 30.0


# ------------------------------------------------------------------- état
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"cash": 0.0, "obligations": [], "history": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"cash": 0.0, "obligations": [], "history": []}


def save_state(state: dict) -> None:
    ecrire_json_atomique(STATE_FILE, state)  # P7-01 : écriture atomique


def set_cash(amount: float) -> None:
    """Met à jour le solde de liquidités (input utilisateur)."""
    state = load_state()
    state["cash"] = round(float(amount), 2)
    save_state(state)


def _record_snapshot(state: dict, total: float, stocks: float, spec: float,
                     bonds: float, cash: float) -> None:
    """Enregistre un point de valeur (dédoublonné par jour)."""
    snap = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": round(total, 2),
        "stocks": round(stocks, 2),
        "spec": round(spec, 2),
        "bonds": round(bonds, 2),
        "cash": round(cash, 2),
    }
    history = state.get("history", [])
    if history and history[-1]["date"] == snap["date"]:
        history[-1] = snap  # remplace le snapshot du jour
    else:
        history.append(snap)
    state["history"] = history


# ---------------------------------------------------------------- calcul
def _compute(api: BSApi) -> dict:
    """Agrège toutes les données du portefeuille (positions + cours + état)."""
    state = load_state()
    positions = [p for p in load_portfolio() if not p.closed]
    specs = [s for s in load_positions() if not s.closed]
    snap = api.market_snapshot()

    # Données marché du noyau (cours, payout, soutenabilité)
    orders: dict[str, dict] = {}
    codes = [p.code for p in positions]
    if codes:
        for o in build_limit_orders(api, codes):
            if "error" not in o:
                orders[o["code"]] = o

    # Noyau dividende
    stocks_value = 0.0
    pnl_total = 0.0
    div_earned = 0.0
    pos_rows: list[dict] = []
    for p in positions:
        o = orders.get(p.code, {})
        last = o.get("last", p.entry_price)
        val = last * p.quantity
        pnl = (last - p.entry_price) * p.quantity
        stocks_value += val
        pnl_total += pnl
        div_earned += p.dividends_earned
        pos_rows.append({
            "code": p.code,
            "name": p.name,
            "qty": p.quantity,
            "entry": p.entry_price,
            "last": last,
            "pnl": pnl,
            "ret_pct": (last / p.entry_price - 1) * 100,
            "net_cost": p.net_yield_pct(p.entry_price),
            "net_now": o.get("net_yield", p.net_yield_pct(last)),
            "payout": o.get("payout"),
            "sustain": o.get("sustainability", "n/a"),
            "value": val,
        })

    # Spéculation
    spec_value = 0.0
    spec_rows: list[dict] = []
    for s in specs:
        q = snap.by_code(s.code)
        price = q.last if q and q.last > 0 else s.entry_price
        val = price * s.remaining
        spec_value += val
        spec_rows.append({
            "code": s.code, "name": s.name, "qty": s.remaining,
            "entry": s.entry_price, "last": price,
            "ret_pct": s.current_return(price), "stop": s.stop_loss,
        })

    # Trésorerie + obligations
    cash = float(state.get("cash", 0.0))
    legacy = state.get("obligations", [])
    legacy_value = sum(float(b.get("amount", 0.0)) for b in legacy)
    bond_positions = load_bond_positions()
    bond_rows: list[dict] = []
    for p in bond_positions:
        line = market_line(p["code"])
        price = line["prev_close"] if line and line.get("prev_close") else p["price"]
        val = p["qty"] * NOMINAL * price / 100.0
        bond_rows.append({
            "code": p["code"], "label": p["label"], "qty": p["qty"],
            "price": p["price"], "value": val,
            "coupons": p["qty"] * NOMINAL * p["coupon"] / 100.0,
            "ytm": ytm(p["price"], p["coupon"], p["maturity"]),
        })
    # Les positions détaillées remplacent le montant forfaitaire hérité
    bonds_value = sum(r["value"] for r in bond_rows) if bond_positions else legacy_value

    total = stocks_value + spec_value + bonds_value + cash

    # Concentration (plus grosse ligne du noyau)
    max_name, max_pct = "", 0.0
    for r in pos_rows:
        pc = (r["value"] / total * 100) if total > 0 else 0.0
        if pc > max_pct:
            max_pct, max_name = pc, r["name"]

    return {
        "state": state,
        "total": total,
        "stocks": stocks_value,
        "spec": spec_value,
        "bonds": bonds_value,
        "cash": cash,
        "pnl": pnl_total,
        "div_earned": div_earned,
        "div_real": total_encaissé(),
        "pos_rows": pos_rows,
        "spec_rows": spec_rows,
        "bond_rows": bond_rows,
        "bond_coupons": sum(r["coupons"] for r in bond_rows),
        "max_name": max_name,
        "max_pct": max_pct,
    }


# --------------------------------------------------------------- formatage
def _pct(value: float, total: float) -> float:
    return (value / total * 100) if total > 0 else 0.0


def _allocation_flag(actual: float, target: float) -> str:
    delta = actual - target
    if delta > 15:
        return "🔴"
    if delta > 5 or delta < -5:
        return "🟠"
    return "✅"


CASH_ALERT_MARGIN = 5.0   # au-delà de la cible + 5 points (30 % -> alerte dès 35 %)
CASH_ALERT_DAYS = 3       # jours de snapshots consécutifs au-dessus avant d'alerter


def alerte_tresorerie(pct_cash: float, history: list | None = None,
                      montant: float | None = None) -> str:
    """Alerte INFORMATIVE sur l'argent qui dort sur le compte — n'ordonne RIEN.

    POURQUOI (mesure du 08/10/2026) : le renforcement sur faiblesse coûte -59 points de
    rendement à capital égal en marché haussier, uniquement parce que les tranches non
    déclenchées dorment à 0 %. La trésorerie n'est pas un problème en soi — c'est une
    prime d'assurance qui paie pendant les krachs (67-69 % de réussite mesurée). Le
    problème est qu'elle DORT : non rémunérée, elle ne rapporte rien.

    Rédigé pour un lecteur sans notion de bourse : le montant en francs vient AVANT le
    pourcentage, la raison d'être de cette poche est rappelée, et la phrase finale dit
    explicitement qu'aucun ordre n'a été passé.

    GARANTIE : cette fonction ne fait que renvoyer du texte. Elle n'appelle aucun ordre,
    aucun achat, aucun module d'investissement — décision explicite du 08/10/2026.

    `history` permet d'injecter l'historique des snapshots (tests) ; à None, il est lu
    depuis l'état du portefeuille.
    """
    seuil = TARGET_CASH + CASH_ALERT_MARGIN
    if pct_cash < seuil:
        return ""

    # Jours consécutifs au-dessus du seuil, d'après l'historique des snapshots.
    if history is None:
        try:
            history = load_state().get("history", [])
        except (OSError, ValueError):
            history = []
    jours = 0
    for snap in reversed(history):
        total = snap.get("total") or 0
        cash = snap.get("cash") or 0
        if total > 0 and (cash / total * 100) >= seuil:
            jours += 1
        else:
            break

    if jours < CASH_ALERT_DAYS:
        return ""

    entete = (f"   ℹ️ {fcfa(montant)} dorment sur ton compte ({pct_cash:.0f} % de ton "
              f"argent)" if montant else
              f"   ℹ️ {pct_cash:.0f} % de ton argent dort sur ton compte")
    return (f"{entete}\n"
            f"      C'est ton matelas de sécurité : il te sert à racheter des actions\n"
            f"      quand tout baisse, et c'est lui qui a le mieux marché pendant les\n"
            f"      crises. Mais laissé là, il ne rapporte rien du tout.\n"
            f"      → Aucun ordre n'est passé, rien n'est déplacé. C'est juste pour\n"
            f"        que tu le saches : à toi de décider si tu le places ailleurs.")


def _format(data: dict) -> str:
    d = data
    total = d["total"]
    history = d["state"].get("history", [])
    prev = history[-1] if history else None
    if prev and prev.get("total", 0) > 0:
        evol = f"{(total / prev['total'] - 1) * 100:+.1f}% vs {prev['date']}"
    else:
        evol = "— (1er rapport)"

    L: list[str] = [
        "📊 RAPPORT MENSUEL — PORTEFEUILLE BRIDGE BANK",
        f"📅 {datetime.now().strftime('%d/%m/%Y')}",
        "",
        f"💰 VALEUR TOTALE : {fcfa(total, signe=False)}  ({evol})",
        (f"   Noyau {fcfa(d['stocks'], signe=False)} ({_pct(d['stocks'], total):.0f}%) · "
         f"Cash {fcfa(d['cash'], signe=False)} ({_pct(d['cash'], total):.0f}%)"),
        "",
        "📈 NOYAU DIVIDENDE",
    ]
    if d["pos_rows"]:
        for r in d["pos_rows"]:
            L.append(f"   {r['code']} ({r['name']}) {r['qty']} act.")
            L.append(f"      {fcfa(r['entry'], signe=False)} → {fcfa(r['last'], signe=False)} · {fcfa(r['pnl'], signe=True)} ({r['ret_pct']:+.1f}%)")
            payout = f"{r['payout']:.0f}%" if r["payout"] is not None else "n/a"
            L.append(f"      rend. net coût {r['net_cost']:.2f}% · actuel {r['net_now']:.2f}% · payout {payout} {r['sustain']}")
        L.append(f"   → plus/moins-value latente : {fcfa(d['pnl'], signe=True)}")
    else:
        L.append("   Aucune position.")

    L.extend(["", "🎯 ALLOCATION vs CIBLE (IPS)"])
    rows = [
        ("Noyau actions", d["stocks"], TARGET_STOCKS),
        ("Liquidités", d["cash"], TARGET_CASH),
        ("Spéculation (suspendue)", d["spec"], TARGET_SPEC),
    ]
    for label, value, target in rows:
        actual = _pct(value, total)
        flag = _allocation_flag(actual, target)
        L.append(f"   {label} : {actual:.0f}% (cible {target:.0f}%) {flag}")

    # Argent qui dort sur le compte — INFORMATION seule, aucun ordre (décision 08/10/2026).
    _cash_msg = alerte_tresorerie(_pct(d["cash"], total), montant=d["cash"])
    if _cash_msg:
        L.append(_cash_msg)

    if d["max_pct"] > CONCENTRATION_WARN:
        L.append(f"   ⚠️ Concentration : {d['max_name']} = {d['max_pct']:.1f}% du portefeuille")

    L.extend(["", "🏛️ OBLIGATIONS — RETIRÉES DE LA STRATÉGIE (03/09/2026, décision LEO : actions uniquement)"])
    if d.get("bond_rows"):
        for b in d["bond_rows"]:
            ytm_s = f"{b['ytm']:.2f}%" if b["ytm"] is not None else "n/a"
            L.append(f"   {b['code']} ({b['label']}) {b['qty']} titres @ {b['price']:.0f}%")
            L.append(f"      valeur {fcfa(b['value'], signe=False)} · coupons {fcfa(b['coupons'], signe=False)}/an bruts · YTM achat {ytm_s}")
    else:
        L.append("   Aucune position (module `bond` conservé en manuel).")

    L.extend(["", "🎲 SPÉCULATION"])
    if d["spec_rows"]:
        for s in d["spec_rows"]:
            L.append(f"   {s['code']} ({s['name']}) {s['qty']} act. · {s['ret_pct']:+.1f}% · stop {fcfa(s['stop'], signe=False)}")
    else:
        L.append("   Aucune position ouverte.")

    L.extend(["", f"💵 DIVIDENDES PERÇUS : {fcfa(d.get('div_real', 0), signe=False)} encaissés (réels) · {fcfa(d.get('div_earned', 0), signe=False)} théoriques"])
    return "\n".join(L)


# -------------------------------------------------------------- haut niveau
def build_report(api: BSApi, record: bool = False) -> str:
    """Génère le rapport mensuel et, si demandé, enregistre un snapshot."""
    data = _compute(api)
    message = _format(data)
    if record:
        state = data["state"]
        _record_snapshot(state, data["total"], data["stocks"], data["spec"],
                         data["bonds"], data["cash"])
        save_state(state)
    return message
