"""Obligations UEMOA cotées à la BRVM.

Fournit :
- le référentiel du carnet d'ordres (data/bonds_market.json, séance du 20/08/2026) ;
- le calcul du rendement actuariel (YTM) par bissection ;
- le suivi des positions achetées (data/bonds_positions.json) : coupons annuels
  attendus, valeur de marché, intégration au rapport mensuel.

Conventions :
- nominal = 10 000 FCFA par titre (déduit des quantités du carnet ; À FAIRE
  VALIDER par Bridge Securities avant le premier ordre) ;
- cours exprimés en % du nominal (100 = au pair) ;
- coupons annuels ; échéance supposée au 31/12 de l'année de maturité
  (approximation — l'avis Bridge donne la date exacte) ;
- fiscalité des intérêts : hypothèse exonération des emprunts d'État, À VÉRIFIER.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MARKET_FILE = DATA_DIR / "bonds_market.json"
POSITIONS_FILE = DATA_DIR / "bonds_positions.json"

NOMINAL = 10_000.0  # FCFA par titre

# Risque émetteur (appréciation qualitative, pas une notation officielle)
_LOW = ("TPCI", "TPBJ", "EOS", "BIDC", "CRRH", "FBOAD", "SNTS", "PTRC")
_HIGH = ("EOM", "TPBF", "TPNE")
_MED = ("FORBT", "FTIMC", "ORGT")


def issuer_risk(code: str) -> str:
    if code.startswith(_LOW):
        return "faible"
    if code.startswith(_HIGH):
        return "élevé"
    if code.startswith(_MED):
        return "moyen"
    return "?"


# ------------------------------------------------------------- référentiel
def load_market() -> list[dict]:
    try:
        data = json.loads(MARKET_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("lines", [])


def market_line(code: str) -> dict | None:
    for line in load_market():
        if line["code"].upper() == code.upper():
            return line
    return None


# ------------------------------------------------------------------- YTM
def ytm(price: float, coupon: float, maturity: int, today: date | None = None) -> float | None:
    """Rendement actuariel (%) — prix en % du nominal, coupons annuels.

    Flux : coupons annuels + remboursement 100 avec le dernier. Échéance
    supposée au 31/12 de l'année de maturité.
    """
    today = today or date.today()
    years = (date(maturity, 12, 31) - today).days / 365.25
    if years <= 0 or price <= 0:
        return None
    # Flux annuels à 1, 2, ..., n ans ; remboursement au pair avec le dernier.
    # Approximation : l'échéance fractionnaire (ex. 3,36 ans) est arrondie à n
    # années entières → YTM légèrement surestimé (< 0,1 pt). Suffisant pour comparer.
    n = max(1, int(round(years)))
    times = [float(i) for i in range(1, n + 1)]
    flows = [coupon] * n
    flows[-1] += 100.0  # remboursement au pair avec le dernier coupon

    def pv(r: float) -> float:
        return sum(cf / (1.0 + r) ** t for cf, t in zip(flows, times))

    lo, hi = -0.9, 0.60  # taux peut être négatif (titre acheté au-dessus du pair)
    if pv(hi) > price:  # prix très décoté → YTM au-delà de 60 %
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if pv(mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0 * 100.0


def current_yield(price: float, coupon: float) -> float | None:
    """Rendement courant (%) = coupon / prix."""
    return (coupon / price * 100.0) if price > 0 else None


def buyable_lines(today: date | None = None) -> list[dict]:
    """Lignes achetables immédiatement (offre vendeur visible), triées par YTM desc."""
    out = []
    for line in load_market():
        if line.get("bid") is None:
            continue
        y = ytm(line["bid"], line["coupon"], line["maturity"], today)
        out.append({
            **line,
            "ytm": y,
            "risk": issuer_risk(line["code"]),
            "cost_per_unit": NOMINAL * line["bid"] / 100.0,
        })
    out.sort(key=lambda r: (r["ytm"] is None, -(r["ytm"] or 0.0)))
    return out


# --------------------------------------------------------------- positions
def load_bond_positions() -> list[dict]:
    try:
        data = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("positions", [])


def save_bond_positions(positions: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text(
        json.dumps({"positions": positions}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_bond_position(code: str, qty: int, price: float, buy_date: str | None = None) -> dict:
    """Enregistre un achat d'obligation (complété depuis le référentiel)."""
    line = market_line(code)
    if line is None:
        raise ValueError(f"{code} : ligne inconnue du référentiel obligations (data/bonds_market.json).")
    if qty <= 0:
        raise ValueError("Quantité invalide (>= 1 titre).")
    if price <= 0 or price > 200:
        raise ValueError("Prix invalide (% du nominal, ex. 98).")
    positions = load_bond_positions()
    entry = {
        "code": line["code"],
        "label": line["label"],
        "qty": int(qty),
        "price": round(float(price), 2),
        "coupon": line["coupon"],
        "maturity": line["maturity"],
        "date": buy_date or date.today().isoformat(),
    }
    positions.append(entry)
    save_bond_positions(positions)
    return entry


def coupons_per_year(positions: list[dict] | None = None) -> float:
    """Coupons annuels bruts attendus (FCFA) sur les positions détenues."""
    if positions is None:
        positions = load_bond_positions()
    return sum(p["qty"] * NOMINAL * p["coupon"] / 100.0 for p in positions)


def bonds_market_value(positions: list[dict] | None = None) -> float:
    """Valeur de marché (cours veille du référentiel, sinon prix d'achat)."""
    if positions is None:
        positions = load_bond_positions()
    total = 0.0
    for p in positions:
        line = market_line(p["code"])
        price = line["prev_close"] if line and line.get("prev_close") else p["price"]
        total += p["qty"] * NOMINAL * price / 100.0
    return total
