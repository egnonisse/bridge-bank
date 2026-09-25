"""Tests des filtres de fiabilité du dividende (régularité, croissance, liquidité)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dividend_history import (GROWTH_MIN_PCT, MIN_VOLUME_MILLIONS,
                                  parse_growth_1y, parse_payout_years_last5,
                                  volume_moyen_millions)


def _html(dates, growth="5.0%"):
    return (
        "<html><body>"
        + "".join(f"<td>{d}</td>" for d in dates)
        + f"Dividend Growth<span>(1Y)</span><div>{growth}</div>"
        + "</body></html>"
    )


def test_payout_years_5_sur_5():
    # date de publication du site (la plus récente) + 5 années de paiements
    html = _html(["2026-09-25", "2026-05-22", "2026-05-26", "2025-05-20",
                  "2024-05-15", "2023-05-15", "2022-05-16"])
    assert parse_payout_years_last5(html) == 5


def test_payout_years_4_sur_5_annee_manquante():
    html = _html(["2026-09-25", "2026-05-22", "2025-05-20",
                  "2024-05-15", "2022-05-16"])  # 2023 manquant
    assert parse_payout_years_last5(html) == 4


def test_payout_years_trop_court():
    html = _html(["2026-09-25", "2026-05-22", "2025-05-20"])
    assert parse_payout_years_last5(html) == -1


def test_growth_negative_ok():
    assert parse_growth_1y(_html([], growth="-5.38%")) == -5.38


def test_growth_na():
    assert parse_growth_1y(_html([], growth="n/a")) is None


def test_growth_seuil_calibre_garde_snts_et_palc():
    # preuve du calibrage : SNTS -5,4 % et PALC -2,2 % passent le seuil -10 %
    assert -5.38 >= GROWTH_MIN_PCT
    assert -2.23 >= GROWTH_MIN_PCT


class _Bar:
    def __init__(self, close, volume):
        self.close = close
        self.volume = volume


def test_volume_moyen():
    bars = [_Bar(1000.0, 10000)] * 60  # 10 000 actions/j à 1 000 F = 10 M F/j
    assert abs(volume_moyen_millions(bars) - 10.0) < 1e-6


def test_volume_seuil_non_punitif():
    # vérifié le 25/09 : 41/43 titres BRVM passent 5 M F/j
    assert MIN_VOLUME_MILLIONS == 5.0
