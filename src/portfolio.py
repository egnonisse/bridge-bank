"""Noyau dividende : positions long terme + sortie sur fondamentaux.

Prix d'entrée (rendement NET 4 %) = `entry_price_for_net(dps)` = dps ÷ 5,45 % ÷ 1,014
(frais de courtage INCLUS — formule unique, B0-04/B1-08 du 12/10) — acheter en dessous.
Prix de sortie (rendement NET 2 %) = dps / DIV_YIELD_EXIT — vendre au-dessus.
Le rendement est NET (après IRVM 12 % + frais de conservation 0,80 %/an),
donc le seuil brut est plus élevé (≈ 5,45 % à l'entrée, ≈ 3,18 % à la sortie).
Sortie sur fondamentaux (JAMAIS sur une simple baisse de cours) :
  1. dividende coupé (>50 %) ou suspendu
  2. PER > 40 (décote résorbée ou bénéfices en chute)
  3. prix de sortie atteint (rendement net tombé à 2 %)
Durée : 3 ans minimum, réévaluation à l'échéance (alerte, pas clôture auto).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .collecte.bsapi import BSApi
from .calibration import seuils_vente
from .calibration.seuils_vente import (  # calibrage + persistance : un seul endroit
    SEUILS_CANDIDATS,
    SEUILS_FILE,
    SEUILS_PAR_DEFAUT,
)
from .regles import (EPISODES_MIN as PROFIT_MIN_EPISODES,  # 8 — voir regles.py
                     LOSS_ALERT_THRESHOLD,                  # −10 % : alerte de couverture
                     MAX_BUY_WEIGHT, MAX_MARKET_WEIGHT,     # concentration (informatif)
                     MAX_POSITION_WEIGHT,
                     PAYOUT_CRITICAL, PAYOUT_TIGHT,         # 1,00 / 0,80
                     PER_MAX as PER_MAX_NOYAU,              # 14,0 — filtres d'achat
                     SELL_FRACTION)                         # 1/3 — fraction vendue
from .taxation import (
    IRVM_DIVIDEND_TAX,
    TARGET_NET_YIELD_ENTRY,
    TARGET_NET_YIELD_EXIT,
    commission,
    entry_price_for_net,
    gross_yield_for_net,
    net_yield,
)
from .portefeuille.format_fr import fcfa, pct  # montants à la française (invariant E1, correction B1-02 du 12/10)
from .infrastructure.paths import DATA_DIR, PORTFOLIO_FILE, REVERSAL_PROFILES  # chemins centralisés (lot 0 du plan docs/architecture.md)
from .infrastructure.ecriture import ecrire_json_atomique  # P7-01 : ecriture atomique

REVERSAL_FILE = REVERSAL_PROFILES  # défini dans paths.py (P6-01) ; PORTFOLIO_FILE vient de l'import (P6-03)
REINF_STATE_FILE = DATA_DIR / "reinf_alert_state.json"  # exclu par .gitignore (*_state.json)
REINF_COOLDOWN_DAYS = 7
REINF_IMPROVE_DOWN_PCT = 0.03  # re-alerte pendant le cooldown si le prix baisse de ≥ 3 %

# Rendement BRUT requis pour atteindre le rendement NET cible (IRVM + frais déduits)
DIV_YIELD_ENTRY = gross_yield_for_net(TARGET_NET_YIELD_ENTRY)  # 4 % net -> ≈ 5,45 % brut
DIV_YIELD_EXIT = gross_yield_for_net(TARGET_NET_YIELD_EXIT)    # 2 % net -> ≈ 3,18 % brut
PER_EXPLODE = 40.0
DIV_CUT_RATIO = 0.5
HOLDING_YEARS = 3

# Seuils de gestion de position (alerte sans clôture automatique)
# Seuils de vente ⅓ CALIBRÉS PAR TITRE (décision LEO 08/09/2026 : un VENDS ⅓ pour
# chaque titre du portefeuille, au seuil le plus fidèle à SON histoire — scripts/
# seuils_par_titre.py, épreuve re-run le 08/09). Règle de choix : le seuil qui
# maximise la probabilité de baisse à J+20. Fiabilité (% de baisse historique) :
# Table de départ et fichier calibré : définis dans src/seuils_vente.py.
# La table de départ ne sert QUE pour un titre absent du fichier calibré.
PROFIT_THRESHOLDS = SEUILS_PAR_DEFAUT
PROFIT_THRESHOLDS_FILE = SEUILS_FILE
PROFIT_SEUILS_CANDIDATS = SEUILS_CANDIDATS
# B1-12 (corrigé le 12/10) : la copie figée PROFIT_DOWN_PROB a été SUPPRIMÉE — elle
# divergeait déjà (PALC 45 vs 46 dans data/profit_thresholds.json) et servait de repli
# muet. Le % de baisse historique ne s'affiche que s'il vient de la mesure calibrée.
# PROFIT_ALERT_THRESHOLD, PROFIT_MIN_EPISODES, LOSS_ALERT_THRESHOLD et SELL_FRACTION
# sont définis dans src/regles.py (catalogue unique).


# Calibrage et persistance des seuils : DÉFINIS dans src/seuils_vente.py (un seul endroit).
# Ces alias préservent les noms historiques attendus par les appelants et les tests.
profit_threshold_for = seuils_vente.pour
_profit_episodes = seuils_vente.episodes
calibrate_profit_threshold = seuils_vente.calibrer
load_profit_thresholds = seuils_vente.charger
save_profit_thresholds = seuils_vente.enregistrer


def calibrate_missing_thresholds(api) -> int:
    """Calibre le seuil de vente de chaque titre détenu qui n'en a pas encore.

    Appelé au début du check quotidien et après chaque ouverture de position : tout titre
    acheté reçoit son seuil automatiquement. Retourne le nombre calibré.

    Chaque changement est ÉCRIT AU JOURNAL (`data/seuils_journal.jsonl`) : c'est la seule
    trace de ce qui a bougé pendant l'exécution, là où git ne voit rien.
    """
    from .collecte.backtest import load_all_history

    calibrated = load_profit_thresholds()
    codes = {p.code for p in load_portfolio() if not p.closed}
    missing = [c for c in codes if c not in calibrated]
    if not missing:
        return 0
    hist = load_all_history(api, force=False)
    done = 0
    for code in missing:
        bars = hist.get(code)
        if not bars:
            continue
        info = calibrate_profit_threshold(code, [b.close for b in bars])
        if info:
            calibrated[code] = info
            done += 1
            seuils_vente.journaliser(
                code, avant=None, apres=info.get("threshold"),
                motif=seuils_vente.MOTIF_CALIBRAGE,
                origine=seuils_vente.ORIGINE_AUTO,
                test={k: info[k] for k in ("down_prob", "borne_basse", "episodes",
                                           "significatif", "mode") if k in info})
    if done:
        save_profit_thresholds(calibrated, origine=seuils_vente.ORIGINE_AUTO)
    return done

# Soutenabilité du dividende (garde-fou anti value-trap) : payout = dividende / BPA.
# La baisse du cours précède souvent la coupe du dividende ; le payout élevé la détecte avant.
# PAYOUT_TIGHT (0,80) et PAYOUT_CRITICAL (1,00) viennent de src/regles.py.

# Niveaux d'alerte (gravité croissante) — cf. IPS §3.4
LEVEL_INFO = 1        # information : rien à faire (console uniquement)
LEVEL_DECISION = 2    # décisionnel : action partielle / réévaluation
LEVEL_FUNDAMENTAL = 3 # fondamental : risque sur le dividende (surveillance)
LEVEL_EXIT = 4        # sortie fondamentale : VENDS TOUT


@dataclass
class PositionAlert:
    """Alerte de gestion de position : un niveau de gravité + un message lisible."""
    level: int
    message: str
    code: str = ""


@dataclass
class DividendPosition:
    code: str
    name: str
    entry_price: float
    quantity: int
    dps: float  # dividende par action (FCFA) à l'ouverture
    per_open: float  # PER à l'ouverture
    opened_at: str = ""
    exit_price: float = 0.0  # prix de sortie (rendement net 2 %)
    entry_price_ref: float = 0.0  # prix d'entrée de référence (rendement net 4 %)
    closed: bool = False
    close_reason: str = ""
    close_price: float = 0.0
    dividends_earned: float = 0.0  # cash total reçu en dividendes
    cash_residual: float = 0.0  # reste non réinvesti (fractionnaire)

    def __post_init__(self) -> None:
        if not self.opened_at:
            self.opened_at = datetime.now().isoformat()
        if self.dps > 0:
            if self.exit_price <= 0:
                self.exit_price = round(self.dps / DIV_YIELD_EXIT, 2)
            if self.entry_price_ref <= 0:
                # B0-04/B1-08 (lot 2) : UNE SEULE formule de prix d'entrée — frais de
                # courtage INCLUS (`entry_price_for_net`), la même que le noyau-check,
                # les ordres limites et l'alerte de renforcement. L'ancienne formule
                # `dps / DIV_YIELD_ENTRY` (IPS pur, sans frais) surestimait le prix max
                # de ~1,4 % (frais d'achat non couverts).
                self.entry_price_ref = round(entry_price_for_net(self.dps), 2)

    def yield_pct(self, price: float) -> float:
        return self.dps / price * 100 if price > 0 else 0.0

    def net_yield_pct(self, price: float) -> float:
        """Rendement NET (en %) après IRVM + frais de conservation."""
        return net_yield(self.dps / price) * 100 if price > 0 else 0.0

    @property
    def years_held(self) -> float:
        try:
            opened = datetime.fromisoformat(self.opened_at)
        except ValueError:
            return 0.0
        return (datetime.now() - opened).days / 365.25

    @property
    def invested(self) -> float:
        return self.entry_price * self.quantity


# ------------------------------------------------------------------- calculs
def _sell_profit_net(pos: DividendPosition, price: float, fraction: float) -> tuple[float, int]:
    """Bénéfice net (après courtage) d'une vente partielle de `fraction` de la position."""
    qty = max(1, int(pos.quantity * fraction))
    gross = (price - pos.entry_price) * qty
    brokerage = commission(price * qty)
    return gross - brokerage, qty


def _dividend_annual_net(pos: DividendPosition) -> float:
    """Dividende net annuel total (après IRVM) pour la position courante."""
    return pos.dps * (1 - IRVM_DIVIDEND_TAX) * pos.quantity


def _next_check_date() -> str:
    """Date de la prochaine alerte possible (fin du cooldown)."""
    return (datetime.now() + timedelta(days=ALERT_COOLDOWN_DAYS)).strftime("%d/%m/%Y")


def _history_line(pos: DividendPosition) -> str:
    """Ligne « 📜 LES AUTRES FOIS » : ce qui suit une hausse, dit en langage courant.

    HONNÊTETÉ DE LA MESURE (09/10/2026)
    -----------------------------------
    Cette ligne affichait « après une hausse de 13 % » **écrit en dur**, alors que le seuil
    du titre vaut 13 % (SNTS), 10 % (SGBC) ou 5 % (SLBC, PALC). Trois titres sur quatre
    recevaient l'affirmation d'un seuil qui n'était pas le leur — et pour SLBC, la
    statistique affichée (39 %, mesurée à +13 %) disait l'inverse de la sienne (54 % à 5 %).

    Deux corrections :

    1. **Le profil est mesuré au seuil du titre** (comme le seuil de vente lui-même) : les
       deux chiffres ne peuvent plus diverger. Si un profil périmé porte un autre seuil, la
       ligne le dit au lieu de laisser croire qu'il s'agit du sien.

    2. **Le taux n'est affiché QUE s'il est statistiquement fondé** (`significatif`). Sur
       peu de cas, « 86 % » se lit comme une probabilité de baisse future alors que sa
       borne basse est 49 % — indiscernable du hasard. Le profil est alors publié pour ce
       qu'il sait vraiment : le délai et la profondeur du repli.

    Traductions conservées (règle de style néophyte) : « séances » → « jours de bourse »,
    pourcentages à la française.
    """
    try:
        data = json.loads(REVERSAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    prof = data.get(pos.code.upper())
    if not prof:
        return ""
    from .portefeuille.format_fr import pct

    seuil_titre = profit_threshold_for(pos.code) * 100
    seuil_profil = prof.get("seuil_pct", 13)
    n = prof.get("episodes", "?")
    fiable = bool(prof.get("significatif", False))

    if abs(seuil_titre - seuil_profil) < 0.5:
        entete = f"après une hausse de {seuil_profil:.0f} % en un mois"
    else:
        # Profil périmé : on le dit, sinon le lecteur rattache la statistique à son seuil.
        entete = (f"repère mesuré à +{seuil_profil:.0f} %, alors que ton seuil "
                  f"est {seuil_titre:.0f} %")

    if fiable:
        line = (f"\n   📜 LES AUTRES FOIS ({n} cas, 9 ans de recul) :\n"
                f"      {entete} — le prix a REBAISSÉ dans {prof['pct_down_20j']} % des cas.\n")
    elif isinstance(n, int) and n < PROFIT_MIN_EPISODES:
        # Vraiment peu de cas : on ne peut rien dire de la fréquence.
        line = (f"\n   📜 LES AUTRES FOIS ({n} cas — trop peu pour une fréquence fiable) :\n"
                f"      {entete}, voici comment ça s'est terminé.\n")
    else:
        # Assez de cas, mais la fréquence reste trop proche du hasard pour en faire une
        # règle. Dire « trop peu de cas » serait FAUX (SGBC en a 30) : le motif est
        # l'imprécision de la mesure, pas la taille de l'échantillon.
        line = (f"\n   📜 LES AUTRES FOIS ({n} cas, 9 ans de recul) :\n"
                f"      {entete}, la suite n'est pas assez nette pour en faire une règle.\n"
                f"      Voici ce qui s'est passé :\n")

    if "trough_delay_median" in prof:
        line += (f"      En moyenne : {pct(prof['median_20j'], signe=True)} un mois plus tard,\n"
                 f"      avec un point bas vers {prof['trough_delay_median']} jours de bourse\n"
                 f"      ({pct(prof['trough_depth_median'])}).")
    if fiable and prof["pct_down_20j"] >= 65:
        line += "\n      ⏳ Tu as environ 2 à 4 semaines pour décider avant la baisse"
    return line


def _double_option_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 2 (décision) : plus-value → vendre 1/3 ou conserver pour le dividende."""
    gain_pct = (price / pos.entry_price - 1) * 100
    gain_fcfa = (price - pos.entry_price) * pos.quantity
    profit_net, _ = _sell_profit_net(pos, price, SELL_FRACTION)
    div_net = _dividend_annual_net(pos)
    net_yld = pos.net_yield_pct(price)
    # Transparence : chaque titre a sa fiabilité historique (calibrage auto 08/09).
    # Pas de copie de repli (B1-12) : sans mesure calibrée, la phrase est simplement omise.
    prob = load_profit_thresholds().get(pos.code, {}).get("down_prob")
    trust = ""
    if prob is not None and prob < 65:
        trust = (
            f"\n   ⚠️ Honnêteté du signal : sur CE titre, après ce niveau de hausse,\n"
            f"      l'historique ne montre une baisse que dans {prob} % des cas.\n"
            f"      → Vends surtout si tu veux du cash ; ne compte pas sur la baisse."
        )
    return PositionAlert(
        LEVEL_DECISION,
        f"⚡ DÉCISION — {pos.name} ({pos.code}) {gain_pct:+.1f} % ({fcfa(gain_fcfa, signe=True)})\n"
        f"   Action : VENDS 1/3 (33 %) → ordre de vente à ≥ {fcfa(price)}\n"
        f"            bénéfice net ≈ {fcfa(profit_net)} (après frais ~1,4 %)\n"
        f"   Alternative : CONSERVE pour ≈ {fcfa(div_net)}/an de dividendes nets\n"
        f"   Rendement net actuel : {net_yld:.1f} %"
        f"{trust}"
        f"{_history_line(pos)}\n"
        f"   Prochaine vérification : {_next_check_date()}",
    )


def _profit_info_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Plus-value au-delà du seuil — on INFORME, on ne propose pas de vendre.

    Rédigé pour un lecteur sans notion de bourse (règle de style LEO 03/09/2026) :
    le gain est donné en francs sur SA ligne, la raison de ne pas vendre est donnée en
    « tant de fois sur tant de cas » avec le repère du pile ou face, et l'action attendue
    est écrite noir sur blanc (« RIEN À FAIRE »).

    Différence avec `_double_option_alert` : aucune consigne de vente. Le seuil reste
    VISIBLE (niveau 2, donc transmis) parce que l'information « ce titre a pris X % »
    reste utile — mais le système s'abstient de recommander une vente sur un signal que
    les données ne soutiennent pas (bornes basses 49/46/36/34 %, toutes sous 50 %).
    """
    from .portefeuille.format_fr import fcfa, pct
    from .calibration.seuils_vente import explication, resume_justification

    gain_pct = (price / pos.entry_price - 1) * 100
    gain_fcfa = (price - pos.entry_price) * pos.quantity
    div_net = _dividend_annual_net(pos)
    net_yld = pos.net_yield_pct(price)
    info = load_profit_thresholds().get(pos.code.upper())
    # Traçabilité MINIMALE (réserve LEO 08/10/2026) : l'alerte dit d'où vient le seuil
    # qui l'a produite — calibrage automatique ou choix manuel, et depuis quand. Sans
    # cela, un seuil change en silence et personne ne peut savoir sur quoi on a décidé.
    justif = resume_justification(pos.code)
    return PositionAlert(
        LEVEL_DECISION,
        f"ℹ️ INFO — {pos.name} ({pos.code}) a pris {pct(gain_pct, signe=True)} "
        f"({fcfa(gain_fcfa, signe=True)} sur ta ligne)\n"
        f"   Tu gagnerais {fcfa(gain_fcfa)} en vendant maintenant.\n"
        f"{explication(info)}\n"
        f"{justif}\n"
        f"   → RIEN À FAIRE. Garde tes actions : elles te paient\n"
        f"     ≈ {fcfa(div_net)} par an, soit {pct(net_yld)} de ton argent\n"
        f"     (ton objectif est d'au moins 4 %).\n"
        f"   Une vente n'a de sens que si l'entreprise coupe son dividende,\n"
        f"   gagne beaucoup moins, ou si le loyer tombe sous 2 %."
        f"{_history_line(pos)}\n"
        f"   Prochaine vérification : {_next_check_date()}",
    )


def _loss_coverage_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 2 (décision) : moins-value → conserver (perte couverte par les dividendes)."""
    loss_pct = (price / pos.entry_price - 1) * 100
    loss_fcfa = (price - pos.entry_price) * pos.quantity
    div_net = _dividend_annual_net(pos)
    net_yld = pos.net_yield_pct(price)
    coverage = (
        f"perte couverte en ~{abs(loss_fcfa) / div_net:.1f} ans"
        if div_net > 0
        else "aucun dividende pour couvrir la perte"
    )
    return PositionAlert(
        LEVEL_DECISION,
        f"⚡ DÉCISION — {pos.name} ({pos.code}) {loss_pct:+.1f} % ({fcfa(loss_fcfa)})\n"
        f"   Action : CONSERVE — {coverage}\n"
        f"   Renforcement : ordre limite d'achat à ≤ {fcfa(price)} (net {net_yld:.1f} %) — si dividende soutenable\n"
        f"   Alternative : vendre seulement si la thèse change (jamais sur le prix)\n"
        f"   Prochaine vérification : {_next_check_date()}",
    )


def payout_ratio(dps: float | None, price: float | None, per: float | None) -> float | None:
    """Payout ratio implicite = dividende / bénéfice par action (BPA = prix / PER).

    Retourne None si PER inconnu ou non positif (pertes), ou si données manquantes.
    A-003 (13/10/2026) : `None` est accepté pour dps/price — un titre sans dividende
    connu peut remonter `None` depuis les données, et l'étape de Soutenabilité
    levait un TypeError au lieu de s'abstenir (donnée manquante ≠ alerte).
    """
    if dps is None or price is None:
        return None
    if dps <= 0 or price <= 0 or per is None or per <= 0:
        return None
    return dps * per / price


def sustainability_alert(name: str, code: str, dps: float, per: float | None, price: float) -> PositionAlert | None:
    """Niveau 3 (fondamental) : dividende non soutenable (payout élevé ou société en perte).

    Garde-fou anti value-trap : détecte une coupe probable AVANT qu'elle n'arrive.
    Applicable à un titre du noyau, qu'une position soit ouverte ou non.
    """
    if per is not None and per <= 0 and dps > 0:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🔴 FONDAMENTAL — {name} ({code}) — société en perte (PER négatif) mais dividende versé\n"
            f"   RISQUE DE COUPE DU DIVIDENDE\n"
            f"   Surveillance renforcée.",
        )
    payout = payout_ratio(dps, price, per)
    if payout is None:
        return None
    if payout > PAYOUT_CRITICAL:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🔴 FONDAMENTAL — {name} ({code}) — payout {payout*100:.0f} %\n"
            f"   RISQUE DE COUPE DU DIVIDENDE\n"
            f"   Surveillance renforcée.",
        )
    if payout > PAYOUT_TIGHT:
        return PositionAlert(
            LEVEL_FUNDAMENTAL,
            f"🟠 FONDAMENTAL — {name} ({code}) — payout {payout*100:.0f} %\n"
            f"   Dividende tendu — surveillance.",
        )
    return None


def _soutenabilite_alert(pos: DividendPosition, dps: float, per: float | None, price: float) -> PositionAlert | None:
    """Compat : soutenabilité pour une position ouverte (wrapper)."""
    return sustainability_alert(pos.name, pos.code, dps, per, price)


def check_sustainability(api: BSApi, codes: list[str]) -> list[PositionAlert]:
    """Vérifie la soutenabilité du dividende de chaque titre du noyau (payout).

    Garde-fou anti value-trap systématique : alerte (niveau 3) si payout > 80 %
    (tendu) ou > 100 % (non couvert), même sans position ouverte.
    """
    from .collecte.fundamentals import get_fundamentals

    snap = api.market_snapshot()
    alerts: list[PositionAlert] = []
    for code in codes:
        quote = snap.by_code(code.strip().upper())
        if quote is None or quote.last <= 0:
            continue
        fund = get_fundamentals(code)
        a = sustainability_alert(
            quote.name, quote.code.strip(), fund.get("dps"), fund.get("per"), quote.last
        )
        if a:
            a.code = quote.code.strip()
            alerts.append(a)
    return alerts


def _info_alert(pos: DividendPosition, price: float) -> PositionAlert:
    """Niveau 1 (information) : variation modérée, rien à faire (console uniquement)."""
    perf = (price / pos.entry_price - 1) * 100
    return PositionAlert(
        LEVEL_INFO,
        f"ℹ️ INFORMATION — {pos.name} ({pos.code}) {perf:+.1f} % — rien à faire",
    )


def status_level(pos: DividendPosition, price: float) -> tuple[int, str]:
    """Niveau + libellé court pour l'affichage console (`portf status`).

    Basé sur le cours seul (sans PER/payout, pour éviter le scraping dans `status`).
    Le libellé distingue un seuil qui DÉCLENCHE (« VENDS 1/3 ») d'un seuil seulement
    informatif (« +X % (info) ») — cohérent avec l'alerte Telegram.
    """
    if pos.closed:
        return LEVEL_EXIT, "VENDU"
    if price >= pos.entry_price * (1 + profit_threshold_for(pos.code)):
        from .calibration.seuils_vente import est_declencheur
        if est_declencheur(load_profit_thresholds().get(pos.code.upper())):
            return LEVEL_DECISION, "VENDS 1/3"
        return LEVEL_DECISION, "SEUIL ATTEINT (info)"
    if price <= pos.entry_price * (1 - LOSS_ALERT_THRESHOLD):
        return LEVEL_DECISION, "CONSERVE"
    return LEVEL_INFO, "rien à faire"


def check_dividend_position(
    pos: DividendPosition,
    current_price: float,
    current_dps: Optional[float] = None,
    current_per: Optional[float] = None,
) -> list[PositionAlert]:
    """Évalue une position dividende. Retourne des alertes hiérarchisées par niveau.

    Niveaux (gravité croissante) :
      - LEVEL_INFO (1)        : variation modérée, rien à faire (console)
      - LEVEL_DECISION (2)    : action partielle / réévaluation
      - LEVEL_FUNDAMENTAL (3) : risque sur le dividende (surveillance)
      - LEVEL_EXIT (4)        : sortie fondamentale → VENDS TOUT

    Sorties fondamentales (VENTE TOTALE) — la thèse « revenu » est morte :
      1. dividende suspendu ou coupé > 50 %
      2. PER > 40 (décote résorbée / bénéfices en chute)
      3. prix de sortie atteint (rendement net ≤ 2 %)
    """
    alerts: list[PositionAlert] = []
    if pos.closed:
        return alerts

    # 1. dividende coupé/suspendu → VENDS TOUT
    if current_dps is not None and pos.dps > 0:
        if current_dps <= 0:
            pos.closed = True
            pos.close_reason = "dividende suspendu"
            alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — dividende suspendu, la thèse « revenu » est morte"))
        elif current_dps < pos.dps * DIV_CUT_RATIO:
            pos.closed = True
            pos.close_reason = "dividende coupé >50%"
            alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — dividende coupé de plus de 50 %"))

    # 2. PER explose → VENDS TOUT
    if not pos.closed and current_per is not None and current_per > PER_EXPLODE:
        pos.closed = True
        pos.close_reason = f"PER {current_per:.1f} > {PER_EXPLODE:.0f}"
        alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — PER {current_per:.1f} > {PER_EXPLODE:.0f}"))

    # 3. prix de sortie atteint → VENDS TOUT — seuil recalculé au dps COURANT quand il est
    #    connu (B1-05, lot 2) : un dividende qui monte écarte le seuil de sortie (on garde le
    #    loyer) ; un dividende qui baisse (sans coupe > 50 %) le rapproche. `pos.exit_price`
    #    (dps d'ouverture) reste le repli quand aucun dps courant n'est fourni.
    exit_ref = (round(current_dps / DIV_YIELD_EXIT, 2)
                if current_dps is not None and current_dps > 0 else pos.exit_price)
    if not pos.closed and exit_ref > 0 and current_price >= exit_ref:
        pos.closed = True
        pos.close_reason = "prix de sortie atteint"
        alerts.append(PositionAlert(LEVEL_EXIT, f"🔴 VENDS TOUT — {pos.name} ({pos.code}) — prix de sortie atteint ({fcfa(current_price)} ≥ {fcfa(exit_ref)})"))

    # 4. soutenabilité (niveau 3)
    if not pos.closed and current_dps is not None and current_dps > 0:
        sa = _soutenabilite_alert(pos, current_dps, current_per, current_price)
        if sa:
            alerts.append(sa)

    # 5. plus-value → décision (niveau 2) — seuil CALIBRÉ PAR TITRE.
    #    Le seuil ne déclenche une consigne de vente que s'il est statistiquement fondé
    #    (borne basse de l'intervalle de confiance ≥ 50 %, cf. src/seuils_vente.py).
    #    Sinon le seuil reste VISIBLE mais informatif : aucune vente n'est proposée.
    if not pos.closed and current_price >= pos.entry_price * (1 + profit_threshold_for(pos.code)):
        from .calibration.seuils_vente import est_declencheur
        info_seuil = load_profit_thresholds().get(pos.code.upper())
        if est_declencheur(info_seuil):
            alerts.append(_double_option_alert(pos, current_price))
        else:
            alerts.append(_profit_info_alert(pos, current_price))

    # 6. moins-value → décision (niveau 2)
    elif not pos.closed and current_price <= pos.entry_price * (1 - LOSS_ALERT_THRESHOLD):
        alerts.append(_loss_coverage_alert(pos, current_price))

    # 7. échéance 3 ans (niveau 2)
    if not pos.closed and pos.years_held >= HOLDING_YEARS:
        alerts.append(PositionAlert(LEVEL_DECISION, f"🟡 DÉCISION — {pos.name} ({pos.code}) — ÉCHÉANCE {HOLDING_YEARS} ans atteinte, réévalue la thèse"))

    # 8. sinon, information (niveau 1)
    if not pos.closed and not any(a.level >= LEVEL_DECISION for a in alerts):
        alerts.append(_info_alert(pos, current_price))

    if pos.closed and not pos.close_price:
        pos.close_price = current_price
    return alerts


def record_dividend(pos: DividendPosition, price: float) -> tuple[float, int, float]:
    """Enregistre un versement de dividende NET (IRVM retenue à la source) et le réinvestit
    dans le même titre (DRIP).

    B1-03 (lot 2, 12/10) : le cash RÉELLEMENT reçu est le NET — l'IRVM 12 % est retenue à la
    source par la SGI. Comptabiliser le brut surestimait de ~13,6 % par versement le cash,
    les actions rachetées et `dividends_earned` cumulé.

    Retourne (cash reçu NET, actions achetées, résidu non réinvesti en FCFA).
    """
    if pos.dps <= 0 or pos.quantity <= 0:
        return 0.0, 0, 0.0
    cash = pos.dps * (1 - IRVM_DIVIDEND_TAX) * pos.quantity
    new_shares = int(cash // price) if price > 0 else 0
    pos.quantity += new_shares
    pos.dividends_earned += cash
    residual = cash - new_shares * price
    pos.cash_residual += residual
    return cash, new_shares, residual


# -------------------------------------------------------------- persistance
class PortfolioInvalide(RuntimeError):
    """portfolio.json illisible — on refuse d'écraser ce qu'on ne sait pas relire (B1-04)."""


def load_portfolio() -> list[DividendPosition]:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        return [DividendPosition(**d) for d in json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))]
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PortfolioInvalide(
            f"{PORTFOLIO_FILE.name} illisible ({type(exc).__name__}: {exc}) — "
            "aucune écriture ne sera faite (corrige ou restaure le fichier)"
        ) from exc


def save_portfolio(positions: list[DividendPosition]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PORTFOLIO_FILE.with_name(PORTFOLIO_FILE.name + ".tmp")
    tmp.write_text(
        json.dumps([asdict(p) for p in positions], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(PORTFOLIO_FILE)  # atomique : un crash ne peut plus tronquer l'original (B1-04)


# ------------------------------------------------- renforcements (noyau dynamique)
# PER_MAX_NOYAU (14,0) et les trois poids de concentration viennent de src/regles.py.
# Rappel de la règle LEO : le verrou de concentration INFORME, il ne bloque jamais.


def _msg_renfort_libre(p, price, entry_ref, net, payout) -> str:
    return (
        f"💪 RENFORCE {p.code} ({p.name}) — le prix est redescendu à {fcfa(price)},\n"
        f"   sous ton seuil de {fcfa(entry_ref)}.\n"
        f"   → Chaque 1 000 F investi ici te paierait au moins 4 % de loyer par\n"
        f"     an (aujourd'hui : {net:.1f} % net), avec un patron qui partage\n"
        f"     {payout*100:.0f} % de ses gains — dans ta zone.\n"
        f"   → Montant : toi seul décides (jamais au-delà de ton plan)."
    )


def _msg_renfort_limite(p, price, entry_ref, net, payout, w_mkt, w_cost, max_qty) -> str:
    return (
        f"💪 RENFORCE LIMITÉ {p.code} ({p.name}) — le prix est redescendu à "
        f"{fcfa(price)}, sous ton seuil de {fcfa(entry_ref)} ({net:.1f} % net,\n"
        f"   patron à {payout*100:.0f} % — tout est vert).\n"
        f"   MAIS il pèse déjà {w_mkt*100:.0f} % de tes actions — par sa HAUSSE,\n"
        f"   pas par tes achats (tu n'as acheté que {w_cost*100:.0f} % de ta poche\n"
        f"   sur lui). Tu peux en profiter : au plus {max_qty} action(s)\n"
        f"   (~{fcfa(max_qty*price)}), pour ne pas faire de ce titre plus de\n"
        f"   {MAX_BUY_WEIGHT*100:.0f} % de TES achats.\n"
        f"   → La limite, c'est toi qui la signes."
    )


def _msg_concentration_achats(p, price, entry_ref, w_cost) -> str:
    return (
        f"🟠 RENFORCE EN CONSCIENCE — {p.code} ({p.name}) est sous ton seuil\n"
        f"   ({fcfa(price)} < {fcfa(entry_ref)}) et paie un bon loyer, mais tu as\n"
        f"   ACHETÉ {w_cost*100:.0f} % de ta poche sur ce titre (repère : 35 %).\n"
        f"   → Le système ne bloque PAS (ta règle) : il te dit le risque.\n"
        f"   → Si tu renforces quand même : en connaissance de cause."
    )


def _msg_ligne_buffett(p, price, entry_ref, w_mkt) -> str:
    return (
        f"🔴 ATTENTION MAXIMALE — {p.code} ({p.name}) est sous ton seuil\n"
        f"   ({fcfa(price)} < {fcfa(entry_ref)}), mais il représente déjà\n"
        f"   {w_mkt*100:.0f} % du portefeuille : plus de la moitié dans un seul\n"
        f"   panier, c'est un pari, pas un loyer.\n"
        f"   → Le système ne bloque PAS (ta règle), mais c'est le signal le plus\n"
        f"     grave qu'il sache émettre. Décision tienne, en pleine lucidité."
    )


def _msg_regime(regime: dict | None) -> str:
    """Dit en langage courant dans quel marché on est (règle de style néophyte).

    Mesure de référence (5 196 observations, 28 ans) : renforcer en entrant en année de
    krach gagne 67-69 % du temps ; en marché haussier, 42-49 %. On traduit en « fois sur
    dix » — plus parlant qu'un pourcentage pour qui n'a pas l'habitude.

    Règle LEO « ne bloque pas » : le renforcement part TOUJOURS, l'alerte est documentée.
    """
    if not regime or not regime.get("etat"):
        return ""
    from .calibration.regime_marche import BAISSIER

    if regime["etat"] == BAISSIER:
        return ("\n   📉 En ce moment, le marché BAISSE dans l'ensemble.\n"
                "      C'est la période où acheter sur baisse a le plus marché :\n"
                "      sur 28 ans de données, ces achats ont été gagnants 7 fois sur 10.")
    return ("\n   📈 En ce moment, le marché MONTE dans l'ensemble.\n"
            "      Acheter sur baisse marche moins bien dans ces périodes :\n"
            "      gagnant 4 fois sur 10 seulement (contre 7 fois sur 10 quand ça baisse).\n"
            "      → Tu peux quand même le faire, en le sachant.")


def reinforcement_messages(positions, price_of, per_of, total_stocks: float = 0.0,
                           regime: dict | None = None):
    """Positions dont le cours est REDESCENDU sous le prix qui garantit 4 % net,
    avec les 4 filtres toujours OK (PER ≤ 14, payout ≤ 80 %) + verrou de
    concentration INFORMATIF (règle LEO 11/09 « ne bloque pas » : l'alerte part
    TOUJOURS, avec le niveau de risque — libre / limité / en conscience / max) :
      - poids marché ≤ 35 %               → 💪 RENFORCE (libre)
      - 35-50 % par HAUSSE (achats ≤ 35 %)→ 💪 RENFORCE LIMITÉ (plafond calculé)
      - 35-50 % par ACHATS (achats > 35 %)→ 🟠 RENFORCE EN CONSCIENCE (averti)
      - poids marché > 50 %               → 🔴 ATTENTION MAXIMALE (averti)
    Rien n'est jamais supprimé : l'information part, LEO décide.

    Retourne (hits, []) : [(code, message)] — blocked conservé vide pour
    compatibilité, anti-spam à la charge de l'appelant.
    """
    from .taxation import entry_price_for_net, net_yield

    hits: list[tuple[str, str]] = []
    total_cost = sum(p.quantity * p.entry_price for p in positions if not p.closed)
    for p in positions:
        if p.closed:
            continue
        price = price_of(p.code)
        if not price or price <= 0:
            continue
        entry_ref = entry_price_for_net(p.dps)
        if price > entry_ref:
            continue
        per = per_of(p.code)
        if per is None or per <= 0 or per > PER_MAX_NOYAU:
            continue
        payout = payout_ratio(p.dps, price, per)
        if payout is None or payout > PAYOUT_TIGHT:
            continue
        w_mkt = (p.quantity * price / total_stocks) if total_stocks > 0 else 0.0
        w_cost = (p.quantity * p.entry_price / total_cost) if total_cost > 0 else 0.0
        net = net_yield(p.dps / price) * 100
        # Contexte de marché ajouté à CHAQUE message (règle LEO : informer, jamais bloquer).
        ctx = _msg_regime(regime)
        if w_mkt > MAX_MARKET_WEIGHT:
            hits.append((p.code, _msg_ligne_buffett(p, price, entry_ref, w_mkt) + ctx))
            continue
        if w_cost > MAX_POSITION_WEIGHT:
            hits.append((p.code, _msg_concentration_achats(p, price, entry_ref, w_cost) + ctx))
            continue
        if w_mkt > MAX_POSITION_WEIGHT:
            max_qty = int((MAX_BUY_WEIGHT * total_cost - p.quantity * p.entry_price) // price)
            if max_qty < 1:
                hits.append((p.code, _msg_concentration_achats(p, price, entry_ref, w_cost) + ctx))
                continue
            hits.append((p.code, _msg_renfort_limite(
                p, price, entry_ref, net, payout, w_mkt, w_cost, max_qty) + ctx))
            continue
        hits.append((p.code, _msg_renfort_libre(p, price, entry_ref, net, payout) + ctx))
    return hits, []


def load_reinf_state() -> dict:
    try:
        return json.loads(REINF_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_reinf_state(state: dict) -> None:
    ecrire_json_atomique(REINF_STATE_FILE, state)  # P7-01 : écriture atomique


def check_reinforcements(api) -> list[tuple[str, str]]:
    """Renforcements du noyau, avec anti-spam 7 jours par titre."""
    from .collecte.fundamentals import get_per_brvm

    positions = load_portfolio()
    snap = api.market_snapshot()

    def price_of(code):
        q = snap.by_code(code)
        return q.last if q and q.last > 0 else 0.0

    def per_of(code):
        return get_per_brvm(code)

    total_stocks = sum(
        (p.quantity * price_of(p.code)) for p in positions if not p.closed
    )
    # Contexte de marché : mesuré une fois par jour (cache), ajouté aux messages.
    # Il n'empêche RIEN (règle LEO « ne bloque pas ») — il documente le régime, parce que
    # renforcer paie 67-69 % du temps en marché baissier contre 42-49 % en marché haussier.
    try:
        from .calibration.regime_marche import regime_du_jour
        regime = regime_du_jour()
    except Exception:
        # Un indicateur indisponible ne doit JAMAIS empêcher l'alerte de partir.
        regime = None
    hits, blocked = reinforcement_messages(positions, price_of, per_of, total_stocks,
                                           regime=regime)
    state = load_reinf_state()
    fresh: list[tuple[str, str]] = []
    now = datetime.now().isoformat()

    def _emit(pairs: list[tuple[str, str]]) -> None:
        for code, msg in pairs:
            last = state.get(code)
            age_days = -1
            last_price = None
            if last is not None:
                if isinstance(last, dict):  # nouveau format {date, price}
                    try:
                        age_days = (datetime.now() - datetime.fromisoformat(last["date"])).days
                    except (ValueError, KeyError):
                        age_days = -1
                    last_price = last.get("price")
                else:  # ancien format (date seule)
                    try:
                        age_days = (datetime.now() - datetime.fromisoformat(last)).days
                    except ValueError:
                        age_days = -1
            price = price_of(code)
            if last is None or age_days >= REINF_COOLDOWN_DAYS:
                fresh.append((code, msg))
                state[code] = {"date": now, "price": price}
            elif last_price and price <= last_price * (1 - REINF_IMPROVE_DOWN_PCT):
                # cooldown actif mais le prix s'est nettement amélioré → re-signal
                fresh.append((code, "📉 LE PRIX S'EST ENCORE AMÉLIORÉ —\n" + msg))
                state[code] = {"date": now, "price": price}

    _emit(hits)     # 💪 RENFORCE (recommandation d'achat)
    _emit(blocked)  # 🚦 CONCENTRATION (blocage — information, jamais un ordre)
    save_reinf_state(state)
    return fresh


# ------------------------------------------------- anti-spam des alertes
ALERT_STATE_FILE = DATA_DIR / "portf_alert_state.json"
ALERT_COOLDOWN_DAYS = 7  # ne pas re-alerter la même position avant 7 jours


def load_alert_state() -> dict:
    if not ALERT_STATE_FILE.exists():
        return {}
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_alert_state(state: dict) -> None:
    ecrire_json_atomique(ALERT_STATE_FILE, state)  # P7-01 : écriture atomique


def is_cooldown_active(state: dict, code: str) -> bool:
    """True si la position a déjà été alertée il y a moins de ALERT_COOLDOWN_DAYS jours."""
    last = state.get(code)
    if not last:
        return False
    try:
        dt = datetime.fromisoformat(last)
    except (TypeError, ValueError):
        return False
    return (datetime.now() - dt).days < ALERT_COOLDOWN_DAYS


# ------------------------------------------------------------- haut niveau
def open_dividend_position(
    api: BSApi, code: str, amount: float, dps: float, per_open: float
) -> DividendPosition:
    """Ouvre une position dividende de `amount` FCFA au cours actuel."""
    from .strategie.speculation import load_positions  # import local : évite la circularité (verrouillé par tests/test_poches_etanches.py)

    snap = api.market_snapshot()
    quote = snap.by_code(code)
    if quote is None or quote.last <= 0:
        raise ValueError(f"Titre {code} introuvable ou sans cotation")
    # Règle IPS : les poches sont étanches (un spéculatif ne devient jamais un investissement).
    norm = quote.code.strip().upper()
    for s in load_positions():
        if not s.closed and s.code.strip().upper() == norm:
            raise ValueError(
                f"Règle IPS — poches étanches : {norm} est déjà détenu dans la poche "
                f"SPÉCULATIVE. Un spéculatif ne devient jamais un investissement long "
                f"terme. (Vends d'abord la ligne spéculative : spec close {norm})"
            )
    quantity = int(amount // quote.last)
    if quantity <= 0:
        raise ValueError(f"Montant {fcfa(amount)} insuffisant pour 1 action à {fcfa(quote.last)}")
    return DividendPosition(
        code=quote.code.strip(),
        name=quote.name,
        entry_price=quote.last,
        quantity=quantity,
        dps=dps,
        per_open=per_open,
    )
