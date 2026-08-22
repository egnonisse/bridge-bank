"""Tests de l'alerte d'entrée spéculative (détection de nouveaux candidats)."""
from src.speculation import detect_new_candidates


def test_detect_new_candidates_first_then_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr("src.speculation.CANDIDATES_STATE_FILE", tmp_path / "cand.json")
    candidates = [
        {"code": "NSBC", "name": "NSIA Banque", "count": 4, "signals": ["momentum", "RSI"]},
        {"code": "BOAM", "name": "BOA Mali", "count": 3, "signals": ["cassure"]},
    ]
    monkeypatch.setattr(
        "src.speculation.screen_speculation", lambda api, min_signals=3: candidates
    )
    api = object()  # screen_speculation est mocké

    new = detect_new_candidates(api, 3)
    assert len(new) == 2  # premier run : tout est nouveau
    assert {c["code"] for c in new} == {"NSBC", "BOAM"}

    # second run : plus rien de nouveau
    assert len(detect_new_candidates(api, 3)) == 0


def test_detect_new_candidates_only_reports_new(monkeypatch, tmp_path):
    monkeypatch.setattr("src.speculation.CANDIDATES_STATE_FILE", tmp_path / "cand.json")
    monkeypatch.setattr(
        "src.speculation.screen_speculation",
        lambda api, min_signals=3: [{"code": "NSBC", "name": "NSIA", "count": 3, "signals": []}],
    )
    api = object()
    detect_new_candidates(api, 3)  # NSBC déjà signalé

    # nouveau candidat ETIT apparaît
    monkeypatch.setattr(
        "src.speculation.screen_speculation",
        lambda api, min_signals=3: [
            {"code": "NSBC", "name": "NSIA", "count": 3, "signals": []},
            {"code": "ETIT", "name": "ETI", "count": 3, "signals": []},
        ],
    )
    new = detect_new_candidates(api, 3)
    assert [c["code"] for c in new] == ["ETIT"]  # seulement le nouveau
