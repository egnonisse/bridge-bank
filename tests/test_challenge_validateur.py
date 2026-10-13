"""Les tests du JUGE (chantier A3 — audit R-001 : module majeur sans test).

Le juge tranche les hypothèses des modèles : c'était le seul moteur majeur du
projet sans aucun test. Ces tests couvrent le durcissement du 13/10/2026 :

  - A3-09 : `resume()` ne plante JAMAIS (0 trade, baseline indisponible) ;
  - A3-05 : p = (1 + #≥) / (1 + N) ; la baseline ne tire pas avant la séance
    éligible, rééchantillonne les durées et conditionne les dates à celles de
    la règle (bootstrap) ;
  - A3-10 : exécution à J+1 — entrées ET sorties au close de la séance suivante ;
  - A3-03 : le verdict exige un AVANTAGE vs baseline positif sur les DEUX moitiés ;
  - A3-04 : l'absence d'`historique_fond` est signalée.

Séries synthétiques uniquement : aucun accès réseau, aucun fichier de `data/`.
"""
from datetime import date, timedelta

import pytest

from src.backtesting.challenge_schema import Hypothese, valider_hypothese
from src.backtesting.challenge_indicateurs import SerieIndicateurs
from src.backtesting import challenge_validateur as cv


# ── Fabriques ───────────────────────────────────────────────────────────────

def _serie(code: str, closes: list[float]) -> SerieIndicateurs:
    """Série synthétique complète (dates ISO triées, indicateurs r5/prix)."""
    n = len(closes)
    dates = [(date(2017, 1, 2) + timedelta(days=i)).isoformat() for i in range(n)]
    inds = []
    for i in range(n):
        d: dict = {"prix": closes[i]}
        if i >= 5 and closes[i - 5]:
            d["r5"] = closes[i] / closes[i - 5] - 1
        inds.append(d)
    return SerieIndicateurs(code=code, dates=dates, closes=closes, indicateurs=inds)


def _plats(n: int = 300, val: float = 100.0) -> list[float]:
    return [val] * n


def _hypo(id_: str, achat: str, duree: int = 5) -> Hypothese:
    h = Hypothese(id=id_, nom=id_, achat=achat, duree_max=duree)
    valider_hypothese(h)
    assert h.valide, h.motifs
    return h


# ── A3-09 : resume() robuste ────────────────────────────────────────────────

def test_resume_ne_plante_jamais():
    """0 trade, tout None : l'ancien code levait TypeError (A3-09)."""
    r = cv.ResultatHypothese(id="T1", nom="sans rien", valide=True)
    txt = r.resume()
    assert "trades : 0" in txt and "n/d" in txt

    r2 = cv.ResultatHypothese(id="T2", nom="baseline ok", valide=True, nb_trades=12,
                              rendement_net_pct=1.5, rendement_median_pct=1.2,
                              baseline_mediane_pct=0.4, baseline_p95_pct=3.0,
                              avantage_vs_baseline_pts=1.1, p_value=0.02)
    assert "p = 0.0200" in r2.resume()

    r3 = cv.ResultatHypothese(id="T3", nom="rejetee", valide=False, motifs=["hors DSL"])
    assert "REJETEE" in r3.resume()


# ── A3-05 : la baseline est bornée à la fenêtre éligible ───────────────────

def test_baseline_ne_tire_pas_avant_la_seance_eligible():
    """Les 250 premières séances ne sont PAS tirables (la règle ne peut pas y
    agir) : sur une série où seules ces séances explosent, aucun panier ne doit
    en venir. Preuve : closes = 100+i ; un tirage à i<250 donnerait 10/i % de
    rendement (ex. i=5 → +200 %)."""
    closes = [100.0 + i for i in range(300)]
    s = _serie("AAA", closes)
    base = cv.baseline_aleatoire({"AAA": s}, nb_trades=10, duree_mediane=10,
                                 tirages=100)
    assert base, "la baseline doit produire des paniers"
    # k >= 250 → rendement ≈ 10/k <= 4 % ; tout résultat > 10 % = tirage illégitime
    assert max(base) < 10.0, "un panier vient d'avant la séance éligible"


# ── A3-05 : p-value (1 + #≥) / (1 + N) ──────────────────────────────────────

def test_p_value_inclut_le_plus_un(monkeypatch):
    s = _serie("AAA", _plats(300))
    h = _hypo("P", "r5 > -1", duree=20)   # toujours vrai → produit des trades

    monkeypatch.setattr(cv, "baseline_aleatoire", lambda *a, **k: [-5.0] * 10)
    r = cv.evaluer_hypothese({"AAA": s}, h, date_coupure="", historique_fond={})
    assert r.p_value == pytest.approx(1 / 11)      # 0/10 → jamais 0,0

    monkeypatch.setattr(cv, "baseline_aleatoire", lambda *a, **k: [99.0] * 10)
    r2 = cv.evaluer_hypothese({"AAA": s}, h, date_coupure="", historique_fond={})
    assert r2.p_value == pytest.approx(1.0)        # 10/10 → jamais 1,1


# ── A3-05 : bootstrap conditionnel aux dates de la règle ───────────────────

def test_bootstrap_conditionnel_utilise_les_dates_de_la_regle():
    """Avec dates_reference + durées fixes, TOUS les paniers partent de la date
    donnée : le rendement retourné est celui de cette date, pas un tirage au
    hasard dans toute la série."""
    closes = [100.0 + i * 0.1 for i in range(300)]
    s = _serie("AAA", closes)
    base = cv.baseline_aleatoire({"AAA": s}, nb_trades=3, duree_mediane=10,
                                 tirages=20, durees=[10],
                                 dates_reference=[s.dates[270]])
    attendu = (s.closes[280] / s.closes[270]) * (1 - cv.FRAIS_ALLER_RETOUR) - 1
    assert base == pytest.approx([attendu * 100] * 20)


# ── A3-10 : exécution à J+1 ────────────────────────────────────────────────

def test_execution_a_j_plus_un():
    """Le signal se déclenche à i (r5 > 0,9) : l'achat doit être exécuté au
    close de i+1 — PAS au prix du signal (l'ancien code achetait au close lu)."""
    closes = _plats(300)
    closes[260] = 200.0            # r5 > 0,9 UNIQUEMENT à i=260
    s = _serie("AAA", closes)
    h = _hypo("J1", "r5 > 0.9", duree=5)

    trades = cv.simuler({"AAA": s}, h)
    assert trades, "le signal doit produire un trade"
    t0 = trades[0]
    assert t0.date_entree == s.dates[261]        # exécuté à J+1
    assert t0.prix_entree == pytest.approx(100.0)   # le close de J+1, pas 200


# ── A3-03 : verdict sur l'AVANTAGE par moitié ──────────────────────────────

def test_verdict_exige_l_avantage_sur_les_deux_moities():
    """Rendements absolus positifs des deux côtés mais avantage négatif sur une
    moitié → REJETÉE (l'ancien critère absolu retenait)."""
    r = cv.ResultatHypothese(id="V", nom="x", valide=True, nb_trades=30,
                             rendement_net_pct=8.0, avantage_vs_baseline_pts=2.0,
                             p_value=0.01, in_sample_pct=12.0, out_sample_pct=4.0,
                             avantage_in_pts=1.5, avantage_out_pts=-0.8)
    v = cv._verdict(r)
    assert v.startswith("REJETEE")
    assert "avantage vs baseline absent" in v

    # Sans avantages par moitié (baseline de moitié indisponible) : repli sur le
    # test absolu — comportement NON régressif.
    r2 = cv.ResultatHypothese(id="V2", nom="y", valide=True, nb_trades=30,
                              rendement_net_pct=8.0, avantage_vs_baseline_pts=2.0,
                              p_value=0.01, in_sample_pct=12.0, out_sample_pct=4.0)
    assert cv._verdict(r2).startswith("RETENUE")


# ── A3-04 : absence d'historique_fond signalée ─────────────────────────────

def test_absence_historique_fond_signalee(monkeypatch, capsys):
    s = _serie("AAA", _plats(300))
    h = _hypo("NOF", "r5 > -1", duree=5)
    monkeypatch.setattr(cv, "baseline_aleatoire", lambda *a, **k: [-1.0] * 5)
    cv.evaluer_hypothese({"AAA": s}, h, date_coupure="", historique_fond=None)
    assert "historique_fond absent" in capsys.readouterr().out


# ── A3-09 (suite) : AUCUN SIGNAL protégé ───────────────────────────────────

def test_aucun_signal_ne_plante_pas():
    s = _serie("AAA", _plats(300))
    h = _hypo("NO", "r5 > 10", duree=5)          # jamais vrai
    r = cv.evaluer_hypothese({"AAA": s}, h, date_coupure="", historique_fond={})
    assert "AUCUN SIGNAL" in r.verdict
    assert r.resume()                             # ne plante pas
