"""Moteur de spéculation BRVM : signaux d'entrée + gestion des positions.

Signaux d'entrée :
  DÉCLENCHEUR (obligatoire) :
    - breakout 20j : cours au-dessus du plus haut des 20 derniers jours
    - volume >= 2x la moyenne 20j (valide la cassure — sans volume, faux breakout)
  CONFIRMATIONS (>= 1 requise, confluence totale >= min_signals) :
    - momentum : variation 20j > +10% ou 60j > +20%
    - RSI entre 50 et 70 (haussier sans surchauffe)
    - golden cross : EMA20 > EMA50 (confirmation de tendance, PAS déclencheur)

Règles de sortie (mécaniques, non négociables) :
  - stop-loss initial : -15% du prix d'entrée
  - palier +20% : vendre 1/3, stop -> break-even (prix d'entrée)
  - palier +35% : vendre 1/3, stop suiveur -> -10% du plus haut
  - palier +50% : clôture finale
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .bsapi import BSApi
from .backtest import load_all_history
from .screening import avg_volume, change_pct, ema, rsi_wilder
from .paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

POSITIONS_FILE = DATA_DIR / "spec_positions.json"
CANDIDATES_STATE_FILE = DATA_DIR / "spec_candidates_state.json"

STOP_LOSS = 0.15
TAKE_1 = 0.20
TAKE_2 = 0.35
TAKE_3 = 0.50
TRAILING = 0.10
MIN_SIGNALS = 3
# Zone morte (ni +20 % ni stop −15 % depuis l'entrée) — calibré 21/08/2026 :
# à J+60, les inertes ont encore 30 % de chances de percer +20 % (vs 22 % de stop,
# médiane +3,1 %) → PAS de clôture automatique, seulement une revue à J+120 (~6 mois).
ZONE_DEAD_INFO_DAYS = 60    # mention info dans `spec status`
ZONE_DEAD_REVIEW_DAYS = 120  # alerte REVUE unique (Telegram)


# ---------------------------------------------------------------- signaux
def detect_signals(quote, bars) -> list[str]:
    """Retourne la liste des signaux d'entrée cochés pour un titre."""
    recent = bars[-90:]
    if len(recent) < 60:
        return []
    closes = [b.close for b in recent]
    rsi = rsi_wilder(closes)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    c20 = change_pct(recent, 20)
    c60 = change_pct(recent, 60)
    avol = avg_volume(recent)
    vratio = quote.volume / avol if avol > 0 else 0.0

    signals: list[str] = []
    if c20 > 10 or c60 > 20:
        signals.append(f"momentum {c20:+.0f}%")
    # Breakout : cassure du plus haut des 20 derniers jours (déclencheur précoce).
    # Remplace l'ancienne « cassure 52s » (trop tardive) — cf. discussion golden cross.
    prior_20 = closes[-21:-1] if len(closes) >= 21 else closes[:-1]
    if prior_20 and quote.last > max(prior_20):
        signals.append("breakout 20j")
    if vratio > 2:
        signals.append(f"volume {vratio:.1f}x")
    if rsi is not None and 50 < rsi < 70:
        signals.append(f"RSI {rsi:.0f}")
    if ema20 and ema50 and ema20 > ema50:
        signals.append("golden cross")
    return signals


def screen_speculation(api: BSApi, min_signals: int = MIN_SIGNALS) -> list[dict]:
    """Candidats spéculatifs : breakout (cassure 20j + volume >= 2x) requis
    + confluence totale >= min_signals (confirmations momentum/RSI/golden cross)."""
    hist = load_all_history(api)
    snap = api.market_snapshot()
    results = []
    for code, bars in hist.items():
        quote = snap.by_code(code.strip().upper())
        if quote is None or quote.last <= 0 or quote.is_obligation:
            continue
        signals = detect_signals(quote, bars)
        # Déclencheur requis : breakout (cassure 20j) validé par un volume >= 2x.
        # Le golden cross seul ne déclenche plus l'entrée (signal tardif).
        has_breakout = "breakout 20j" in signals
        has_volume = any(s.startswith("volume") for s in signals)
        if not (has_breakout and has_volume):
            continue
        if len(signals) >= min_signals:
            results.append(
                {
                    "code": quote.code.strip(),
                    "name": quote.name,
                    "last": quote.last,
                    "signals": signals,
                    "count": len(signals),
                }
            )
    results.sort(key=lambda r: -r["count"])
    return results


# ---------------------------------------------------------------- position
@dataclass
class SpecPosition:
    code: str
    name: str
    entry_price: float
    quantity: int
    opened_at: str = ""
    stop_loss: float = 0.0
    highest: float = 0.0
    sold_1: bool = False  # palier +20% : 1/3 vendu
    sold_2: bool = False  # palier +35% : 1/3 vendu
    review_alerted: bool = False  # alerte REVUE (zone morte J+120) déjà envoyée
    closed: bool = False
    close_reason: str = ""
    close_price: float = 0.0

    def __post_init__(self) -> None:
        if not self.opened_at:
            self.opened_at = datetime.now().isoformat()
        if self.stop_loss <= 0:
            self.stop_loss = round(self.entry_price * (1 - STOP_LOSS), 2)
        if self.highest <= 0:
            self.highest = self.entry_price

    @property
    def remaining(self) -> int:
        """Actions restantes (1/3 vendu à +20%, 1/3 à +35%, reste à +50%)."""
        if self.sold_2:
            return self.quantity // 3
        if self.sold_1:
            return self.quantity * 2 // 3
        return self.quantity

    @property
    def current_return(self, price: float) -> float:
        return (price / self.entry_price - 1) * 100 if self.entry_price else 0.0


def check_position(pos: SpecPosition, price: float) -> list[str]:
    """Évalue une position spéculative. Retourne des instructions actionnables."""
    events: list[str] = []
    if pos.closed:
        return events

    # 1. stop-loss / stop suiveur
    if price <= pos.stop_loss:
        pos.closed = True
        pos.close_price = price
        pos.close_reason = f"STOP déclenché à {price:,.0f} (stop {pos.stop_loss:,.0f})"
        events.append(f"🔴 VENDS TOUT (100 %) {pos.name} ({pos.code}) — stop déclenché, vends tout à {price:,.0f} FCFA")
        return events

    # 2. mise à jour du plus haut + stop suiveur (après +35%)
    if price > pos.highest:
        pos.highest = price
        if pos.sold_2:
            pos.stop_loss = round(pos.highest * (1 - TRAILING), 2)

    # 3. palier +20% : vendre 1/3, stop -> break-even
    if not pos.sold_1 and price >= pos.entry_price * (1 + TAKE_1):
        pos.sold_1 = True
        pos.stop_loss = pos.entry_price
        events.append(f"🟡 VENDS 1/3 (33 %) de {pos.name} ({pos.code}) — +20% atteint, garde les 2/3 restants (stop remonté au prix d'achat)")

    # 4. palier +35% : vendre 1/3, stop suiveur -10%
    if not pos.sold_2 and price >= pos.entry_price * (1 + TAKE_2):
        pos.sold_2 = True
        pos.stop_loss = round(pos.highest * (1 - TRAILING), 2)
        events.append(f"🟡 VENDS 1/3 (33 %) de {pos.name} ({pos.code}) — +35% atteint, garde le dernier 1/3 (stop suiveur actif)")

    # 5. palier +50% : clôture finale
    if price >= pos.entry_price * (1 + TAKE_3):
        pos.closed = True
        pos.close_price = price
        pos.close_reason = f"+50% atteint : clôture finale à {price:,.0f}"
        events.append(f"🔴 VENDS LE RESTE (dernier 1/3) {pos.name} ({pos.code}) — +50% atteint, encaisse le gain")

    return events


# -------------------------------------------------------------- persistance
def load_positions() -> list[SpecPosition]:
    if not POSITIONS_FILE.exists():
        return []
    try:
        data = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
        return [SpecPosition(**d) for d in data]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def save_positions(positions: list[SpecPosition]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text(
        json.dumps([asdict(p) for p in positions], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# -------------------------------------------------------------- zone morte
def zone_morte_status(pos: SpecPosition, api: BSApi) -> tuple[int, bool] | None:
    """(séances depuis l'ouverture, en zone morte) ou None si non applicable.

    Zone morte = ni +20 % ni −15 % touchés depuis l'entrée (et aucun palier vendu).
    Basé sur l'historique réel du titre depuis la date d'ouverture.
    """
    if pos.closed or pos.sold_1 or pos.sold_2:
        return None
    try:
        opened = datetime.fromisoformat(pos.opened_at)
    except ValueError:
        return None
    bars = load_all_history(api).get(pos.code.strip().upper(), [])
    if not bars:
        return None
    hit_up = hit_down = False
    sessions = 0
    for b in bars:
        d = b.date
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d)
            except ValueError:
                continue
        if d < opened:
            continue
        sessions += 1
        c = float(b.close)
        if c <= 0:
            continue
        if c >= pos.entry_price * (1 + TAKE_1):
            hit_up = True
        if c <= pos.entry_price * (1 - STOP_LOSS):
            hit_down = True
    if sessions == 0:
        return None
    return sessions, (not hit_up and not hit_down)


# ------------------------------------------------------------- haut niveau
def open_position(api: BSApi, code: str, amount: float) -> SpecPosition:
    """Ouvre une position spéculative de `amount` FCFA au cours actuel."""
    from .portfolio import load_portfolio  # import local : évite la circularité

    snap = api.market_snapshot()
    quote = snap.by_code(code)
    if quote is None or quote.last <= 0:
        raise ValueError(f"Titre {code} introuvable ou sans cotation")
    # Règle IPS : les poches sont étanches (un investissement ne devient pas un trade).
    norm = quote.code.strip().upper()
    for p in load_portfolio():
        if not p.closed and p.code.strip().upper() == norm:
            raise ValueError(
                f"Règle IPS — poches étanches : {norm} est déjà détenu dans le NOYAU "
                f"dividende. Un investissement ne devient pas une position spéculative. "
                f"(Si la thèse noyau est morte, clôture d'abord : portf close {norm})"
            )
    quantity = int(amount // quote.last)
    if quantity <= 0:
        raise ValueError(f"Montant {amount:,.0f} insuffisant pour 1 action à {quote.last:,.0f}")
    return SpecPosition(
        code=quote.code.strip(),
        name=quote.name,
        entry_price=quote.last,
        quantity=quantity,
    )


def check_all(api: BSApi) -> list[str]:
    """Vérifie toutes les positions ouvertes. Retourne les instructions."""
    positions = load_positions()
    snap = api.market_snapshot()
    events: list[str] = []
    for pos in positions:
        if pos.closed:
            continue
        quote = snap.by_code(pos.code)
        if quote is None or quote.last <= 0:
            continue
        for ev in check_position(pos, quote.last):
            events.append(ev)  # ev contient déjà l'action + le titre
        # Zone morte prolongée → revue unique (l'histoire : conserver est positif,
        # mais le setup mérite une vérification après ~6 mois sans événement).
        zm = zone_morte_status(pos, api)
        if (
            zm
            and zm[1]
            and zm[0] >= ZONE_DEAD_REVIEW_DAYS
            and not pos.review_alerted
        ):
            pos.review_alerted = True
            events.append(
                f"🔍 REVUE {pos.name} ({pos.code}) — {zm[0]} séances sans +20 % ni stop −15 %.\n"
                f"   Historique out-of-sample 2023-2026 : 62 % des inertes montent ensuite "
                f"(médiane nette +4,4 % sur les 60 séances suivantes, après frais) → conserver "
                f"reste défendable, mais vérifie que le setup est toujours valide.\n"
                f"   Sinon clôture manuelle : spec close {pos.code}"
            )
    save_positions(positions)
    return events


# --------------------------------------------------------- candidats (entrée)
def load_candidates_state() -> dict:
    if not CANDIDATES_STATE_FILE.exists():
        return {"seen_codes": []}
    try:
        return json.loads(CANDIDATES_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"seen_codes": []}


def save_candidates_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check_open_spec_positions(api, notifier) -> None:
    """Filet des paris ouverts : stop −15 % et paliers +20/+35/+50.

    Vérifié chaque matin par le check quotidien (les paris rapides du soir ont été
    SUPPRIMÉS le 10/09 — décision LEO : la BRVM exécute trop lentement, l'ordre du
    lendemain manque l'occasion). Le filet, lui, survit : il protège les positions
    spéculatives QUE LEO a pu ouvrir « en conscience », sans jamais passer d'ordre.
    """
    snap = api.market_snapshot()
    sent = 0
    for p in load_positions():
        if p.closed:
            continue
        q = snap.by_code(p.code)
        if q is None or q.last <= 0:
            continue
        last = q.last
        if last <= p.stop_loss:
            msg = (
                f"🔴 STOP — {p.name} ({p.code})\n\n"
                f"Ton pari est tombé à {last:,.0f} F : sous ton filet de\n"
                f"{p.stop_loss:,.0f} F (−15 %).\n\n"
                f"📋 Action : VENDS TOUT, sans discuter.\n"
                f"🚫 Rappel : un pari perdant ne devient JAMAIS un investissement."
            )
        elif last >= p.entry_price * 1.50 and not (p.sold_1 and p.sold_2):
            msg = (
                f"🎉 DERNIER PALIER — {p.name} ({p.code}) à {last:,.0f} F (+50 %)\n\n"
                f"📋 Action : VENDS LE RESTE de la position.\n"
                f"🚫 Rappel : un pari gagné reste un pari — encaisse."
            )
        elif last >= p.entry_price * 1.35 and p.sold_1 and not p.sold_2:
            msg = (
                f"📈 PALIER +35 % — {p.name} ({p.code}) à {last:,.0f} F\n\n"
                f"📋 Action : vends encore 1 sur 3 (il t'en reste 1/3 après).\n"
                f"🚫 Règle : +20 % vendre 1/3 · +35 % encore 1/3 · +50 % tout."
            )
        elif last >= p.entry_price * 1.20 and not p.sold_1:
            msg = (
                f"📈 PALIER +20 % — {p.name} ({p.code}) à {last:,.0f} F\n\n"
                f"📋 Action : vends 1 sur 3 — tu sécurises et le reste devient gratuit.\n"
                f"🚫 Règle : +20 % vendre 1/3 · +35 % encore 1/3 · +50 % tout."
            )
        else:
            continue
        print(msg)
        if notifier.enabled:
            notifier.send(msg)
        sent += 1
    return sent


def detect_new_candidates(api: BSApi, min_signals: int = MIN_SIGNALS) -> list[dict]:
    """Nouveaux candidats spéculatifs (≥ min_signals) jamais vus → alerte d'entrée.

    L'état stocke les codes déjà signalés pour ne pas re-alerter les mêmes
    titres chaque jour.
    """
    candidates = screen_speculation(api, min_signals)
    state = load_candidates_state()
    seen = set(state.get("seen_codes", []))
    new = [c for c in candidates if c["code"] not in seen]
    state["seen_codes"] = [c["code"] for c in candidates]
    save_candidates_state(state)
    return new
