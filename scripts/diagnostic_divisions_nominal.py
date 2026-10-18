"""Diagnostic des drawdowns aberrants — recherche de divisions de nominal.

Un drawdown de -96 % sur une action BRVM est impossible : cela vient presque
toujours d'une DIVISION DE NOMINAL (split) non ajustee dans l'historique.
Le cours "chute" brutalement d'un rapport rond (1:10, 1:5...) sans que rien
n'ait change pour l'actionnaire.
"""
import json
import pickle
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

with open(HISTORY_BRUT, "rb") as fh:
    hist = pickle.load(fh)

print("=" * 86)
print("  RECHERCHE DE DIVISIONS DE NOMINAL (sauts de cours anormaux)")
print("=" * 86)

RATIOS_SUSPECTS = [2, 3, 4, 5, 10, 20, 50, 100]

suspects = []
for code, barres in sorted(hist.items()):
    closes = [(str(getattr(b, "date", ""))[:10], b.close) for b in barres
              if getattr(b, "close", None)]
    if len(closes) < 20:
        continue
    for i in range(1, len(closes)):
        d0, c0 = closes[i - 1]
        d1, c1 = closes[i]
        if not c0 or not c1:
            continue
        ratio = c0 / c1
        # Saut de -50 % ou plus en une seance
        if ratio >= 2:
            proche = min(RATIOS_SUSPECTS, key=lambda r: abs(r - ratio))
            ecart = abs(proche - ratio) / proche
            suspects.append({
                "code": code, "date": d1, "avant": c0, "apres": c1,
                "ratio": round(ratio, 3), "ratio_rond": proche,
                "ecart_au_ratio": round(ecart * 100, 1),
                "division_probable": ecart < 0.05,
            })

print(f"\n  {len(suspects)} sauts de cours >= 50 % detectes\n")

divisions = [s for s in suspects if s["division_probable"]]
autres = [s for s in suspects if not s["division_probable"]]

print(f"  DONT {len(divisions)} correspondant a un RAPPORT ROND (division probable)")
print(f"  et  {len(autres)} autres (variation reelle ou donnee douteuse)\n")

# --- Titres concernes ---------------------------------------------------
from collections import defaultdict
from src.infrastructure.paths import HISTORY_BRUT, chemin_data  # noqa: E402  (B2-09)
par_code = defaultdict(list)
for s in divisions:
    par_code[s["code"]].append(s)

print("=" * 86)
print("  TITRES AVEC DIVISION DE NOMINAL PROBABLE")
print("=" * 86)
for code, lst in sorted(par_code.items()):
    print(f"\n  {code}  ({len(lst)} division(s))")
    for s in lst:
        print(f"    {s['date']}  {s['avant']:>10,.0f} -> {s['apres']:>9,.0f} F  "
              f"(x{s['ratio']:.2f}  ~1:{s['ratio_rond']})")

# --- Impact --------------------------------------------------------------
print("\n" + "=" * 86)
print("  IMPACT SUR LES STATISTIQUES")
print("=" * 86)
codes_touches = sorted(par_code.keys())
print(f"  {len(codes_touches)} titres sur {len(hist)} sont touches")
print(f"  soit {len(codes_touches) / len(hist) * 100:.0f} % de l'univers")

# Exemple detaille sur le pire cas
if codes_touches:
    pire = max(codes_touches, key=lambda c: len(par_code[c]))
    barres = hist[pire]
    closes = [b.close for b in barres if getattr(b, "close", None)]
    print(f"\n  Exemple — {pire} :")
    print(f"    premier cours : {closes[0]:,.0f} F")
    print(f"    dernier cours : {closes[-1]:,.0f} F")
    print(f"    'perte' apparente : {(closes[-1] / closes[0] - 1) * 100:.1f} %")
    total_ratio = 1
    for s in par_code[pire]:
        total_ratio *= s["ratio_rond"]
    print(f"    ratio cumule des divisions : 1:{total_ratio}")
    print(f"    cours AJUSTE du premier jour : {closes[0] / total_ratio:,.0f} F")
    perf_ajustee = (closes[-1] / (closes[0] / total_ratio) - 1) * 100
    print(f"    performance REELLE : {perf_ajustee:+.1f} %  "
          f"(au lieu de {(closes[-1] / closes[0] - 1) * 100:+.1f} %)")

print("\n" + "=" * 86)
print("  CONCLUSION")
print("=" * 86)
if divisions:
    print("  >>> L'historique N'EST PAS AJUSTE des divisions de nominal.")
    print("  >>> Les statistiques (drawdown, performance) sont FAUSSES.")
    print("  >>> Le jeu de donnees ne doit PAS etre soumis aux modeles en l'etat.")
    print("")
    print("  Correction requise : diviser tous les cours anterieurs a chaque")
    print("  division par le ratio correspondant (reechantillonnage a rebours).")
else:
    print("  Aucune division detectee — verifier une autre cause.")

print("=" * 86)

# --- Export pour correction ---------------------------------------------
sortie = chemin_data("divisions_nominal_detectees.json")
sortie.write_text(json.dumps(divisions, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n  Detail exporte : {sortie.name} ({len(divisions)} entrees)")
