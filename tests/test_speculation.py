"""Tests de la logique de spéculation (sortie mécanique, critique pour l'argent réel).

Couvre : stop-loss, paliers +20/+35/+50%, stop suiveur, remaining, persistance,
ouverture de position, détection de signaux.
"""
import pytest

from src.domaine.models import Quote, Snapshot
from src.strategie.speculation import (
    SpecPosition,
    check_position,
    detect_signals,
    load_positions,
    open_position,
    save_positions,
)


def make_pos(entry=10000, qty=100):
    return SpecPosition(code="TEST", name="Test", entry_price=entry, quantity=qty)


# ---------------------------------------------------------------- stop-loss
def test_stop_loss_initial():
    p = make_pos()
    check_position(p, 8400)  # -16% -> sous le stop -15% (8500)
    assert p.closed
    assert "STOP" in p.close_reason


def test_no_stop_above_threshold():
    p = make_pos()
    check_position(p, 8600)  # -14% -> au-dessus du stop
    assert not p.closed


# ------------------------------------------------------------- palier +20%
def test_take1_sells_third_and_break_even():
    p = make_pos()
    events = check_position(p, 12000)
    assert p.sold_1 and not p.sold_2 and not p.closed
    assert p.stop_loss == 10000  # break-even
    assert any("+20%" in e for e in events)


def test_break_even_triggers():
    p = make_pos()
    check_position(p, 12000)
    check_position(p, 9900)  # sous le break-even
    assert p.closed and "STOP" in p.close_reason


# ------------------------------------------------------------- palier +35%
def test_take2_trailing_stop():
    p = make_pos()
    check_position(p, 12000)
    events = check_position(p, 13500)
    assert p.sold_2 and not p.closed
    assert p.stop_loss == round(13500 * 0.9, 2)
    assert any("+35%" in e for e in events)


def test_trailing_stop_follows_high():
    p = make_pos()
    check_position(p, 12000)
    check_position(p, 13500)
    check_position(p, 14000)  # nouveau plus haut
    assert p.stop_loss == round(14000 * 0.9, 2)


def test_trailing_stop_triggers():
    p = make_pos()
    check_position(p, 12000)
    check_position(p, 13500)
    check_position(p, 14000)
    check_position(p, 12500)  # sous le stop suiveur (12600)
    assert p.closed


# ------------------------------------------------------------- palier +50%
def test_take3_final_close_cascade():
    p = make_pos()
    events = check_position(p, 15000)
    assert p.closed and "+50%" in p.close_reason
    assert p.sold_1 and p.sold_2  # les paliers intermédiaires sont passés


# ---------------------------------------------------------------- remaining
def test_remaining_progression():
    p = make_pos(qty=100)
    assert p.remaining == 100
    p.sold_1 = True
    assert p.remaining == 66
    p.sold_2 = True
    assert p.remaining == 33


# --------------------------------------------------------------- persistance
def test_persist_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("src.strategie.speculation.POSITIONS_FILE", tmp_path / "spec.json")
    p = make_pos()
    p.sold_1 = True
    save_positions([p])
    loaded = load_positions()
    assert len(loaded) == 1
    assert loaded[0].code == "TEST"
    assert loaded[0].sold_1 is True
    assert loaded[0].remaining == 66


# ------------------------------------------------------------ open_position
def test_open_position_quantity_and_stop():
    class FakeAPI:
        def __init__(self):
            self.snap = Snapshot(stocks=[Quote(code="NSBC", name="NSIA", last=23650, is_index=False)])

        def market_snapshot(self):
            return self.snap

    pos = open_position(FakeAPI(), "NSBC", 100000)
    assert pos.quantity == 4  # 100000 // 23650
    assert pos.stop_loss == round(23650 * 0.85, 2)


def test_open_position_insufficient_amount():
    class FakeAPI:
        def __init__(self):
            self.snap = Snapshot(stocks=[Quote(code="X", name="X", last=50000, is_index=False)])

        def market_snapshot(self):
            return self.snap

    with pytest.raises(ValueError):
        open_position(FakeAPI(), "X", 10000)  # pas assez pour 1 action à 50000


# --------------------------------------------------------------- signaux
def test_detect_signals_uptrend(make_bars):
    closes = [float(100 + i) for i in range(70)]  # hausse constante
    bars = make_bars(closes, volumes=[1000] * 70)
    quote = Quote(code="X", name="X", last=closes[-1], high_52w=closes[-1] * 0.5, volume=5000, is_index=False)
    signals = detect_signals(quote, bars)
    joined = " ".join(signals)
    assert "momentum" in joined
    assert "golden cross" in joined
    assert "breakout 20j" in joined
    # Décision 12/10 : le volume ne compte PLUS dans la confluence…
    assert "volume" not in joined
    # …mais il reste affiché en information (5000 vs moyenne 1000 → 5x).
    from src.strategie.speculation import volume_info
    assert volume_info(quote, bars) == "volume 5.0x"


def test_screen_speculation_requires_full_confluence(monkeypatch):
    """Régression : le filtre doit garder les titres >= min_signals (pas l'inverse).

    Décision 12/10 : le volume est sorti du décompte — la confluence se calcule
    sur breakout + momentum/RSI/golden cross uniquement.
    """
    from src.strategie import speculation as sp

    class FakeAPI:
        def market_snapshot(self):
            return Snapshot(stocks=[
                Quote(code="AAA", name="A", last=100, is_index=False),
                Quote(code="BBB", name="B", last=100, is_index=False),
                Quote(code="CCC", name="C", last=100, is_index=False),
            ])

    monkeypatch.setattr(sp, "load_all_history",
                        lambda api: {"AAA": [1], "BBB": [1], "CCC": [1]})
    monkeypatch.setattr(sp, "detect_signals", lambda q, bars: {
        "AAA": ["breakout 20j", "momentum +15%", "RSI 62"],  # 3 → candidat
        "BBB": ["breakout 20j", "momentum +15%"],            # 2 → pas candidat
        "CCC": ["momentum +15%", "RSI 62", "golden cross"],  # pas de breakout → exclu
    }[q.code])
    monkeypatch.setattr(sp, "volume_info", lambda q, bars: None)

    res = sp.screen_speculation(FakeAPI(), min_signals=3)
    assert [r["code"] for r in res] == ["AAA"]


def test_volume_ne_requalifie_pas_un_titre(monkeypatch):
    """Un volume énorme sans confluence suffisante ne crée PAS de candidat
    (avant la décision 12/10, volume + breakout suffisaient à qualifier)."""
    from src.strategie import speculation as sp

    class FakeAPI:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="VOL", name="V", last=100, is_index=False)])

    monkeypatch.setattr(sp, "load_all_history", lambda api: {"VOL": [1]})
    monkeypatch.setattr(sp, "detect_signals", lambda q, bars: ["breakout 20j"])
    monkeypatch.setattr(sp, "volume_info", lambda q, bars: "volume 9.9x")

    res = sp.screen_speculation(FakeAPI(), min_signals=3)
    assert res == []   # le volume (information) ne compte pas dans la confluence
