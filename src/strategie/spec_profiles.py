"""Profils de spéculation « durée » — détecteurs de schémas + stats calibrées.

Trois schémas éprouvés (épreuves 10 ans, net de frais 2,8 %) :
  CASSURE : le titre dépasse son plus haut des 250 séances (1 an)
  EVEIL   : rebond >= +10 % depuis le creux des 60 séances
  PANIQUE : RSI 14 < 30 (chute récente)

Les statistiques globales (n, taux de réussite, médiane, paliers touchés)
sont CALIBRÉES par scripts/calibrate_spec_profiles.py → data/spec_profiles.json.
"""
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
HORIZON = 252


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
    if closes[i] / creux60 - 1 >= 0.10:
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
    # Fallback : valeurs RE-MESURÉES le 12/11/2026 (cache courant, espacement réparé).
    # L'ancien bloc portait CASSURE n=5 / EVEIL n=28 / PANIQUE n=18 : ces effectifs venaient
    # d'un bug d'espacement (le compteur était partagé entre titres). Après correctif :
    # 257 / 934 / 421 — et les médianes s'effondrent (+105 % -> +18 %, +21 % -> +5 %), ce qui
    # illustre le biais de petit échantillon. "zones" reste vide ici : sans le fichier
    # calibré, la fiche s'abstient (⚪ non concluant) plutôt que d'inventer une zone.
    return {
        "_fallback": True,
        "CASSURE": {"n": 257, "win_12m": 0.673, "median_net_12m": 0.183,
                    "touched": {"0.10": 0.844, "0.20": 0.708, "0.35": 0.568,
                                "0.50": 0.444, "1.00": 0.198}, "zones": {}},
        "EVEIL": {"n": 934, "win_12m": 0.55, "median_net_12m": 0.053,
                  "touched": {"0.10": 0.756, "0.20": 0.6, "0.35": 0.451,
                              "0.50": 0.353, "1.00": 0.175}, "zones": {}},
        "PANIQUE": {"n": 421, "win_12m": 0.511, "median_net_12m": 0.019,
                    "touched": {"0.10": 0.758, "0.20": 0.582, "0.35": 0.399,
                                "0.50": 0.311, "1.00": 0.138}, "zones": {}},
    }
