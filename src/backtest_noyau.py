"""Backtest du NOYAU — achat et conservation, dividendes reinvestis.

POURQUOI UN MOTEUR SEPARE
-------------------------
Le juge du challenge simule des allers-retours courts (60 a 250 seances) et note
la plus-value. Ce n'est pas le noyau. Le noyau, c'est :
  - acheter des titres a rendement net >= 4 %, PER <= 14, payout <= 80 % ;
  - les GARDER des annees ;
  - encaisser les dividendes et les REINVESTIR (c'est le moteur du revenu) ;
  - sortir sur les FONDAMENTAUX (dividende coupe, rendement effondre), pas sur
    un signal de prix.

Mesurer ceci avec le juge du trading donnerait un chiffre qui ne veut rien dire.
D'ou ce module.

CE QU'IL MESURE
---------------
  - rendement TOTAL (plus-value + dividendes reinvestis) ;
  - revenu annuel effectivement encaisse ;
  - drawdown maximal ;
  - comparaison a un panier ALEATOIRE de meme taille, meme date, meme duree,
    dividendes reinvestis aussi (sinon la comparaison est truquee).

LIMITE ASSUMEE
--------------
La source fondamentale ne remonte pas avant 2021 : la fenetre est 2022-2026,
soit ~4 ans de marche HAUSSIER. Un noyau se juge idealement sur 10-20 ans et a
travers un krach. Ce module mesure ce qui est mesurable ; il ne pretend pas
trancher la question de fond.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

# Filtres du noyau (seuils valides par LEO)
# Filtres d'entrée du noyau : définis dans src/regles.py (catalogue unique).
# RENDEMENT_NET_MIN = 0,04 · PER_MAX = 14,0 · PAYOUT_MAX = 0,80 · IRVM = 0,12
from .regles import IRVM, PAYOUT_MAX, PER_MAX, RENDEMENT_NET_MIN  # noqa: E402


@dataclass
class Position:
    """Une ligne du noyau, suivie en nombre d'actions."""

    code: str
    date_entree: str
    cours_entree: float
    actions: float
    capital_initial: float
    dividendes_encaisses: float = 0.0
    actions_rachetees: float = 0.0
    reinvestissements: int = 0

    def valeur(self, cours: float) -> float:
        return self.actions * cours

    def rendement_total(self, cours: float) -> float:
        """Rendement total : valeur finale contre capital initial."""
        if not self.capital_initial:
            return 0.0
        return self.valeur(cours) / self.capital_initial - 1


@dataclass
class ResultatNoyau:
    date_debut: str = ""
    date_fin: str = ""
    capital_initial: float = 0.0
    valeur_finale: float = 0.0
    dividendes_totaux: float = 0.0
    rendement_total_pct: float = 0.0
    rendement_vs_prix_seul_pct: float = 0.0
    revenu_annuel_pct: float = 0.0
    drawdown_max_pct: float = 0.0
    nb_titres: int = 0
    nb_reinvestissements: int = 0
    positions: list[Position] = field(default_factory=list)
    detail_par_titre: dict = field(default_factory=dict)


def _index_dates(dates: list[str], cible: str) -> int | None:
    """Premier indice dont la date est >= cible (recherche dichotomique)."""
    lo, hi = 0, len(dates) - 1
    if not dates or dates[-1] < cible:
        return None
    if dates[0] >= cible:
        return 0
    while lo < hi:
        mid = (lo + hi) // 2
        if dates[mid] < cible:
            lo = mid + 1
        else:
            hi = mid
    return lo


def simuler_position(barres: list, dividendes: list[dict], date_entree: str,
                     date_sortie: str, capital: float) -> Position | None:
    """Achete, encaisse les dividendes, les reinvestit, jusqu'a date_sortie.

    Le reinvestissement se fait au cours de la seance de detachement : c'est ce
    que fait un investisseur qui place son dividende des qu'il le recoit.
    """
    dates = [str(getattr(b, "date", ""))[:10] for b in barres]
    closes = [float(getattr(b, "close", 0) or 0) for b in barres]
    i0 = _index_dates(dates, date_entree)
    if i0 is None:
        return None
    i1 = None
    for k in range(len(dates) - 1, -1, -1):
        if dates[k] <= date_sortie:
            i1 = k
            break
    if i1 is None or i1 <= i0:
        return None
    cours_entree = closes[i0]
    if not cours_entree:
        return None

    pos = Position(code="", date_entree=dates[i0], cours_entree=cours_entree,
                   actions=capital / cours_entree, capital_initial=capital)

    # Dividendes detaches pendant la detention, dans l'ordre
    for d in dividendes or []:
        dx = d.get("ex_date", "")
        if not (dates[i0] < dx <= dates[i1]):
            continue
        ic = _index_dates(dates, dx)
        if ic is None or ic > i1:
            continue
        cours_j = closes[ic]
        if not cours_j:
            continue
        net = pos.actions * d["montant"] * (1 - IRVM)
        pos.dividendes_encaisses += net
        nouvelles = net / cours_j
        pos.actions += nouvelles
        pos.actions_rachetees += nouvelles
        pos.reinvestissements += 1

    pos.date_sortie = dates[i1]      # type: ignore[attr-defined]
    return pos


def _drawdown_max(barres: list, i0: int, i1: int) -> float:
    """Pire baisse depuis un sommet entre deux indices."""
    pic = 0.0
    pire = 0.0
    for i in range(i0, i1 + 1):
        c = float(getattr(barres[i], "close", 0) or 0)
        if not c:
            continue
        if c > pic:
            pic = c
        if pic:
            dd = c / pic - 1
            if dd < pire:
                pire = dd
    return pire


def backtester_noyau(hist: dict, hf: dict, date_debut: str, date_fin: str,
                     capital: float = 1_000_000.0) -> ResultatNoyau:
    """Simule le noyau : selection a date_debut, conservation jusqu'a date_fin.

    Selection : titres dont les fondamentaux CONNUS a date_debut respectent les
    trois filtres. Aucun regard sur le futur (fondamentaux_a_la_date).
    """
    from src.fondamentaux_historiques import fondamentaux_a_la_date

    res = ResultatNoyau(date_debut=date_debut, date_fin=date_fin,
                        capital_initial=capital)

    # 1. Selection point-in-time
    retenus = []
    for code, barres in hist.items():
        t = hf.get(code)
        if t is None:
            continue
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        i0 = _index_dates(dates, date_debut)
        if i0 is None or i0 >= len(barres) - 30:
            continue
        cours = float(getattr(barres[i0], "close", 0) or 0)
        if not cours:
            continue
        f = fondamentaux_a_la_date(t, dates[i0], cours)
        ny, per, po = f.get("net_yield"), f.get("per"), f.get("payout")
        if ny is None or ny < RENDEMENT_NET_MIN:
            continue
        if per is not None and per > PER_MAX:
            continue
        if po is not None and po > PAYOUT_MAX:
            continue
        retenus.append((code, cours))

    if not retenus:
        return res

    # 2. Repartition egale et conservation avec reinvestissement
    part = capital / len(retenus)
    positions = []
    for code, _ in retenus:
        t = hf.get(code)
        p = simuler_position(hist[code], t.dividendes if t else [],
                             date_debut, date_fin, part)
        if p is None:
            continue
        p.code = code
        positions.append(p)

    if not positions:
        return res

    res.positions = positions
    res.nb_titres = len(positions)
    res.nb_reinvestissements = sum(p.reinvestissements for p in positions)
    res.dividendes_totaux = sum(p.dividendes_encaisses for p in positions)

    # 3. Valeur finale — on evalue chaque ligne au dernier cours disponible
    valeur_totale = 0.0
    valeur_sans_div = 0.0
    for p in positions:
        barres = hist[p.code]
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        i1 = None
        for k in range(len(dates) - 1, -1, -1):
            if dates[k] <= date_fin:
                i1 = k
                break
        if i1 is None:
            continue
        cours_fin = float(getattr(barres[i1], "close", 0) or 0)
        if not cours_fin:
            continue
        valeur_totale += p.valeur(cours_fin)
        # Ce que la ligne vaudrait SANS reinvestir les dividendes
        actions_init = p.capital_initial / p.cours_entree
        valeur_sans_div += actions_init * cours_fin + p.dividendes_encaisses
        res.detail_par_titre[p.code] = {
            "cours_entree": p.cours_entree,
            "cours_fin": cours_fin,
            "actions_finales": round(p.actions, 4),
            "dividendes": round(p.dividendes_encaisses, 2),
            "rendement_pct": round(p.rendement_total(cours_fin) * 100, 2),
        }

    res.valeur_finale = valeur_totale
    if capital:
        res.rendement_total_pct = (valeur_totale / capital - 1) * 100
        res.rendement_vs_prix_seul_pct = (valeur_sans_div / capital - 1) * 100

    # 4. Revenu annuel : dividendes / capital / duree
    try:
        a0, a1 = int(date_debut[:4]), int(date_fin[:4])
        annees = (a1 - a0) + (int(date_fin[5:7]) - int(date_debut[5:7])) / 12
        annees = max(annees, 0.5)
    except Exception:
        annees = 1.0
    res.revenu_annuel_pct = (res.dividendes_totaux / capital / annees) * 100

    # 5. Drawdown maximal du portefeuille (somme des lignes au fil du temps)
    res.drawdown_max_pct = _drawdown_portefeuille(hist, positions,
                                                  date_debut, date_fin) * 100
    return res


def _drawdown_portefeuille(hist: dict, positions: list[Position],
                           date_debut: str, date_fin: str) -> float:
    """Drawdown du portefeuille reconstitue (cours + actions detenues).

    ATTENTION — le piege qui a fausse la premiere mesure
    ---------------------------------------------------
    Sur la BRVM, beaucoup de valeurs ne cotent PAS tous les jours. Sommer
    `actions * cours` en ignorant les titres sans cote ce jour-la fait chuter la
    valeur du portefeuille artificiellement : on mesurait alors -73 % la ou
    l'indice du marche ne perdait que -2,3 %.

    Correction : on reporte la DERNIERE COTE CONNUE de chaque titre
    (forward-fill). Un titre sans transaction aujourd'hui vaut encore ce qu'il
    valait hier — c'est la realite comptable du portefeuille.
    """
    series = {}
    for p in positions:
        barres = hist[p.code]
        series[p.code] = {
            str(getattr(b, "date", ""))[:10]: float(getattr(b, "close", 0) or 0)
            for b in barres
        }
    if not series:
        return 0.0
    toutes = sorted({d for s in series.values() for d in s
                     if date_debut <= d <= date_fin})
    if len(toutes) < 30:
        return 0.0

    # Derniere cote connue par titre, mise a jour au fil du temps
    derniere: dict[str, float] = {}
    pic = 0.0
    pire = 0.0
    for d in toutes:
        v = 0.0
        for p in positions:
            c = series[p.code].get(d)
            if c:
                derniere[p.code] = c
            cours_connu = derniere.get(p.code)
            if cours_connu:
                v += p.actions * cours_connu
        if v > pic:
            pic = v
        if pic:
            dd = v / pic - 1
            if dd < pire:
                pire = dd
    return pire


def panier_aleatoire_noyau(hist: dict, hf: dict, nb_titres: int,
                           date_debut: str, date_fin: str,
                           capital: float, tirages: int = 100,
                           graine: int = 7) -> list[float]:
    """Rendements de paniers ALEATOIRES de meme taille, meme periode.

    Les paniers aleatoires encaissent AUSSI les dividendes et les reinvestissent :
    comparer le noyau a des paniers sans dividendes reviendrait a se donner
    raison d'avance.
    """
    from src.fondamentaux_historiques import fondamentaux_a_la_date

    rng = random.Random(graine)
    # Univers : titres disposant d'un historique couvrant la periode
    univers = []
    for code, barres in hist.items():
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        i0 = _index_dates(dates, date_debut)
        if i0 is None or i0 >= len(barres) - 30:
            continue
        if dates[-1] < date_fin and len(dates) < 200:
            continue
        univers.append(code)
    if len(univers) < nb_titres:
        return []

    part = capital / nb_titres
    resultats = []
    for _ in range(tirages):
        tir = rng.sample(univers, nb_titres)
        total = 0.0
        for code in tir:
            t = hf.get(code)
            p = simuler_position(hist[code],
                                 t.dividendes if t else [],
                                 date_debut, date_fin, part)
            if p is None:
                total += part
                continue
            dates = [str(getattr(b, "date", ""))[:10] for b in hist[code]]
            i1 = None
            for k in range(len(dates) - 1, -1, -1):
                if dates[k] <= date_fin:
                    i1 = k
                    break
            if i1 is None:
                total += part
                continue
            cf = float(getattr(hist[code][i1], "close", 0) or 0)
            total += p.valeur(cf) if cf else part
        resultats.append((total / capital - 1) * 100)
    return resultats
