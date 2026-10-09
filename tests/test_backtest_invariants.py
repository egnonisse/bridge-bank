"""Invariants du backtest — ce qui doit rester vrai quelle que soit la modification.

POURQUOI CE FICHIER EXISTE
--------------------------
Le drawdown du portefeuille est reconstitué à partir des cours, et sur la BRVM beaucoup de
valeurs **ne cotent pas tous les jours**. Sommer `actions × cours` en ignorant les titres
sans cote ce jour-là fait chuter la valeur du portefeuille **artificiellement** : la
première mesure avait donné −73 % là où l'indice du marché ne perdait que −2,3 %.

La correction (report de la dernière cote connue, « forward-fill ») était documentée dans
le code … mais **aucun test ne la protégeait**. Une futur simplification « inutile » de la
boucle aurait recréé le bug en silence, et il aurait fallu le redécouvrir.

C'est exactement le type de trou que le document `docs/INVARIANTS-METIER.md` sert à rendre
visible.
"""
from types import SimpleNamespace

import pytest

from src.backtesting.backtest_noyau import _drawdown_portefeuille


def _jours(n: int = 60) -> list[str]:
    """n dates croissantes au format attendu par la fonction (YYYY-MM-DD)."""
    out = []
    for i in range(n):
        mois = 1 + i // 30
        out.append(f"2026-{mois:02d}-{(i % 30) + 1:02d}")
    return out


def test_un_titre_sans_cote_ne_fabrique_pas_de_drawdown():
    """LE test de l'invariant : un titre qui cesse de coter ne doit pas créer de baisse.

    Montage : deux titres à 1 000 F, portefeuille de 2 000 F. Le titre B ne cote plus
    après le 10ᵉ jour, mais vaut toujours 1 000 F comptablement.

    - SANS forward-fill : B vaut 0 → le portefeuille « passe » de 2 000 à 1 000 F, soit
      un drawdown de −50 % entièrement fabriqué.
    - AVEC forward-fill : B reste à sa dernière cote → drawdown 0.
    """
    jours = _jours(60)
    barres_a = [SimpleNamespace(date=d, close=1000.0) for d in jours]
    barres_b = [SimpleNamespace(date=d, close=1000.0) for d in jours[:10]]

    hist = {"A": barres_a, "B": barres_b}
    positions = [SimpleNamespace(code="A", actions=1),
                 SimpleNamespace(code="B", actions=1)]

    dd = _drawdown_portefeuille(hist, positions, jours[0], jours[-1])
    assert dd == pytest.approx(0.0), (
        "le drawdown doit rester nul : le titre B n'a pas perdu de valeur, il ne cote "
        "simplement plus. Un résultat proche de −0,5 signifie que le forward-fill a été "
        "perdu.")


def test_le_drawdown_reel_est_bien_mesure():
    """Symétrique du test précédent : une VRAIE baisse doit être comptée.

    Sans ce test, une fonction qui renverrait toujours 0 passerait le test ci-dessus.
    """
    jours = _jours(60)
    # A : 1 000 F puis 700 F à partir du jour 30 → le portefeuille perd 15 %.
    barres_a = [SimpleNamespace(date=d, close=1000.0 if i < 30 else 700.0)
                for i, d in enumerate(jours)]
    barres_b = [SimpleNamespace(date=d, close=1000.0) for d in jours]

    hist = {"A": barres_a, "B": barres_b}
    positions = [SimpleNamespace(code="A", actions=1),
                 SimpleNamespace(code="B", actions=1)]

    dd = _drawdown_portefeuille(hist, positions, jours[0], jours[-1])
    # 2 000 F → 1 700 F = −15 %
    assert dd == pytest.approx(-0.15, abs=0.01)


def test_serie_trop_courte_ne_plante_pas():
    """Sous 30 dates, la mesure n'a pas de sens : on renvoie 0, on ne plante pas."""
    jours = _jours(20)
    barres = [SimpleNamespace(date=d, close=1000.0) for d in jours]
    positions = [SimpleNamespace(code="A", actions=1)]

    assert _drawdown_portefeuille({"A": barres}, positions, jours[0], jours[-1]) == 0.0


def test_portefeuille_vide_ne_plante_pas():
    assert _drawdown_portefeuille({}, [], "2026-01-01", "2026-03-01") == 0.0
