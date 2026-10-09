"""Tests de la surveillance des ordres limites + re-alerte renforcement (prix amélioré)."""
from datetime import datetime

from src.strategie.noyau_check import prep_watch_alerts
from src.portfolio import check_reinforcements, load_portfolio


def test_alerte_quand_le_prix_passe_sous_la_limite():
    watch = {"BOAC": {"limit": 35000.0, "name": "BOA CI"}}
    alerts, watch = prep_watch_alerts(watch, price_of=lambda c: 34800.0)
    assert len(alerts) == 1
    assert "TON ORDRE LIMITE EST PRÊT" in alerts[0]
    assert "34,800" in alerts[0]


def test_silence_au_dessus_de_la_limite():
    watch = {"BOAC": {"limit": 35000.0, "name": "BOA CI"}}
    alerts, _ = prep_watch_alerts(watch, price_of=lambda c: 36000.0)
    assert alerts == []


def test_pas_de_re_alerte_pour_une_petite_amelioration():
    watch = {"BOAC": {"limit": 35000.0, "name": "BOA CI",
                      "alerted_at": datetime.now().isoformat(), "alerted_price": 34800.0}}
    # −2 % sous le prix déjà signalé → pas de re-alerte (seuil 3 %)
    alerts, _ = prep_watch_alerts(watch, price_of=lambda c: 34200.0)
    assert alerts == []


def test_re_alerte_si_le_prix_s_ameliore_encore_de_plus_de_3_pct():
    watch = {"BOAC": {"limit": 35000.0, "name": "BOA CI",
                      "alerted_at": datetime.now().isoformat(), "alerted_price": 34800.0}}
    # −4,3 % sous le prix déjà signalé → re-alerte
    alerts, watch = prep_watch_alerts(watch, price_of=lambda c: 33300.0)
    assert len(alerts) == 1
    assert watch["BOAC"]["alerted_price"] == 33300.0


class _FakeSnap:
    def __init__(self, prices):
        self._prices = prices

    def by_code(self, code):
        p = self._prices.get(code)
        if p is None:
            return None

        class _Q:
            last = p
            name = code
        return _Q()


class _FakeAPI:
    def __init__(self, prices):
        self._prices = prices

    def market_snapshot(self):
        return _FakeSnap(self._prices)


def test_re_alerte_renforcement_quand_le_prix_baisse_de_3_pct_pendant_le_cooldown(monkeypatch, tmp_path):
    from datetime import timedelta

    # état factice : alerte envoyée hier à 38 000 → cooldown actif
    state = {"SLBC": {"date": (datetime.now() - timedelta(days=1)).isoformat(),
                      "price": 38000.0}}
    state_file = tmp_path / "reinf_state.json"
    state_file.write_text(str(state).replace("'", '"'), encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REINF_STATE_FILE", state_file)
    monkeypatch.setattr("src.collecte.fundamentals.get_per_brvm", lambda code: 13.7)

    prices = {"SLBC": 36500.0, "SGBC": 50000.0, "SNTS": 50000.0}  # seul SLBC sous son seuil
    api = _FakeAPI(prices)

    hits = check_reinforcements(api)
    msgs = [m for _, m in hits]
    assert msgs and "LE PRIX S'EST ENCORE AMÉLIORÉ" in msgs[0]


def test_pas_de_re_alerte_renforcement_pour_une_baisse_faible(monkeypatch, tmp_path):
    from datetime import timedelta

    state = {"SLBC": {"date": (datetime.now() - timedelta(days=1)).isoformat(),
                      "price": 38000.0}}
    state_file = tmp_path / "reinf_state.json"
    state_file.write_text(str(state).replace("'", '"'), encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REINF_STATE_FILE", state_file)
    monkeypatch.setattr("src.collecte.fundamentals.get_per_brvm", lambda code: 13.7)

    prices = {"SLBC": 37500.0, "SGBC": 50000.0, "SNTS": 50000.0}  # −1,3 % seulement
    hits = check_reinforcements(_FakeAPI(prices))
    assert hits == []
