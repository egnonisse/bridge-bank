"""Tests du module obligations (YTM, référentiel, positions)."""
from datetime import date

import pytest

from src.bonds import (
    NOMINAL,
    add_bond_position,
    bonds_market_value,
    buyable_lines,
    coupons_per_year,
    current_yield,
    issuer_risk,
    load_bond_positions,
    load_market,
    market_line,
    ytm,
)

TODAY = date(2026, 8, 20)


def test_market_has_70_lines():
    lines = load_market()
    assert len(lines) == 70
    assert market_line("TPCI.O87")["bid"] == 98
    assert market_line("EOS.O9")["prev_close"] == 98


def test_issuer_risk():
    assert issuer_risk("TPCI.O87") == "faible"
    assert issuer_risk("EOS.O9") == "faible"
    assert issuer_risk("EOM.O8") == "élevé"
    assert issuer_risk("TPNE.O4") == "élevé"
    assert issuer_risk("ORGT.O2") == "moyen"


def test_ytm_at_par_equals_coupon():
    # Acheté au pair (100), le rendement actuariel = coupon
    y = ytm(100, 6.0, 2028, TODAY)
    assert y == pytest.approx(6.0, abs=0.15)


def test_ytm_discount_above_coupon():
    # TPCI.O87 : 98 → YTM > coupon (gain de remboursement en plus)
    y = ytm(98, 5.9, 2029, TODAY)
    assert y == pytest.approx(6.5, abs=0.3)
    assert y > 5.9


def test_ytm_premium_can_be_negative():
    # Pétro Ivoire à 130 : perte au remboursement (100) supérieure aux coupons
    y = ytm(130, 6.8, 2029, TODAY)
    assert y is not None and y < 0


def test_ytm_expired_returns_none():
    assert ytm(100, 6.0, 2024, TODAY) is None


def test_current_yield():
    assert current_yield(98, 5.9) == pytest.approx(6.02, abs=0.05)
    assert current_yield(100, 6.5) == pytest.approx(6.5)


def test_buyable_lines_sorted_by_ytm():
    lines = buyable_lines(TODAY)
    assert len(lines) == 12  # 12 lignes avec offre vendeur le 20/08
    assert lines[0]["code"] == "TPCI.O87"  # meilleur YTM (décote 98)
    assert lines[0]["risk"] == "faible"
    assert lines[-1]["code"] == "PTRC.O1"  # YTM négatif → dernier
    assert lines[-1]["ytm"] < 0
    assert lines[0]["cost_per_unit"] == pytest.approx(9_800.0)


def test_add_position_and_coupons(monkeypatch, tmp_path):
    monkeypatch.setattr("src.bonds.POSITIONS_FILE", tmp_path / "positions.json")
    entry = add_bond_position("TPCI.O87", 10, 98, buy_date="2026-08-21")
    assert entry["label"] == "TPCI 5,90% 2024-2029"
    assert entry["coupon"] == 5.9

    positions = load_bond_positions()
    assert len(positions) == 1
    assert positions[0]["qty"] == 10

    # 10 titres × 10 000 F × 5,9 % = 5 900 F/an de coupons bruts
    assert coupons_per_year(positions) == pytest.approx(5_900.0)
    # Valeur au cours veille (98) : 10 × 10 000 × 0,98 = 98 000 F
    assert bonds_market_value(positions) == pytest.approx(98_000.0)


def test_add_position_unknown_code(monkeypatch, tmp_path):
    monkeypatch.setattr("src.bonds.POSITIONS_FILE", tmp_path / "positions.json")
    with pytest.raises(ValueError, match="inconnue"):
        add_bond_position("XXXX.O1", 10, 100)


def test_add_position_invalid_qty(monkeypatch, tmp_path):
    monkeypatch.setattr("src.bonds.POSITIONS_FILE", tmp_path / "positions.json")
    with pytest.raises(ValueError, match="Quantité"):
        add_bond_position("TPCI.O87", 0, 100)


def test_nominal_constant():
    assert NOMINAL == 10_000.0
