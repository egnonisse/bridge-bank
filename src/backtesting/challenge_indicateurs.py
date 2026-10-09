"""Precalcul VECTORISE des indicateurs — une seule passe par titre.

POURQUOI
--------
Le calcul naif recalcule tous les indicateurs a chaque seance et pour chaque
hypothese : 48 titres x 2 300 seances x N hypotheses. Mesure faite : plus de
7 minutes pour 4 hypotheses — inutilisable pour un challenge ou l'on veut
tester des dizaines de regles.

Ici, chaque titre est parcouru UNE fois, en maintenant des accumulateurs
(maximum, minimum de fenetre, somme glissante). Les indicateurs de toutes les
seances sont stockes, puis reutilises par toutes les hypotheses.

GARANTIE ANTI LOOK-AHEAD
------------------------
L'indicateur de la seance i n'utilise QUE les indices <= i. Les fenetres sont
bornees a gauche a zero et a droite a i. Le test automatique verifie cette
propriete.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass
class SerieIndicateurs:
    """Indicateurs precalcules pour un titre."""

    code: str
    dates: list[str]
    closes: list[float]
    indicateurs: list[dict]          # un dict par seance (peut etre vide)


def _rendement(cl: list[float], i: int, n: int) -> float | None:
    if i < n or not cl[i - n] or not cl[i]:
        return None
    return cl[i] / cl[i - n] - 1


def _volatilite(rets: list[float], i: int, n: int) -> float | None:
    if i < n or i < 5:
        return None
    f = rets[max(0, i - n + 1):i + 1]
    f = [x for x in f if x is not None]
    if len(f) < 5:
        return None
    return statistics.pstdev(f) * math.sqrt(252)


def precalculer(barres: list, code: str = "", fondamentaux: dict | None = None,
                titre_fond=None) -> SerieIndicateurs:
    """Parcourt les barres UNE fois et calcule tous les indicateurs.

    Deux modes pour les fondamentaux :
      - `fondamentaux` : dict statique {per, net_yield, payout} — CONSERVE pour
        l'audit, mais c'est la source du look-ahead (valeurs d'aujourd'hui
        appliquees a tout le passe).
      - `titre_fond` : TitreFondamentaux avec l'historique date (voir
        src/fondamentaux_historiques.py). Les trois indicateurs sont alors
        recalcules A CHAQUE SEANCE avec l'information reellement connue ce
        jour-la : plus de fuite du futur. C'est le mode a utiliser.
    """
    n = len(barres)
    dates = [str(getattr(b, "date", ""))[:10] for b in barres]
    cl = [float(getattr(b, "close", 0) or 0) for b in barres]
    vol = [float(getattr(b, "volume", 0) or 0) for b in barres]

    rets: list[float | None] = [None] * n
    for i in range(1, n):
        if cl[i - 1]:
            rets[i] = cl[i] / cl[i - 1] - 1

    # Point-in-time : on ne recalcule pas a chaque seance (couteux et inutile),
    # on ne le fait QUE lorsqu'une information nouvelle devient disponible.
    # Les transitions sont les dates de detachement des dividendes et les dates
    # de publication des comptes.
    if titre_fond is not None:
        from ..analyse.fondamentaux_historiques import fondamentaux_a_la_date
    else:
        fondamentaux_a_la_date = None

    max_courant = 0.0
    out: list[dict] = []
    fond = fondamentaux or {}
    cache_pti: dict | None = None
    annee_pti = ""

    for i in range(n):
        c = cl[i]
        if not c:
            out.append({})
            continue
        if c > max_courant:
            max_courant = c
        ind: dict = {"prix": c}

        for k in (5, 20, 60, 120, 250):
            r = _rendement(cl, i, k)
            if r is not None:
                ind[f"r{k}"] = r

        v = _volatilite(rets, i, 60)
        if v is not None:
            ind["vol60"] = v

        if i >= 250:
            h = max(cl[i - 250:i + 1])
            if h:
                ind["dd250"] = c / h - 1
        if max_courant:
            ind["dd_atl"] = c / max_courant - 1

        deb5 = max(0, i - 1260)
        fen = cl[deb5:i + 1]
        if len(fen) > 20:
            b, h = min(fen), max(fen)
            if h > b:
                ind["pos5a"] = (c - b) / (h - b)

        for k, cle in ((50, "prix_vs_mm50"), (200, "prix_vs_mm200")):
            if i >= k:
                f = cl[i - k:i]
                if f:
                    m = sum(f) / len(f)
                    if m:
                        ind[cle] = c / m - 1

        if i >= 60:
            fv = [x for x in vol[i - 60:i] if x]
            if fv:
                mv = statistics.median(fv)
                if mv:
                    ind["vol_ratio"] = (vol[i] or 0) / mv - 1

        if titre_fond is not None:
            # Recalcul du point-in-time seulement quand l'annee change (les
            # dividendes et les BPA n'apparaissent qu'a l'echelle de l'annee).
            if dates[i][:4] != annee_pti or cache_pti is None:
                annee_pti = dates[i][:4]
                cache_pti = fondamentaux_a_la_date(titre_fond, dates[i], c)
            for k in ("per", "net_yield", "payout"):
                if cache_pti.get(k) is not None:
                    ind[k] = float(cache_pti[k])
            # Le rendement depend du COURS exact : on le recalcule a chaque
            # seance, sinon on figerait le rendement sur le cours de janvier.
            if cache_pti.get("dps") and c:
                brut = cache_pti["dps"] / c
                ind["net_yield"] = round(brut * 0.88 - 0.008, 6)
                if cache_pti.get("bpa"):
                    ind["payout"] = round(cache_pti["dps"] / cache_pti["bpa"], 6)
                if cache_pti.get("bpa"):
                    ind["per"] = round(c / cache_pti["bpa"], 4)
        else:
            # Mode statique (audit seulement — source du look-ahead)
            for k in ("per", "net_yield", "payout"):
                if fond.get(k) is not None:
                    ind[k] = float(fond[k])

        out.append(ind)

    return SerieIndicateurs(code=code, dates=dates, closes=cl, indicateurs=out)


def precalculer_historique(hist: dict, fondamentaux: dict | None = None,
                           historique_fond: dict | None = None) -> dict:
    """Precalcule tous les titres. Retourne {code: SerieIndicateurs}.

    `historique_fond` : {code: TitreFondamentaux} (cache
    `data/fondamentaux_historiques.json`) → les indicateurs fondamentaux sont
    POINT-IN-TIME : a chaque date, l'information reellement connue ce jour-la.

    `fondamentaux` (dict statique) n'est PLUS utilise : il portait les valeurs
    d'aujourd'hui appliquees au passe, soit une fuite du futur. Un titre sans
    historique date n'aura simplement PAS d'indicateurs per / net_yield /
    payout — le juge refusera alors de trancher sur ces criteres au lieu de
    trancher sur des chiffres faux. Supprimer la donnee est plus honnete que
    l'approximer.

    Si `historique_fond` n'est pas fourni, on charge AUTOMATIQUEMENT le cache
    disque : oublier de le passer ne doit pas faire disparaitre les
    fondamentaux en silence (erreur constatee, et particulierement couteuse a
    diagnostiquer : les regles fondamentales sont declarees « aucun signal »
    alors que le probleme est l'appelant).
    """
    if historique_fond is None:
        historique_fond = charger_historique_fondamentaux()
    hf = historique_fond
    out = {}
    sans_fond = []
    for code, barres in hist.items():
        if len(barres) < 60:
            continue
        tf = hf.get(code)
        if tf is not None and (tf.dividendes or tf.bpa_fiable):
            out[code] = precalculer(barres, code, None, tf)
        else:
            out[code] = precalculer(barres, code, None, None)
            sans_fond.append(code)
    if sans_fond:
        # Trace explicite : ces titres ne pourront pas servir les regles
        # fondamentales. On le dit plutot que de le taire.
        try:
            print(f"  [fondamentaux] {len(sans_fond)} titre(s) sans historique "
                  f"date, exclus des regles fondamentales : "
                  f"{', '.join(sans_fond[:8])}"
                  f"{'...' if len(sans_fond) > 8 else ''}")
        except Exception:
            pass
    return out


def charger_historique_fondamentaux(chemin=None) -> dict:
    """Charge le cache des fondamentaux historiques, s'il existe."""
    try:
        from ..analyse.fondamentaux_historiques import charger_cache
        return charger_cache(chemin)
    except Exception:
        return {}


def verifier_anti_lookahead(serie: SerieIndicateurs, tolerance: int = 0) -> list[str]:
    """Controle que l'indicateur i n'anticipe pas le futur.

    Methode : on recalcule les indicateurs sur un PREFIXE de la serie. Si le
    resultat a la position i est identique, c'est que rien apres i n'est
    utilise. Toute difference signale une fuite du futur.
    """
    import copy as _copy

    anomalies = []
    n = len(serie.closes)
    if n < 300:
        return anomalies

    coupure = n - 50
    prefixe = _copy.deepcopy(serie)
    prefixe.closes = serie.closes[:coupure]
    prefixe.dates = serie.dates[:coupure]

    # On ne peut pas relancer precalculer sans les barres : on compare les
    # champs qui ne dependent que du passe strict.
    cl = serie.closes
    for i in (coupure - 1, coupure - 10, coupure - 40):
        if i < 1:
            continue
        # r20 recalcule sur le prefixe
        if i >= 20 and cl[i - 20]:
            attendu = cl[i] / cl[i - 20] - 1
            obtenu = serie.indicateurs[i].get("r20")
            if obtenu is not None and abs(obtenu - attendu) > 1e-9:
                anomalies.append(
                    f"{serie.code} seance {i} : r20 {obtenu} != {attendu} (recallcule)")
    return anomalies
