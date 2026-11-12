"""Tests des taux de réussite PAR ZONE mesurés (chantier « prix des alertes spé », 09/11/2026).

Remplace les taux codés en dur (FORCE 83 %, etc.) par la mesure réelle
(audit/spec_zones_mesure_2026-11-02.md) : chaque taux affiche son effectif,
sous 10 cas la fiche dit « échantillon insuffisant », et le « 83 % » infondé a
disparu (zone 80-100 : « aucun cas concluant (2 cas) »). La ligne « Verdict
prix » est informative : elle ne bloque aucun achat. AUCUN appel réseau.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.strategie.spec_fiche import (  # noqa: E402
    SEUIL_CAS_ZONE,
    _texte_zone,
    build_fiche,
    format_verdict_prix,
)


@pytest.fixture(autouse=True)
def _aucun_appel_reseau(monkeypatch):
    """Aucun test ne touche le réseau (leçon du 30/10/2026) : build_fiche
    interroge le fondamental ; ici il est remplacé par « fondamental inconnu »."""
    from src.collecte import fundamentals

    monkeypatch.setattr(fundamentals, "get_fundamentals", lambda code: {})
    monkeypatch.setattr(fundamentals, "get_dps", lambda code: None)


def test_seuil_cas_zone_vaut_10():
    assert SEUIL_CAS_ZONE == 10


def test_zone_force_n_affiche_plus_83_mais_l_effectif_reel():
    """(12/11/2026) La zone 80-100 n'est plus « aucun cas concluant » : après réparation
    de l'espacement du calibrage, ses effectifs sont réels. Le 83 % codé en dur reste banni."""
    txt = _texte_zone("FORCE", {"n": 91, "win_12m": 0.67, "median_net_12m": 0.18})
    assert "83" not in txt
    assert "67 % de réussite sur 91 cas" in txt
    assert "gain médian +18 %" in txt


def test_zone_sans_effectif_suffisant_s_abstient():
    """Sous SEUIL_CAS_ZONE cas POUR CE SCHÉMA : aucun taux, seulement l'effectif."""
    for n in (0, 3, 9):
        txt = _texte_zone("BAS_SOLIDE", {"n": n, "win_12m": 1.0, "median_net_12m": 0.88})
        assert "cas seulement POUR CE SCHÉMA" in txt
        assert "100 %" not in txt
        assert "réussite" not in txt


def test_zone_haut_fragile_porte_son_contexte_et_son_effectif():
    txt = _texte_zone("HAUT_FRAGILE", {"n": 28, "win_12m": 0.50, "median_net_12m": 0.017})
    assert "60-80" in txt
    assert "50 % de réussite sur 28 cas" in txt


def test_zone_bas_ecrase_affiche_la_mesure_reelle_de_panique():
    """PANIQUE en zone 0-20 : 317 cas, 48 %, médiane négative — « pas cher ne paie pas »."""
    txt = _texte_zone("BAS_ECRASE", {"n": 317, "win_12m": 0.483, "median_net_12m": -0.035})
    assert "48 % de réussite sur 317 cas" in txt
    assert "gain médian −4 %" in txt


def test_aucun_taux_code_en_dur_ne_survit_dans_la_fiche():
    closes = [100.0] * 300 + [150.0]                 # CASSURE -> fiche complète
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    msg = f.message()
    assert "83 %" not in msg
    assert "0 gagnant sur 4" not in msg
    assert "100 % de réussite sur 10 cas" not in msg   # l'ancien chiffre tous schémas


def test_verdict_prix_niveau_par_zone():
    """Le niveau suit le TAUX MESURÉ, pas la zone — correctif du 12/11/2026."""
    for win, emoji, mot in ((0.65, "✅", "favorable"), (0.55, "🟡", "neutre"),
                            (0.45, "🔴", "défavorable")):
        t = format_verdict_prix({"zone_label": "BAS_SOLIDE",
                                 "zone_stats": {"n": 40, "win_12m": win, "median_net_12m": 0.05}})
        assert f"{emoji} Verdict prix : {mot}" in t, f"win={win} devrait porter {emoji} : {t}"


def test_la_zone_ne_commande_plus_la_couleur():
    """Le défaut d'origine : la zone 60-80 s'affichait 🔴 en annonçant 66 % de réussite.
    Désormais deux zones différentes avec le MÊME taux portent la même couleur, et c'est le
    taux qui décide."""
    stats_bon = {"n": 40, "win_12m": 0.66, "median_net_12m": 0.12}
    a = format_verdict_prix({"zone_label": "HAUT_FRAGILE", "zone_stats": stats_bon})
    b = format_verdict_prix({"zone_label": "BAS_SOLIDE", "zone_stats": stats_bon})
    assert "✅" in a and "✅" in b          # 66 % => favorable, quelle que soit la zone
    assert "60-80" in a and "20-40" in b   # mais la zone reste nommée
    assert "🔴" not in a


def test_verdict_prix_porte_effectif_et_gain_median():
    t = format_verdict_prix({"zone_label": "HAUT_FRAGILE",
                             "zone_stats": {"n": 28, "win_12m": 0.50, "median_net_12m": 0.017}})
    assert "sur 28 cas" in t
    assert "gain médian +2 %" in t
    assert "POUR CE SCHÉMA" in t


def test_verdict_prix_non_concluant_sous_le_seuil_pour_ce_schema():
    """(12/11/2026) Le défaut corrigé : une zone mesurée « 100 % sur 10 cas » TOUS SCHÉMAS
    était affichée comme ✅ sur une alerte dont le schéma n'avait que 3 cas. Sous
    SEUIL_CAS_ZONE cas POUR CE SCHÉMA, la ligne doit dire « non concluant » et annoncer
    l'effectif — jamais afficher le taux d'une autre population."""
    t = format_verdict_prix({"zone_label": "BAS_SOLIDE",
                             "zone_stats": {"n": 3, "win_12m": 1.0, "median_net_12m": 0.88}})
    assert "⚪ Verdict prix : non concluant" in t
    assert "3 cas seulement" in t
    assert "100 %" not in t
    # sans aucune statistique de zone, on s'abstient aussi
    assert "non concluant" in format_verdict_prix({"zone_label": "BAS_SOLIDE"})


def test_verdict_prix_ligne_placee_juste_apres_position_prix():
    closes = [100.0] * 1200 + [80.0] * 60 + [96.0]
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    lines = f.message().split("\n")
    idx = next(i for i, l in enumerate(lines) if l.startswith("💵 Position du prix"))
    assert "Verdict prix" in lines[idx + 1]


def test_message_complet_garde_biais_de_survie_et_frequence_pas_probabilite():
    closes = [100.0] * 300 + [150.0]
    f = build_fiche("TEST", "Test", closes)
    msg = f.message()
    assert "Verdict prix" in msg
    assert "biais de survie" in msg
    assert "PAS une probabilité" in msg
