"""Le JUGE du challenge : valide une hypothese par backtest sur donnees reelles.

PRINCIPE
--------
Un modele de langage ne valide rien. Il propose. C'est ce module qui tranche,
en simulant la regle sur l'historique BRVM verifie (544 points de controle
contre la source officielle) et en la comparant a une reference aleatoire.

TROIS GARDE-FOUS METHODOLOGIQUES
--------------------------------
1. BASELINE ALEATOIRE OBLIGATOIRE. Dans un marche qui monte, une regle gagne
   sans rien prouver. On tire 100 paniers aleatoires a la meme date, on garde
   le meme nombre de seances : une hypothese ne compte que si elle BAT ce
   tirage. Le marche BRVM a fait +145 % entre 2017 et 2026 : la reference
   n'est jamais zero.
2. IN / OUT-OF-SAMPLE. La periode est coupee en deux : la regle est jugee sur
   les deux moities separement. Un avantage qui n'existe que sur une moitie est
   de la chance, pas une decouverte.
3. NET DE FRAIS. Aller-retour = 2,8 % (1,4 % par sens, courtage reel).
   Aucun resultat brut n'est affiche.

Aucun resultat de ce module n'est communique aux modeles : ils proposent a
l'aveugle. C'est la condition pour que leur raisonnement soit honnete.
"""
from __future__ import annotations

import math
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from ..infrastructure.paths import RACINE, HISTORY_CACHE  # chemins centralisés (lot 0 du plan docs/architecture.md)
from ..collecte.history_io import charger_cache  # lecture centralisée (P6-04) + empreinte (P7-03)

sys.path.insert(0, str(RACINE))

from .challenge_schema import Hypothese, compiler, evaluer_compilee  # noqa: E402

# Frais aller-retour : dérivés du courtage réel dans src/regles.py.
from ..regles import FRAIS_ALLER_RETOUR  # noqa: E402
from ..taxation import IRVM_DIVIDEND_TAX  # noqa: E402  (C4 : plus de 0,88 en dur, 12/10)
SEANCES_MIN_INDICATEURS = 250   # historique requis avant la 1re decision
NB_TIRAGES_ALEATOIRES = 100


@dataclass
class Trade:
    code: str
    date_entree: str
    date_sortie: str
    prix_entree: float
    prix_sortie: float
    seances: int
    motif_sortie: str
    # Dividendes NETS encaisses pendant la detention (par action, IRVM deduite).
    # Sans ce champ, une strategie de dividende est jugee sur sa seule
    # plus-value : elle perd 5 a 7 points par an dans la comparaison, ce qui la
    # condamne par construction. Mesure sur la regle « rendement net >= 4 % » :
    # +15,24 % de plus-value seule contre +18,19 % pour le hasard — soit un
    # verdict « non concluante » qui ne dit rien de la strategie reelle.
    dividendes: float = 0.0

    @property
    def rendement_net(self) -> float:
        """Rendement net de frais, DIVIDENDES INCLUS (fraction).

        Le detenteur d'une action encaisse le dividende detache pendant sa
        periode de detention : l'ignorer reviendrait a mesurer une autre
        strategie que celle testee.
        """
        if not self.prix_entree:
            return 0.0
        brut = (self.prix_sortie + self.dividendes) / self.prix_entree
        return brut * (1 - FRAIS_ALLER_RETOUR) - 1


@dataclass
class ResultatHypothese:
    id: str
    nom: str
    valide: bool
    motifs: list[str] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    rendement_net_pct: float | None = None
    rendement_median_pct: float | None = None
    nb_trades: int = 0
    taux_reussite: float | None = None
    baseline_mediane_pct: float | None = None
    baseline_p95_pct: float | None = None
    avantage_vs_baseline_pts: float | None = None
    p_value: float | None = None
    in_sample_pct: float | None = None
    out_sample_pct: float | None = None
    verdict: str = ""

    def resume(self) -> str:
        if not self.valide:
            return (f"  {self.id} — {self.nom}\n"
                    f"    REJETEE (hors DSL) : " + " ; ".join(self.motifs))
        lignes = [
            f"  {self.id} — {self.nom}",
            f"    trades : {self.nb_trades}   rendement net moyen : "
            f"{self.rendement_net_pct:+.2f} %   median : {self.rendement_median_pct:+.2f} %",
            f"    reussite : {self.taux_reussite*100:.1f} %"
            if self.taux_reussite is not None else "",
            f"    baseline aleatoire : mediane {self.baseline_mediane_pct:+.2f} %  "
            f"95e pct {self.baseline_p95_pct:+.2f} %",
            f"    avantage vs baseline : {self.avantage_vs_baseline_pts:+.2f} pts   "
            f"p = {self.p_value:.4f}",
            f"    in-sample {self.in_sample_pct:+.2f} %   "
            f"out-of-sample {self.out_sample_pct:+.2f} %",
            f"    -> {self.verdict}",
        ]
        return "\n".join(l for l in lignes if l)


# ---------------------------------------------------------------------------
#  INDICATEURS
# ---------------------------------------------------------------------------

def _rendement(cl: list[float], i: int, n: int) -> float | None:
    if i < n or not cl[i - n]:
        return None
    return cl[i] / cl[i - n] - 1


def _mm(cl: list[float], i: int, n: int) -> float | None:
    if i < n:
        return None
    f = cl[i - n:i]
    return sum(f) / len(f) if f else None


def _vol(cl: list[float], i: int, n: int) -> float | None:
    if i < n + 1:
        return None
    rets = []
    for k in range(i - n + 1, i + 1):
        if cl[k - 1]:
            rets.append(cl[k] / cl[k - 1] - 1)
    if len(rets) < 5:
        return None
    return statistics.pstdev(rets) * math.sqrt(252)


def indicateurs(barres: list, i: int, fond: dict | None) -> dict:
    """Indicateurs a la seance i — n'utilise QUE les donnees <= i."""
    cl = [float(getattr(b, "close", 0) or 0) for b in barres]
    vol = [float(getattr(b, "volume", 0) or 0) for b in barres]
    if i >= len(cl) or not cl[i]:
        return {}
    out: dict = {"prix": cl[i]}

    for n in (5, 20, 60, 120, 250):
        r = _rendement(cl, i, n)
        if r is not None:
            out[f"r{n}"] = r

    v = _vol(cl, i, 60)
    if v is not None:
        out["vol60"] = v

    if i >= 250:
        haut = max(cl[i - 250:i + 1])
        if haut:
            out["dd250"] = cl[i] / haut - 1
    haut_total = max(cl[:i + 1])
    if haut_total:
        out["dd_atl"] = cl[i] / haut_total - 1

    fen = cl[max(0, i - 1260):i + 1]
    if len(fen) > 20:
        bas, haut = min(fen), max(fen)
        if haut > bas:
            out["pos5a"] = (cl[i] - bas) / (haut - bas)

    for n, cle in ((50, "prix_vs_mm50"), (200, "prix_vs_mm200")):
        m = _mm(cl, i, n)
        if m:
            out[cle] = cl[i] / m - 1

    if i >= 60:
        med_v = statistics.median([x for x in vol[i - 60:i] if x]) if any(vol[i - 60:i]) else 0
        if med_v:
            out["vol_ratio"] = (vol[i] or 0) / med_v - 1

    if fond:
        for k in ("per", "net_yield", "payout"):
            if fond.get(k) is not None:
                out[k] = float(fond[k])
    return out


# ---------------------------------------------------------------------------
#  BACKTEST D'UNE HYPOTHESE
# ---------------------------------------------------------------------------

def _dividendes_detaches(titre_fond, date_entree: str, date_sortie: str) -> float:
    """Somme des dividendes NETS detaches entre deux dates (par action).

    Un dividende est detache a sa date ex : celui qui detient l'action ce
    jour-la l'encaisse. On applique l'IRVM de 12 % (preleve a la source en
    Cote d'Ivoire) car c'est le montant REELLEMENT credite. Ignorer les
    dividendes reviendrait a juger une strategie de revenu sur sa seule
    plus-value — biais defavorable de 5 a 7 points par an.
    """
    if titre_fond is None or not getattr(titre_fond, "dividendes", None):
        return 0.0
    total = 0.0
    for d in titre_fond.dividendes:
        if date_entree < d["ex_date"] <= date_sortie:
            total += d["montant"] * (1 - IRVM_DIVIDEND_TAX)  # net d'IRVM (taxation.py)
    return total


def simuler(series: dict, h: Hypothese, date_debut: str = "",
            date_fin: str = "", historique_fond: dict | None = None) -> list[Trade]:
    """Simule la regle sur les indicateurs PRECALCULES. Une position par titre.

    `series` : {code: SerieIndicateurs} — voir src/challenge_indicateurs.py.
    L'usage d'indicateurs precalcules divise le temps de calcul par plus de
    100 ; ils garantissent aussi qu'aucune hypothese ne voit le futur, la
    propriete etant verifiee une fois pour toutes a la construction.

    `historique_fond` : {code: TitreFondamentaux}. Sert a crediter les
    dividendes detaches pendant la detention. Sans lui, le rendement mesure est
    celui d'un autre investisseur que celui qu'on teste.
    """
    trades: list[Trade] = []
    hf = historique_fond or {}

    # Compilation UNE fois : c'est ce qui rend le backtest rapide
    ach = compiler(h.achat)
    ven = compiler(h.vente) if h.vente else None

    for code, s in series.items():
        n = len(s.dates)
        if n < SEANCES_MIN_INDICATEURS + 10:
            continue
        tf = hf.get(code)
        en_position = False
        i_entree = 0
        prix_entree = 0.0

        for i in range(SEANCES_MIN_INDICATEURS, n - 1):
            d = s.dates[i]
            if date_debut and d < date_debut:
                continue
            if date_fin and d > date_fin:
                if en_position:
                    ps = s.closes[i]
                    if ps:
                        trades.append(Trade(
                            code=code, date_entree=s.dates[i_entree],
                            date_sortie=d, prix_entree=prix_entree,
                            prix_sortie=ps, seances=i - i_entree,
                            motif_sortie="fin de periode",
                            dividendes=_dividendes_detaches(
                                tf, s.dates[i_entree], d)))
                break

            ind = s.indicateurs[i]
            if not ind:
                continue

            if not en_position:
                if evaluer_compilee(ach, ind):
                    en_position = True
                    i_entree = i
                    prix_entree = ind["prix"]
            else:
                seances = i - i_entree
                motif = None
                if ven is not None and evaluer_compilee(ven, ind):
                    motif = "regle de vente"
                elif seances >= h.duree_max:
                    motif = f"duree ({seances} seances)"
                if motif and prix_entree:
                    trades.append(Trade(
                        code=code, date_entree=s.dates[i_entree],
                        date_sortie=d, prix_entree=prix_entree,
                        prix_sortie=ind["prix"], seances=seances,
                        motif_sortie=motif,
                        dividendes=_dividendes_detaches(
                            tf, s.dates[i_entree], d)))
                    en_position = False

        if en_position and prix_entree:
            j = n - 1
            ps = s.closes[j]
            if ps:
                trades.append(Trade(
                    code=code, date_entree=s.dates[i_entree],
                    date_sortie=s.dates[j], prix_entree=prix_entree,
                    prix_sortie=ps, seances=j - i_entree,
                    motif_sortie="fin de serie",
                    dividendes=_dividendes_detaches(
                        tf, s.dates[i_entree], s.dates[j])))
    return trades


def _rendement_moyen(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    return statistics.mean(t.rendement_net for t in trades) * 100


def baseline_aleatoire(series: dict, nb_trades: int, duree_mediane: int,
                       date_debut: str = "", date_fin: str = "",
                       tirages: int = NB_TIRAGES_ALEATOIRES,
                       graine: int = 12345,
                       historique_fond: dict | None = None) -> list[float]:
    """Rendements de paniers ALEATOIRES equivalents (meme nombre, meme duree).

    C'est la reference obligatoire : sans elle, un marche haussier ferait
    passer n'importe quelle regle pour gagnante. Le tirage se fait dans la
    MEME plage de dates et avec la MEME duree de detention que l'hypothese
    testee, sinon la comparaison n'a pas de sens.

    `historique_fond` : les paniers aleatoires encaissent EUX AUSSI les
    dividendes detaches pendant leur detention. Oublier de le faire
    avantagerait artificiellement l'hypothese testee — exactement le biais
    qu'on cherche a mesurer, mais dans l'autre sens.
    """
    rng = random.Random(graine)
    hf = historique_fond or {}
    codes = [c for c, s in series.items()
             if len(s.dates) >= SEANCES_MIN_INDICATEURS + 10]
    if not codes or nb_trades <= 0:
        return []

    # Index des bornes de dates par titre, calcule UNE fois
    bornes: dict[str, tuple[int, int] | None] = {}
    for c in codes:
        s = series[c]
        if date_debut or date_fin:
            deb = fin_ = None
            for k, d in enumerate(s.dates):
                if deb is None and (not date_debut or d >= date_debut):
                    deb = k
                if not date_fin or d <= date_fin:
                    fin_ = k
            if deb is None or fin_ is None or fin_ - deb < duree_mediane + 1:
                bornes[c] = None
            else:
                bornes[c] = (deb, fin_)
        else:
            bornes[c] = (0, len(s.dates) - 1)
    codes = [c for c in codes if bornes.get(c)]

    if not codes:
        return []

    resultats = []
    for _ in range(tirages):
        rendements = []
        for _ in range(nb_trades):
            code = rng.choice(codes)
            s = series[code]
            debut, fin_ = bornes[code]
            if fin_ - debut < duree_mediane + 1:
                continue
            i = rng.randint(debut, fin_ - duree_mediane - 1)
            pe, ps = s.closes[i], s.closes[i + duree_mediane]
            if pe:
                div = _dividendes_detaches(hf.get(code), s.dates[i],
                                           s.dates[i + duree_mediane])
                rendements.append(((ps + div) / pe) * (1 - FRAIS_ALLER_RETOUR) - 1)
        if rendements:
            resultats.append(statistics.mean(rendements) * 100)
    return resultats


def evaluer_hypothese(series: dict, h: Hypothese,
                      date_coupure: str | None = None,
                      historique_fond: dict | None = None) -> ResultatHypothese:
    """Juge complet d'une hypothese : avantage, significativite, robustesse.

    `historique_fond` est transmis a la simulation ET a la baseline : les
    dividendes sont credites des DEUX cotes, sinon la comparaison mesure autre
    chose que l'avantage reel de la regle.
    """
    r = ResultatHypothese(id=h.id, nom=h.nom, valide=h.valide, motifs=h.motifs)
    if not h.valide:
        r.verdict = "REJETEE — hypothese non conforme au langage autorise"
        return r

    trades = simuler(series, h, historique_fond=historique_fond)
    r.trades = trades
    r.nb_trades = len(trades)
    if not trades:
        r.verdict = ("AUCUN SIGNAL — la regle ne s'est jamais declenchee sur "
                     "l'historique (0 trade)")
        return r

    r.rendement_net_pct = _rendement_moyen(trades)
    r.rendement_median_pct = statistics.median(t.rendement_net for t in trades) * 100
    r.taux_reussite = sum(1 for t in trades if t.rendement_net > 0) / len(trades)

    duree_med = int(statistics.median(t.seances for t in trades)) or 20

    dates = [t.date_entree for t in trades]
    base = baseline_aleatoire(series, len(trades), duree_med,
                              min(dates), max(dates),
                              historique_fond=historique_fond)
    if base:
        r.baseline_mediane_pct = statistics.median(base)
        r.baseline_p95_pct = sorted(base)[int(len(base) * 0.95)]
        r.avantage_vs_baseline_pts = r.rendement_net_pct - r.baseline_mediane_pct
        r.p_value = sum(1 for x in base if x >= r.rendement_net_pct) / len(base)

    if date_coupure:
        ins = [t for t in trades if t.date_entree < date_coupure]
        outs = [t for t in trades if t.date_entree >= date_coupure]
        if ins:
            r.in_sample_pct = _rendement_moyen(ins)
        if outs:
            r.out_sample_pct = _rendement_moyen(outs)

    r.verdict = _verdict(r)
    return r


def _verdict(r: ResultatHypothese) -> str:
    """Verdict motive, dans l'ordre de rigueur decroissante."""
    if r.nb_trades < 10:
        return (f"PREUVE INSUFFISANTE — {r.nb_trades} trade(s) seulement : "
                "trop peu pour conclure quoi que ce soit")
    if r.p_value is not None and r.p_value > 0.05:
        return (f"NON CONCLUANTE — {r.p_value*100:.0f} % des paniers aleatoires "
                "font aussi bien ou mieux (hasard non ecarte)")
    if r.avantage_vs_baseline_pts is None:
        return "NON EVALUABLE — baseline indisponible"
    if r.avantage_vs_baseline_pts <= 0:
        return "REJETEE — ne bat pas le tirage aleatoire"

    # Robustesse : les deux moities doivent survivre
    if r.in_sample_pct is not None and r.out_sample_pct is not None:
        if r.in_sample_pct <= 0 or r.out_sample_pct <= 0:
            return ("REJETEE — avantage present sur une seule moitie de la "
                    "periode (probable surajustement)")
        if abs(r.in_sample_pct - r.out_sample_pct) > 40:
            return ("FRAGILE — ecart de plus de 40 pts entre les deux moities")

    return (f"RETENUE SOUS CONDITION — bat le hasard de "
            f"{r.avantage_vs_baseline_pts:+.1f} pts (p={r.p_value:.3f}) sur "
            f"{r.nb_trades} trades, et tient sur les deux moities")


def charger_fondamentaux() -> dict:
    """PER / rendement net / payout par titre, depuis le dataset du challenge.

    ATTENTION AUX NOMS DE CHAMPS : le dataset (`challenge_dataset.json`) utilise
    `rendement_net_pct` et `payout_pct`, alors que le langage d'hypotheses
    expose `net_yield` et `payout` (en FRACTION). Sans cette conversion, toute
    regle fondamentale recoit des indicateurs absents : elle produit 0 trade et
    est declaree « aucun signal » a tort — 7 hypotheses sur 20 ont ete perdues
    ainsi lors du premier passage.
    """
    import json

    ds = RACINE / "data" / "challenge_dataset.json"
    if ds.exists():
        try:
            d = json.loads(ds.read_text(encoding="utf-8"))
            out = {}
            for t in d.get("titres", []):
                c = t.get("code")
                if not c:
                    continue
                per = t.get("per")
                rn = t.get("rendement_net_pct")
                po = t.get("payout_pct")
                out[c] = {
                    # Tous ramenes dans l'unite du langage (fractions)
                    "per": float(per) if per is not None else None,
                    "net_yield": (float(rn) / 100.0) if rn is not None else None,
                    "payout": (float(po) / 100.0) if po is not None else None,
                }
            if out:
                return out
        except Exception:
            pass

    # Repli : ancien cache, si ses cles correspondent deja au langage
    p = RACINE / "data" / "fundamentals_cache.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d:
                return d
        except Exception:
            pass
    return {}


def charger_historique(chemin: Path | None = None) -> dict:
    p = chemin or HISTORY_CACHE  # défini dans paths.py (P6-01)
    if not p.exists():
        raise SystemExit(
            f"Historique propre introuvable : {p}\n"
            "Lancer : python scripts/preparer_historique_propre.py")
    return charger_cache(p)  # lecture centralisée (P6-04) + empreinte SHA-256 (P7-03)
