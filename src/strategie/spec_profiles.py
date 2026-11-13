"""Profils de spéculation « durée » — détecteurs de schémas + stats calibrées.

Trois schémas éprouvés (épreuves 10 ans, net de frais 2,8 %) :
  CASSURE : le titre dépasse son plus haut des 250 séances (1 an)
  EVEIL   : rebond >= +10 % depuis le creux des 60 séances
  PANIQUE : RSI 14 < 30 (chute récente)

Les statistiques globales (n, taux de réussite, médiane, paliers touchés)
sont CALIBRÉES par scripts/calibrate_spec_profiles.py → data/spec_profiles.json.
"""
import bisect
import datetime
import json
import logging
import statistics
from pathlib import Path
from ..infrastructure.paths import DATA_DIR as DATA  # chemins centralisés (lot 0 du plan docs/architecture.md)

log = logging.getLogger(__name__)

PROFILES_FILE = DATA / "spec_profiles.json"

ZONE_FORCE = (0.80, 1.01)   # zone de force (83 % de réussite)
ZONE_HAUT_FRAGILE = (0.60, 0.80)  # danger (0 % gagnants)
ZONE_BAS_SOLIDE = (0.20, 0.40)    # bas sans être écrasé (80 %)
ZONE_BAS_ECRASE = (0.0, 0.20)     # piège (50 %)

from ..regles import FRAIS_ALLER_RETOUR as FRAIS  # noqa: E402

# HORIZON_JOURS remplace l'ancien HORIZON = 252 (SEANCES), qui etait faux de ~15 jours.
#
# Mesure du 12/11/2026 sur les 1 615 cas : une annee calendaire ne contient qu'une MEDIANE
# DE 240 SEANCES sur la BRVM (min 69, max 249), et 1 615 cas sur 1 615 ont MOINS de 252
# seances dans 365 jours. Mesurer sur 252 seances revenait donc a mesurer sur ~380 jours,
# soit 13 mois. Effet mesure (252 seances -> 365 jours calendaires) :
#   CASSURE  mediane +16,3 % -> +17,1 % | reussite 65,9 % -> 68,2 %  (stable)
#   EVEIL    mediane  +5,9 % ->  +3,5 % | reussite 55,6 % -> 54,2 %  (favorable -> neutre)
#   PANIQUE  mediane  +3,2 % ->  -0,6 % | reussite 52,2 % -> 49,3 %  (neutre -> defavorable)
# L'ecart MOYEN atteint -12,3 points sur PANIQUE alors que l'ecart MEDIAN est nul : les trois
# mois de fenetre en trop laissaient courir les cas extremes jusqu'a un pic. C'est le biais
# que ce changement supprime.
HORIZON_JOURS = 365


def index_fin_horizon(dates, i, jours=HORIZON_JOURS):
    """Index de la derniere seance dont la date est <= dates[i] + `jours` calendaires.

    `dates` doit etre une liste TRIEE d'objets comparables entre eux (datetime.date de
    preference). Recherche binaire : O(log n), appelable sur 1 615 cas sans ralentir.

    Renvoie i quand aucune seance ne suit dans la fenetre (fenetre vide) — l'appelant doit
    alors traiter le cas comme non mature plutot que comme un rendement nul.
    """
    limite = dates[i] + datetime.timedelta(days=jours)
    return bisect.bisect_right(dates, limite) - 1


def fenetre_complete(dates, i, j):
    """Vrai si la fenetre calendaire contient au moins une seance ET est terminee.

    `j > i` est indispensable : quand aucune seance ne suit dans la fenetre,
    index_fin_horizon renvoie i, la tranche closes[i+1:j+1] serait VIDE, et max() ou
    futur[-1] levent alors ValueError / IndexError — vecu au premier lancement.

    La fenetre est terminee soit parce qu'une seance existe AU-DELA de la limite
    (j < len-1), soit parce que la serie s'arrete mais couvre deja les 365 jours.
    Une fenetre qui s'arrete faute de donnees donne un rendement PARTIEL : la compter
    comme un rendement a 12 mois surestime les cas recents.
    """
    if j <= i:
        return False
    return j < len(dates) - 1 or (dates[j] - dates[i]).days >= HORIZON_JOURS


def ema(vals, n):
    k = 2 / (n + 1)
    out = []
    e = None
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(vals, n=14):
    out = [None] * len(vals)
    gains = losses = 0.0
    avg_g = avg_l = 0.0
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        g, l = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            gains += g
            losses += l
            if i == n:
                avg_g, avg_l = gains / n, losses / n
                out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
        else:
            avg_g = (avg_g * (n - 1) + g) / n
            avg_l = (avg_l * (n - 1) + l) / n
            out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def detect_schemas(closes, volumes=None):
    """Détecte les schémas ACTIFS sur la dernière séance d'une série.

    Retourne une liste de codes : "CASSURE", "EVEIL", "PANIQUE".
    volumes : liste alignée sur closes ; si fournie, la CASSURE exige un
    volume >= médiane des 60 dernières séances (une cassure sans volume
    n'est pas une vraie demande — règle du challenge croisé 25/09).
    B1-10 (13/10/2026) : une médiane NULLE (titre illiquide, trou de données)
    ne confirme plus rien d'office — sans volume réel, pas de confirmation.
    """
    if len(closes) < 260 or closes[-1] <= 0:
        return []
    i = len(closes) - 1
    found = []
    # cassure du plus haut des 250 séances, confirmée par le volume
    if closes[i] > max(closes[i - 250 : i]):
        vol_ok = True
        if volumes and len(volumes) == len(closes):
            med = statistics.median(volumes[-61:-1])
            # B1-10 (13/10/2026) : médiane nulle = aucun volume réel sur la fenêtre —
            # elle ne CONFIRME plus rien d'office (avant : `med <= 0` → vol_ok = True,
            # le faux breakout que la règle volume du 25/09 devait bloquer).
            vol_ok = med > 0 and volumes[i] >= med
        if vol_ok:
            found.append("CASSURE")
    # éveil : rebond >= +10 % depuis le creux des 60 séances, confirmé
    # par un volume >= médiane des 60 séances (épreuve 25/09 : sans le
    # volume, un seul print illiquide peut créer un faux rebond)
    creux60 = min(closes[i - 60 : i])
    # GARDE-FOU (13/11/2026) : une clôture à 0 dans la fenêtre des 60 séances (donnée
    # manquante, titre suspendu) rendait creux60 nul, et la division levait un
    # ZeroDivisionError qui faisait tomber TOUT detect_schemas — donc la calibration et les
    # alertes du matin. Reproduit : detect_schemas([100.0]*250 + [100.0]*58 + [0.0, 100.0, 105.0])
    # Un creux nul ne peut pas servir de référence : on ne mesure pas un rebond depuis zéro.
    if creux60 > 0 and closes[i] / creux60 - 1 >= 0.10:
        vol_ok = True
        if volumes and len(volumes) == len(closes):
            med = statistics.median(volumes[-61:-1])
            # B1-10 (13/10/2026) : médiane nulle = aucun volume réel sur la fenêtre —
            # elle ne CONFIRME plus rien d'office (avant : `med <= 0` → vol_ok = True,
            # le faux breakout que la règle volume du 25/09 devait bloquer).
            vol_ok = med > 0 and volumes[i] >= med
        if vol_ok:
            found.append("EVEIL")
    # panique : RSI 14 < 30
    r = rsi(closes)
    if r[i] is not None and r[i] < 30:
        found.append("PANIQUE")
    return found


def zone_of(closes, years=5):
    """Position du dernier cours dans la fourchette des ~5 ans (0 à 100)."""
    n = min(len(closes) - 1, years * 252)
    window = closes[-n - 1 : -1] + [closes[-1]]
    lo, hi = min(window), max(window)
    if hi <= lo:
        return 0.0
    return (closes[-1] - lo) / (hi - lo)


def zone_label(zone: float) -> str:
    if zone < 0.20:
        return "BAS_ECRASE"
    if zone < 0.40:
        return "BAS_SOLIDE"
    if zone < 0.60:
        return "MILIEU"
    if zone < 0.80:
        return "HAUT_FRAGILE"
    return "FORCE"


def load_profiles() -> dict:
    """Stats calibrées par schéma — le repli sur les valeurs figées est SIGNALÉ.

    B1-10 (13/10/2026) : si le fichier de calibrage est absent ou illisible, le
    repli (valeurs des épreuves 16-17/09/2026) est journalisé ET marqué
    `"_fallback": True` — la fiche l'affiche (« statistiques de secours, non
    recalibrées »). Avant, un fichier perdu faisait afficher ces chiffres de
    septembre comme s'ils étaient la mesure COURANTE, sans aucune mention.
    """
    if PROFILES_FILE.exists():
        try:
            data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
            data.pop("_fallback", None)   # le fichier calibré ne porte jamais ce marqueur
            return data
        except Exception as exc:
            log.warning("spec_profiles.json illisible (%s) — repli sur les stats figées", exc)
    else:
        log.warning("spec_profiles.json absent — repli sur les stats figées (16-17/09/2026)")
    # Fallback : valeurs RE-MESURÉES le 12/11/2026 sur le CACHE PROPRE (divisions ajustées).
    # Historique : ce bloc a porté 5/28/18 cas (bug d'espacement), puis 257/934/421 (mesuré
    # sur CACHE_BRUT, donc avec de faux signaux créés par les divisions), et enfin les valeurs
    # ci-dessous. Une division 10:1 apparaît comme une chute de −90 % sur une série brute :
    # RSI < 30 → faux PANIQUE, titre projeté en zone basse. "zones" reste vide ici : sans le
    # fichier calibré, la fiche s'abstient (⚪) plutôt que d'inventer une zone.
    return {
        "_fallback": True,
        "CASSURE": {"n": 270, "win_12m": 0.681, "median_net_12m": 0.172,
                    "touched": {"0.10": 0.822, "0.20": 0.685, "0.35": 0.548,
                                "0.50": 0.433, "1.00": 0.196}, "zones": {}},
        "EVEIL": {"n": 940, "win_12m": 0.544, "median_net_12m": 0.037,
                  "touched": {"0.10": 0.745, "0.20": 0.591, "0.35": 0.433,
                              "0.50": 0.331, "1.00": 0.156}, "zones": {}},
        "PANIQUE": {"n": 420, "win_12m": 0.498, "median_net_12m": -0.005,
                    "touched": {"0.10": 0.762, "0.20": 0.564, "0.35": 0.371,
                                "0.50": 0.276, "1.00": 0.11}, "zones": {}},
    }
