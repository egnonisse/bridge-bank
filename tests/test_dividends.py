"""Tests du suivi des encaissements réels de dividendes (avis BSTrade)."""
from src.dividends import add_dividend, load_dividends, total_encaissé


def test_add_and_total(monkeypatch, tmp_path):
    monkeypatch.setattr("src.dividends.DIVIDENDES_FILE", tmp_path / "div.json")
    add_dividend("SGBC", 2293.0, actions=3, date="2026-08-24")
    add_dividend("SLBC", 1500.0, actions=4, date="2026-08-25")
    items = load_dividends()
    assert len(items) == 2
    assert items[0]["code"] == "SGBC"
    assert items[0]["actions"] == 3
    assert abs(total_encaissé() - 3793.0) < 0.01


def test_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("src.dividends.DIVIDENDES_FILE", tmp_path / "vide.json")
    assert load_dividends() == []
    assert total_encaissé() == 0.0
