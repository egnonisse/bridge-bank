#!/usr/bin/env python
"""Réconciliation du cache de cours avec les Bulletins Officiels de la Cote (BOC).

POURQUOI CE SCRIPT EXISTE
-------------------------
Un auditeur externe a relevé que les cours utilisés par le projet ne sont pas
horodatés dans les fiches et que ses propres relevés diffèrent des nôtres.
Ce script mesure, SANS RÉSEAU, ce que le cache local contient réellement pour
une liste de titres, et le compare à des valeurs de référence fournies
(BOC BRVM). Il distingue :

  - MESURÉ localement : date de la dernière barre du cache, clôture, volume,
    valeur échangée (clôture × volume, approximation — le BOC publie la valeur
    réellement échangée, qui diffère légèrement).
  - COMPARÉ : écart en % entre le cache et la référence à la MÊME date.

La source lue est le cache CANONIQUE (history_clean.pkl, celui des décisions),
via charger_cache() qui vérifie l'empreinte SHA-256. Option --brut pour lire
le cache brut. Pour les titres listés, la dernière barre des deux caches est
identique (les divisions n'affectent que les barres ANTÉRIEURES à l'opération).

Aucun import de BSApi ni aucun appel HTTP : exécutable hors ligne.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from src.collecte.history_io import charger_cache  # noqa: E402
from src.infrastructure.paths import HISTORY_BRUT, HISTORY_CACHE  # noqa: E402

TITRES_PAR_DEFAUT = ["ORGT", "TTLC", "SNTS", "PALC", "SGBC"]

# --------------------------------------------------------------------------
# Valeurs de référence par défaut : Bulletins Officiels de la Cote (BRVM),
# relevées le 12/11/2026 sur les PDF officiels brvm.org (boc_YYYYMMDD_2.pdf)
# pour les séances des 09, 10 et 11/11, et sur la page « cours-actions » de
# brvm.org (mise à jour du jeudi 12/11) pour la séance du 12/11, dont le PDF
# BOC n'était PAS encore publié au moment du contrôle (HTTP 404 sur
# boc_20261112_2.pdf). Ces valeurs sont injectables/remplaçables via --ref.
# --------------------------------------------------------------------------
REFERENCES_PAR_DEFAUT: dict[str, dict[str, dict[str, float]]] = {
    "ORGT": {
        "2026-11-09": {"close": 2650.0, "volume": 646, "source": "BOC 09/11 (PDF brvm.org)"},
        "2026-11-10": {"close": 2505.0, "volume": 1466, "source": "BOC 10/11 (PDF brvm.org)"},
        "2026-11-11": {"close": 2550.0, "volume": 284, "source": "BOC 11/11 (PDF brvm.org)"},
        "2026-11-12": {"close": 2560.0, "volume": 1542, "source": "brvm.org cours-actions 12/11 (BOC non publié)"},
    },
    "TTLC": {
        "2026-11-09": {"close": 3030.0, "volume": 4470, "source": "BOC 09/11 (PDF brvm.org)"},
        "2026-11-10": {"close": 3030.0, "volume": 7127, "source": "BOC 10/11 (PDF brvm.org)"},
        "2026-11-11": {"close": 3015.0, "volume": 1644, "source": "BOC 11/11 (PDF brvm.org)"},
        "2026-11-12": {"close": 3095.0, "volume": 2656, "source": "brvm.org cours-actions 12/11 (BOC non publié)"},
    },
    "SNTS": {
        "2026-11-09": {"close": 4150.0, "volume": 105946, "source": "BOC 09/11 (PDF brvm.org)"},
        "2026-11-10": {"close": 4000.0, "volume": 270403, "source": "BOC 10/11 (PDF brvm.org)"},
        "2026-11-11": {"close": 4190.0, "volume": 85624, "source": "BOC 11/11 (PDF brvm.org)"},
        "2026-11-12": {"close": 4195.0, "volume": 231018, "source": "brvm.org cours-actions 12/11 (BOC non publié)"},
    },
    "PALC": {
        "2026-11-09": {"close": 7600.0, "volume": 13342, "source": "BOC 09/11 (PDF brvm.org)"},
        "2026-11-10": {"close": 7595.0, "volume": 5782, "source": "BOC 10/11 (PDF brvm.org)"},
        "2026-11-11": {"close": 7590.0, "volume": 635, "source": "BOC 11/11 (PDF brvm.org)"},
        "2026-11-12": {"close": 7645.0, "volume": 7679, "source": "brvm.org cours-actions 12/11 (BOC non publié)"},
    },
    "SGBC": {
        "2026-11-09": {"close": 39000.0, "volume": 6089, "source": "BOC 09/11 (PDF brvm.org)"},
        "2026-11-10": {"close": 38900.0, "volume": 2721, "source": "BOC 10/11 (PDF brvm.org)"},
        "2026-11-11": {"close": 38600.0, "volume": 1126, "source": "BOC 11/11 (PDF brvm.org)"},
        "2026-11-12": {"close": 38890.0, "volume": 3570, "source": "brvm.org cours-actions 12/11 (BOC non publié)"},
    },
}


# ---------------------------------------------------------------------- CLI
def _parse_ref_arg(texte: str) -> tuple[str, str, dict[str, float]]:
    """« CODE|AAAA-MM-JJ|close|volume » -> (code, date, {close, volume})."""
    morceaux = texte.split("|")
    if len(morceaux) != 4:
        raise SystemExit(
            f"--ref mal formé : « {texte} » — attendu CODE|AAAA-MM-JJ|close|volume")
    code, date, close_s, vol_s = morceaux
    try:
        datetime.strptime(date, "%Y-%m-%d")
        close = float(close_s)
        volume = float(vol_s)
    except ValueError as exc:
        raise SystemExit(f"--ref mal formé : « {texte} » — {exc}") from exc
    return code.strip().upper(), date, {"close": close, "volume": volume,
                                        "source": "injecté via --ref"}


def _merger_refs(arg: argparse.Namespace) -> dict[str, dict[str, dict[str, float]]]:
    """Références finales : défaut + fichier JSON + --ref inline (par ordre)."""
    refs: dict[str, dict[str, dict[str, float]]] = (
        {} if arg.no_defaults else json.loads(json.dumps(REFERENCES_PAR_DEFAUT)))

    if arg.ref_file:
        with open(arg.ref_file, encoding="utf-8") as fh:
            ajout = json.load(fh)
        for code, par_date in ajout.items():
            refs.setdefault(code.upper(), {}).update(par_date)

    for texte in arg.ref or []:
        code, date, val = _parse_ref_arg(texte)
        refs.setdefault(code, {})[date] = val
    return refs


def _ecart_pct(observe: float, reference: float) -> float | None:
    if reference in (None, 0.0):
        return None
    return (observe - reference) / reference * 100.0


def _fmt(value: float | None, ndigits: int = 0) -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value == int(value):
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.{ndigits}f}".replace(",", " ")


def _date_barre(bar) -> str:
    return bar.date.strftime("%Y-%m-%d")


def _charger(arg: argparse.Namespace) -> dict:
    chemin = HISTORY_BRUT if arg.brut else HISTORY_CACHE
    return charger_cache(chemin)


def _derniere_barre(hist: dict, code: str):
    bars = hist.get(code) or hist.get(code.lower())
    if not bars:
        return None
    return bars[-1]


def afficher_titres(arg: argparse.Namespace, hist: dict, refs: dict,
                    aujourdhui: datetime) -> None:
    print("Titre | Dernière séance (cache) | Clôture | Volume | Valeur éch.≈ | "
          "Réf. clôture (même date) | Δ clôture | Réf. volume | Δ volume | "
          "Retard (j) | Réf. la + récente")
    print("-" * 150)
    for code in arg.codes:
        code = code.strip().upper()
        bar = _derniere_barre(hist, code)
        if bar is None:
            print(f"{code:5} | ABSENT DU CACHE")
            continue
        date = _date_barre(bar)
        valeur = bar.close * bar.volume
        retard = (aujourdhui - bar.date).days
        ref_par_date = refs.get(code, {})
        ref_meme_date = ref_par_date.get(date)
        dates_refs = [d for d in ref_par_date]
        derniere_ref = max(dates_refs) if dates_refs else None

        ref_close = ref_meme_date.get("close") if ref_meme_date else None
        ref_vol = ref_meme_date.get("volume") if ref_meme_date else None
        d_close = _ecart_pct(bar.close, ref_close)
        d_vol = _ecart_pct(bar.volume, ref_vol)

        d_close_s = f"{d_close:+.2f} %" if d_close is not None else "pas de réf."
        d_vol_s = f"{d_vol:+.2f} %" if d_vol is not None else "pas de réf."
        ref_close_s = _fmt(ref_close) if ref_close is not None else "—"
        ref_vol_s = _fmt(ref_vol, 0) if ref_vol is not None else "—"

        print(f"{code:5} | {date} | {_fmt(bar.close)} | {_fmt(bar.volume)} | "
              f"{_fmt(valeur)} | {ref_close_s} | {d_close_s} | {ref_vol_s} | "
              f"{d_vol_s} | {retard} | {derniere_ref or '—'} "
              f"{('(plus récente que le cache)' if derniere_ref and derniere_ref > date else '')}")


def afficher_distribution(hist: dict, aujourdhui: datetime) -> None:
    """Retard (jours civils) de la dernière barre pour TOUS les titres du cache."""
    from collections import Counter
    compteur: Counter = Counter()
    par_date: dict[str, list[str]] = {}
    for code, bars in sorted(hist.items()):
        if not bars:
            continue
        retard = (aujourdhui - bars[-1].date).days
        compteur[retard] += 1
        par_date.setdefault(_date_barre(bars[-1]), []).append(code)

    max_retard = max(compteur) if compteur else 0
    print(f"\n=== Distribution du retard (dernière barre vs aujourd'hui, {aujourdhui:%Y-%m-%d}) ===")
    print(f"{len(hist)} titres dans le cache ; retard max {max_retard} j.")
    for retard in sorted(compteur):
        n = compteur[retard]
        print(f"  retard {retard:3} j : {n:2} titre(s)")
    print("\nDétail par date de dernière barre :")
    for date in sorted(par_date):
        liste = par_date[date]
        print(f"  {date} : {len(liste)} titre(s) — {', '.join(sorted(liste))}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Réconcilie le cache de cours local avec les BOC BRVM (hors ligne).")
    ap.add_argument("codes", nargs="*", default=TITRES_PAR_DEFAUT,
                    help="codes des titres (défaut : %s)" % " ".join(TITRES_PAR_DEFAUT))
    ap.add_argument("--brut", action="store_true",
                    help="lire history_cache.pkl (brut) au lieu de history_clean.pkl (propre)")
    ap.add_argument("--ref-file", help="fichier JSON {CODE: {DATE: {close, volume}}}")
    ap.add_argument("--ref", action="append", default=None,
                    help="référence inline CODE|AAAA-MM-JJ|close|volume (répétable)")
    ap.add_argument("--no-defaults", action="store_true",
                    help="ignorer les références par défaut embarquées")
    ap.add_argument("--distribution", action="store_true",
                    help="afficher la distribution du retard pour TOUS les titres")
    arg = ap.parse_args()

    if not arg.codes:
        arg.codes = TITRES_PAR_DEFAUT

    hist = _charger(arg)
    refs = _merger_refs(arg)
    aujourdhui = datetime.now()

    afficher_titres(arg, hist, refs, aujourdhui)
    if arg.distribution:
        afficher_distribution(hist, aujourdhui)


if __name__ == "__main__":
    main()
