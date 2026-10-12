"""Tests du contrôle d'intégrité du cache historique."""
import json
from datetime import datetime, timedelta

from src.collecte.cache_integrity import (
    cache_signature,
    check_against_api,
    check_all_integrity,
    check_freshness,
    detect_jumps,
    reversal_profile_stale,
)
from src.domaine.models import HistoryBar, Quote, Snapshot

TODAY = datetime(2026, 8, 21)


def bar(day_offset: int, close: float) -> HistoryBar:
    return HistoryBar(
        date=TODAY - timedelta(days=day_offset),
        open=close, high=close, low=close, close=close, volume=1000,
    )


def test_signature_depends_on_content():
    h1 = {"AAA": [bar(0, 100)], "BBB": [bar(0, 100)]}
    h2 = {"AAA": [bar(0, 100), bar(1, 101)]}  # une barre de plus
    assert cache_signature(h1) != cache_signature(h2)


def test_detect_jumps():
    # artefact : cassure isolée qui REVIENT au niveau précédent (95 → 30 → 92)
    bad = {"AAA": [bar(4, 100), bar(3, 95), bar(2, 30), bar(1, 90), bar(0, 92)]}
    assert any("AAA" in p for p in detect_jumps(bad))
    ok = {"AAA": [bar(2, 100), bar(1, 95), bar(0, 96)]}
    assert detect_jumps(ok) == []


def test_detect_jumps_ignores_real_splits():
    # division de nominal réelle : niveau bas permanent (x0.10 puis stable)
    split = {"AAA": [bar(4, 100), bar(3, 95), bar(2, 10), bar(1, 10.5), bar(0, 10)]}
    assert detect_jumps(split) == []


def test_check_against_api_fresh_cache():
    hist = {"AAA": [bar(1, 100), bar(0, 105)]}
    snap = Snapshot(stocks=[Quote(code="AAA", name="X", last=105.0)])
    assert check_against_api(hist, snap, TODAY) == []
    snap_bad = Snapshot(stocks=[Quote(code="AAA", name="X", last=200.0)])
    assert any("AAA" in p for p in check_against_api(hist, snap_bad, TODAY))


def test_check_against_api_stale_cache_skipped():
    hist = {"AAA": [bar(10, 100), bar(9, 100)]}  # dernière barre : 9 jours
    snap = Snapshot(stocks=[Quote(code="AAA", name="X", last=500.0)])
    assert check_against_api(hist, snap, TODAY) == []  # cache trop vieux → pas comparé


def test_check_freshness(monkeypatch, tmp_path):
    # registre des dormants isolé (fichier absent = aucun titre exempté)
    monkeypatch.setattr("src.collecte.cache_integrity.INACTIFS_FILE", tmp_path / "inactifs.json")
    old = {"AAA": [bar(10, 100), bar(9, 100)]}
    fresh = {"AAA": [bar(1, 100), bar(0, 100)]}
    assert any("AAA" in p for p in check_freshness(old, TODAY))
    assert check_freshness(fresh, TODAY) == []


def test_reversal_profile_stale(monkeypatch, tmp_path):
    f = tmp_path / "rev.json"
    f.write_text(json.dumps({"_meta": {"cache_signature": "ancienne"}, "SNTS": {}}),
                 encoding="utf-8")
    monkeypatch.setattr("src.collecte.cache_integrity.REVERSAL_FILE", f)
    hist = {"AAA": [bar(0, 100)]}
    assert reversal_profile_stale(hist) is True
    f.write_text(json.dumps({"_meta": {"cache_signature": cache_signature(hist)}, "SNTS": {}}),
                 encoding="utf-8")
    assert reversal_profile_stale(hist) is False


def test_check_all_integrity_ok(monkeypatch, tmp_path):
    hist = {"AAA": [bar(1, 100), bar(0, 105)]}
    f = tmp_path / "rev.json"
    f.write_text(json.dumps({"_meta": {"cache_signature": cache_signature(hist)}}),
                 encoding="utf-8")
    monkeypatch.setattr("src.collecte.cache_integrity.REVERSAL_FILE", f)
    monkeypatch.setattr("src.collecte.cache_integrity.INACTIFS_FILE", tmp_path / "inactifs.json")
    snap = Snapshot(stocks=[Quote(code="AAA", name="X", last=105.0)])
    assert check_all_integrity(hist, snap, TODAY) == []


# ------------------- titres DORMANTS (vérifiés « source muette ») — 12/10/2026

def _registre(tmp_path, contenu: dict):
    f = tmp_path / "inactifs.json"
    f.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return f


def test_titre_dormant_verifie_ne_crie_pas(monkeypatch, tmp_path):
    """Un titre vérifié dormant récemment (même dernière barre) = fait de marché,
    pas un « cache en retard » : aucune alerte."""
    old = {"SEMC": [bar(10, 100), bar(9, 100)]}
    date_barre = old["SEMC"][-1].date.strftime("%Y-%m-%d")
    monkeypatch.setattr("src.collecte.cache_integrity.INACTIFS_FILE",
                        _registre(tmp_path, {"SEMC": {"derniere_barre": date_barre,
                                                      "verifie_le": TODAY.strftime("%Y-%m-%d")}}))
    assert check_freshness(old, TODAY) == []


def test_titre_dormant_verification_perimee_realerte(monkeypatch, tmp_path):
    """Une vérification trop ancienne (> 8 j) ne fait plus foi → l'alerte revient."""
    old = {"SEMC": [bar(10, 100), bar(9, 100)]}
    date_barre = old["SEMC"][-1].date.strftime("%Y-%m-%d")
    vieux_jour = (TODAY - timedelta(days=10)).strftime("%Y-%m-%d")
    monkeypatch.setattr("src.collecte.cache_integrity.INACTIFS_FILE",
                        _registre(tmp_path, {"SEMC": {"derniere_barre": date_barre,
                                                      "verifie_le": vieux_jour}}))
    assert any("SEMC" in p for p in check_freshness(old, TODAY))


def test_titre_dormant_avec_nouvelle_barre_realerte(monkeypatch, tmp_path):
    """Si la dernière barre ne correspond plus au registre (le titre a re-traité),
    la vérification ne vaut plus → alerte."""
    old = {"SEMC": [bar(10, 100), bar(9, 100)]}
    monkeypatch.setattr("src.collecte.cache_integrity.INACTIFS_FILE",
                        _registre(tmp_path, {"SEMC": {"derniere_barre": "2020-01-01",
                                                      "verifie_le": TODAY.strftime("%Y-%m-%d")}}))
    assert any("SEMC" in p for p in check_freshness(old, TODAY))
