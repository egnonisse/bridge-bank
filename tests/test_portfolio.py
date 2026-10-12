"""Tests du noyau dividende (positions long terme + sortie sur fondamentaux)."""
from datetime import datetime, timedelta

from src.domaine.models import Quote, Snapshot
from src.portfolio import (
    LEVEL_DECISION,
    LEVEL_FUNDAMENTAL,
    LEVEL_INFO,
    DividendPosition,
    check_dividend_position,
    load_portfolio,
    open_dividend_position,
    record_dividend,
    save_portfolio,
)


def make_pos(dps=1740, per=7.74, entry=32000, qty=3, opened=None):
    return DividendPosition(
        code="SNTS",
        name="Sonatel",
        entry_price=entry,
        quantity=qty,
        dps=dps,
        per_open=per,
        opened_at=opened or datetime.now().isoformat(),
    )


# -------------------------------------------------------- prix entrée/sortie
def test_exit_and_entry_prices():
    from src.taxation import entry_price_for_net

    p = make_pos(dps=1740)
    # rendement NET 2 % -> brut 3,18 % pour la sortie ; entrée = formule UNIQUE du code
    # (frais de courtage inclus — B0-04/B1-08 du 12/10).
    assert abs(p.exit_price - 54685.71) < 0.01
    assert abs(p.entry_price_ref - entry_price_for_net(1740)) < 0.01
    assert abs(p.entry_price_ref - 31459.57) < 0.01  # et la valeur concrète est gelée


def test_yield_pct():
    p = make_pos(dps=1740)
    assert abs(p.yield_pct(32000) - 5.4375) < 0.01


def test_net_yield_pct():
    p = make_pos(dps=1740)
    # brut 5,4375 % -> net = 5,4375*0,88 - 0,8 = 3,985 %
    assert abs(p.net_yield_pct(32000) - 3.985) < 0.02


# ----------------------------------------------------- sortie sur fondamentaux
def test_dividend_suspended():
    p = make_pos()
    check_dividend_position(p, 32000, current_dps=0, current_per=8)
    assert p.closed and "suspendu" in p.close_reason


def test_dividend_cut_over_50pct():
    p = make_pos(dps=1740)
    check_dividend_position(p, 32000, current_dps=500, current_per=8)  # < 870
    assert p.closed and "coupé" in p.close_reason


def test_dividend_small_cut_no_trigger():
    p = make_pos(dps=1740)
    check_dividend_position(p, 32000, current_dps=1500, current_per=8)  # baisse < 50%
    assert not p.closed


def test_per_explodes():
    p = make_pos()
    check_dividend_position(p, 32000, current_dps=1740, current_per=45)
    assert p.closed and "PER" in p.close_reason


def test_exit_price_reached():
    p = make_pos(dps=1740)  # exit = 54685.71
    check_dividend_position(p, 90000, current_dps=1740, current_per=8)
    assert p.closed and "prix de sortie" in p.close_reason


def test_no_trigger_when_sane():
    p = make_pos()
    check_dividend_position(p, 35000, current_dps=1800, current_per=8)
    assert not p.closed


def test_price_drop_does_not_trigger():
    """Une simple baisse de cours ne clôture PAS (logique dividende), mais alerte sur la couverture."""
    p = make_pos()
    alerts = check_dividend_position(p, 20000, current_dps=1740, current_per=8)  # -37% de cours
    assert not p.closed  # la thèse dividende est intacte
    assert any("perte couverte" in a.message for a in alerts)  # alerte de couverture, pas de vente


def test_profit_alert_informative_par_defaut():
    """Plus-value au-delà du seuil : INFORMATION, plus de consigne de vente.

    Changement du 08/10/2026 — aucune borne basse d'intervalle de confiance n'atteint
    50 % sur les 4 titres du portefeuille : le seuil ne déclenche plus de vente. Le
    message reste de niveau 2 (donc transmis) mais annonce qu'il n'ordonne rien.
    """
    p = make_pos()  # entry 32000, qty 3, dps 1740
    alerts = check_dividend_position(p, 40000, current_dps=1740, current_per=8)  # +25%
    assert not p.closed
    assert all(a.level == LEVEL_DECISION for a in alerts)
    joined = "\n".join(a.message for a in alerts)
    assert "INFO" in joined
    assert "VENDS 1/3" not in joined
    assert "RIEN À FAIRE" in joined
    # Le revenu conservé est annoncé en francs (et non en « net » nu).
    assert "par an" in joined


def test_double_option_alert_reste_disponible_pour_un_seuil_fonde():
    """Le mode DÉCLENCHEUR existe toujours — il n'est simplement plus atteint.

    On le teste directement : si un titre présentait un jour une borne basse ≥ 50 %,
    c'est ce message qui partirait. Le supprimer ferait perdre la fonctionnalité.
    """
    from src.portfolio import _double_option_alert

    p = make_pos()
    msg = _double_option_alert(p, 40000).message
    assert "VENDS 1/3" in msg
    assert "ordre de vente" in msg
    assert "CONSERVE" in msg
    assert "bénéfice net" in msg


def test_profit_threshold_boundary_13pct():
    """Frontière : +13% déclenche le niveau 2 ; juste en dessous reste niveau 1."""
    p = make_pos()  # entry 32000
    at_threshold = check_dividend_position(p, 32000 * 1.13, current_dps=1740, current_per=8)
    assert any(a.level == LEVEL_DECISION for a in at_threshold)
    below = check_dividend_position(p, 32000 * 1.129, current_dps=1740, current_per=8)
    assert all(a.level == LEVEL_INFO for a in below)


def test_loss_coverage_alert():
    """Moins-value >= -10% : décision — conserver (perte couverte par les dividendes)."""
    p = make_pos()
    alerts = check_dividend_position(p, 20000, current_dps=1740, current_per=8)
    assert not p.closed
    assert all(a.level == LEVEL_DECISION for a in alerts)
    joined = "\n".join(a.message for a in alerts)
    assert "perte couverte en ~" in joined
    assert "Renforcement" in joined
    assert "ordre limite d'achat" in joined
    assert "CONSERVE" in joined


def test_small_profit_info_only():
    """Une plus-value modeste (< +13%) ne produit qu'une alerte d'information (niveau 1)."""
    p = make_pos()
    alerts = check_dividend_position(p, 35000, current_dps=1800, current_per=8)  # +9.4%
    assert not p.closed
    assert alerts and all(a.level == LEVEL_INFO for a in alerts)
    assert "rien à faire" in alerts[0].message


# --- Seuils de vente ⅓ CALIBRÉS PAR TITRE (décision LEO 08/09) ---

def _pos(code, entry=30000.0):
    # dps 2000 : rendement net ~4,5 % → reste au-dessus du seuil de sortie 2 %.
    # Les tests de SEUIL de plus-value passent current_dps=2000 (dps inchangé) : un dps
    # courant réduit ferait légitimement déclencher la SORTIE (prix de sortie recalculé
    # au dividende courant — correction B1-05), ce qui masquerait le seuil testé.
    return DividendPosition(code=code, name=code, entry_price=entry, quantity=3,
                            dps=2000.0, per_open=10.0)


def test_sgbc_seuil_10_pct_atteint_mais_informatif():
    """SGBC : le seuil de 10 % est toujours SURVEILLÉ, mais n'ordonne plus la vente."""
    alerts = check_dividend_position(_pos("SGBC"), 30000 * 1.11,
                                     current_dps=2000, current_per=10)
    decision = [a for a in alerts if a.level == LEVEL_DECISION]
    assert decision, "le franchissement du seuil doit rester signalé"
    assert "INFO" in decision[0].message
    assert "VENDS 1/3" not in decision[0].message


def test_sgbc_pas_de_declenchement_a_9_pct():
    alerts = check_dividend_position(_pos("SGBC"), 30000 * 1.09,
                                     current_dps=2000, current_per=10)
    assert all(a.level != LEVEL_DECISION for a in alerts)


def test_slbc_seuil_5_pct_atteint_mais_informatif():
    """SLBC : signal faible -> information seule."""
    alerts = check_dividend_position(_pos("SLBC"), 30000 * 1.06,
                                     current_dps=2000, current_per=10)
    decision = [a for a in alerts if a.level == LEVEL_DECISION]
    assert decision
    assert "INFO" in decision[0].message
    assert "VENDS 1/3" not in decision[0].message


def test_palc_seuil_5_pct_avec_avertissement_fiabilite():
    """PALC : le pire signal du portefeuille — informé, pas vendu, et expliqué simplement."""
    alerts = check_dividend_position(_pos("PALC"), 30000 * 1.06,
                                     current_dps=2000, current_per=10)
    decision = [a for a in alerts if a.level == LEVEL_DECISION]
    assert decision and "VENDS 1/3" not in decision[0].message
    assert "INFO" in decision[0].message
    # La raison est donnée en langage courant (règle de style néophyte).
    assert "pile ou face" in decision[0].message


def test_snts_reste_a_13_pct_malgre_le_default():
    alerts = check_dividend_position(_pos("SNTS"), 30000 * 1.12,
                                     current_dps=2000, current_per=10)
    assert all(a.level != LEVEL_DECISION for a in alerts)  # 12 % < 13 % : rien


# --- Calibrage AUTOMATIQUE du seuil par titre (décision LEO 08/09) ---
from src.portfolio import calibrate_profit_threshold  # noqa: E402


def _serie_retournement_10pct():
    """Série synthétique : après +10 %, baisse 8 fois sur 10 ; après +5 %, 50/50."""
    closes, price = [], 100.0
    import random
    rng = random.Random(42)
    for _ in range(40):  # 40 vagues
        for _ in range(20):
            closes.append(price)
        target = 1.10 * price if len(closes) % 2 == 0 else 1.06 * price
        step = (target - price) / 10
        for _ in range(10):
            price += step
            closes.append(price)
        # après un pic +10 % : baisse 8/10 ; après +6 % : 50/50
        if target >= price * 0.999 and target / closes[-20] >= 1.09:
            if rng.random() < 0.8:
                for _ in range(20):
                    price *= 0.995
                    closes.append(price)
        price = max(price, 80.0)
    return closes


def test_calibrage_choisit_le_seuil_le_plus_fiable():
    closes = _serie_retournement_10pct()
    info = calibrate_profit_threshold("TEST", closes)
    assert info is not None
    assert info["threshold"] >= 0.10  # doit choisir 10 %+ (le retournement net), pas 5 %


def test_calibrage_insuffisant_renvoie_none():
    closes = [100.0 + i * 0.1 for i in range(60)]  # 60 séances calmes : aucun épisode
    assert calibrate_profit_threshold("TEST", closes) is None


# --------------------------------------------------------- ligne 📜 HISTOIRE
def test_history_line_with_profile(monkeypatch, tmp_path):
    """Profil SIGNIFICATIF : le taux est fondé, on l'affiche."""
    import json

    from src.portfolio import _history_line

    prof = {
        "_meta": {}, "SNTS": {
            "seuil_pct": 13, "significatif": True,
            "episodes": 10, "pct_down_20j": 90, "median_5j": -1.0,
            "median_20j": -3.5, "median_60j": -13.0,
            "trough_delay_median": 44, "trough_depth_median": -14.2,
            "trough_depth_worst": -22.8,
        },
    }
    f = tmp_path / "rev.json"
    f.write_text(json.dumps(prof), encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REVERSAL_FILE", f)

    p = make_pos()  # SNTS
    line = _history_line(p)
    assert "📜 LES AUTRES FOIS" in line
    assert "90 % des cas" in line
    # Format français : virgule décimale, pas le point anglais.
    assert "-3,5 %" in line
    # Langage courant : plus de « séances » ni de « médiane » nus.
    assert "44 jours de bourse" in line
    # pct_down_20j = 90 (>= 65) ET profil fiable : le délai est annoncé.
    assert "2 à 4 semaines" in line


def test_history_line_sans_taux_quand_non_significatif(monkeypatch, tmp_path):
    """Profil NON significatif : le taux ne doit PAS être affiché.

    C'est la condition de transparence statistique : « 86 % » sur 7 cas se lit comme une
    probabilité de baisse future alors que sa borne basse est 49 % — indiscernable du
    hasard. Le seuil de vente porte déjà sa propre probabilité ; la répéter ici sans
    garantie recréerait deux chiffres pour une même notion.
    """
    import json

    from src.portfolio import _history_line

    prof = {"_meta": {}, "SNTS": {
        "seuil_pct": 13, "significatif": False, "borne_basse": 49,
        "episodes": 7, "pct_down_20j": 86, "median_20j": -3.1,
        "trough_delay_median": 46, "trough_depth_median": -12.4,
    }}
    f = tmp_path / "rev.json"
    f.write_text(json.dumps(prof), encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REVERSAL_FILE", f)

    line = _history_line(make_pos())
    assert "86 %" not in line, "le taux non concluant ne doit pas être affiché"
    # …mais le descriptif reste : c'est ce que le profil sait vraiment.
    assert "-3,1 %" in line and "46 jours de bourse" in line
    assert "trop peu" in line, "7 cas < 8 : le motif doit être dit"


def test_history_line_distingue_peu_de_cas_et_signal_flou(monkeypatch, tmp_path):
    """Deux causes de non-significativité, deux phrases différentes.

    SGBC a 30 cas : dire « trop peu de cas » serait FAUX. Le motif est que la fréquence
    reste trop proche du hasard, pas la taille de l'échantillon.
    """
    import json

    from src.portfolio import _history_line

    prof = {"_meta": {}, "SNTS": {
        "seuil_pct": 13, "significatif": False, "borne_basse": 46,
        "episodes": 30, "pct_down_20j": 63, "median_20j": -1.8,
        "trough_delay_median": 18, "trough_depth_median": -5.4,
    }}
    f = tmp_path / "rev.json"
    f.write_text(json.dumps(prof), encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REVERSAL_FILE", f)

    line = _history_line(make_pos())
    assert "30 cas" in line
    assert "trop peu" not in line, (
        "30 cas n'est pas « trop peu » — le motif est l'imprécision, pas l'effectif")
    assert "pas assez nette" in line
    # Pas de délai annoncé sans base fiable : le ⏳ accompagne le taux, pas le descriptif.
    assert "2 à 4 semaines" not in line
    # Aucun jargon ne doit subsister dans cette ligne.
    for jargon in ("séances", "médiane", "fenêtre de manœuvre"):
        assert jargon.lower() not in line.lower(), f"jargon non traduit : {jargon}"


def test_history_line_missing_code(monkeypatch, tmp_path):
    import json

    from src.portfolio import _history_line

    f = tmp_path / "rev.json"
    f.write_text(json.dumps({"SNTS": {"pct_down_20j": 90, "median_20j": -3.5,
                                      "trough_delay_median": 44, "trough_depth_median": -14.2}}),
                 encoding="utf-8")
    monkeypatch.setattr("src.portfolio.REVERSAL_FILE", f)
    p = make_pos()  # code SNTS présent... on teste un autre code
    p.code = "XXXX"
    assert _history_line(p) == ""


def test_history_line_no_file(monkeypatch, tmp_path):
    from src.portfolio import _history_line

    monkeypatch.setattr("src.portfolio.REVERSAL_FILE", tmp_path / "absent.json")
    assert _history_line(make_pos()) == ""


# ---------------------------------------------------------------- durée 3 ans
def test_holding_period_alert():
    opened = (datetime.now() - timedelta(days=3 * 365 + 5)).isoformat()
    p = make_pos(opened=opened)
    alerts = check_dividend_position(p, 35000, current_dps=1800, current_per=8)
    assert not p.closed  # l'échéance alerte, ne clôture pas
    assert any("ÉCHÉANCE" in a.message for a in alerts)


# --------------------------------------------------------------- persistance
def test_persist_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("src.portfolio.PORTFOLIO_FILE", tmp_path / "portf.json")
    save_portfolio([make_pos()])
    loaded = load_portfolio()
    assert len(loaded) == 1
    assert loaded[0].code == "SNTS"
    assert abs(loaded[0].exit_price - 54685.71) < 0.01


# ------------------------------------------------------- anti-spam (cooldown)
def test_cooldown_empty_state():
    from src.portfolio import is_cooldown_active

    assert not is_cooldown_active({}, "SNTS")


def test_cooldown_recent_alert():
    from datetime import datetime, timedelta

    from src.portfolio import is_cooldown_active

    state = {"SNTS": datetime.now().isoformat()}  # alerté à l'instant
    assert is_cooldown_active(state, "SNTS")


def test_cooldown_expired():
    from datetime import datetime, timedelta

    from src.portfolio import is_cooldown_active

    old = (datetime.now() - timedelta(days=10)).isoformat()  # il y a 10 jours
    assert not is_cooldown_active({"SNTS": old}, "SNTS")


# --------------------------------------------------- soutenabilité (payout)
def test_payout_ratio():
    from src.portfolio import payout_ratio

    assert abs(payout_ratio(1740, 32000, 7.74) - 0.421) < 0.01  # 1740*7.74/32000
    assert payout_ratio(1740, 32000, None) is None  # PER inconnu
    assert payout_ratio(1740, 32000, -5) is None     # pertes
    assert payout_ratio(0, 32000, 8) is None         # pas de dividende


def test_soutenabilite_critical():
    from src.portfolio import _soutenabilite_alert

    p = make_pos()
    alert = _soutenabilite_alert(p, 5000, 8.0, 20000)  # payout = 200 %
    assert alert and "RISQUE DE COUPE" in alert.message


def test_soutenabilite_tight():
    from src.portfolio import _soutenabilite_alert

    p = make_pos()
    alert = _soutenabilite_alert(p, 2250, 8.0, 20000)  # payout = 90 %
    assert alert and "tendu" in alert.message


def test_soutenabilite_sain():
    from src.portfolio import _soutenabilite_alert

    p = make_pos()
    assert _soutenabilite_alert(p, 1250, 8.0, 20000) is None  # payout = 50 %


def test_soutenabilite_losses():
    from src.portfolio import _soutenabilite_alert

    p = make_pos()
    alert = _soutenabilite_alert(p, 1740, -5.0, 32000)  # PER négatif (pertes)
    assert alert and "en perte" in alert.message


def test_check_sustainability_flags_value_trap(monkeypatch):
    from src.domaine.models import Quote, Snapshot

    from src.portfolio import check_sustainability

    class FakeAPI:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="SOGC", name="SOGB", last=7315, is_index=False)])

    monkeypatch.setattr("src.collecte.fundamentals.get_fundamentals", lambda code: {"per": 13.49, "dps": 570})
    alerts = check_sustainability(FakeAPI(), ["SOGC"])
    assert len(alerts) == 1
    assert alerts[0].level == LEVEL_FUNDAMENTAL
    assert alerts[0].code == "SOGC"
    assert "RISQUE DE COUPE" in alerts[0].message


def test_check_sustainability_sain(monkeypatch):
    from src.domaine.models import Quote, Snapshot

    from src.portfolio import check_sustainability

    class FakeAPI:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="SNTS", name="Sonatel", last=32000, is_index=False)])

    monkeypatch.setattr("src.collecte.fundamentals.get_fundamentals", lambda code: {"per": 7.74, "dps": 1977})
    assert check_sustainability(FakeAPI(), ["SNTS"]) == []


# ------------------------------------------------------------- open_position
def test_open_dividend_position():
    class FakeAPI:
        def __init__(self):
            self.snap = Snapshot(stocks=[Quote(code="SNTS", name="Sonatel", last=32000, is_index=False)])

        def market_snapshot(self):
            return self.snap

    pos = open_dividend_position(FakeAPI(), "SNTS", 100000, dps=1740, per_open=7.74)
    assert pos.quantity == 3  # 100000 // 32000
    assert abs(pos.exit_price - 54685.71) < 0.01
    from src.taxation import entry_price_for_net
    assert abs(pos.entry_price_ref - entry_price_for_net(1740)) < 0.01  # formule unique B0-04/B1-08


# ---------------------------------------------------------- réinvestissement
def test_record_dividend_not_enough_for_share():
    p = make_pos(dps=1740, qty=3)  # net d'IRVM = 1740×0,88×3 = 4593,60 < prix 32000
    cash, shares, residual = record_dividend(p, 32000)
    assert cash == 4593.60  # NET d'IRVM 12 % — le cash réellement reçu (correction B1-03)
    assert shares == 0
    assert residual == 4593.60
    assert p.quantity == 3  # inchangé
    assert p.dividends_earned == 4593.60


def test_record_dividend_buys_shares():
    p = make_pos(dps=1740, qty=20)  # net = 30624, à 30000 -> 1 action
    cash, shares, residual = record_dividend(p, 30000)
    assert cash == 30624.0
    assert shares == 1
    assert residual == 624.0  # 30624 - 30000
    assert p.quantity == 21
    assert p.cash_residual == 624.0


def test_record_dividend_compounds():
    """Le réinvestissement augmente la base -> dividende suivant plus gros (net d'IRVM)."""
    p = make_pos(dps=1740, qty=20)  # net 30624 -> 1 action -> 21 actions
    record_dividend(p, 30000)
    # second versement sur 21 actions
    cash2, _, _ = record_dividend(p, 30000)
    assert cash2 == 1740 * 0.88 * 21  # 32 155,20 net
