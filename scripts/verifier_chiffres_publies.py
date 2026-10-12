"""Rejeu des chiffres publiés — la version AUTOMATISÉE de la vérification du 12/10/2026.

POURQUOI CE SCRIPT
------------------
Les chiffres qui fondent des décisions (l'attribution des paliers, −45,4 pt — invariant B1)
étaient re-vérifiés à la main : on rejouait les scripts, on relisait les sorties, on
comparait de tête. Ici, la comparaison est PROGRAMMÉE : chaque valeur rejouée est
confrontée à `audit/preuves/chiffres_reference.json`, et tout écart est signalé
(code de sortie 1).

CE QU'IL FAIT
-------------
  1. rejoue les 6 scripts de mesure EN SÉRIE (jamais en parallèle) ;
  2. relit les sorties JSON et les lignes clés des sorties texte ;
  3. compare à la référence ; écrit un rapport daté dans `audit/preuves/` ;
  4. code de sortie 0 (tout colle) ou 1 (au moins un écart).

PORTÉE, LIMITES ET PRÉCAUTIONS
------------------------------
  - ~15 minutes : à la demande (`pytest -m preuve` le déclenche), PAS à chaque poussée —
    le crochet pre-push ne fait que les filets rapides, exprès.
  - **Les scripts de mesure réécrivent `data/` : c'est leur fonction.** Après un rejeu
    propre, `git diff data/` doit être VIDE si les chiffres n'ont pas bougé. Si un écart
    apparaît, les nouveaux fichiers SONT la mesure : à examiner (et à acter dans la
    référence), jamais à écraser en silence.
  - Un chiffre qui ne se reproduit pas n'est pas « faux » : c'est un défaut de traçabilité
    qu'on consigne, puis on passe au suivant.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
REFERENCE = RACINE / "audit" / "preuves" / "chiffres_reference.json"


def _lancer(script: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    """Exécute un script du projet et retourne sa sortie (série : un seul à la fois)."""
    return subprocess.run(
        [sys.executable, str(RACINE / "scripts" / script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RACINE), timeout=timeout,
    )


def _lire_sortie(chemin_relatif: str) -> dict:
    return json.loads((RACINE / chemin_relatif).read_text(encoding="utf-8"))


def _comparer_num(nom: str, valeur, attendu, ecarts: list[str], tolerance: float = 1e-6):
    if valeur is None:
        ecarts.append(f"{nom} : ABSENT de la sortie (attendu {attendu!r})")
        return
    if abs(float(valeur) - float(attendu)) > max(abs(float(attendu)) * tolerance, 1e-9):
        ecarts.append(f"{nom} : {valeur!r} != référence {attendu!r}")


def _dernier_pt(ligne: str) -> float | None:
    """Dernier « +26.2 pt » / « -16.05 pts » d'une ligne de tableau."""
    trouves = re.findall(r"([+-]?\d+(?:\.\d+)?)\s+pts?\b", ligne)
    return float(trouves[-1]) if trouves else None


def _pourcentages(ligne: str) -> list[float]:
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)%", ligne)]


def main() -> int:
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    debut = time.time()
    ecarts: list[str] = []
    journal: list[str] = []

    def note(msg: str):
        journal.append(msg)
        print(msg, flush=True)

    # ── 1. entrée progressive ────────────────────────────────────────────────
    note("── tester_entree_progressive.py")
    r = _lancer("tester_entree_progressive.py")
    _comparer_num("entree_progressive.observations",
                  _lire_sortie(ref["entree_progressive"]["sortie"]).get("observations"),
                  ref["entree_progressive"]["observations"], ecarts)

    # ── 2. renforcement (28 ans) ─────────────────────────────────────────────
    note("── validation_longue.py")
    _lancer("validation_longue.py")
    sortie = _lire_sortie(ref["renforcement"]["sortie"])
    _comparer_num("renforcement.observations", sortie.get("observations"),
                  ref["renforcement"]["observations"], ecarts)
    _comparer_num("renforcement.seuil", sortie.get("seuil"),
                  ref["renforcement"]["seuil"], ecarts)
    _comparer_num("renforcement.tranches", sortie.get("tranches"),
                  ref["renforcement"]["tranches"], ecarts)

    # ── 3. rebalancement ─────────────────────────────────────────────────────
    note("── tester_rebalancement.py")
    _lancer("tester_rebalancement.py")
    sortie = _lire_sortie(ref["rebalancement"]["sortie"])
    for mode, attendu in ref["rebalancement"]["medianes_10_ans"].items():
        _comparer_num(f"rebalancement.10ans.{mode}",
                      sortie.get("medianes", {}).get(mode, {}).get("10"), attendu, ecarts)

    # ── 4. détachements ──────────────────────────────────────────────────────
    note("── mesurer_detachements.py")
    _lancer("mesurer_detachements.py")
    sortie = _lire_sortie(ref["detachements"]["sortie"])
    for champ, attendu in ref["detachements"].items():
        if champ in ("script", "sortie"):
            continue
        _comparer_num(f"detachements.{champ}", sortie.get(champ), attendu, ecarts)

    # ── 5. attribution (sortie TEXTE) ────────────────────────────────────────
    note("── tester_strategie_leo.py")
    r = _lancer("tester_strategie_leo.py")
    texte = r.stdout
    # PIÈGE : le script publie DEUX tableaux avec les mêmes libellés de lignes — les
    # RÉSULTATS (où le 2e % est le revenu/an) puis la NORMALISATION (rendement/expo).
    # On ne lit QUE le bloc NORMALISATION, sinon on capture 10,76 % au lieu de 94,9 %.
    i_norm = texte.find("NORMALISATION")
    zone = texte[i_norm:] if i_norm >= 0 else texte
    lignes = zone.splitlines()
    lu = {"renforcement": None, "paliers": None, "strategie_complete": None}
    for ligne in lignes:
        if "A  noyau passif" in ligne:
            pct = _pourcentages(ligne)
            if len(pct) >= 2:
                _comparer_num("attribution.noyau.rendement_pct", pct[0],
                              ref["attribution"]["noyau"]["rendement_pct"], ecarts)
                _comparer_num("attribution.noyau.exposition_pct", pct[1],
                              ref["attribution"]["noyau"]["exposition_pct"], ecarts)
        if "noyau + renforcement" in ligne and " pt" in ligne:
            lu["renforcement"] = _dernier_pt(ligne)
        if "noyau + paliers" in ligne and " pt" in ligne:
            lu["paliers"] = _dernier_pt(ligne)
        if "strategie complete" in ligne and " pt" in ligne:
            lu["strategie_complete"] = _dernier_pt(ligne)
    for cle, attendu in ref["attribution"]["normalise_vs_noyau_pt"].items():
        _comparer_num(f"attribution.normalise.{cle}", lu.get(cle), attendu, ecarts)

    # ── 6. paliers (3 règles, sortie TEXTE) ──────────────────────────────────
    note("── tester_paliers.py")
    r = _lancer("tester_paliers.py")
    lu = {}
    for ligne in r.stdout.splitlines():
        for mode in ref["paliers_3_regles"]["ecarts_vs_duree_pt"]:
            if re.match(rf"\s*{mode}\s+-?\d", ligne):
                lu[mode] = _dernier_pt(ligne)
    for mode, attendu in ref["paliers_3_regles"]["ecarts_vs_duree_pt"].items():
        _comparer_num(f"paliers_3_regles.{mode}", lu.get(mode), attendu, ecarts)

    # ── Rapport ──────────────────────────────────────────────────────────────
    duree = time.time() - debut
    date = time.strftime("%Y-%m-%d")
    rapport = RACINE / "audit" / "preuves" / f"verification_chiffres_{date}.txt"
    entete = (f"Rejeu des chiffres publiés — {date}\n"
              f"Référence : audit/preuves/chiffres_reference.json\n"
              f"Durée : {duree / 60:.1f} min\n\n")
    if ecarts:
        corps = "ÉCARTS DÉTECTÉS :\n" + "\n".join(f"  ✗ {e}" for e in ecarts) + "\n"
        note(entete + corps + "\n✗ " + str(len(ecarts)) + " écart(s) — les nouveaux "
             "fichiers de data/ SONT la mesure : les examiner, puis acter dans la référence.")
    else:
        corps = "Aucun écart : toutes les valeurs rejouées correspondent à la référence.\n"
        note(entete + "✓ " + corps.strip())
    rapport.write_text(entete + corps, encoding="utf-8")
    note(f"\nRapport écrit : {rapport.relative_to(RACINE)}")
    note(f"Durée totale : {duree / 60:.1f} min")
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
