"""L'effectif d'un schéma doit être annoncé comme fragile quand il est faible.

(02/11/2026) Le « 83 % de réussite » de la zone FORCE reposait sur 2 cas et s'affichait
comme une certitude ; la même faute de précision vivait sur les SCHÉMAS : « 80 % de 5 cas
OBSERVÉS » était affirmé sans réserve alors que CASSURE ne compte que 5 cas depuis le
recalibrage. Une fréquence observée sur cinq cas n'est pas une statistique — et LEO
décide avec ce chiffre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.strategie import spec_fiche as sf  # noqa: E402


@pytest.fixture(autouse=True)
def _aucun_appel_reseau(monkeypatch):
    """`build_fiche` interroge le fondamental : on l'abstient (jamais de réseau ici)."""
    from src.collecte import fundamentals

    monkeypatch.setattr(fundamentals, "get_fundamentals", lambda code: {})
    monkeypatch.setattr(fundamentals, "get_dps", lambda code: None)


def _fiche_cassure(n: int, monkeypatch):
    prof = {"CASSURE": {"n": n, "win_12m": 0.80, "median_net_12m": 1.054,
                        "touched": {"0.10": 0.80, "0.20": 0.80, "0.50": 0.80}}}
    monkeypatch.setattr(sf, "load_profiles", lambda: prof)
    closes = [100.0] * 300 + [150.0]      # plafond d'un an cassé -> schéma CASSURE
    fiche = sf.build_fiche("TEST", "Test", closes)
    assert fiche is not None
    return fiche


def test_effectif_faible_est_annonce_comme_fragile(monkeypatch):
    msg = _fiche_cassure(5, monkeypatch).message()
    assert "5 cas OBSERVÉS" in msg
    assert "5 cas SEULEMENT" in msg
    assert "pas une statistique" in msg


def test_effectif_suffisant_n_ajoute_aucune_reserve(monkeypatch):
    msg = _fiche_cassure(28, monkeypatch).message()
    assert "28 cas OBSERVÉS" in msg
    assert "cas SEULEMENT" not in msg


def test_le_seuil_vient_de_la_constante_partagee(monkeypatch):
    """Le seuil n'est pas un 10 en dur : il vient de SEUIL_CAS_ZONE (zones ET schémas)."""
    assert sf.SEUIL_CAS_ZONE == 10
    msg = _fiche_cassure(sf.SEUIL_CAS_ZONE - 1, monkeypatch).message()
    assert "cas SEULEMENT" in msg
    msg = _fiche_cassure(sf.SEUIL_CAS_ZONE, monkeypatch).message()
    assert "cas SEULEMENT" not in msg
