"""Tests du renforcement du noyau (racheter bas) + plan d'action quotidien."""
from src.main import _build_heartbeat
from src.portfolio import DividendPosition, reinforcement_messages


def _pos(code="SLBC", dps=2127.0):
    return DividendPosition(code=code, name="SOLIBRA CI", entry_price=38025.0,
                            quantity=4, dps=dps, per_open=14.0)


def test_reinforce_quand_cours_sous_seuil_et_filtres_ok():
    hits = reinforcement_messages([_pos()],
                                  price_of=lambda c: 38000.0,
                                  per_of=lambda c: 13.7)
    assert [c for c, _ in hits] == ["SLBC"]
    assert "RENFORCE SLBC" in hits[0][1]
    assert "4 %" in hits[0][1]  # le loyer garanti, en langage simple


def test_pas_de_reinforcement_quand_trop_cher():
    hits = reinforcement_messages([_pos()],
                                  price_of=lambda c: 40000.0,
                                  per_of=lambda c: 13.7)
    assert hits == []


def test_pas_de_reinforcement_quand_payout_tendu():
    # per 15 -> payout = 2127*15/38000 = 84 % > 80 %
    hits = reinforcement_messages([_pos()],
                                  price_of=lambda c: 38000.0,
                                  per_of=lambda c: 15.0)
    assert hits == []


def test_pas_de_reinforcement_quand_per_trop_haut():
    hits = reinforcement_messages([_pos()],
                                  price_of=lambda c: 38000.0,
                                  per_of=lambda c: 20.0)
    assert hits == []


def test_heartbeat_avec_plan_daction():
    msg = _build_heartbeat([("BOC", True)], ["Vends 1 sur 3 de SNTS", "RENFORCE SLBC"])
    assert "🎯 AUJOURD'HUI POUR TON NOYAU" in msg
    assert "Vends 1 sur 3 de SNTS" in msg
    assert "RENFORCE SLBC" in msg


def test_heartbeat_sans_action():
    msg = _build_heartbeat([("BOC", True)], [])
    assert "ne touche à rien" in msg
