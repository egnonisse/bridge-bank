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
    ZONE_LABELS,
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


def test_zone_force_n_affiche_plus_83_mais_aucun_cas_concluant():
    _label, txt = ZONE_LABELS["FORCE"]
    assert "83" not in txt
    assert "aucun cas concluant (2 cas)" in txt
    assert "échantillon insuffisant" in txt          # 2 cas < 10


def test_zone_haut_fragile_affiche_14_pct_sur_7_cas():
    _label, txt = ZONE_LABELS["HAUT_FRAGILE"]
    assert "14 % de réussite sur 7 cas" in txt
    assert "échantillon insuffisant" in txt          # 7 cas < 10
    assert "s'essoufflent" in txt


def test_zone_bas_ecrase_affiche_53_pct_sur_19_cas_sans_insuffisant():
    _label, txt = ZONE_LABELS["BAS_ECRASE"]
    assert "53 % de réussite sur 19 cas" in txt
    assert "échantillon insuffisant" not in txt      # 19 cas >= 10


def test_zone_bas_solide_affiche_100_pct_sur_10_cas():
    _label, txt = ZONE_LABELS["BAS_SOLIDE"]
    assert "100 % de réussite sur 10 cas" in txt
    assert "échantillon insuffisant" not in txt      # 10 n'est pas < 10


def test_zone_milieu_affiche_62_pct_sur_13_cas():
    _label, txt = ZONE_LABELS["MILIEU"]
    assert "62 % de réussite sur 13 cas" in txt
    assert "échantillon insuffisant" not in txt


def test_aucun_taux_codé_83_nulle_part():
    for _label, txt in ZONE_LABELS.values():
        assert "83 %" not in txt
        assert "80 % de réussite" not in txt         # l'ancien 80 % a disparu
    closes = [100.0] * 300 + [150.0]                 # CASSURE -> fiche complète
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert "83 %" not in f.message()
    assert "0 gagnant sur 4" not in f.message()


def test_verdict_prix_niveau_par_zone():
    assert "✅ Verdict prix : favorable" in format_verdict_prix({"zone_label": "BAS_SOLIDE"})
    assert "🟡 Verdict prix : neutre" in format_verdict_prix({"zone_label": "MILIEU"})
    assert "🔴 Verdict prix : défavorable" in format_verdict_prix({"zone_label": "BAS_ECRASE"})
    assert "🔴 Verdict prix : défavorable" in format_verdict_prix({"zone_label": "HAUT_FRAGILE"})
    assert "⚪ Verdict prix : non concluant" in format_verdict_prix({"zone_label": "FORCE"})


def test_verdict_prix_porte_effectif_et_gain_median():
    t = format_verdict_prix({"zone_label": "HAUT_FRAGILE"})
    assert "sur 7 cas" in t
    assert "−33 %" in t
    t2 = format_verdict_prix({"zone_label": "FORCE"})
    assert "aucun cas concluant (2 cas)" in t2


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
