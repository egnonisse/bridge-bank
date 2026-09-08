"""Tests du renforcement du noyau + verrou de concentration INTELLIGENT
(origine du poids : hausse ≠ achats) + plan d'action quotidien."""
from src.main import _build_heartbeat
from src.portfolio import DividendPosition, reinforcement_messages


def _slbc(entry=38124.0, qty=5):
    return DividendPosition(code="SLBC", name="SOLIBRA CI", entry_price=entry,
                            quantity=qty, dps=2127.0, per_open=14.0)


def _snts(entry=32435.56, qty=6):
    return DividendPosition(code="SNTS", name="SONATEL SN", entry_price=entry,
                            quantity=qty, dps=1977.0, per_open=8.0)


def _sgbc(entry=39140.4, qty=5):
    return DividendPosition(code="SGBC", name="SGBCI", entry_price=39140.4,
                            quantity=qty, dps=2606.0, per_open=12.0)


def _prix(portefeuille):
    # prix réels : SLBC sous son seuil (38 457), SGBC payout frontière (skip),
    # SNTS juste sous son seuil (35 700) → poids marché 35,1 % > 35 → cas « limité »
    return {p.code: {"SLBC": 37250.0, "SGBC": 38500.0, "SNTS": 35700.0}.get(p.code, 0.0)
            for p in portefeuille}


def test_reinforce_libre_quand_poids_market_et_achat_sous_plafond():
    # Portefeuille réel : SLBC 30,5 % marché / 26 % achats → libre
    hits, blocked = reinforcement_messages([_slbc(), _snts(), _sgbc()],
                                           price_of=_prix([_slbc(), _snts(), _sgbc()]).get,
                                           per_of=lambda c: {"SLBC": 13.7}.get(c),
                                           total_stocks=800000.0)
    assert [c for c, _ in hits] == ["SLBC"]
    assert "RENFORCE SLBC" in hits[0][1] and "LIMITÉ" not in hits[0][1]
    assert blocked == []


def test_renforcement_limite_quand_poids_market_vient_de_la_hausse():
    # SNTS : 37,9 % marché (>35) mais 33,5 % achats (≤35) → LIMITÉ avec plafond
    hits, blocked = reinforcement_messages([_slbc(), _snts(), _sgbc()],
                                           price_of=_prix([_slbc(), _snts(), _sgbc()]).get,
                                           per_of=lambda c: 8.0,
                                           total_stocks=609750.0)
    assert blocked == []
    snts_hit = [m for c, m in hits if c == "SNTS"]
    assert snts_hit and "RENFORCE LIMITÉ" in snts_hit[0]
    assert "1 action" in snts_hit[0]  # plafond calculé : (40 %×580 935 − 194 613)//35 000 = 1
    assert "par sa HAUSSE" in snts_hit[0]


def test_bloque_quand_concentration_choisie_par_les_achats():
    # SLBC achetée chère (50 000) : 62,8 % des ACHATS mais 49 % du marché → bloqué
    pos = _slbc(entry=50000.0, qty=4)
    sgbc = _sgbc(qty=3)
    hits, blocked = reinforcement_messages([pos, sgbc],
                                           price_of={"SLBC": 28000.0, "SGBC": 38500.0}.get,
                                           per_of=lambda c: {"SLBC": 10.0}.get(c),
                                           total_stocks=227500.0)
    assert hits == []
    assert [c for c, _ in blocked] == ["SLBC"]
    assert "CONCENTRATION CHOISIE" in blocked[0][1]


def test_bloque_ligne_buffett_au_dela_de_la_moitie():
    # SLBC seule : 50,7 % du marché → ligne Buffett, quelle que soit l'origine
    hits, blocked = reinforcement_messages([_slbc(qty=4)],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=300000.0)
    assert hits == []
    assert [c for c, _ in blocked] == ["SLBC"]
    assert "LIGNE BUFFETT" in blocked[0][1]
    assert "moitié" in blocked[0][1]


def test_pas_de_reinforcement_quand_trop_cher():
    hits, blocked = reinforcement_messages([_slbc(), _snts()],
                                           price_of=lambda c: 40000.0,
                                           per_of=lambda c: 13.7,
                                           total_stocks=800000.0)
    assert hits == [] and blocked == []


def test_pas_de_reinforcement_quand_payout_tendu():
    hits, blocked = reinforcement_messages([_slbc(), _snts()],
                                           price_of=lambda c: 38000.0,
                                           per_of=lambda c: 15.0,
                                           total_stocks=800000.0)
    assert hits == [] and blocked == []


def test_heartbeat_avec_plan_daction():
    msg = _build_heartbeat([("BOC", True)],
                           ["Vends 1 sur 3 de SNTS", "RENFORCE LIMITÉ SGBC (plafond indiqué)"])
    assert "🎯 AUJOURD'HUI POUR TON NOYAU" in msg
    assert "Vends 1 sur 3 de SNTS" in msg
    assert "RENFORCE LIMITÉ SGBC" in msg


def test_heartbeat_sans_action():
    msg = _build_heartbeat([("BOC", True)], [])
    assert "ne touche à rien" in msg
