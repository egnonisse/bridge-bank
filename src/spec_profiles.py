"""Profils de spéculation « durée » — détecteurs de schémas + stats calibrées.

Trois schémas éprouvés (épreuves 10 ans, net de frais 2,8 %) :
  CASSURE : le titre dépasse son plus haut des 250 séances (1 an)
  EVEIL   : rebond >= +10 % depuis le creux des 60 séances
  PANIQUE : RSI 14 < 30 (chute récente)

Les statistiques globales (n, taux de réussite, médiane, paliers touchés)
sont CALIBRÉES par scripts/calibrate_spec_profiles.py → data/spec_profiles.json.
"""
import json
import statistics
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
PROFILES_FILE = DATA / "spec_profiles.json"

ZONE_FORCE = (0.80, 1.01)   # zone de force (83 % de réussite)
ZONE_HAUT_FRAGILE = (0.60, 0.80)  # danger (0 % gagnants)
ZONE_BAS_SOLIDE = (0.20, 0.40)    # bas sans être écrasé (80 %)
ZONE_BAS_ECRASE = (0.0, 0.20)     # piège (50 %)

FRAIS = 0.028
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
            vol_ok = med <= 0 or volumes[i] >= med
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
            vol_ok = med <= 0 or volumes[i] >= med
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
    """Stats calibrées par schéma (fallback : stats historiques figées)."""
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback : valeurs des épreuves (16-17/09/2026)
    return {
        "CASSURE": {"n": 10, "win_12m": 0.70, "median_net_12m": 0.569,
                    "touched": {"0.10": 0.90, "0.20": 0.80, "0.35": 0.70,
                                "0.50": 0.70, "1.00": 0.30}},
        "EVEIL": {"n": 29, "win_12m": 0.59, "median_net_12m": 0.172,
                  "touched": {}},
        "PANIQUE": {"n": 17, "win_12m": 0.59, "median_net_12m": 0.153,
                    "touched": {}},
        "ZONES": {"BAS_ECRASE": {"win": 0.50, "median": 0.035},
                  "BAS_SOLIDE": {"win": 0.80, "median": 0.247},
                  "MILIEU": {"win": 1.00, "median": 0.443},
                  "HAUT_FRAGILE": {"win": 0.00, "median": -0.388},
                  "FORCE": {"win": 0.83, "median": 0.624}},
    }
