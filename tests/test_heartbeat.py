"""Tests du heartbeat quotidien (silence ≠ bug)."""
from src.main import _build_heartbeat


def test_heartbeat_all_quiet():
    msg = _build_heartbeat([("BOC", True), ("Stops (spéculation)", True)])
    assert "rien à signaler" in msg
    assert "🔔" not in msg
    assert "BOC" in msg


def test_heartbeat_with_event():
    msg = _build_heartbeat([("BOC", True), ("Opportunités value", False)])
    assert "🔔 événement" in msg
    assert "Opportunités value : 🔔" in msg
    assert "alerte ci-dessus" in msg
