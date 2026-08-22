"""Tests du screener fondamentaux (value+dividende, magic formula).

Le scraping est simulé (mock) pour tester la logique de filtrage/classement
sans dépendre du réseau lent.

Le seuil de rendement est NET (4 % après IRVM 12 % + frais 0,80 %/an),
soit ≈ 5,45 % de rendement BRUT. Les dps de test sont les dividendes
officiels BRVM 2025 (en brut).
"""
from src.models import Quote, Snapshot
from src.screener import flag_value_traps, screen_magic_formula, screen_value_dividend


class FakeAPI:
    def __init__(self, stocks):
        self.snap = Snapshot(stocks=stocks)

    def market_snapshot(self):
        return self.snap


def _stocks():
    return [
        Quote(code="SNTS", name="Sonatel", last=32000, is_index=False),
        Quote(code="BOAS", name="BOA SN", last=7700, is_index=False),
        Quote(code="SOGC", name="SOGB", last=7915, is_index=False),
        Quote(code="PALC", name="PalmCI", last=8980, is_index=False),
        Quote(code="SLBC", name="Solibra", last=37400, is_index=False),
        Quote(code="SGBC", name="SGBCI", last=39000, is_index=False),
        Quote(code="FAIBL", name="Faible", last=10000, is_index=False),
        Quote(code="ETIT", name="ETI", last=69, is_index=False),
        Quote(code="UNLC", name="Unilever", last=56300, is_index=False),
        Quote(code="FTSC", name="Filtisac", last=2185, is_index=False),
    ]


def _funds():
    return {
        "SNTS": {"per": 7.74, "dps": 1977},  # brut 6,18 % -> net 4,64 %
        "BOAS": {"per": 12.57, "dps": 511},  # net 5,04 %
        "SOGC": {"per": 13.69, "dps": 570},  # net 5,54 %
        "PALC": {"per": 8.95, "dps": 502},  # net 4,12 %
        "SLBC": {"per": 13.45, "dps": 2127},  # net 4,20 %
        "SGBC": {"per": 11.97, "dps": 2606},  # net 5,08 %
        "FAIBL": {"per": 10.0, "dps": 490},  # brut 4,90 % -> net 3,51 % (< 4 %)
        "ETIT": {"per": 3.40, "dps": 1},  # net 0,48 %
        "UNLC": {"per": 832, "dps": 0},  # PER absurde
        "FTSC": {"per": 66, "dps": 1727},  # 79 % exceptionnel
    }


NOYAU = ["SNTS", "BOAS", "SOGC", "PALC", "SLBC", "SGBC"]


def test_value_dividend_filters(monkeypatch):
    monkeypatch.setattr("src.screener.scrape_all_fundamentals", lambda api, force=False: _funds())
    results = screen_value_dividend(FakeAPI(_stocks()))
    codes = [r["code"] for r in results]
    for c in NOYAU:
        assert c in codes  # dps officiels -> rendement NET >= 4 %
    assert "FAIBL" not in codes  # net 3,51 % < 4 %
    assert "ETIT" not in codes
    assert "UNLC" not in codes
    assert "FTSC" not in codes


def test_value_dividend_sorted_by_per(monkeypatch):
    monkeypatch.setattr("src.screener.scrape_all_fundamentals", lambda api, force=False: _funds())
    results = screen_value_dividend(FakeAPI(_stocks()))
    pers = [r["per"] for r in results]
    assert pers == sorted(pers)


def test_net_yield_reported(monkeypatch):
    monkeypatch.setattr("src.screener.scrape_all_fundamentals", lambda api, force=False: _funds())
    results = {r["code"]: r for r in screen_value_dividend(FakeAPI(_stocks()))}
    assert abs(results["BOAS"]["net_yield"] - 5.04) < 0.05
    assert abs(results["SGBC"]["net_yield"] - 5.08) < 0.05


def test_magic_formula_ranking(monkeypatch):
    monkeypatch.setattr("src.screener.scrape_all_fundamentals", lambda api, force=False: _funds())
    results = screen_magic_formula(FakeAPI(_stocks()))
    scores = [r["score"] for r in results]
    assert scores == sorted(scores)  # trié par score croissant
    assert results[0]["code"] == "SNTS"  # meilleur combo PER+rendement


def test_flag_value_traps(monkeypatch):
    stocks = [
        Quote(code="SUSP", name="Suspect", last=15000, is_index=False),  # yld 13.3%
        Quote(code="CHER", name="Cher", last=1000, is_index=False),  # PER 30
        Quote(code="OK", name="Sain", last=10000, is_index=False),  # yld 5%, PER 10
    ]
    funds = {
        "SUSP": {"per": 10, "dps": 2000},  # rendement 13.3% -> anormal
        "CHER": {"per": 30, "dps": 50},  # rendement 5%, PER 30 -> élevé
        "OK": {"per": 10, "dps": 500},  # rendement 5%, PER 10 -> sain
    }
    monkeypatch.setattr("src.screener.scrape_all_fundamentals", lambda api, force=False: funds)
    traps = flag_value_traps(FakeAPI(stocks))
    codes = {t["code"] for t in traps}
    assert "SUSP" in codes  # rendement anormal
    assert "CHER" in codes  # PER élevé
    assert "OK" not in codes  # sain
