"""Tests de la ligne « Position du prix » de la fiche spé (chantier « prix des alertes spé », 09/11/2026).

Deux faits mesurés, informatifs — JAMAIS des seuils d'achat :
  - percentile_5ans  : part des séances des 5 ans strictement sous le cours (= zone × 100, arrondi) ;
  - depuis_creux_pct : chemin parcouru depuis le creux des 60 séances précédentes : (cours − creux) / creux × 100.

Règle : donnée absente (historique < 5 ans, creux invalide) → « indisponible », jamais une
valeur inventée ni un zéro trompeur. Toutes les séries sont synthétiques : AUCUN appel réseau.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.strategie.spec_fiche import build_fiche  # noqa: E402


@pytest.fixture(autouse=True)
def _aucun_appel_reseau(monkeypatch):
    """Aucun test ne touche le réseau (leçon du 30/10/2026) : build_fiche interroge
    le fondamental ; ici il est remplacé par « fondamental inconnu » (abstention)."""
    from src.collecte import fundamentals

    monkeypatch.setattr(fundamentals, "get_fundamentals", lambda code: {})
    monkeypatch.setattr(fundamentals, "get_dps", lambda code: None)


def test_position_prix_affichee_avec_historique_5_ans():
    """1261 séances (≥ 5 ans) : base à 100, creux à 80 sur 60 séances, rebond à 96.
    → percentile = zone × 100 = (96−80)/(100−80) = 80 ; depuis le creux : +20 %."""
    closes = [100.0] * 1200 + [80.0] * 60 + [96.0]
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert f.blocks["percentile_5ans"] == 80
    assert f.blocks["depuis_creux_pct"] == pytest.approx(20.0)
    msg = f.message()
    assert ("💵 Position du prix : 80e percentile sur 5 ans "
            "| +20 % depuis le creux des 60 séances") in msg


def test_percentile_indisponible_si_historique_court():
    """301 séances (< 5 ans) : le percentile « sur 5 ans » ne peut pas être honnête
    → « indisponible » ; le creux des 60 séances reste mesurable (+50 %)."""
    closes = [100.0] * 300 + [150.0]  # CASSURE de 1 an
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert f.blocks["percentile_5ans"] is None
    assert f.blocks["depuis_creux_pct"] == pytest.approx(50.0)
    msg = f.message()
    assert "percentile sur 5 ans : indisponible" in msg
    assert "+50 % depuis le creux des 60 séances" in msg


def test_cours_sous_le_creux_est_dit_nouveau_plus_bas():
    """PANIQUE au plus bas : le cours passe SOUS le creux des 60 séances → la fiche
    le dit tel quel (nouveau plus bas), jamais maquillé en « + »."""
    closes = [100.0] * 260 + [100.0 - 2.0 * i for i in range(1, 21)]  # dernier = 60
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert "PANIQUE" in f.schemas
    assert f.blocks["depuis_creux_pct"] < 0
    msg = f.message()
    assert "sous le creux des 60 séances (nouveau plus bas)" in msg
    assert "percentile sur 5 ans : indisponible" in msg  # 280 séances < 5 ans


def test_position_prix_suit_la_ligne_cours_de_reference():
    """La ligne est placée JUSTE après « Cours de référence : … », sur une seule ligne."""
    closes = [100.0] * 1200 + [80.0] * 60 + [96.0]
    f = build_fiche("TEST", "Test", closes)
    lines = f.message().split("\n")
    idx = next(i for i, l in enumerate(lines) if l.startswith("Cours de référence"))
    assert lines[idx + 1].startswith("💵 Position du prix")
    assert "|" in lines[idx + 1]
