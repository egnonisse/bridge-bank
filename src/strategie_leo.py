"""Moteur de simulation de la STRATEGIE REELLE de LEO.

POURQUOI CE MOTEUR EXISTE
-------------------------
Le juge du challenge simule des allers-retours courts et le backtest du noyau
simule un achat unique conserve. Aucun des deux ne reproduit ce que LEO fait
reellement, tel qu'il ressort de son releve Bridge Bank (01/01/2025 -> 08/10/2026) :

  1. ENTREE PROGRESSIVE — il n'achete jamais tout d'un coup. PALM CI : 8 achats
     etales sur 30 jours ; SGB CI : 3 achats sur un mois ; SONATEL : 2 achats
     le meme jour puis conservation.
  2. RENFORCEMENT SUR FAIBLESSE — il ajoute quand le cours baisse. PALM :
     8 908 -> 8 518 -> 8 112 -> 7 859 F, soit des paliers de 4 a 5 %.
  3. PALIERS DE SORTIE — il vend par fractions a des gains croissants. SONATEL :
     3 actions a +15,5 %, 2 a +18,6 %, 1 a +28,3 %. NB : les seuils REELS sont
     plus BAS que les +20/+35/+50 documentes.
  4. REBALANCEMENT — il vend un gagnant pour financer un retardataire. Les
     ventes SONATEL du 02/09, 08/09 et 21/09 sont suivies d'achats PALM, SMB,
     SOLIBRA les jours suivants.
  5. RESERVE DE CASH — il conserve une poche de liquidites (46 % au 08/10/2026,
     apres un depot de 700 000 F).

REGLE DE RIGUEUR
----------------
Les parametres par defaut viennent des ACTES OBSERVES, jamais d'une optimisation
sur le passe. Optimiser les parametres pour que la strategie gagne serait de la
triche : on fabriquerait une methode qui marche sur l'historique et echoue en
reel. Le challenge multi-modeles (phase 4) fera varier ces parametres, mais le
code jugera — et le point de depart reste ce que LEO fait.

Les valeurs observees sont documentees avec leur INCERTITUDE : les achats de
LEO sont opportunistes (SONATEL en 2 lots le meme jour, PALM en 8 lots sur un
mois), donc un parametre unique ne peut pas tout capturer. C'est assume.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

# Frais BSTrade : courtage 0,8 % + TVA 18 % sur le courtage + BRVM 0,456 %
# => ~1,4 % par sens, soit 2,8 % aller-retour (minimum 1 000 F par ordre).
# Frais Bridge Bank : définis dans src/regles.py (dérivés du courtage réel,
# jamais recopiés — `FRAIS_PAR_SENS` et `FRAIS_ALLER_RETOUR` ont des SENS différents).
from .regles import FRAIS_MINIMUM, FRAIS_PAR_SENS  # noqa: E402


@dataclass
class Parametres:
    """Les 5 composants, avec les valeurs observees dans le releve.

    Chaque champ porte la valeur par defaut (= comportement reel observe) et
    peut etre remplace pour tester une variante.
    """

    # 1. Entree progressive
    nb_tranches: int = 3              # PALM 8, SGB 3, SOLIBRA 2, SONATEL 2 -> median 3
    espacement_jours: int = 12        # PALM ~4 j, SGB ~14 j -> compromis

    # 2. Renforcement sur faiblesse
    renforcement_actif: bool = True
    seuil_renforcement: float = 0.045  # PALM : 4,4 % / 4,8 % / 3,1 % -> ~4,5 %
    max_tranches_renforcement: int = 4

    # 3. Paliers de sortie (SEUILS REELS, plus bas que les documentes)
    paliers_actifs: bool = True
    seuils_vente: tuple = ((0.15, 1 / 3), (0.20, 1 / 3))
    duree_max_seances: int = 250

    # 4. Rebalancement
    rebalancement_actif: bool = False   # desactive par defaut : voir note ci-dessous
    seuil_rebalancement: float = 0.20   # gain au-dela duquel on arbitre

    # 5. Reserve de cash (fraction du capital jamais investie)
    cash_cible: float = 0.15

    # Budget par ligne. `budget_max_ligne` est le PLAFOND de capital engage sur
    # un titre, toutes tranches et renforts confondus.
    #
    # POURQUOI CE PLAFOND EXISTE
    # --------------------------
    # Sans lui, la variante « renforcement » achete davantage que la variante
    # passive (14 achats contre 5 dans la premiere mesure) : elle gagne plus,
    # mais seulement parce qu'elle est PLUS EXPOSEE au marche. Compare un
    # portefeuille a 50 % investi et un autre a 100 % ne dit rien sur la
    # qualite des habitudes — cela mesure la part investie.
    # Avec le plafond, toutes les variantes engagent le meme capital par titre :
    # seule la REPARTITION DANS LE TEMPS change, ce qui est exactement la
    # question posee.
    budget_ligne: float = 100_000.0     # montant d'UNE decision d'achat
    budget_max_ligne: float = 300_000.0  # plafond de capital engage par titre


@dataclass
class Position:
    code: str
    actions: float = 0.0
    cout_total: float = 0.0            # frais inclus
    tranches_achetees: int = 0
    date_dernier_achat: str = ""
    cours_dernier_achat: float = 0.0
    dividendes: float = 0.0
    ventes: list = field(default_factory=list)   # (date, actions, cours, fraction)

    @property
    def cmp(self) -> float:
        return self.cout_total / self.actions if self.actions else 0.0

    def valeur(self, cours: float) -> float:
        return self.actions * cours


@dataclass
class ResultatStrategie:
    nom: str = ""
    capital_initial: float = 0.0
    valeur_finale: float = 0.0
    cash_final: float = 0.0
    dividendes: float = 0.0
    frais_payes: float = 0.0
    nb_achats: int = 0
    nb_ventes: int = 0
    drawdown_max_pct: float = 0.0
    rendement_pct: float = 0.0
    revenu_annuel_pct: float = 0.0
    nb_lignes: int = 0
    # Exposition : part moyenne du capital investie en titres. Indispensable
    # pour comparer des variantes entre elles : une regle qui vend tot est
    # MOINS exposee, donc gagne moins dans un marche haussier. Sans ce chiffre,
    # on attribuerait a la regle ce qui n'est qu'un effet d'exposition.
    exposition_moyenne_pct: float = 0.0
    capital_deploye: float = 0.0
    detail: dict = field(default_factory=dict)


def _cout_ordre(montant: float) -> float:
    """Frais d'un ordre, avec le minimum de 1 000 F applique par sens."""
    return max(montant * FRAIS_PAR_SENS, FRAIS_MINIMUM)


class MoteurLeo:
    """Simule la strategie reelle sur un historique de barres.

    Usage :
        m = MoteurLeo(hist, hf, params, capital=1_000_000)
        res = m.executer(date_debut, date_fin,
                         univers=["SGB","SOLIBRA","SONATEL","PALM","SMB"])
    """

    def __init__(self, hist: dict, hf: dict, params: Parametres | None = None,
                 capital: float = 1_000_000.0):
        self.hist = hist
        self.hf = hf
        self.p = params or Parametres()
        self.capital = capital
        self.cash = capital
        self.positions: dict[str, Position] = {}
        self.frais_payes = 0.0
        self.nb_achats = 0
        self.nb_ventes = 0
        self.journal: list[tuple] = []

    # ------------------------------------------------------------------
    #  Outils
    # ------------------------------------------------------------------
    def _series(self, code: str, date_debut: str, date_fin: str):
        """Dates et cours d'un titre sur la fenetre."""
        barres = self.hist.get(code)
        if not barres:
            return [], []
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        closes = [float(getattr(b, "close", 0) or 0) for b in barres]
        idx = [(d, c) for d, c in zip(dates, closes)
               if date_debut <= d <= date_fin and c > 0]
        return [d for d, _ in idx], [c for _, c in idx]

    def _dividendes_periode(self, code: str, d1: str, d2: str) -> float:
        """Dividendes nets (IRVM 12 %) detaches entre deux dates, par action."""
        t = self.hf.get(code)
        if t is None or not getattr(t, "dividendes", None):
            return 0.0
        return sum(d["montant"] * 0.88 for d in t.dividendes
                   if d1 < d["ex_date"] <= d2)

    def _acheter(self, code: str, date: str, cours: float, montant: float,
                 motif: str) -> bool:
        """Achete pour `montant` F (frais inclus). Retourne True si execute."""
        montant = min(montant, self.cash)
        if montant < FRAIS_MINIMUM * 2 or cours <= 0:
            return False
        frais = _cout_ordre(montant)
        net = montant - frais
        if net <= 0:
            return False
        actions = net / cours
        pos = self.positions.setdefault(code, Position(code=code))
        pos.actions += actions
        pos.cout_total += montant          # frais inclus dans le CMP
        pos.tranches_achetees += 1
        pos.date_dernier_achat = date
        pos.cours_dernier_achat = cours
        self.cash -= montant
        self.frais_payes += frais
        self.nb_achats += 1
        self.journal.append((date, "ACHAT", code, round(montant), motif))
        return True

    def _vendre(self, code: str, date: str, cours: float, actions: float,
                motif: str, marqueur: float = 0.0) -> float:
        """Vend des actions. Retourne le produit net encaisse.

        `marqueur` : le seuil de palier declencheur (0.15, 0.20...). Il est
        stocke dans la ligne de vente pour empecher de rejouer le MEME palier a
        chaque seance. Sans ce marqueur, la regle vend tous les jours des que le
        seuil est franchi (mesure : 1 013 ventes au lieu de 4).
        """
        pos = self.positions.get(code)
        if pos is None or actions <= 0 or cours <= 0:
            return 0.0
        actions = min(actions, pos.actions)
        if actions <= 0:
            return 0.0
        brut = actions * cours
        frais = _cout_ordre(brut)
        net = brut - frais
        # Le cout des actions vendues sort au prorata du CMP
        cout_sorti = pos.cmp * actions
        pos.actions -= actions
        pos.cout_total -= cout_sorti
        self.cash += net
        self.frais_payes += frais
        self.nb_ventes += 1
        pos.ventes.append((date, actions, cours, marqueur))
        self.journal.append((date, "VENTE", code, round(net), motif))
        if pos.actions < 1e-9:
            self.positions.pop(code, None)
        return net

    # ------------------------------------------------------------------
    #  Execution
    # ------------------------------------------------------------------
    def executer(self, date_debut: str, date_fin: str,
                 univers: list[str] | None = None) -> ResultatStrategie:
        """Simule la strategie sur la fenetre."""
        if univers is None:
            univers = [c for c in self.hist
                       if self._series(c, date_debut, date_fin)[0]]

        # Pre-calcul des series : on avance seance par seance sur le CALENDRIER
        # GLOBAL (union des dates), comme le ferait un investisseur qui regarde
        # le marche chaque jour.
        series = {}
        for code in univers:
            d, c = self._series(code, date_debut, date_fin)
            if len(d) >= 30:
                series[code] = (d, c, {dd: cc for dd, cc in zip(d, c)})
        if not series:
            return ResultatStrategie(nom="leo", capital_initial=self.capital)

        toutes_dates = sorted({d for (dd, _, _) in series.values() for d in dd})
        budget = self.p.budget_ligne

        # Echeancier d'achat par titre : on etale l'entree en nb_tranches
        a_acheter = {code: 0 for code in series}      # tranches restantes
        dernier_jour_achat = {code: "" for code in series}
        cible = {code: 0.0 for code in series}

        # Suivi de l'exposition : part du capital investie en titres, mesuree a
        # chaque seance puis moyennee. C'est ce qui permet de distinguer « la
        # regle est mauvaise » de « la regle est peu investie » : une regle qui
        # vend tot gagne moins dans un marche haussier par simple effet
        # d'exposition, et non par defaut de methode.
        exposition_cumulee = 0.0
        nb_mesures = 0
        # Drawdown du portefeuille : on suit le sommet de valeur et la pire
        # baisse depuis ce sommet. Meme precaution que dans le backtest du
        # noyau : on reporte la DERNIERE COTE CONNUE de chaque titre, sinon les
        # jours sans transaction font chuter la valeur artificiellement.
        derniere_cote: dict[str, float] = {}
        sommet_valeur = 0.0
        pire_drawdown = 0.0

        for i, date in enumerate(toutes_dates):
            if date > date_fin:
                break

            # --- 1. VALEUR COURANTE (exposition + drawdown) --------------
            valeur_titres = 0.0
            for code, pos in self.positions.items():
                if code not in series:
                    continue
                c = series[code][2].get(date)
                if c:
                    derniere_cote[code] = c
                cours_connu = derniere_cote.get(code)
                if cours_connu:
                    valeur_titres += pos.actions * cours_connu
            total_courant = valeur_titres + self.cash
            if total_courant > 0:
                exposition_cumulee += valeur_titres / total_courant
                nb_mesures += 1
            if total_courant > sommet_valeur:
                sommet_valeur = total_courant
            if sommet_valeur:
                dd = total_courant / sommet_valeur - 1
                if dd < pire_drawdown:
                    pire_drawdown = dd

            for code, (dates, closes, par_date) in series.items():
                cours = par_date.get(date)
                if cours is None:
                    continue
                pos = self.positions.get(code)

                # --- 2. PALIERS DE SORTIE --------------------------------
                # On ne vend chaque palier qu'UNE fois : la liste des seuils
                # deja executes est portee par pos.ventes (marqueur `seuil`).
                if pos is not None and self.p.paliers_actifs and pos.cmp:
                    gain = cours / pos.cmp - 1
                    for seuil, fraction in self.p.seuils_vente:
                        deja_fait = any(abs(v[3] - seuil) < 1e-9
                                        for v in pos.ventes)
                        if gain >= seuil and not deja_fait and pos.actions > 0:
                            n = pos.actions * fraction
                            if n > 0:
                                self._vendre(code, date, cours, n,
                                             f"palier +{seuil*100:.0f} %",
                                             marqueur=seuil)

                # --- 3. ENTREE PROGRESSIVE / RENFORCEMENT ----------------
                dispo = self.cash - self.capital * self.p.cash_cible
                # Taille d'une tranche : le plafond de la ligne divise par le
                # nombre de tranches prevues. Ainsi TOUTES les variantes engagent
                # le meme capital par titre ; seule la repartition dans le temps
                # change (c'est la question posee).
                tranche = self.p.budget_max_ligne / max(self.p.nb_tranches, 1)
                engage = pos.cout_total if pos else 0.0

                if pos is None:
                    # Premiere entree : ouvre la position
                    if dispo > tranche * 0.5:
                        self._acheter(code, date, cours, tranche,
                                      f"entree 1/{self.p.nb_tranches}")

                elif pos.tranches_achetees < self.p.nb_tranches:
                    # Tranches suivantes : espacees dans le temps
                    if self._jours_ecoules(pos.date_dernier_achat, date,
                                           dates) >= self.p.espacement_jours:
                        if dispo > tranche * 0.5:
                            k = pos.tranches_achetees + 1
                            self._acheter(code, date, cours, tranche,
                                          f"entree {k}/{self.p.nb_tranches}")

                # Renforcement sur faiblesse, DANS la limite du plafond de ligne
                elif self.p.renforcement_actif and pos.actions > 0:
                    reste = self.p.budget_max_ligne - engage
                    baisse = cours / pos.cours_dernier_achat - 1
                    if (baisse <= -self.p.seuil_renforcement
                            and reste > tranche * 0.5 and dispo > tranche * 0.5):
                        self._acheter(code, date, cours, min(tranche, reste),
                                      f"renfort ({baisse*100:+.1f} %)")

            # --- 4. DIVIDENDES (credites chaque jour) -------------------
            if i > 0:
                for code, pos in list(self.positions.items()):
                    if code not in series:
                        continue
                    d = self._dividendes_periode(code, toutes_dates[i - 1], date)
                    if d > 0:
                        montant = pos.actions * d
                        self.cash += montant
                        pos.dividendes += montant
                        self.journal.append((date, "DIVIDENDE", code,
                                             round(montant), ""))

        # --- 5. VALEUR FINALE -------------------------------------------
        derniere = toutes_dates[-1]
        valeur_titres = 0.0
        detail = {}
        for code, pos in self.positions.items():
            if code not in series:
                continue
            par_date = series[code][2]
            cours = par_date.get(derniere)
            if cours is None:
                for d in reversed(series[code][0]):
                    if d <= derniere:
                        cours = series[code][2][d]
                        break
            if cours:
                v = pos.valeur(cours)
                valeur_titres += v
                detail[code] = {
                    "actions": round(pos.actions, 4),
                    "cmp": round(pos.cmp, 2),
                    "cours_final": cours,
                    "valeur": round(v),
                    "dividendes": round(pos.dividendes),
                    "tranches": pos.tranches_achetees,
                    "ventes": len(pos.ventes),
                }

        r = ResultatStrategie(nom="leo")
        r.capital_initial = self.capital
        r.cash_final = self.cash
        r.valeur_finale = valeur_titres + self.cash
        r.dividendes = sum(p.dividendes for p in self.positions.values())
        r.frais_payes = self.frais_payes
        r.nb_achats = self.nb_achats
        r.nb_ventes = self.nb_ventes
        r.nb_lignes = len(self.positions)
        r.detail = detail
        r.exposition_moyenne_pct = (exposition_cumulee / nb_mesures * 100
                                    if nb_mesures else 0.0)
        r.drawdown_max_pct = pire_drawdown * 100
        r.capital_deploye = sum(p.cout_total for p in self.positions.values())
        if self.capital:
            r.rendement_pct = (r.valeur_finale / self.capital - 1) * 100
        try:
            a0, a1 = int(date_debut[:4]), int(date_fin[:4])
            annees = max((a1 - a0) + (int(date_fin[5:7]) - int(date_debut[5:7])) / 12, 0.5)
        except Exception:
            annees = 1.0
        r.revenu_annuel_pct = (r.dividendes / self.capital / annees) * 100
        return r

    @staticmethod
    def _jours_ecoules(d1: str, d2: str, dates: list[str]) -> int:
        """Nombre de seances entre deux dates (rang dans la serie)."""
        i1 = i2 = None
        for i, d in enumerate(dates):
            if i1 is None and d >= d1:
                i1 = i
            if d <= d2:
                i2 = i
        if i1 is None or i2 is None:
            return 999
        return max(i2 - i1, 0)


# ---------------------------------------------------------------------------
#  VARIANTES A COMPARER (le test d'attribution)
# ---------------------------------------------------------------------------

def variante_noyau_passif() -> Parametres:
    """A — achat unique, conservation, dividendes encaisses (reference)."""
    return Parametres(
        nb_tranches=1, espacement_jours=0, renforcement_actif=False,
        paliers_actifs=False, rebalancement_actif=False, cash_cible=0.0,
    )


def variante_complete() -> Parametres:
    """B — la strategie reelle de LEO (les 5 composants)."""
    return Parametres(
        nb_tranches=3, espacement_jours=12, renforcement_actif=True,
        seuil_renforcement=0.045, paliers_actifs=True,
        seuils_vente=((0.15, 1 / 3), (0.20, 1 / 3)),
        rebalancement_actif=False,     # voir note : non modelise par defaut
        cash_cible=0.15,
    )


def variante_renforcement_seul() -> Parametres:
    """C — noyau + renforcement sur faiblesse, sans paliers."""
    p = variante_complete()
    p.paliers_actifs = False
    return p


def variante_paliers_seuls() -> Parametres:
    """D — noyau + paliers, sans renforcement."""
    p = variante_complete()
    p.renforcement_actif = False
    p.nb_tranches = 1
    return p
