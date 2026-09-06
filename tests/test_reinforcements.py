"""Tests du renforcement du noyau (racheter bas) + verrou de concentration + plan d'action."""
from src.main import _build_heartbeat
from src.portfolio import DividendPosition, reinforcement_messages


def _pos(code="SLBC", dps=2127.0):
    return DividendPosition(code=code, name="SOLIBRA CI", entry_price=38025.0,
                            quantity=4, dps=dps, per_open=14.0)


def test_reinforce_quand_cours_sous_seuil_et_filtres_ok():
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=800000.0)
    assert [c for c, _ in hits] == ["SLBC"]
    assert blocked == []
    assert "RENFORCE SLBC" in hits[0][1]
    assert "4 %" in hits[0][1]  # le loyer garanti, en langage simple


def test_pas_de_reinforcement_quand_trop_cher():
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 40000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=800000.0)
    assert hits == [] and blocked == []


def test_pas_de_reinforcement_quand_payout_tendu():
    # per 15 -> payout = 2127*15/38000 = 84 % > 80 %
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 15.0,
                                           total_stocks=800000.0)
    assert hits == [] and blocked == []


def test_pas_de_reinforcement_quand_per_trop_haut():
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 20.0,
                                           total_stocks=800000.0)
    assert hits == [] and blocked == []


def test_blocage_concentration_au_dessus_du_plafond():
    # 4 SLBC × 38 000 = 152 000 sur un total de 300 000 → 51 % > 35 % → bloqué
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=300000.0)
    assert hits == []
    assert [c for c, _ in blocked] == ["SLBC"]
    assert "BLOQUE" in blocked[0][1]
    assert "35 %" in blocked[0][1]


def test_concentration_sous_plafond_ne_bloque_pas():
    # 152 000 / 500 000 = 30 % ≤ 35 % → renforce normalement
    hits, blocked = reinforcement_messages([_pos()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=500000.0)
    assert [c for c, _ in hits] == ["SLBC"]
    assert blocked == []


def test_heartbeat_avec_plan_daction():
    msg = _build_heartbeat([("BOC", True)], ["Vends 1 sur 3 de SNTS", "RENFORCE SLBC"])
    assert "🎯 AUJOURD'HUI POUR TON NOYAU" in msg
    assert "Vends 1 sur 3 de SNTS" in msg
    assert "RENFORCE SLBC" in msg


def test_heartbeat_sans_action():
    msg = _build_heartbeat([("BOC", True)], [])
    assert "ne touche à rien" in msg
