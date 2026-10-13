"""P7-01 (photo statique) : toute écriture d'un fichier d'état JSON passe par
`src.infrastructure.ecriture.ecrire_json_atomique`.

POURQUOI CE TEST
----------------
`spec_positions.json` (positions de trading RÉEL) était écrit par un `write_text` direct :
un crash en cours d'écriture pouvait laisser un fichier tronqué, que l'ancien loader
avalait en silence (`return []`) — « aucune position » au lieu d'une erreur (audit P7-01,
corrigé au lot 5). Le lot 6 a généralisé l'écriture atomique aux ~17 sites d'état.

Une régression ne se verrait PAS dans les tests de valeur (le fichier s'écrit bien en
temps normal). Ce contrôle statique, si : tout `X.write_text(json.dumps(...))` est
interdit SAUF si `X` est un temporaire (motif `tmp`/`temporaire`/`temp`, écrit puis
`replace()` — le motif atomique inline légitime).

Les chemins littéraux recopiés (« data/… ») sont couverts par
`scripts/verifier_chemins.py` ; ce test-ci couvre l'ATOMICITÉ.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Capture « variable.write_text( [+ retours à la ligne] json.dumps »
MOTIF = re.compile(
    r"(?m)([A-Za-z_][\w.]*)\.write_text\(\s*(?:#[^\n]*\n\s*)?(json|_json)\.dumps\b"
)
# Un temporaire légitime (écrit puis .replace()) porte l'un de ces préfixes/noms.
AUTORISE = re.compile(r"(?i)^(tmp|temporaire|temp)[\w.]*$|\.tmp\b|temporaire")


def _fichiers_src() -> list[Path]:
    return [
        f
        for f in sorted((RACINE / "src").rglob("*.py"))
        if "__pycache__" not in f.parts
    ]


def test_aucune_ecriture_json_non_atomique() -> None:
    """Tout `.write_text(json.dumps(...))` doit viser un temporaire (atomique)."""
    coupables: list[str] = []
    for f in _fichiers_src():
        source = f.read_text(encoding="utf-8")
        for m in MOTIF.finditer(source):
            variable = m.group(1)
            if AUTORISE.search(variable):
                continue
            ligne = source[: m.start()].count("\n") + 1
            coupables.append(f"{f.relative_to(RACINE).as_posix()}:{ligne} → {variable}.write_text(...)")

    assert not coupables, (
        "Écriture JSON non atomique (P7-01) — utiliser "
        "ecrire_json_atomique() de src/infrastructure/ecriture.py :\n  "
        + "\n  ".join(coupables)
    )
