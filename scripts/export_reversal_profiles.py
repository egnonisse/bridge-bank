"""Exporte les profils de retournement, AU SEUIL PROPRE DE CHAQUE TITRE.

POURQUOI CE SCRIPT A ÉTÉ RÉÉCRIT (09/10/2026)
---------------------------------------------
Il mesurait tous les titres sur un seuil unique de +13 %, avec une définition d'épisode
DIFFÉRENTE de celle du seuil de vente :

    profil (avant) : hausse entre 13 % et 65 %, espacement de 10 séances
    seuil  (vente) : hausse >= seuil du titre, espacement de 20 séances, sans plafond

D'où DEUX chiffres pour une même notion — SNTS affichait « 86 % sur 7 cas » (seuil) puis
« 90 % sur 10 cas » (profil), et SLBC recevait une statistique mesurée à +13 % (39 %) alors
que son propre seuil donne 54 %.

MAINTENANT : une seule définition, celle de `src/seuils_vente.py` — donc celle qui DÉCIDE.

    hausse >= seuil du titre sur 20 séances, fenêtres disjointes (espacement de 20)

Trois choix, chacun justifié :

  1. **Fenêtres disjointes (espacement 20)** plutôt que 10 : deux épisodes à 10 séances
     d'écart partagent la moitié de leur fenêtre — ils ne sont pas indépendants. Espacer de
     10 gonfle le nombre de cas (SNTS 7 -> 10) sans apporter d'information, ce qui donne
     l'illusion d'une preuve plus solide. *Davantage de cas n'est pas une meilleure preuve.*

  2. **Pas de borne haute** : l'alerte se déclenche dès que le seuil est franchi, quelle que
     soit l'ampleur. Décrire la situation avec des cas plafonnés à +65 % décrirait autre
     chose que ce que l'utilisateur observe. (Mesuré : la borne ne changeait quasiment rien
     — 10/10, 42/42, 67/67, 87/88 — donc la retirer ne coûte rien.)

  3. **Borne basse de Wilson publiée** : un taux observé seul se lit comme une probabilité
     de baisse future. Sur 7 cas à 86 %, la borne basse est 49 % — indiscernable du hasard.
     Le profil porte donc le même verdict statistique que le seuil, plus un drapeau `fiable`.

La probabilité (J+20) est calculée sur EXACTEMENT les mêmes épisodes que le seuil de vente :
les deux chiffres ne peuvent plus diverger. Les statistiques descriptives (J+5/J+60, délai et
profondeur du creux) portent sur les épisodes disposant d'assez de recul — leur effectif est
publié séparément (`episodes_60j`).

    python scripts/export_reversal_profiles.py
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.cache_integrity import cache_signature
from src.calibration import seuils_vente as sv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reversal_profiles.json"

MIN_EPISODES = sv.MIN_EPISODES        # 8 — seuil de SIGNIFICATIVITÉ (regles.py)
MIN_EPISODES_PUBLICATION = 5          # 5 — seuil de PUBLICATION (décrire un creux en a
                                      #     besoin, pas de conclure sur une probabilité)
HORIZON_DESCRIPTIF = 60               # recul nécessaire pour le creux et J+60

# Deux seuils, parce que ce sont deux questions différentes :
#   - PUBLIER ? « a-t-on de quoi décrire ce qui suit une hausse ? » → 5 cas suffisent
#   - CONCLURE ? « le taux bat-il le hasard ? » → 8 cas ET borne basse >= 50 %
# Les confondre privait SNTS (7 cas) de toute description, alors que son creux médian est
# une information utile même sur 7 cas. Le champ `significatif` tranche à l'affichage.

DEFINITION = ("hausse >= seuil du titre en 20 seances, "
              "fenetres disjointes (espacement 20), sans borne haute")


def _profil_titre(closes: list[float], seuil: float) -> dict | None:
    """Profil d'un titre, mesuré à SON seuil, avec la définition du seuil de vente."""
    idx = sv.indices_episodes(closes, seuil)
    if not idx:
        return None
    n_ep = len(idx)

    f5 = [closes[i + 5] / closes[i] - 1 for i in idx]
    f20 = [closes[i + 20] / closes[i] - 1 for i in idx]
    k = sum(1 for f in f20 if f < 0)
    p, borne_basse, _ = sv.intervalle_wilson(k, n_ep)

    profil: dict = {
        "seuil_pct": round(seuil * 100),
        "episodes": n_ep,
        "pct_down_20j": round(p * 100),
        "borne_basse": round(borne_basse * 100),
        "significatif": bool(n_ep >= MIN_EPISODES and borne_basse >= sv.BORNE_BASSE_MIN),
        "median_5j": round(statistics.median(f5) * 100, 1),
        "median_20j": round(statistics.median(f20) * 100, 1),
    }

    # Statistiques descriptives : sous-ensemble ayant 60 séances de recul.
    idx60 = [i for i in idx if i + HORIZON_DESCRIPTIF < len(closes)]
    if idx60:
        f60 = [closes[i + HORIZON_DESCRIPTIF] / closes[i] - 1 for i in idx60]
        delais, creux = [], []
        for i in idx60:
            fut = closes[i + 1:i + HORIZON_DESCRIPTIF + 1]
            jmin = min(range(len(fut)), key=lambda j: fut[j])
            delais.append(jmin + 1)
            creux.append(fut[jmin] / closes[i] - 1)
        profil.update({
            "episodes_60j": len(idx60),
            "median_60j": round(statistics.median(f60) * 100, 1),
            "trough_delay_median": round(statistics.median(delais)),
            "trough_depth_median": round(statistics.median(creux) * 100, 1),
            "trough_depth_worst": round(min(creux) * 100, 1),
        })
    return profil


def main() -> int:
    hist_all = load_all_history(BSApi(), force=False)
    seuils = sv.charger()
    profils: dict = {}
    ignores = 0

    for code, bars in hist_all.items():
        if len(bars) < 140:
            continue
        closes = [float(b.close) for b in bars]
        seuil = float(seuils.get(code, {}).get(
            "threshold", sv.SEUILS_PAR_DEFAUT.get(code, 0.13)))

        # Publication : assez de cas pour DÉCRIRE (le creux, le délai), pas pour conclure.
        # Le champ `significatif` (calculé sur MIN_EPISODES + Wilson) décide de l'affichage.
        if len(sv.indices_episodes(closes, seuil)) < MIN_EPISODES_PUBLICATION:
            ignores += 1
            continue

        profil = _profil_titre(closes, seuil)
        if profil:
            profils[code] = profil

    OUT.write_text(
        json.dumps({"_meta": {
            "definition": DEFINITION,
            "fenetre": "20 seances",
            "espacement": 20,
            "borne_haute": None,
            "horizon_probabilite": 20,
            "horizon_descriptif": HORIZON_DESCRIPTIF,
            "min_episodes": MIN_EPISODES,
            "cache_signature": cache_signature(hist_all),
        }, **profils}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"{len(profils)} profils exportes ({ignores} titres ignores, < {MIN_EPISODES} cas)")
    print(f"  -> {OUT}")
    print()
    print(f"{'titre':7s}{'seuil':>7s}{'cas':>5s}{'baisse':>8s}{'borne':>7s}  {'fiable':6s}{'creux':>8s}")
    for code, p in sorted(profils.items()):
        creux = f"{p.get('trough_depth_median', 0)}%" if "trough_depth_median" in p else "-"
        print(f"{code:7s}{p['seuil_pct']:>6d}%{p['episodes']:>5d}{p['pct_down_20j']:>7d}%"
              f"{p['borne_basse']:>6d}%  {'oui' if p['significatif'] else 'non':6s}{creux:>8s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
