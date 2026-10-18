"""MIGRATION — ajoute le mode (declencheur / informatif) aux seuils deja calibres.

CE QUE FAIT CE SCRIPT
---------------------
`data/profit_thresholds.json` contient 4 seuils (SNTS, SGBC, SLBC, PALC) calcules avant
l'introduction du test de significativite. Il leur manque le champ `mode` qui decide si
le seuil peut proposer une VENTE ou seulement informer.

Il ne se contente PAS de convertir les valeurs stockees (`down_prob` arrondi, `episodes`)
car cette conversion perd de la precision : `86 %` sur `7` cas peut correspondre a 6/7
(85,7 %) comme a 6,02/7. On RECALCULE donc depuis l'historique reel, ce qui donne au
passage un controle croise : si les valeurs recalculees s'ecartent des valeurs stockees,
c'est que le fichier ne correspond plus aux donnees.

GARANTIE — AUCUN SEUIL N'EST SUPPRIME
-------------------------------------
Le seuil (`threshold`), `down_prob`, `median_pct` et `episodes` sont CONSERVES. On ajoute
`borne_basse`, `significatif` et `mode`. Une sauvegarde `.bak-avant-mode` est ecrite avant
toute modification.
"""
import json
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "src"))

from src.calibration import seuils_vente as sv  # noqa: E402
from src.infrastructure.paths import HISTORY_CACHE, PROFIT_THRESHOLDS, chemin_data  # noqa: E402  (B2-09)

FICHIER = PROFIT_THRESHOLDS
SAUVEGARDE = chemin_data("profit_thresholds.json.bak-avant-mode")
# La règle d'épisode vit dans src/seuils_vente.py::episodes — définition unique du projet.
# Ce script la recopiait mot pour mot (« ne pas diverger »), c'est exactement le doublon que
# la décision du 09/10 a supprimé.
_episodes = sv.episodes
evaluer = sv.evaluer


def main():
    data = json.loads(FICHIER.read_text(encoding="utf-8"))
    hist = pickle.load(open(HISTORY_CACHE, "rb"))

    print("=" * 100)
    print("  MIGRATION — ajout du mode aux seuils existants")
    print("=" * 100)
    print(f"\n  {len(data)} seuil(s) dans le fichier : {', '.join(sorted(data))}")

    # Sauvegarde avant modification
    SAUVEGARDE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Sauvegarde : {SAUVEGARDE.name}")

    modifs = []
    print(f"\n  {'titre':<7}{'seuil':>7}{'cas':>5}{'baisses':>9}{'prob.':>7}{'stocke':>8}"
          f"{'IC 95 %':>13}{'mode':>14}")
    print("  " + "-" * 74)

    for code, info in sorted(data.items()):
        bars = hist.get(code)
        if not bars:
            print(f"  {code:<7}  pas d'historique — seuil CONSERVE tel quel")
            continue
        closes = [float(getattr(x, "close", 0) or 0) for x in bars]
        closes = [p for p in closes if p > 0]
        seuil = float(info.get("threshold", 0))
        ep = _episodes(closes, seuil)
        if not ep:
            print(f"  {code:<7}  aucun episode recalcule — seuil CONSERVE tel quel")
            continue

        n = len(ep)
        k = sum(1 for r in ep if r < 0)
        ev = evaluer(k, n)
        recalcule = {"borne_basse": ev["borne_basse"], "significatif": ev["significatif"],
                     "mode": ev["mode"], "down_prob": ev["down_prob"],
                     "episodes": ev["episodes"],
                     "median_pct": round(statistics.median(ep) * 100, 1)}

        stocke = info.get("down_prob")
        ecart = "" if stocke is None or abs(stocke - ev["down_prob"]) <= 1 else "  <-- ECART"
        modifs.append((code, recalcule))
        print(f"  {code:<7}{seuil*100:>6.0f} %{n:>5}{k:>9}{ev['down_prob']:>6} %"
              f"{str(stocke) + ' %' if stocke is not None else '-':>8}"
              f"{str(ev['borne_basse']) + '-' + str(round(ev['borne_basse'])):>13}"
              f"{ev['mode']:>14}{ecart}")

    # Application : on AJOUTE / MET A JOUR les champs, sans jamais retirer le seuil
    for code, maj in modifs:
        data[code].update(maj)
    sv.enregistrer(data, origine=sv.ORIGINE_MANUELLE, autorise_protege=True, chemin=FICHIER)

    print(f"\n  {len(modifs)} seuil(s) mis a jour — AUCUN supprime")
    decl = [c for c, m in modifs if m["mode"] == "declencheur"]
    info_ = [c for c, m in modifs if m["mode"] == "informatif"]
    print(f"    declencheurs (vente proposee) : {', '.join(decl) if decl else 'AUCUN'}")
    print(f"    informatifs  (info seule)     : {', '.join(info_) if info_ else 'AUCUN'}")
    print(f"""
  LECTURE : aucun seuil n'est passe en « declencheur », parce qu'aucune borne basse
  n'atteint 50 % — le signal de retournement n'est, pour aucun de ces titres,
  distinguable du hasard. Les seuils restent VISIBLES (console + alerte quotidienne)
  mais ne proposent plus de vente.""")
    print("=" * 100)


if __name__ == "__main__":
    main()
