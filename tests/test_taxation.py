"""Tests de la fiscalité et des frais de transaction (commission)."""
from src.taxation import commission


def test_commission_small_order_min_1000():
    """Ordre de 50 000 F : courtage 0,8 % = 400 F < 1 000 F → min 1 000 F s'applique."""
    # courtage 1 000 + TVA 180 + BRVM 228 = 1 408 F
    assert abs(commission(50000) - 1408.0) < 0.01


def test_commission_medium_order_no_min():
    """Ordre de 150 000 F : courtage 1 200 F > 1 000 F → pas de min."""
    # courtage 1 200 + TVA 216 + BRVM 684 = 2 100 F
    assert abs(commission(150000) - 2100.0) < 0.01


def test_commission_rate_about_1_4pct():
    """Sur un ordre moyen (≥ 125 000 F), le taux effectif ≈ 1,40 %."""
    assert abs(commission(150000) / 150000 - 0.014) < 0.0001


def test_commission_small_order_rate_higher():
    """Un petit ordre subit un taux effectif plus élevé (min 1 000 F)."""
    rate = commission(50000) / 50000
    assert rate > 0.02  # ~2,8 % vs 1,4 % sur ordre moyen


def test_commission_zero_or_negative():
    assert commission(0) == 0.0
    assert commission(-100) == 0.0
