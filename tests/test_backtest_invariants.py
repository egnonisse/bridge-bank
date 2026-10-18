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

from datetime import datetime, timedelta

import pytest

from src.backtesting.backtest_noyau import _drawdown_portefeuille
from src.domaine.models import HistoryBar, Quote, Snapshot


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


# ═══════════ fraîcheur des DONNÉES du cache historique (incident du 12/10/2026) ═══════════
# Un refresh peut capturer des données DÉJÀ en retard : le 09/10, le fichier était daté du
# jour mais ses dernières barres dataient du 30/09 — et le mtime « frais » a figé ce cache
# sept jours de plus (réutilisé jusqu'au 16/10). La leçon : la fraîcheur se juge sur les
# DONNÉES (dernière barre), pas sur le mtime.

def _barre(quand, close):
    return HistoryBar(date=quand, open=close, high=close, low=close, close=close, volume=1000)


def test_donnees_fraiches_juge_sur_la_derniere_barre():
    from src.collecte import backtest as bt

    maintenant = datetime.now()
    vieux = {"AAA": [_barre(maintenant - timedelta(days=10), 100.0)]}
    frais = {"AAA": [_barre(maintenant - timedelta(days=1), 100.0)]}
    assert not bt._donnees_fraiches(vieux)
    assert bt._donnees_fraiches(frais)
    assert not bt._donnees_fraiches({})  # vide = pas exploitable


def test_cache_fichier_recent_mais_donnees_vieilles_declenche_le_refetch(monkeypatch, tmp_path):
    """Le nœud de l'incident : mtime du jour + barres vieilles ⇒ LE CACHE EST IGNORÉ
    et un re-téléchargement est déclenché (auto-réparation)."""
    import pickle

    from src.collecte import backtest as bt

    maintenant = datetime.now()
    cache = tmp_path / "history_cache.pkl"
    with cache.open("wb") as fh:  # mtime = maintenant : « fichier frais »
        pickle.dump({"AAA": [_barre(maintenant - timedelta(days=15), 100.0)]}, fh)
    monkeypatch.setattr(bt, "CACHE_BRUT", cache)
    monkeypatch.setattr(bt, "INACTIFS_FILE", tmp_path / "inactifs.json")

    appels = []

    class FakeApi:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="AAA", name="X", last=2.0)])

        def history(self, code, start, end):
            appels.append(code)
            return [_barre(maintenant - timedelta(days=1), 2.0)]

    hist = bt.load_all_history(FakeApi(), force=False)
    assert appels == ["AAA"], "un re-téléchargement devait être déclenché"
    assert hist["AAA"][-1].close == 2.0, "les données fraîches doivent remplacer le cache périmé"
