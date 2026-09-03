"""Noyau dividende : positions long terme + sortie sur fondamentaux.

Prix d'entrée (rendement NET 4 %) = dps / DIV_YIELD_ENTRY — acheter en dessous.
Prix de sortie (rendement NET 2 %) = dps / DIV_YIELD_EXIT — vendre au-dessus.
Le rendement est NET (après IRVM 15 % + frais de conservation 0,80 %/an),
donc le seuil brut est plus élevé (≈ 5,65 % à l'entrée, ≈ 3,29 % à la sortie).
Sortie sur fondamentaux (JAMAIS sur une simple baisse de cours) :
  1. dividende coupé (>50 %) ou suspendu
  2. PER > 40 (décote résorbée ou bénéfices en chute)
  3. prix de sortie atteint (rendement net tombé à 2 %)
Durée : 3 ans minimum, réévaluation à l'échéance (alerte, pas clôture auto).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .bsapi import BSApi
from .taxation import (
    IRVM_DIVIDEND_TAX,
    TARGET_NET_YIELD_ENTRY,
    TARGET_NET_YIELD_EXIT,
    commission,
    gross_yield_for_net,
    net_yield,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
REVERSAL_FILE = DATA_DIR / "reversal_profiles.json"
REINF_STATE_FILE = DATA_DIR / "reinf_alert_state.json"  # exclu par .gitignore (*_state.json)
REINF_COOLDOWN_DAYS = 7

# Rendement BRUT requis pour atteindre le rendement NET cible (IRVM + frais déduits)
DIV_YIELD_ENTRY = gross_yield_for_net(TARGET_NET_YIELD_ENTRY)  # 4 % net -> ≈ 5,65 % brut
DIV_YIELD_EXIT = gross_yield_for_net(TARGET_NET_YIELD_EXIT)    # 2 % net -> ≈ 3,29 % brut
PER_EXPLODE = 40.0
DIV_CUT_RATIO = 0.5
HOLDING_YEARS = 3

# Seuils de gestion de position (alerte sans clôture automatique)
# +13 % validé le 21/08/2026 par l'historique 9 ans : sur 54 épisodes SNTS à +13 % en
# 20 séances, le titre est plus bas 20 séances après dans 89 % des cas (médiane −3,3 %).
# À +15 %, la surchauffe est pire mais le seuil se déclenche 33 % moins souvent (36 cas).
PROFIT_ALERT_THRESHOLD = 0.13  # plus-value ≥ +13 % -> alerte décisionnelle (vendre / conserver)
LOSS_ALERT_THRESHOLD = 0.10    # moins-value ≥ -10 % -> alerte de couverture par les dividendes
SELL_FRACTION = 1 / 3          # fraction proposée à la vente (1/3 = 33 %)

# Soutenabilité du dividende (garde-fou anti value-trap) : payout = dividende / BPA.
# La baisse du cours précède souvent la coupe du dividende ; le payout élevé la détecte avant.
PAYOUT_TIGHT = 0.80      # payout > 80 % : dividende tendu (vigilance)
PAYOUT_CRITICAL = 1.00   # payout > 100 % : dividende non couvert par les bénéfices (risque de coupe)

# Niveaux d'alerte (gravité croissante) — cf. IPS §3.4
LEVEL_INFO = 1        # information : rien à faire (console uniquement)
LEVEL_DECISION = 2    # décisionnel : action partielle / réévaluation
LEVEL_FUNDAMENTAL = 3 # fondamental : risque sur le dividende (surveillance)
LEVEL_EXIT = 4        # sortie fondamentale : VENDS TOUT


@dataclass
class PositionAlert:
    """Alerte de gestion de position : un niveau de gravité + un message lisible."""
    level: int
    message: str
    code: str = ""


@dataclass
class DividendPosition:
    code: str
    name: str
    entry_price: float
    quantity: int
    dps: float  # dividende par action (FCFA) à l'ouverture
    per_open: float  # PER à l'ouverture
    opened_at: str = ""
    exit_price: float = 0.0  # prix de sortie (rendement net 2 %)
    entry_price_ref: float = 0.0  # prix d'entrée de référence (rendement net 4 %)
    closed: bool = False
    close_reason: str = ""
    close_price: float = 0.0
    dividends_earned: float = 0.0  # cash total reçu en dividendes
    cash_residual: float = 0.0  # reste non réinvesti (fractionnaire)

    def __post_init__(self) -> None:
        if not self.opened_at:
            self.opened_at = datetime.now().isoformat()
        if self.dps > 0:
            if self.exit_price <= 0:
                self.exit_price = round(self.dps / DIV_YIELD_EXIT, 2)
            if self.entry_price_ref <= 0:
                self.entry_price_ref = round(self.dps / DIV_YIELD_ENTRY, 2)

    def yield_pct(self, price: float) -> float:
        return self.dps / price * 100 if price > 0 else 0.0

    def net_yield_pct(self, price: float) -> float:
        """Rendement NET (en %) après IRVM + frais de conservation."""
        return net_yield(self.dps / price) * 100 if price > 0 else 0.0

    @property
    def years_held(self) -> float:
        try:
            opened = datetime.fromisoformat(self.opened_at)
        except ValueError:
            return 0.0
        return (datetime.now() - opened).days / 365.25

    @property
    def invested(self) -> float:
        return self.entry_price * self.quantity


# ------------------------------------------------------------------- calculs
def _sell_profit_net(pos: DividendPosition, price: float, fraction: float) -> tuple[float, int]:
    """Bénéfice net (après courtage) d'une vente partielle de `fraction` de la position."""
    qty = max(1, int(pos.quantity * fraction))
    gross = (price - pos.entry_price) * qty
    brokerage = commission(price * qty)
    return gross - brokerage, qty


def _dividend_annual_net(pos: DividendPosition) -> float:
    """Dividende net annuel total (après IRVM) pour la position courante."""
    return pos.dps * (1 - IRVM_DIVIDEND_TAX) * pos.quantity


def _next_check_date() -> str:
    """Date de la prochaine alerte possible (fin du cooldown)."""
    return (datetime.now() + timedelta(days=ALERT_COOLDOWN_DAYS)).strftime("%d/%m/%Y")


def _history_line(pos: DividendPosition) -> str:
    """Ligne « 📜 HISTOIRE » de l'alerte : profil de retournement du titre (si fiable)."""
    try:
        data = json.loads(REVERSAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    prof = data.get(pos.code.upper())
    if not prof:
        return ""
    line = (
        f"\n   📜 HISTOIRE {pos.code} (9 ans) : après +13 % en 20 séances, baisse dans "
        f"{prof['pct_down_20j']} % des cas\n"
        f"      médiane {prof['median_20j']:+.1f} % à ~1 mois · creux à ~{prof['trough_delay_median']} séances "
        f"({prof['trough_depth_median']:+.1f} %)"
    )
    if prof["pct_down_20j"] >= 65:
        line += "\n      ⏳ Fenêtre de manœuvre estimée : ~2 à 4 semaines avant la baisse franche"
    return line


def _double_option_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 2 (décision) : plus-value → vendre 1/3 ou conserver pour le dividende."""
    gain_pct = (price / pos.entry_price - 1) * 100
    gain_fcfa = (price - pos.entry_price) * pos.quantity
    profit_net, _ = _sell_profit_net(pos, price, SELL_FRACTION)
    div_net = _dividend_annual_net(pos)
    net_yld = pos.net_yield_pct(price)
    return PositionAlert(
        LEVEL_DECISION,
        f"⚡ DÉCISION — {pos.name} ({pos.code}) {gain_pct:+.1f} % ({gain_fcfa:+,.0f} F)\n"
        f"   Action : VENDS 1/3 (33 %) → ordre de vente à ≥ {price:,.0f} F\n"
        f"            bénéfice net ≈ {profit_net:,.0f} F (après frais ~1,4 %)\n"
        f"   Alternative : CONSERVE pour ≈ {div_net:,.0f} F/an de dividendes nets\n"
        f"   Rendement net actuel : {net_yld:.1f} %"
        f"{_history_line(pos)}\n"
        f"   Prochaine vérification : {_next_check_date()}",
    )


def _loss_coverage_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 2 (décision) : moins-value → conserver (perte couverte par les dividendes)."""
    loss_pct = (price / pos.entry_price - 1) * 100
    loss_fcfa = (price - pos.entry_price) * pos.quantity
    div_net = _dividend_annual_net(pos)
    net_yld = pos.net_yield_pct(price)
    coverage = (
        f"perte couverte en ~{abs(loss_fcfa) / div_net:.1f} ans"
        if div_net > 0
        else "aucun dividende pour couvrir la perte"
    )
    return PositionAlert(
        LEVEL_DECISION,
        f"⚡ DÉCISION — {pos.name} ({pos.code}) {loss_pct:+.1f} % ({loss_fcfa:,.0f} F)\n"
        f"   Action : CONSERVE — {coverage}\n"
        f"   Renforcement : ordre limite d'achat à ≤ {price:,.0f} F (net {net_yld:.1f} %) — si dividende soutenable\n"
        f"   Alternative : vendre seulement si la thèse change (jamais sur le prix)\n"
        f"   Prochaine vérification : {_next_check_date()}",
    )


def payout_ratio(dps: float, price: float, per: float | None) -> float | None:
    """Payout ratio implicite = dividende / bénéfice par action (BPA = prix / PER).

    Retourne None si PER inconnu ou non positif (pertes), ou si données manquantes.
    """
    if dps <= 0 or price <= 0 or per is None or per <= 0:
        return None
    return dps * per / price


def sustainability_alert(name: str, code: str, dps: float, per: float | None, price: float) -> PositionAlert | None:
    """Niveau 3 (fondamental) : dividende non soutenable (payout élevé ou société en perte).

    Garde-fou anti value-trap : détecte une coupe probable AVANT qu'elle n'arrive.
    Applicable à un titre du noyau, qu'une position soit ouverte ou non.
    """
    if per is not None and per <= 0 and dps > 0:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🔴 FONDAMENTAL — {name} ({code}) — société en perte (PER négatif) mais dividende versé\n"
            f"   RISQUE DE COUPE DU DIVIDENDE\n"
            f"   Surveillance renforcée.",
        )
    payout = payout_ratio(dps, price, per)
    if payout is None:
        return None
    if payout > PAYOUT_CRITICAL:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🔴 FONDAMENTAL — {name} ({code}) — payout {payout*100:.0f} %\n"
            f"   RISQUE DE COUPE DU DIVIDENDE\n"
            f"   Surveillance renforcée.",
        )
    if payout > PAYOUT_TIGHT:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🟠 FONDAMENTAL — {name} ({code}) — payout {payout*100:.0f} %\n"
            f"   Dividende tendu — surveillance.",
        )
    return None


def _soutenabilite_alert(pos: DividendPosition, dps: float, per: float | None, price: float) -> PositionAlert | None:
    """Compat : soutenabilité pour une position ouverte (wrapper)."""
    return sustainability_alert(pos.name, pos.code, dps, per, price)


def check_sustainability(api: BSApi, codes: list[str]) -> list[PositionAlert]:
    """Vérifie la soutenabilité du dividende de chaque titre du noyau (payout).

    Garde-fou anti value-trap systématique : alerte (niveau 3) si payout > 80 %
    (tendu) ou > 100 % (non couvert), même sans position ouverte.
    """
    from .fundamentals import get_fundamentals

    snap = api.market_snapshot()
    alerts: list[PositionAlert] = []
    for code in codes:
        quote = snap.by_code(code.strip().upper())
        if quote is None or quote.last <= 0:
            continue
        fund = get_fundamentals(code)
        a = sustainability_alert(
            quote.name, quote.code.strip(), fund.get("dps"), fund.get("per"), quote.last
        )
        if a:
            a.code = quote.code.strip()
            alerts.append(a)
    return alerts


def _info_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 1 (information) : variation modérée, rien à faire (console uniquement)."""
    perf = (price / pos.entry_price - 1) * 100
    return PositionAlert(
        LEVEL_INFO,
        f"ℹ️ INFORMATION — {pos.name} ({pos.code}) {perf:+.1f} % — rien à faire",
    )


def status_level(pos: DividendPosition, price: float) -> tuple[int, str]:
    """Niveau + libellé court pour l'affichage console (`portf status`).

    Basé sur le cours seul (sans PER/payout, pour éviter le scraping dans `status`).
    """
    if pos.closed:
        return LEVEL_EXIT, "VENDU"
    if price >= pos.entry_price * (1 + PROFIT_ALERT_THRESHOLD):
        return LEVEL_DECISION, "VENDS 1/3"
    if price <= pos.entry_price * (1 - LOSS_ALERT_THRESHOLD):
        return LEVEL_DECISION, "CONSERVE"
    return LEVEL_INFO, "rien à faire"


def check_dividend_position(
    pos: DividendPosition,
    current_price: float,
    current_dps: Optional[float] = None,
    current_per: Optional[float] = None,
) -> list[PositionAlert]:
    """Évalue une position dividende. Retourne des alertes hiérarchisées par niveau.

    Niveaux (gravité croissante) :
      - LEVEL_INFO (1)        : variation modérée, rien à faire (console)
      - LEVEL_DECISION (2)    : action partielle / réévaluation
      - LEVEL_FUNDAMENTAL (3) : risque sur le dividende (surveillance)
      - LEVEL_EXIT (4)        : sortie fondamentale → VENDS TOUT

    Sorties fondamentales (VENTE TOTALE) — la thèse « revenu » est morte :
      1. dividende suspendu ou coupé > 50 %
      2. PER > 40 (décote résorbée / bénéfices en chute)
      3. prix de sortie atteint (rendement net ≤ 2 %)
    """
    alerts: list[PositionAlert] = []
    if pos.closed:
        return alerts

    # 1. dividende coupé/suspendu → VENDS TOUT
    if current_dps is not None and pos.dps > 0:
        if current_dps <= 0:
            pos.closed = True
            pos.close_reason = "dividende suspendu"
            alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — dividende suspendu, la thèse « revenu » est morte"))
        elif current_dps < pos.dps * DIV_CUT_RATIO:
            pos.closed = True
            pos.close_reason = "dividende coupé >50%"
            alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — dividende coupé de plus de 50 %"))

    # 2. PER explose → VENDS TOUT
    if not pos.closed and current_per is not None and current_per > PER_EXPLODE:
        pos.closed = True
        pos.close_reason = f"PER {current_per:.1f} > {PER_EXPLODE:.0f}"
        alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — PER {current_per:.1f} > {PER_EXPLODE:.0f}"))

    # 3. prix de sortie atteint → VENDS TOUT
    if not pos.closed and pos.exit_price > 0 and current_price >= pos.exit_price:
        pos.closed = True
        pos.close_reason = "prix de sortie atteint"
        alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — prix de sortie atteint ({current_price:,.0f} ≥ {pos.exit_price:,.0f})"))

    # 4. soutenabilité (niveau 3)
    if not pos.closed and current_dps is not None and current_dps > 0:
        sa = _soutenabilite_alert(pos, current_dps, current_per, current_price)
        if sa:
            alerts.append(sa)

    # 5. plus-value → décision (niveau 2)
    if not pos.closed and current_price >= pos.entry_price * (1 + PROFIT_ALERT_THRESHOLD):
        alerts.append(_double_option_alert(pos, current_price))

    # 6. moins-value → décision (niveau 2)
    elif not pos.closed and current_price <= pos.entry_price * (1 - LOSS_ALERT_THRESHOLD):
        alerts.append(_loss_coverage_alert(pos, current_price))

    # 7. échéance 3 ans (niveau 2)
    if not pos.closed and pos.years_held >= HOLDING_YEARS:
        alerts.append(PositionAlert(LEVEL_DECISION, f"🟡 DÉCISION — {pos.name} ({pos.code}) — ÉCHÉANCE {HOLDING_YEARS} ans atteinte, réévalue la thèse"))

    # 8. sinon, information (niveau 1)
    if not pos.closed and not any(a.level >= LEVEL_DECISION for a in alerts):
        alerts.append(_info_alert(pos, current_price))

    if pos.closed and not pos.close_price:
        pos.close_price = current_price
    return alerts


def record_dividend(pos: DividendPosition, price: float) -> tuple[float, int, float]:
    """Enregistre un versement de dividende et le réinvestit dans le même titre (DRIP).

    Retourne (cash reçu, actions achetées, résidu non réinvesti en FCFA).
    """
    if pos.dps <= 0 or pos.quantity <= 0:
        return 0.0, 0, 0.0
    cash = pos.dps * pos.quantity
    new_shares = int(cash // price) if price > 0 else 0
    pos.quantity += new_shares
    pos.dividends_earned += cash
    residual = cash - new_shares * price
    pos.cash_residual += residual
    return cash, new_shares, residual


# -------------------------------------------------------------- persistance
def load_portfolio() -> list[DividendPosition]:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        return [DividendPosition(**d) for d in json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def save_portfolio(positions: list[DividendPosition]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(
        json.dumps([asdict(p) for p in positions], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ------------------------------------------------- renforcements (noyau dynamique)
PER_MAX_NOYAU = 14.0  # même limite que les filtres d'achat qualifié (noyau_check)


def reinforcement_messages(positions, price_of, per_of) -> list[tuple[str, str]]:
    """Positions dont le cours est REDESCENDU sous le prix qui garantit 4 % net,
    avec les 4 filtres toujours OK (PER ≤ 14, payout ≤ 80 %). Style néophyte.

    price_of(code) -> float (0 si indisponible) ; per_of(code) -> float|None.
    Retourne [(code, message néophyte)] — à soumettre à l'anti-spam par l'appelant.
    """
    from .taxation import entry_price_for_net, net_yield

    out: list[tuple[str, str]] = []
    for p in positions:
        if p.closed:
            continue
        price = price_of(p.code)
        if not price or price <= 0:
            continue
        entry_ref = entry_price_for_net(p.dps)
        if price > entry_ref:
            continue
        per = per_of(p.code)
        if per is None or per <= 0 or per > PER_MAX_NOYAU:
            continue
        payout = payout_ratio(p.dps, price, per)
        if payout is None or payout > PAYOUT_TIGHT:
            continue
        net = net_yield(p.dps / price) * 100
        msg = (
            f"💪 RENFORCE {p.code} ({p.name}) — le prix est redescendu à {price:,.0f} F,\n"
            f"   sous ton seuil de {entry_ref:,.0f} F.\n"
            f"   → Chaque 1 000 F investi ici te paierait au moins 4 % de loyer par\n"
            f"     an (aujourd'hui : {net:.1f} % net), avec un patron qui partage\n"
            f"     {payout*100:.0f} % de ses gains — dans ta zone.\n"
            f"   → Montant : toi seul décides (jamais au-delà de ton plan)."
        )
        out.append((p.code, msg))
    return out


def load_reinf_state() -> dict:
    try:
        return json.loads(REINF_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_reinf_state(state: dict) -> None:
    REINF_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_reinforcements(api) -> list[tuple[str, str]]:
    """Renforcements du noyau, avec anti-spam 7 jours par titre."""
    from .fundamentals import get_per_brvm

    positions = load_portfolio()
    snap = api.market_snapshot()

    def price_of(code):
        q = snap.by_code(code)
        return q.last if q and q.last > 0 else 0.0

    def per_of(code):
        return get_per_brvm(code)

    hits = reinforcement_messages(positions, price_of, per_of)
    state = load_reinf_state()
    fresh: list[tuple[str, str]] = []
    now = datetime.now().isoformat()
    for code, msg in hits:
        last = state.get(code)
        if last is None:
            fresh.append((code, msg))
            state[code] = now
        else:
            try:
                age = datetime.now() - datetime.fromisoformat(last)
            except ValueError:
                age = datetime.now() - datetime.now()
            if age.days >= REINF_COOLDOWN_DAYS:
                fresh.append((code, msg))
                state[code] = now
    save_reinf_state(state)
    return fresh


# ------------------------------------------------- anti-spam des alertes
ALERT_STATE_FILE = DATA_DIR / "portf_alert_state.json"
ALERT_COOLDOWN_DAYS = 7  # ne pas re-alerter la même position avant 7 jours


def load_alert_state() -> dict:
    if not ALERT_STATE_FILE.exists():
        return {}
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_alert_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def is_cooldown_active(state: dict, code: str) -> bool:
    """True si la position a déjà été alertée il y a moins de ALERT_COOLDOWN_DAYS jours."""
    last = state.get(code)
    if not last:
        return False
    try:
        dt = datetime.fromisoformat(last)
    except (TypeError, ValueError):
        return False
    return (datetime.now() - dt).days < ALERT_COOLDOWN_DAYS


# ------------------------------------------------------------- haut niveau
def open_dividend_position(
    api: BSApi, code: str, amount: float, dps: float, per_open: float
) -> DividendPosition:
    """Ouvre une position dividende de `amount` FCFA au cours actuel."""
    from .speculation import load_positions  # import local : évite la circularité

    snap = api.market_snapshot()
    quote = snap.by_code(code)
    if quote is None or quote.last <= 0:
        raise ValueError(f"Titre {code} introuvable ou sans cotation")
    # Règle IPS : les poches sont étanches (un spéculatif ne devient jamais un investissement).
    norm = quote.code.strip().upper()
    for s in load_positions():
        if not s.closed and s.code.strip().upper() == norm:
            raise ValueError(
                f"Règle IPS — poches étanches : {norm} est déjà détenu dans la poche "
                f"SPÉCULATIVE. Un spéculatif ne devient jamais un investissement long "
                f"terme. (Vends d'abord la ligne spéculative : spec close {norm})"
            )
    quantity = int(amount // quote.last)
    if quantity <= 0:
        raise ValueError(f"Montant {amount:,.0f} insuffisant pour 1 action à {quote.last:,.0f}")
    return DividendPosition(
        code=quote.code.strip(),
        name=quote.name,
        entry_price=quote.last,
        quantity=quantity,
        dps=dps,
        per_open=per_open,
    )
