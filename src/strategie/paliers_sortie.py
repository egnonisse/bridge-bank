"""Le systeme de PALIERS de sortie bat-il une sortie simple ?

LA REGLE REELLE DE LEO (jamais mesuree jusqu'ici)
-------------------------------------------------
  +20 %  -> vendre 1/3, puis ramener le stop au prix d'entree (break-even)
  +35 %  -> vendre 1/3, puis stop suiveur
  +50 %  -> clore la position
  et un garde-fou : stop a -15 % sur la totalite.

POURQUOI CETTE QUESTION COMPTE
------------------------------
C'est la regle de sortie effectivement appliquee en production. Personne ne
l'avait confrontee a une alternative simple. Or une regle de sortie a deux
effets opposes :
  - elle PROTEGE le capital (le stop au break-even apres +20 % evite de rendre
    un gain) ;
  - elle PLAFONNE les hausses (vendre par tiers a 20 %, c'est couper les
    meilleures trajectoires, celles qui font x2).
Lequel l'emporte ? C'est une question empirique, pas de principe.

PROTOCOLE
---------
Memes signaux d'ACHAT, memes dates, meme univers. Seule la SORTIE change :
  A. duree fixe (reference neutre)
  B. paliers de LEO
  C. stop simple -15 %, sinon duree fixe
  D. paliers SANS vente partielle (stop suiveur seul) — isole l'effet d'echelle

Le sens n'est jamais considere comme acquis : on compare des rendements moyens
sur l'ensemble des trades, et le taux de reussite.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# Frais aller-retour : dérivés du courtage réel dans src/regles.py.
from ..regles import FRAIS_ALLER_RETOUR as FRAIS  # noqa: E402
STOP_INITIAL = -0.15   # garde-fou sur la position entiere


@dataclass
class SortiePartielle:
    """Une fraction vendue a un palier."""

    seuil: float          # ex. 0.20 pour +20 %
    fraction: float       # ex. 1/3
    date: str
    cours: float
    rendement: float      # rendement de CETTE fraction, net de sa part de frais


@dataclass
class TradePartiel:
    """Resultat d'une regle de sortie sur UN trade."""

    code: str
    date_entree: str
    date_sortie: str
    cours_entree: float
    seances: int
    sorties: list[SortiePartielle] = field(default_factory=list)
    fraction_restante: float = 1.0
    motif_final: str = ""

    @property
    def rendement_net(self) -> float:
        """Rendement net de frais, pondere par les fractions vendues.

        Chaque fraction supporte sa part des frais d'aller-retour : vendre en
        trois fois ne coute pas le meme prix que vendre d'un coup (trois ordres,
        trois fois la commission minimale).
        """
        if not self.cours_entree:
            return 0.0
        total = 0.0
        parts = 0.0
        for s in self.sorties:
            # frais au prorata de la fraction vendue
            r = (s.cours / self.cours_entree) * (1 - FRAIS * s.fraction) - 1
            total += r * s.fraction
            parts += s.fraction
        return total

    @property
    def a_vendu_avant_fin(self) -> bool:
        return any(s.rendement > 0 for s in self.sorties[:-1]) if len(self.sorties) > 1 else False


def simuler_paliers(barres: list, i_entree: int, duree_max: int,
                    mode: str = "paliers") -> TradePartiel | None:
    """Applique une regle de sortie a un trade ouvert.

    modes :
      "duree"   : on garde jusqu'a duree_max, rien d'autre.
      "paliers" : +20 % vendre 1/3 (stop au break-even), +35 % vendre 1/3
                  (stop suiveur), +50 % clore, stop initial -15 %.
      "stop"    : stop -15 % sur toute la position, sinon duree_max.
      "suiveur" : paliers SANS vente partielle — stop au break-even apres +20 %,
                  stop suiveur apres +35 %, sans jamais vendre par tiers.
    """
    n = len(barres)
    closes = [float(getattr(b, "close", 0) or 0) for b in barres]
    dates = [str(getattr(b, "date", ""))[:10] for b in barres]
    prix_entree = closes[i_entree]
    if not prix_entree:
        return None

    t = TradePartiel(code="", date_entree=dates[i_entree],
                     date_sortie=dates[i_entree], cours_entree=prix_entree,
                     seances=0)

    if mode == "duree":
        j = min(i_entree + duree_max, n - 1)
        t.sorties.append(SortiePartielle(1.0, 1.0, dates[j], closes[j], 0.0))
        t.fraction_restante = 0.0
        t.date_sortie = dates[j]
        t.seances = j - i_entree
        t.motif_final = "duree"
        return t

    seuils = [(0.20, 1 / 3), (0.35, 1 / 3)]
    stop = STOP_INITIAL
    reste = 1.0
    palier = 0
    sommet = prix_entree

    for i in range(i_entree + 1, min(i_entree + duree_max + 1, n)):
        c = closes[i]
        if not c:
            continue
        if c > sommet:
            sommet = c
        var = c / prix_entree - 1

        # 1. Stop (touche en premier : on suppose le pire dans la seance)
        if var <= stop:
            if reste > 0:
                t.sorties.append(SortiePartielle(reste, reste, dates[i], c, 0.0))
                reste = 0.0
            t.motif_final = "stop"
            t.date_sortie = dates[i]
            t.seances = i - i_entree
            break

        # 2. Paliers de vente
        if mode == "paliers" and palier < len(seuils) and var >= seuils[palier][0]:
            _, frac = seuils[palier]
            v = min(frac, reste)
            if v > 0:
                t.sorties.append(SortiePartielle(seuils[palier][0], v, dates[i],
                                                 c, var))
                reste -= v
                # Apres le 1er palier : stop au break-even
                if palier == 0:
                    stop = max(stop, 0.0)
                # Apres le 2e : stop suiveur a -10 % sous le sommet
                elif palier == 1:
                    stop = max(stop, sommet / prix_entree - 1 - 0.10)
            palier += 1
            if reste <= 1e-9:
                t.motif_final = "dernier palier atteint"
                t.date_sortie = dates[i]
                t.seances = i - i_entree
                break

        elif mode == "suiveur":
            if var >= 0.20 and stop < 0:
                stop = max(stop, 0.0)
            if var >= 0.35:
                stop = max(stop, sommet / prix_entree - 1 - 0.10)

        # 3. Cloture a +50 % en mode paliers
        if mode == "paliers" and var >= 0.50 and reste > 0:
            t.sorties.append(SortiePartielle(0.50, reste, dates[i], c, var))
            reste = 0.0
            t.motif_final = "+50 % atteint"
            t.date_sortie = dates[i]
            t.seances = i - i_entree
            break
    else:
        j = min(i_entree + duree_max, n - 1)
        if reste > 0:
            t.sorties.append(SortiePartielle(reste, reste, dates[j], closes[j], 0.0))
            reste = 0.0
        t.motif_final = "duree"
        t.date_sortie = dates[j]
        t.seances = j - i_entree

    t.fraction_restante = reste
    return t


def comparer_modes(series: dict, signaux: list[tuple[str, int]],
                   duree_max: int = 120, historique_fond: dict = None) -> dict:
    """Compare les modes de sortie sur un MEME ensemble de signaux d'achat.

    `signaux` : liste de (code, index) — les points d'entree a tester.
    """
    modes = ("duree", "paliers", "stop", "suiveur")
    out: dict[str, list[TradePartiel]] = {m: [] for m in modes}

    for code, i in signaux:
        barres = series.get(code)
        if barres is None:
            continue
        for m in modes:
            t = simuler_paliers(barres, i, duree_max, m)
            if t is not None:
                t.code = code
                out[m].append(t)
    return out


def collecter_signaux(series: dict, achat) -> list[tuple[str, int]]:
    """Points d'entree d'une condition d'achat sur tout l'historique.

    `achat` : indicateurs precalcules {code: SerieIndicateurs} et un predicat
    a utiliser via evaluer_compilee.
    """
    signaux = []
    for code, s in series.items():
        for i, ind in enumerate(s.indicateurs):
            if ind and achat(ind):
                signaux.append((code, i))
    return signaux


def bilan(trades: list[TradePartiel]) -> dict:
    """Statistiques agregees d'un mode de sortie."""
    if not trades:
        return {"n": 0}
    rends = [t.rendement_net for t in trades]
    return {
        "n": len(trades),
        "rendement_moyen_pct": statistics.mean(rends) * 100,
        "rendement_median_pct": statistics.median(rends) * 100,
        "taux_reussite": sum(1 for r in rends if r > 0) / len(rends),
        "pire_pct": min(rends) * 100,
        "meilleur_pct": max(rends) * 100,
        "duree_mediane": statistics.median(t.seances for t in trades),
        "ecart_type_pct": (statistics.pstdev(rends) * 100 if len(rends) > 1 else 0.0),
    }
