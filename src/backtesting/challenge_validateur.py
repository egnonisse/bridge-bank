"""Le JUGE du challenge : valide une hypothese par backtest sur donnees reelles.

PRINCIPE
--------
Un modele de langage ne valide rien. Il propose. C'est ce module qui tranche,
en simulant la regle sur l'historique BRVM verifie (544 points de controle
contre la source officielle) et en la comparant a une reference aleatoire.

GARDE-FOUS METHODOLOGIQUES (durcis le 13/10/2026 — audit A3-03/04/05/09/10)
---------------------------------------------------------------------------
1. BASELINE ALEATOIRE OBLIGATOIRE. Dans un marche qui monte, une regle gagne
   sans rien prouver. On tire NB_TIRAGES_ALEATOIRES paniers (>= 1000) dans la
   MEME fenetre que la regle (seances >= SEANCES_MIN_INDICATEURS), avec les
   MEMES durees de detention (reechantillonnees) et les MEMES dates d'entree
   (bootstrap conditionnel — sans cela, la correlation entre trades d'un meme
   jour rend les p-values trop faibles). Une regle ne compte que si elle BAT
   ce tirage.
2. IN / OUT-OF-SAMPLE PAR L'AVANTAGE. La periode est coupee en deux
   (DATE_COUPURE_DEFAUT, fixe) ; on exige un AVANTAGE vs baseline positif sur
   CHAQUE moitie (baseline recalculee par moitie) — un rendement absolu positif
   ne prouve rien dans un marche a +145 %.
3. NET DE FRAIS. Aller-retour = 2,8 % (1,4 % par sens, courtage reel).
   Aucun resultat brut n'est affiche.
4. EXECUTION A J+1. Un signal lu au close de la seance i est execute au close
   de la seance i+1, entrees ET sorties (on ne trade pas le close qu'on vient
   de lire sur une place au fixing) — A3-10.
5. p-VALUE HONNETE. p = (1 + #paniers >= regle) / (1 + N) : jamais 0,0000.
   `seuil_p` est ajuste au nombre d'hypotheses testees — les orchestrateurs
   passent 0,05 / nb_hypotheses (Bonferroni), cf. A3-05.
6. DIVIDENDES DES DEUX COTES. `historique_fond` est requis pour que la regle
   ET la baseline encaissent les dividendes ; absent, un message le signale.

Aucun resultat de ce module n'est communique aux modeles : ils proposent a
l'aveugle. C'est la condition pour que leur raisonnement soit honnete.
"""
from __future__ import annotations

import bisect
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
NB_TIRAGES_ALEATOIRES = 1000    # A3-05 : granularite p-value = 1/(N+1), jamais 0,0000
DATE_COUPURE_DEFAUT = "2022-01-01"  # A3-03 : coupure UNIQUE (pas choisie apres les resultats)


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
    avantage_in_pts: float | None = None    # A3-03 : avantage vs baseline, moitie in-sample
    avantage_out_pts: float | None = None   # A3-03 : avantage vs baseline, moitie out-of-sample
    seuil_p: float = 0.05                   # A3-05 : seuil de l'appelant (ajuste au nb d'hypotheses)
    verdict: str = ""

    def resume(self) -> str:
        """Formatage ROBUSTE (A3-09) : aucune valeur n'est garantie présente
        (0 trade, baseline indisponible, pas de coupure) — jamais de plantage."""
        if not self.valide:
            return (f"  {self.id} — {self.nom}\n"
                    f"    REJETEE (hors DSL) : " + " ; ".join(self.motifs))

        def nb(x: float | None, fmt: str = "+.2f") -> str:
            return format(x, fmt) if x is not None else "n/d"

        lignes = [
            f"  {self.id} — {self.nom}",
            f"    trades : {self.nb_trades}   rendement net moyen : "
            f"{nb(self.rendement_net_pct)} %   median : {nb(self.rendement_median_pct)} %",
            (f"    reussite : {self.taux_reussite*100:.1f} %"
             if self.taux_reussite is not None else ""),
            f"    baseline aleatoire : mediane {nb(self.baseline_mediane_pct)} %  "
            f"95e pct {nb(self.baseline_p95_pct)} %",
            (f"    avantage vs baseline : {nb(self.avantage_vs_baseline_pts)} pts   "
             f"p = {self.p_value:.4f}   (seuil {self.seuil_p:.4f})"
             if self.p_value is not None
             else f"    avantage vs baseline : {nb(self.avantage_vs_baseline_pts)} pts   p = n/d"),
            f"    in-sample {nb(self.in_sample_pct)} %   "
            f"out-of-sample {nb(self.out_sample_pct)} %",
            f"    avantage par moitie (in / out) : {nb(self.avantage_in_pts)} / "
            f"{nb(self.avantage_out_pts)} pts",
            f"    -> {self.verdict}",
        ]
        return "\n".join(l for l in lignes if l)


# ---------------------------------------------------------------------------
#  (bloc « indicateurs » local SUPPRIME le 13/10/2026 — audit A3-13/D5 :
#   il dupliquait `challenge_indicateurs.precalculer`, n'etait appele par
#   personne (aucun import externe, aucun usage interne) et maintenait une
#   seconde implementation a garder coherente. Les series arrivent
#   PRECALCULEES via SerieIndicateurs.)
# ---------------------------------------------------------------------------


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

    EXECUTION A J+1 (A3-10) : le signal est LU au close de la seance `i` ;
    l'ordre est execute au close de la seance `i+1` — entrees ET sorties. Sur
    une place au fixing, on ne peut pas trader le close qu'on vient de lire :
    sans ce decalage, une regle de reaction courte mesure un avantage que la
    baseline (tiree au hasard) n'a pas.

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
                    # A3-10 : execution au close de la seance SUIVANTE
                    j = i + 1
                    pj = s.closes[j] if j < n else 0
                    if pj:
                        en_position = True
                        i_entree = j
                        prix_entree = pj
            else:
                seances = i - i_entree
                motif = None
                if ven is not None and evaluer_compilee(ven, ind):
                    motif = "regle de vente"
                elif seances >= h.duree_max:
                    motif = f"duree ({seances} seances)"
                if motif:
                    # A3-10 : sortie executee au close de la seance SUIVANTE
                    j = i + 1
                    pj = s.closes[j] if j < n else 0
                    if pj:
                        trades.append(Trade(
                            code=code, date_entree=s.dates[i_entree],
                            date_sortie=s.dates[j], prix_entree=prix_entree,
                            prix_sortie=pj, seances=j - i_entree,
                            motif_sortie=motif,
                            dividendes=_dividendes_detaches(
                                tf, s.dates[i_entree], s.dates[j])))
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
                       historique_fond: dict | None = None,
                       durees: list[int] | None = None,
                       dates_reference: list[str] | None = None) -> list[float]:
    """Rendements de paniers ALEATOIRES equivalents (meme nombre, memes conditions).

    C'est la reference obligatoire : sans elle, un marche haussier ferait
    passer n'importe quelle regle pour gagnante. Le tirage reproduit les
    conditions REELLES de la regle (A3-05) :
      - fenetre bornee a SEANCES_MIN_INDICATEURS (la ou la regle a le DROIT
        de trader — l'ancien tirage pouvait commencer a la seance 0) ;
      - durees de detention REECHANTILLONNEES sur celles des trades reels
        (`durees`) au lieu d'une duree mediane figee ;
      - dates de depart tirees DANS les dates d'entree de la regle
        (`dates_reference`, bootstrap conditionnel) : la regle entre souvent
        sur plusieurs titres le meme jour (regime commun) ; des dates
        independantes sous-estiment la variance et donnent des p-values trop
        faibles.

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

    def _duree() -> int:
        return rng.choice(durees) if durees else duree_mediane

    duree_min = min(durees) if durees else duree_mediane

    # Index des bornes de dates par titre, calcule UNE fois
    bornes: dict[str, tuple[int, int] | None] = {}
    for c in codes:
        s = series[c]
        deb = fin_ = None
        for k, d in enumerate(s.dates):
            if deb is None and (not date_debut or d >= date_debut):
                deb = k
            if not date_fin or d <= date_fin:
                fin_ = k
        if deb is None or fin_ is None:
            bornes[c] = None
            continue
        deb = max(deb, SEANCES_MIN_INDICATEURS)  # A3-05 : jamais avant l'eligible
        if fin_ - deb < duree_min + 1:
            bornes[c] = None
        else:
            bornes[c] = (deb, fin_)
    codes = [c for c in codes if bornes.get(c)]

    if not codes:
        return []

    resultats = []
    for _ in range(tirages):
        rendements = []
        for _ in range(nb_trades):
            duree = _duree()
            if dates_reference:
                # A3-05 : bootstrap conditionnel aux dates de la regle
                code = s = None
                k = 0
                debut = fin_ = 0
                for _essai in range(5):
                    code = rng.choice(codes)
                    s = series[code]
                    k = bisect.bisect_left(s.dates, rng.choice(dates_reference))
                    debut, fin_ = bornes[code]
                    if debut <= k and k + duree <= fin_:
                        break
                    code = None
                if code is None:
                    continue
            else:
                code = rng.choice(codes)
                s = series[code]
                debut, fin_ = bornes[code]
                if fin_ - debut < duree + 1:
                    continue
                k = rng.randint(debut, fin_ - duree)
            pe, ps = s.closes[k], s.closes[k + duree]
            if pe:
                div = _dividendes_detaches(hf.get(code), s.dates[k],
                                           s.dates[k + duree])
                rendements.append(((ps + div) / pe) * (1 - FRAIS_ALLER_RETOUR) - 1)
        if rendements:
            resultats.append(statistics.mean(rendements) * 100)
    return resultats


def evaluer_hypothese(series: dict, h: Hypothese,
                      date_coupure: str | None = DATE_COUPURE_DEFAUT,
                      historique_fond: dict | None = None,
                      seuil_p: float = 0.05) -> ResultatHypothese:
    """Juge complet d'une hypothese : avantage, significativite, robustesse.

    `historique_fond` est transmis a la simulation ET a la baseline : les
    dividendes sont credites des DEUX cotes, sinon la comparaison mesure autre
    chose que l'avantage reel de la regle. Son absence est SIGNALEE (A3-04).

    `date_coupure` : defaut DATE_COUPURE_DEFAUT — une coupure FIGEE, jamais
    choisie apres avoir vu les resultats (A3-03). Une chaine vide desactive la
    coupure (usage explicite et rare).

    `seuil_p` (A3-05) : les orchestrateurs passent 0,05 / nb_hypotheses
    (Bonferroni). Le seuil non ajuste de 0,05 laisse attendre ≈ 1 faux positif
    sur 20 hypotheses — le seuil est donc declare par l'appelant.
    """
    r = ResultatHypothese(id=h.id, nom=h.nom, valide=h.valide, motifs=h.motifs,
                          seuil_p=seuil_p)
    if not h.valide:
        r.verdict = "REJETEE — hypothese non conforme au langage autorise"
        return r

    if historique_fond is None:
        print(f"[juge] ATTENTION {h.id} : historique_fond absent — dividendes NON "
              "credites (regle ET baseline) : verdict potentiellement biaise (A3-04).")

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
    durees = [t.seances for t in trades]
    dates_ref = [t.date_entree for t in trades]

    base = baseline_aleatoire(series, len(trades), duree_med,
                              min(dates_ref), max(dates_ref),
                              historique_fond=historique_fond,
                              durees=durees, dates_reference=dates_ref)
    if base:
        r.baseline_mediane_pct = statistics.median(base)
        r.baseline_p95_pct = sorted(base)[int(len(base) * 0.95)]
        r.avantage_vs_baseline_pts = r.rendement_net_pct - r.baseline_mediane_pct
        # A3-05 : (1 + #>=) / (1 + N) — jamais 0,0000, granularite honnete.
        r.p_value = (1 + sum(1 for x in base if x >= r.rendement_net_pct)) / (1 + len(base))

    if date_coupure:
        ins = [t for t in trades if t.date_entree < date_coupure]
        outs = [t for t in trades if t.date_entree >= date_coupure]
        if ins:
            r.in_sample_pct = _rendement_moyen(ins)
        if outs:
            r.out_sample_pct = _rendement_moyen(outs)
        # A3-03 : l'AVANTAGE vs baseline, recalcule SEPAREMENT sur chaque moitie
        if ins and outs:
            bi = baseline_aleatoire(series, len(ins), duree_med,
                                    min(t.date_entree for t in ins),
                                    max(t.date_entree for t in ins),
                                    historique_fond=historique_fond,
                                    durees=[t.seances for t in ins],
                                    dates_reference=[t.date_entree for t in ins])
            bo = baseline_aleatoire(series, len(outs), duree_med,
                                    min(t.date_entree for t in outs),
                                    max(t.date_entree for t in outs),
                                    historique_fond=historique_fond,
                                    durees=[t.seances for t in outs],
                                    dates_reference=[t.date_entree for t in outs])
            if bi and r.in_sample_pct is not None:
                r.avantage_in_pts = r.in_sample_pct - statistics.median(bi)
            if bo and r.out_sample_pct is not None:
                r.avantage_out_pts = r.out_sample_pct - statistics.median(bo)

    r.verdict = _verdict(r)
    return r


def _verdict(r: ResultatHypothese) -> str:
    """Verdict motive, dans l'ordre de rigueur decroissante."""
    if r.nb_trades < 10:
        return (f"PREUVE INSUFFISANTE — {r.nb_trades} trade(s) seulement : "
                "trop peu pour conclure quoi que ce soit")
    if r.p_value is not None and r.p_value > r.seuil_p:
        return (f"NON CONCLUANTE — {r.p_value*100:.1f} % des paniers aleatoires "
                f"font aussi bien ou mieux (seuil {r.seuil_p:.4f} ; hasard non ecarte)")
    if r.avantage_vs_baseline_pts is None:
        return "NON EVALUABLE — baseline indisponible"
    if r.avantage_vs_baseline_pts <= 0:
        return "REJETEE — ne bat pas le tirage aleatoire"

    # Robustesse (A3-03) : l'AVANTAGE vs baseline (pas le rendement absolu)
    # doit tenir sur les deux moities.
    if r.avantage_in_pts is not None and r.avantage_out_pts is not None:
        if r.avantage_in_pts <= 0 or r.avantage_out_pts <= 0:
            return (f"REJETEE — avantage vs baseline absent sur une moitie "
                    f"(in {r.avantage_in_pts:+.1f} / out {r.avantage_out_pts:+.1f} pts : "
                    "probable surajustement)")
        if abs(r.avantage_in_pts - r.avantage_out_pts) > 40:
            return ("FRAGILE — ecart de plus de 40 pts d'avantage entre les deux moities")
    elif r.in_sample_pct is not None and r.out_sample_pct is not None:
        # Repli (baseline par moitie indisponible) : le test absolu d'origine.
        if r.in_sample_pct <= 0 or r.out_sample_pct <= 0:
            return "REJETEE — rendement negatif sur une moitie (avantage par moitie indisponible)"

    return (f"RETENUE SOUS CONDITION — bat le hasard de "
            f"{r.avantage_vs_baseline_pts:+.1f} pts (p={r.p_value:.3f}) sur "
            f"{r.nb_trades} trades, et l'avantage tient sur les deux moities")


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
        except Exception as exc:
            print(f"[juge] charger_fondamentaux : dataset illisible ({exc}) — "
                  "repli sur l'ancien cache")

    # Repli : ancien cache, si ses cles correspondent deja au langage
    p = RACINE / "data" / "fundamentals_cache.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d:
                return d
        except Exception as exc:
            print(f"[juge] charger_fondamentaux : cache de repli illisible ({exc})")
    return {}


def charger_historique(chemin: Path | None = None) -> dict:
    p = chemin or HISTORY_CACHE  # défini dans paths.py (P6-01)
    if not p.exists():
        raise SystemExit(
            f"Historique propre introuvable : {p}\n"
            "Lancer : python scripts/preparer_historique_propre.py")
    return charger_cache(p)  # lecture centralisée (P6-04) + empreinte SHA-256 (P7-03)
