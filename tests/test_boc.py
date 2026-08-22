"""Tests du scraping BOC (Bulletin Officiel de la Cote)."""
import pytest

from src.boc import detect_events, match_code, parse_operations

OPERATIONS_SAMPLE = """
OPERATIONS EN COURS
Emetteur
Opération
SGB CI
Paiement de dividendes de 2 606 F CFA par action (IRVM applicable de 12 % pour les personnes physiques et 10 % pour les personnes morales), le 24/08/2026
SERVAIR ABIDJAN CI
Paiement de dividendes de 229 F CFA par action (IRVM applicable de 12 % pour les personnes physiques et 10 % pour les personnes morales), le 30/09/2026
AVIS
"""


def test_match_code():
    assert match_code("SGB CI") == "SGBC"
    assert match_code("SONATEL SN") == "SNTS"
    assert match_code("SOLIBRA CI") == "SLBC"
    assert match_code("PALMCI") == "PALC"
    assert match_code("SERVAIR ABIDJAN CI") is None


def test_parse_operations():
    ops = parse_operations(OPERATIONS_SAMPLE)
    assert len(ops) == 2
    sg = next(o for o in ops if o["code"] == "SGBC")
    assert sg["montant"] == 2606.0
    assert sg["date_paiement"] == "24/08/2026"
    # SERVAIR n'est pas dans le noyau -> code None mais bien parsé
    sv = next(o for o in ops if o["emetteur"].startswith("SERVAIR"))
    assert sv["montant"] == 229.0
    assert sv["code"] is None


def test_detect_events_announce_then_rectify(monkeypatch, tmp_path):
    monkeypatch.setattr("src.boc.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr("src.boc.fetch_sikafinance_dividendes", lambda: {})  # pas de réseau

    # 1er run : annonce
    events = detect_events(OPERATIONS_SAMPLE, None, ["SGBC", "SNTS", "SLBC", "PALC"])
    assert len(events) == 1
    assert events[0]["action"] == "ANNONCÉ"
    assert events[0]["montant"] == 2606.0

    # 2e run : montant rectifié (2 606 -> 3 000)
    rectified = OPERATIONS_SAMPLE.replace("2 606", "3 000")
    events2 = detect_events(rectified, None, ["SGBC", "SNTS", "SLBC", "PALC"])
    assert len(events2) == 1
    assert events2[0]["action"] == "RECTIFIÉ"
    assert events2[0]["ancien"] == 2606.0
    assert events2[0]["montant"] == 3000.0

    # 3e run : aucun changement -> silence
    assert detect_events(rectified, None, ["SGBC"]) == []


def test_detect_events_cross_check_divergence(monkeypatch, tmp_path):
    monkeypatch.setattr("src.boc.STATE_FILE", tmp_path / "state.json")
    # sikafinance (source indépendante) donne un montant différent du BOC
    monkeypatch.setattr("src.boc.fetch_sikafinance_dividendes", lambda: {"SGBC": 3000.0})
    events = detect_events(OPERATIONS_SAMPLE, None, ["SGBC"])
    assert len(events) == 1
    assert "cross_sika" in events[0]
    assert events[0]["cross_sika"] == 3000.0  # divergence vs 2606 du BOC
