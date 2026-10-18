"""Explore les donnees de Bridge Bank pour preparer le jeu de donnees du challenge.

Objectif : savoir EXACTEMENT ce qu'on a (periode, titres, qualite) avant de
le presenter a des modeles de langage.
"""
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Le pickle contient des objets de src/models.py -> il faut le projet dans le path
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import DATA_DIR, HISTORY_BRUT, chemin_data  # noqa: E402  (B2-09)

print("=" * 80)
print("  INVENTAIRE DES DONNEES — BRIDGE BANK")
print("=" * 80)

# ---------------------------------------------------------------- fichiers
print("\n" + "-" * 80)
print("  1. FICHIERS DE DONNEES")
print("-" * 80)
for f in sorted(DATA_DIR.glob("*")):
    if f.is_dir() or f.name.startswith(".hermes"):
        continue
    taille = f.stat().st_size
    unite = f"{taille / 1024:.1f} Ko" if taille > 1024 else f"{taille} o"
    print(f"  {f.name:34} {unite:>12}")

# ---------------------------------------------------------------- historique
print("\n" + "-" * 80)
print("  2. HISTORIQUE DE COURS (history_cache.pkl)")
print("-" * 80)
pkl = HISTORY_BRUT
if pkl.exists():
    with open(pkl, "rb") as fh:
        hist = pickle.load(fh)
    print(f"  type racine : {type(hist).__name__}")
    if isinstance(hist, dict):
        codes = list(hist.keys())
        print(f"  nombre de titres : {len(codes)}")
        print(f"  codes : {', '.join(sorted(codes)[:30])}")

        # Bornes de periode, en gerant les differents formats de barres
        premieres, dernieres, volumes = [], [], []
        for code, barres in hist.items():
            if not barres:
                continue
            def _date(b):
                for attr in ("date", "day", "timestamp", "t"):
                    v = getattr(b, attr, None) if not isinstance(b, dict) else b.get(attr)
                    if v is not None:
                        return str(v)[:10]
                return None
            d0, d1 = _date(barres[0]), _date(barres[-1])
            if d0:
                premieres.append(d0)
            if d1:
                dernieres.append(d1)
            volumes.append(len(barres))

        if premieres:
            print(f"  periode couverte : {min(premieres)} -> {max(dernieres)}")
        if volumes:
            print(f"  seances par titre : min={min(volumes)} max={max(volumes)} "
                  f"moyenne={sum(volumes) / len(volumes):.0f}")
            print(f"  TOTAL barres      : {sum(volumes):,}".replace(",", " "))

        # Exemple de structure
        ex_code = sorted(hist.keys())[0]
        ex = hist[ex_code][0]
        print(f"\n  structure d'une barre ({ex_code}) :")
        if isinstance(ex, dict):
            for k, v in list(ex.items())[:12]:
                print(f"    {k:14} = {v}")
        else:
            for champ in ("code", "date", "open", "high", "low", "close", "volume"):
                if hasattr(ex, champ):
                    print(f"    {champ:14} = {getattr(ex, champ)}")
else:
    print("  ABSENT")

# ---------------------------------------------------------------- autres caches
print("\n" + "-" * 80)
print("  3. AUTRES CACHES")
print("-" * 80)
for nom, desc in [("fundamentals_cache.json", "fondamentaux"),
                  ("per_cache.json", "PER"),
                  ("magic_formula_brvm.json", "magic formula"),
                  ("bonds_market.json", "obligations"),
                  ("madis_seen_state.json", "etat MADIS")]:
    p = chemin_data(nom)
    if not p.exists():
        print(f"  {nom:30} absent")
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            n = len(d)
            ex = list(d.items())[:3]
            print(f"  {nom:30} dict de {n} entrees — {desc}")
            for k, v in ex:
                vs = str(v)[:70]
                print(f"      {k}: {vs}")
        elif isinstance(d, list):
            print(f"  {nom:30} liste de {len(d)} elements — {desc}")
        else:
            print(f"  {nom:30} {type(d).__name__}")
    except Exception as e:
        print(f"  {nom:30} illisible ({str(e)[:40]})")

# ---------------------------------------------------------------- obligations
print("\n" + "-" * 80)
print("  4. MARCHE OBLIGATAIRE")
print("-" * 80)
b = chemin_data("bonds_market.json")
if b.exists():
    try:
        d = json.loads(b.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            for k, v in list(d.items())[:8]:
                print(f"  {k}: {str(v)[:80]}")
        else:
            print(f"  {type(d).__name__} — {len(d)} elements")
    except Exception as e:
        print(f"  illisible : {e}")

print("\n" + "=" * 80)
print("  FIN DE L'INVENTAIRE")
print("=" * 80)
