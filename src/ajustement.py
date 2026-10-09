"""Ajustement de l'historique des divisions de nominal (splits).

⚠️  MODULE D'APPUI — N'EST PLUS LA VOIE DE REFERENCE
----------------------------------------------------
L'ajustement de reference est desormais assure par `src/divisions_officielles.py`,
base sur les operations PUBLIEES (data/divisions_officielles.json) — 38 divisions,
verifiees par croisement avec les cours.

Ce module ici conserve la DETECTION heuristique. Elle est conservee pour un seul
usage : AUDITER la reference officielle (voir `comparer_avec_officiel`). Elle ne
doit JAMAIS servir a ajuster l'historique : mesure faite sur les donnees, elle
trouve 12 divisions la ou il y en a 34, et se trompe sur les petites parites
(1:2) comme sur les ratios hors liste (1:25, 1:40, 1:64).

PROBLEME INITIAL (historique)
-----------------------------
L'historique brut n'est pas ajuste des divisions de nominal. Un titre qui
valait 117 600 F en aout 2017 et vaut 12 000 F apres une division 1:10 montre
une « chute » de -90 % qui n'a jamais eu lieu : l'actionnaire a recu 10 fois
plus de titres de valeur 10 fois moindre.

Sans correction, toute statistique de performance ou de drawdown est FAUSSE.

METHODE (heuristique, pour audit seulement)
-------------------------------------------
On parcourt les barres de la plus ancienne a la plus recente. A chaque cassure
de niveau PERMANENTE (detectee par `_is_probable_split` de cache_integrity),
on divise tous les cours ANTERIEURS par le ratio, et on multiplie les volumes
par ce meme ratio.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, replace

from .collecte.cache_integrity import _is_probable_split

# Ratios de division observes sur la BRVM
RATIOS_BRVM = (2, 3, 4, 5, 10, 20, 50, 100)

# Tolerance pour reconnaitre un rapport rond (5 %)
TOLERANCE_RATIO = 0.05

# Facteur minimum de cassure pour parler de division
SAUT_MIN = 1.8


@dataclass
class Division:
    """Une division de nominal detectee."""

    index: int          # position de la premiere barre APRES division
    date: str           # date de la division
    ratio: int          # rapport rond retenu (ex. 10 pour 1:10)
    ratio_mesure: float  # rapport effectivement observe
    avant: float        # cours juste avant
    apres: float        # cours juste apres


def ratio_rond(rapport: float) -> int | None:
    """Rapproche un rapport mesure du rapport rond BRVM le plus proche.

    Retourne None si aucun rapport rond ne correspond a moins de 5 %.
    """
    if rapport < SAUT_MIN:
        return None
    meilleur = min(RATIOS_BRVM, key=lambda r: abs(r - rapport) / r)
    if abs(meilleur - rapport) / meilleur <= TOLERANCE_RATIO:
        return meilleur
    return None


def detecter_divisions(closes: list[float], dates: list[str]) -> list[Division]:
    """Repere toutes les divisions de nominal d'un titre."""
    trouvees: list[Division] = []
    for i in range(1, len(closes)):
        c0, c1 = closes[i - 1], closes[i]
        if not c0 or not c1 or c0 <= 0 or c1 <= 0:
            continue
        rapport = c0 / c1
        if rapport < SAUT_MIN:
            continue
        # Confirme par la logique existante du projet (niveau permanent)
        if not _is_probable_split(closes, i):
            continue
        rond = ratio_rond(rapport)
        if rond is None:
            continue
        trouvees.append(Division(
            index=i,
            date=dates[i],
            ratio=rond,
            ratio_mesure=round(rapport, 3),
            avant=c0,
            apres=c1,
        ))
    return trouvees


def ajuster_barres(barres: list, dates: list[str], closes: list[float]) -> int:
    """Ajuste les barres SUR PLACE. Retourne le nombre de divisions traitees.

    Les barres sont modifiees via dataclasses.replace : on ne touche pas au
    cache d'origine (l'appelant decide de persister ou non).
    """
    divisions = detecter_divisions(closes, dates)
    if not divisions:
        return 0

    # On applique de la plus RECENTE a la plus ANCIENNE : chaque division
    # recalibre tout ce qui precede, sans interferer avec les suivantes.
    for d in sorted(divisions, key=lambda x: -x.index):
        for j in range(d.index):
            b = barres[j]
            maj = {"close": round(b.close / d.ratio, 4)}
            for champ in ("open", "high", "low"):
                v = getattr(b, champ, None)
                if v:
                    maj[champ] = round(v / d.ratio, 4)
            # Le volume est multiplie : plus de titres, chacun moins cher
            vol = getattr(b, "volume", None)
            if vol:
                maj["volume"] = int(vol * d.ratio)
            try:
                barres[j] = replace(b, **maj)
            except TypeError:
                # Objet non-dataclass : on modifie les attributs directement
                for k, v in maj.items():
                    setattr(barres[j], k, v)
    return len(divisions)


def ajuster_historique(hist: dict) -> dict:
    """Ajuste tout un historique {code: [barres]}.

    Retourne un nouveau dictionnaire — l'entree n'est pas modifiee, ce qui
    permet de comparer avant/apres.
    """
    resultat = {}
    rapport = []
    for code, barres in hist.items():
        if not barres:
            resultat[code] = barres
            continue
        copies = list(barres)  # copie superficielle : on remplace les elements
        dates = [str(getattr(b, "date", ""))[:10] for b in copies]
        closes = [float(getattr(b, "close", 0) or 0) for b in copies]
        n = ajuster_barres(copies, dates, closes)
        resultat[code] = copies
        if n:
            rapport.append((code, n))
    return {"historique": resultat, "divisions": rapport}


def decrire(barres_avant: list, barres_apres: list) -> str:
    """Resume l'effet de l'ajustement sur un titre."""
    def perf(bs):
        cl = [float(b.close) for b in bs if getattr(b, "close", None)]
        return (cl[-1] / cl[0] - 1) * 100 if len(cl) > 1 and cl[0] else 0

    return (f"  avant : {perf(barres_avant):+8.1f} %\n"
            f"  apres : {perf(barres_apres):+8.1f} %")
