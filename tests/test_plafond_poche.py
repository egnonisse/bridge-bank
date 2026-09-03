"""Tests du plafond de poche proposé (spéculation en conscience)."""
from scripts.close_check import propose_plafond


def test_propose_plafond_10_pct():
    assert propose_plafond(730_000) == 70_000
    assert propose_plafond(1_500_000) == 150_000
    assert propose_plafond(0) == 70_000
    assert propose_plafond(60_000) == 10_000  # plancher
