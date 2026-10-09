"""Compare les définitions d'épisode avant de choisir laquelle devient LA référence.

POURQUOI CE SCRIPT
------------------
Le seuil de vente et le profil de retournement mesurent le MÊME phénomène (« le prix a
monté, que fait-il ensuite ? ») avec DEUX définitions différentes :

    seuil   : hausse >= seuil, dédoublonnage par saut de 20 séances, pas de borne haute
    profil  : hausse entre 13 % et 65 %, espacement minimal de 10 séances, suite sur 60 j

D'où deux chiffres pour une même notion (SNTS : 86 % sur 7 cas contre 90 % sur 10 cas).

Ce script mesure l'effet de CHAQUE règle séparément, pour choisir en connaissance de cause
plutôt que par préférence. Il n'écrit rien.

    python scripts/comparer_definitions_episodes.py
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history  # noqa: E402
from src.bsapi import BSApi  # noqa: E402
from src.calibration import seuils_vente as sv  # noqa: E402


def episodes(closes: list[float], seuil: float, borne_haute: float | None = None,
             espacement: int = 20, horizon: int = 20) -> list[int]:
    """Indices des épisodes selon la définition demandée.

    - `borne_haute` : None = toute hausse >= seuil ; sinon plafond de la hausse retenue.
    - `espacement`  : distance minimale entre deux épisodes retenus.
    - `horizon`     : séances futures exigées (60 pour les stats de creux).
    """
    n = len(closes)
    raw = []
    i = 20
    while i < n - horizon:
        ref = closes[i - 20]
        if ref > 0:
            ret = closes[i] / ref - 1
            if ret >= seuil and (borne_haute is None or ret <= borne_haute):
                raw.append(i)
        i += 1
    # Dédoublonnage : premier arrivé, premier retenu, puis on saute l'espacement.
    idx: list[int] = []
    for j in raw:
        if not idx or j - idx[-1] >= espacement:
            idx.append(j)
    return idx


def wilson(k: int, n: int) -> float:
    return sv.intervalle_wilson(k, n)[1] * 100


def main() -> int:
    hist = load_all_history(BSApi(), force=False)
    seuils = sv.charger()

    titres = [c for c in ("SNTS", "SGBC", "SLBC", "PALC") if c in hist]
    print(f"{'titre':7s}{'seuil':>7s} | {'définition':38s} {'cas':>4s} {'baisse':>7s} {'borne basse':>12s}")
    print("-" * 82)

    for code in titres:
        closes = [float(b.close) for b in hist[code]]
        seuil = float(seuils.get(code, {}).get("threshold", 0.13))

        definitions = [
            ("seuil de vente (espace 20, sans borne)", seuil, None, 20, 20),
            ("profil actuel (espace 10, borne 65 %)", seuil, 0.65, 10, 60),
            ("profil SANS borne (espace 10)", seuil, None, 10, 60),
            ("profil espace 20 SANS borne", seuil, None, 20, 60),
            ("reference : espace 20, sans borne, h20", seuil, None, 20, 20),
        ]
        for libelle, s, bh, esp, hor in definitions:
            idx = episodes(closes, s, bh, esp, hor)
            if not idx:
                print(f"{code:7s}{s*100:6.0f}% | {libelle:38s} {0:>4d} {'—':>7s} {'—':>12s}")
                continue
            f20 = [closes[i + 20] / closes[i] - 1 for i in idx]
            n = len(f20)
            k = sum(1 for f in f20 if f < 0)
            taux = k / n * 100
            bb = wilson(k, n)
            marque = "  <-- FIABLE" if bb >= 50 else ""
            print(f"{code:7s}{s*100:6.0f}% | {libelle:38s} {n:>4d} {taux:>6.0f}% {bb:>11.0f}%{marque}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
