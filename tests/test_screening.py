"""Tests des indicateurs techniques et du score (screening)."""
from src.screening import avg_volume, change_pct, compute_score, ema, rsi_wilder, sma


# -------------------------------------------------------------------- RSI
def test_rsi_uptrend_is_high():
    r = rsi_wilder([float(i) for i in range(1, 20)])
    assert r is not None and r > 90


def test_rsi_downtrend_is_low():
    r = rsi_wilder([float(i) for i in range(19, 0, -1)])
    assert r is not None and r < 10


def test_rsi_within_bounds():
    import random

    closes = [50 + random.uniform(-5, 5) for _ in range(40)]
    r = rsi_wilder(closes)
    assert r is not None and 0 <= r <= 100


def test_rsi_insufficient_data():
    assert rsi_wilder([1.0, 2.0, 3.0]) is None  # moins de 15 points


# ---------------------------------------------------------------- moyennes
def test_sma_last_three():
    assert sma([1, 2, 3, 4, 5], 3) == 4.0


def test_ema_constant_series():
    assert ema([10.0] * 30, 10) == 10.0


# ---------------------------------------------------------------- momentum
def test_change_pct(make_bars):
    bars = make_bars([100, 110, 121])  # +21% sur 3 séances
    assert abs(change_pct(bars, 5) - 21.0) < 0.01


def test_change_pct_zero_if_flat(make_bars):
    bars = make_bars([100, 100, 100])
    assert change_pct(bars, 5) == 0.0


# ------------------------------------------------------------------ volume
def test_avg_volume(make_bars):
    bars = make_bars([100] * 25, volumes=[200] * 25)
    assert avg_volume(bars) == 200.0


# ------------------------------------------------------------------- score
def test_compute_score_ordering_and_bounds():
    high = compute_score(50, 100, 90, 110, 2, 12, 3, 0.9)
    low = compute_score(85, 100, 90, 80, -3, -15, 0.2, 0.1)
    assert high > low
    assert -1.5 <= high <= 5.5
    assert -1.5 <= low <= 5.5
