"""Régime de marché — l'indicateur qui conditionne le renforcement.

POURQUOI CE MODULE
------------------
Mesure sur 5 196 observations (28 ans) : le renforcement sur faiblesse gagne dans
**67-69 % des cas quand on entre en année de krach**, mais seulement **42-49 % en année
normale**. Le même geste vaut donc son contraire selon l'état du marché. Aujourd'hui le
système renforce dès qu'un titre repasse sous son seuil, sans regarder où en est le
marché : la moitié du temps, il propose une action dont les données disent qu'elle ne
paie pas.

INDICATEUR RETENU — l'indice médian des titres suivis
-----------------------------------------------------
Défini explicitement, sans source externe :

    1. Pour chaque date où au moins 5 titres cotent, on prend la MÉDIANE des variations
       quotidiennes (contre la dernière cote connue de chaque titre).
    2. L'indice est le produit cumulé de (1 + médiane), base 100 au premier jour.
    3. Le régime est BAISSIER si l'indice est sous sa moyenne des `FENETRE` derniers
       points, HAUSSIER sinon.

Pourquoi la médiane et pas la moyenne : quelques valeurs extrêmes (une division mal
ajustée, un titre illiquide qui bondit) déplacent une moyenne, jamais une médiane. C'est
le même choix que pour l'indice de contrôle des 28 ans.

Pourquoi une fenêtre de 200 séances (~10 mois) : assez longue pour ignorer une correction
de quelques semaines (qui n'est PAS un krach et où le renforcement reste neutre), assez
courte pour réagir à un vrai retournement comme mars 2020 ou 2018.

LIMITE ASSUMÉE
--------------
C'est un indicateur CONSTRUIT à partir des titres qu'on suit : il ne mesure pas « le
marché BRVM » au sens officiel, il mesure l'environnement des titres du portefeuille.
C'est ce qui importe ici — mais il faut le dire tel quel, pas le présenter comme l'indice
BRVM Composite.
"""
from __future__ import annotations

import statistics
from pathlib import Path

FENETRE = 200          # ~10 mois de cotation
MIN_TITRES = 5         # en dessous, la médiane n'a pas de sens

HAUSSIER = "haussier"
BAISSIER = "baissier"


def construire_indice(series: dict[str, dict[str, float]]) -> list[tuple[str, float]]:
    """Indice médian base 100 à partir de {code: {date: cours}}.

    MÉTHODE — buy & hold, PAS rebalancement quotidien
    -------------------------------------------------
    Chaque titre est d'abord normalisé (base 100 à sa première cote). L'indice est
    ensuite la MÉDIANE des valeurs normalisées disponibles à chaque date.

    La première version cumulait `(1 + médiane des variations quotidiennes)`. C'est un
    indice à REBALANCEMENT QUOTIDIEN : il subit le *volatility drag* et, sur 46 titres
    volatils et 10 ans, il affichait une baisse de 43 % là où le marché montait. Un
    indicateur de régime qui se trompe de sens est pire qu'aucun indicateur — d'où ce
    choix d'une moyenne buy & hold, qui ne suppose aucun rebalancement.

    La médiane (et non la moyenne) protège des valeurs extrêmes : un titre illiquide qui
    bondit, ou une division mal ajustée, déplacent une moyenne mais jamais une médiane.
    """
    normalise: dict[str, dict[str, float]] = {}
    for code, s in series.items():
        dates_titre = sorted(s)
        if not dates_titre:
            continue
        base = s[dates_titre[0]]
        if not base:
            continue
        normalise[code] = {d: s[d] / base * 100 for d in dates_titre}

    dates = sorted({d for s in series.values() for d in s})
    out: list[tuple[str, float]] = []
    for d in dates:
        valeurs = [n[d] for n in normalise.values() if d in n]
        if len(valeurs) >= MIN_TITRES:
            out.append((d, statistics.median(valeurs)))
    return out


def etat_marche(series: dict[str, dict[str, float]],
                fenetre: int = FENETRE) -> dict:
    """Régime de marché + les chiffres qui le justifient (traçables, pas un booléen nu)."""
    indice = construire_indice(series)
    if len(indice) < 30:
        return {"etat": HAUSSIER, "raison": "historique insuffisant — prudence",
                "valeur": None, "moyenne": None, "ecart_pct": None, "points": len(indice)}

    valeurs = [v for _, v in indice]
    n = min(fenetre, len(valeurs))
    moyenne = statistics.mean(valeurs[-n:])
    courante = valeurs[-1]
    ecart = (courante / moyenne - 1) * 100 if moyenne else 0.0
    return {
        "etat": BAISSIER if courante < moyenne else HAUSSIER,
        "raison": f"indice {'sous' if courante < moyenne else 'au-dessus de'} sa moyenne {n} séances",
        "valeur": round(courante, 2),
        "moyenne": round(moyenne, 2),
        "ecart_pct": round(ecart, 2),
        "points": len(valeurs),
        "date": indice[-1][0],
    }


def charger_series_quotidiennes(chemin: Path) -> dict[str, dict[str, float]]:
    """Charge data/history_clean.pkl (cours quotidiens, ajustés des divisions)."""
    import pickle

    h = pickle.load(open(chemin, "rb"))
    out: dict[str, dict[str, float]] = {}
    for code, barres in h.items():
        d = {}
        for b in barres:
            dt = str(getattr(b, "date", ""))[:10]
            c = getattr(b, "close", None) or getattr(b, "cours", None)
            if dt and c:
                d[dt] = float(c)
        if len(d) > 250:
            out[code] = dict(sorted(d.items()))
    return out


def regime_du_jour(chemin_hist: Path | None = None,
                   chemin_cache: Path | None = None) -> dict:
    """Régime de marché, avec cache disque (un calcul par jour).

    Le calcul parcourt 46 titres × ~2 400 dates : inutile de le refaire à chaque appel
    dans la même journée. Le cache porte la DATE de calcul, pas une durée — il expire
    donc naturellement au changement de jour, sans minuterie à maintenir.
    """
    import json
    from datetime import date

    base = Path(__file__).resolve().parent.parent
    chemin_hist = chemin_hist or (base / "data" / "history_clean.pkl")
    chemin_cache = chemin_cache or (base / "data" / "regime_marche.json")
    aujourdhui = date.today().isoformat()

    try:
        cache = json.loads(chemin_cache.read_text(encoding="utf-8"))
        if cache.get("calcule_le") == aujourdhui:
            return cache
    except (OSError, ValueError):
        pass

    series = charger_series_quotidiennes(chemin_hist)
    etat = etat_marche(series)
    etat["calcule_le"] = aujourdhui
    try:
        chemin_cache.write_text(json.dumps(etat, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    except OSError:
        pass
    return etat
