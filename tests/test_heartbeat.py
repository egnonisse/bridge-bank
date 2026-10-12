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


def test_heartbeat_signale_les_echecs():
    """B2-04 (CORRIGÉ 12/10) — une étape en échec = titre ⚠️ + statut ❌ ;
    un check qui plante ne doit JAMAIS s'annoncer « ✅ »."""
    msg = _build_heartbeat([("BOC", True), ("Annonces BRVM", True)],
                           echecs=["Annonces BRVM"])
    first_line = msg.splitlines()[0]
    assert "✅" not in first_line, "un check en échec ne peut pas afficher le titre ✅"
    assert "1 étape(s) en ÉCHEC" in first_line
    assert "Annonces BRVM : ❌" in msg
    assert "BOC : ✅" in msg  # les étapes saines restent lisibles


def test_heartbeat_sans_echec_garde_le_titre_vert():
    """B2-04 (CORRIGÉ) — sans échec, le titre reste « ✅ » (comportement historique)."""
    msg = _build_heartbeat([("BOC", True)])
    assert msg.splitlines()[0].startswith("✅ Check quotidien Bridge Bank")
