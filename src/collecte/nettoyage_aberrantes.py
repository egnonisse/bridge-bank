"""Nettoyage des valeurs aberrantes isolees de l'historique BRVM.

PROBLEME
--------
Certaines barres portent un cours manifestement faux : PRSC affiche 123 000 F
le 08/10/2019 au milieu d'une serie a 2 650 F de mediane. Une seule barre de ce
type suffit a produire un drawdown de -98 % et a fausser toute statistique.

METHODE
-------
Pour chaque barre, on compare le cours a la MEDIANE des 20 barres voisines.
Si le rapport sort de la fourchette [1/seuil, seuil] — soit x5 a la hausse, soit
/5 a la baisse (test SYMETRIQUE, B2-11) — la barre est declaree aberrante.

Correction : la barre est remplacee par la mediane locale (interpolation
robuste). On ne supprime rien — la serie garde sa longueur.

POURQUOI 5x
-----------
La BRVM est peu liquide : des ecarts de 3x existent legitimement (petites
capitalisations, carnets vides). Au-dela de 5x la mediane locale, il s'agit
d'une erreur de saisie ou d'un report de cours.
"""
from __future__ import annotations

import copy
import statistics
from dataclasses import replace

SEUIL = 5.0
VOISINS = 20


def _mediane_locale(cl, i, n=VOISINS):
    lo = max(0, i - n)
    hi = min(len(cl), i + n + 1)
    voisins = [c for j, c in enumerate(cl[lo:hi], start=lo) if j != i and c]
    return statistics.median(voisins) if voisins else 0.0


def reperer_aberrantes(barres, seuil=SEUIL, voisins=VOISINS):
    """Retourne la liste des indices de barres aberrantes.

    Test SYMÉTRIQUE (B2-11, corrigé le 12/10) : une barre dont le cours sort de la
    fourchette [médiane ÷ seuil, médiane × seuil] est aberrante — l'ancienne version ne
    voyait que les pics (cours > 5×), jamais les effondrements isolés (10 F au milieu de
    100 F), qui fabriquent pourtant de faux signaux baissiers (cassures, RSI, stops).
    """
    cl = [float(getattr(b, "close", 0) or 0) for b in barres]
    out = []
    for i, c in enumerate(cl):
        if not c:
            continue
        med = _mediane_locale(cl, i, voisins)
        if med > 0 and not (1.0 / seuil < c / med < seuil):
            out.append(i)
    return out


def nettoyer(barres, seuil=SEUIL, voisins=VOISINS):
    """Retourne une copie nettoyee des barres.

    Retourne (barres_nettoyees, liste_des_corrections).
    """
    resultat = copy.deepcopy(barres)
    cl = [float(getattr(b, "close", 0) or 0) for b in resultat]
    corrections = []

    for i in reperer_aberrantes(resultat, seuil, voisins):
        med = _mediane_locale(cl, i, voisins)
        if med <= 0:
            continue
        avant = cl[i]
        maj = {"close": round(med, 6)}
        for champ in ("open", "high", "low"):
            v = getattr(resultat[i], champ, None)
            if v and not (1.0 / seuil < float(v) / med < seuil):  # symétrique (B2-11)
                maj[champ] = round(med, 6)
        try:
            resultat[i] = replace(resultat[i], **maj)
        except TypeError:
            for k, v in maj.items():
                setattr(resultat[i], k, v)
        cl[i] = med  # la valeur corrigee sert aux calculs suivants
        corrections.append({
            "date": str(getattr(resultat[i], "date", ""))[:10],
            "avant": round(avant, 2),
            "apres": round(med, 2),
            "facteur": round(avant / med, 2) if med else None,
        })
    return resultat, corrections


def nettoyer_historique(hist, seuil=SEUIL, voisins=VOISINS):
    """Nettoie tout un historique {code: [barres]}."""
    out = {}
    rapport = []
    total = 0
    for code, barres in hist.items():
        if not barres:
            out[code] = barres
            continue
        propres, corrections = nettoyer(barres, seuil, voisins)
        out[code] = propres
        if corrections:
            total += len(corrections)
            rapport.append({"code": code, "corrections": corrections})
    return {"historique": out, "rapport": rapport, "total_corrections": total}
