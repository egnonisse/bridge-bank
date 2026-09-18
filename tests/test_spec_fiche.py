"""Tests de la fiche spé (schémas, zones, verdicts, anti-spam d'état)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.spec_fiche import build_fiche
from src.spec_profiles import detect_schemas, zone_of, zone_label


def test_cassure_verdict_oui_et_niveaux():
    closes = [100.0] * 300 + [150.0]  # casse 1 an de plafond à 100
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert f.verdict == "OUI"
    assert f.blocks["main"] == "CASSURE"
    assert f.blocks["entry_lo"] == 100.0      # le plafond cassé
    assert abs(f.blocks["entry_hi"] - 105.0) < 1e-6
    assert abs(f.blocks["stop"] - 85.0) < 1e-6
    msg = f.message()
    assert "CASSURE" in msg
    assert "70 % des 10 cas" in msg           # stats calibrées
    assert "34,300" not in msg                # pas de chiffre en dur d'un autre titre


def test_panique_en_zone_piege_dit_non():
    # 260 séances stables à 100, puis chute continue -> RSI < 30 et zone écrasée
    closes = [100.0] * 260 + [100 - 2 * i for i in range(1, 15)]
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    assert "PANIQUE" in f.schemas
    assert f.verdict == "NON"
    assert "LA FICHE DIT NON" in f.message()
    assert "ne devient JAMAIS un loyer" in f.message()


def test_aucun_schema_retourne_none():
    closes = [100.0] * 300
    assert build_fiche("TEST", "Test", closes) is None


def test_serie_trop_courte_retourne_none():
    assert build_fiche("TEST", "Test", [100.0] * 100) is None


def test_detect_schemas_eveil():
    # rebond de +10 % depuis le creux des 60 séances
    closes = [100.0] * 260 + [90.0] * 30 + [99.5, 100.0, 101.0, 103.0, 105.0]
    schemas = detect_schemas(closes)
    assert "EVEIL" in schemas


def test_zone_labels():
    assert zone_label(0.05) == "BAS_ECRASE"
    assert zone_label(0.30) == "BAS_SOLIDE"
    assert zone_label(0.50) == "MILIEU"
    assert zone_label(0.70) == "HAUT_FRAGILE"
    assert zone_label(0.95) == "FORCE"


def test_zone_of_extremes():
    closes = [x for x in range(100, 200)] + [150.0]
    z = zone_of(closes, years=1)
    assert 0.49 < z < 0.51


def test_antispam_state(monkeypatch, tmp_path):
    from src import spec_veille as sv

    monkeypatch.setattr(sv, "STATE_FILE", Path(tmp_path) / "state.json")
    st = sv.load_state()
    assert st == {}
    st["X:CASSURE"] = "2026-09-01"
    sv.save_state(st)
    assert sv.load_state()["X:CASSURE"] == "2026-09-01"
