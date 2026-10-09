"""Tests des filtres noyau (alerte d'achat qualifiée)."""
from src.strategie.noyau_check import evaluate_noyau_candidate


def _mock_fund(monkeypatch, per: float, dps: float):
    monkeypatch.setattr("src.strategie.noyau_check.get_fundamentals",
                        lambda code: {"per": per, "dps": dps})


def test_opportunity_tous_filtres_passent(monkeypatch):
    # SGBC-like : dps 2606, PER 11.7, cours 38 950 → net ≈ 5,1 %, payout ≈ 78 %
    _mock_fund(monkeypatch, per=11.7, dps=2606.0)
    res = evaluate_noyau_candidate("SGBC", 38950.0, "SOCIETE GENERALE CI")
    assert res["verdict"] == "opportunity"
    assert "🎯 OPPORTUNITÉ NOYAU" in res["message"]
    assert "5.1 %" in res["message"]


def test_limit_fondamentaux_ok_mais_trop_cher(monkeypatch):
    _mock_fund(monkeypatch, per=10.0, dps=500.0)
    res = evaluate_noyau_candidate("BOAC", 15000.0, "BANK OF AFRICA CI")
    assert res["verdict"] == "limit"
    assert "📉 À PRÉPARER" in res["message"]
    # prix d'entrée du code : dps / 0,054545 / 1,014 (frais de transaction inclus)
    assert "9,040" in res["message"]


def test_silence_payout_tendu(monkeypatch):
    _mock_fund(monkeypatch, per=13.0, dps=2606.0)
    assert evaluate_noyau_candidate("XXX", 39000.0) is None


def test_silence_per_trop_haut(monkeypatch):
    _mock_fund(monkeypatch, per=20.0, dps=2606.0)
    assert evaluate_noyau_candidate("YYY", 30000.0) is None


def test_silence_pas_de_dividende(monkeypatch):
    _mock_fund(monkeypatch, per=8.0, dps=None)
    assert evaluate_noyau_candidate("ZZZ", 30000.0) is None
