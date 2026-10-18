"""Non-régression des CHIFFRES PUBLIÉS — les valeurs qui fondent des décisions.

Pourquoi ce fichier existe (priorité n°1 de la passation du 12/10/2026) : les chiffres
publiés dans le rapport 28 ans (et l'invariant B1 : « un seuil non significatif ne
déclenche jamais une vente ») reposaient sur une vérification MANUELLE. Ici :

  1. tests RAPIDES (suite standard) — la chaîne référence → sorties versionnées → documents :
     si une sortie de `data/` bouge sans que la référence soit atualisée, ça casse ;
     si un document cesse de citer le chiffre qui fonde une règle, ça casse.
  2. un test REJEU (marqué `preuve`, exclu par défaut) — relance les 6 scripts de mesure
     en série (~15 min) et compare au fichier de référence. C'est `pytest -m preuve`.

Un contrôle qui ne peut pas échouer ne prouve rien : ce dispositif a été vérifié en le
cassant volontairement (fr. la note du 12/10 dans audit/chiffres_publies_verifies.md).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
REFERENCE = json.loads(
    (RACINE / "audit" / "preuves" / "chiffres_reference.json").read_text(encoding="utf-8"))


def _sortie(mesure: str) -> dict:
    return json.loads((RACINE / REFERENCE[mesure]["sortie"]).read_text(encoding="utf-8"))


# ═══════════════════ la référence elle-même ══════════════════════════════════════════

def test_la_reference_porte_sa_provenance():
    """Toute mesure publiée porte sa provenance : date, preuves brutes, documents."""
    prov = REFERENCE["_provenance"]
    assert prov["date"] == "2026-10-13"
    preuves = RACINE / "audit" / "preuves"
    assert preuves.is_dir()
    assert list(preuves.glob("remesure_*.txt")), "les preuves brutes de re-mesure existent"
    assert (RACINE / "audit" / "chiffres_publies_verifies.md").exists()
    assert (RACINE / "docs" / "INVARIANTS-METIER.md").exists()
    # Chaque mesure renvoie à SON script ; celles qui écrivent un JSON portent aussi leur
    # sortie. L'attribution et les paliers (3 règles) publient en sortie TEXTE : script seul.
    for mesure, bloc in REFERENCE.items():
        if mesure.startswith("_"):
            continue
        assert bloc["script"].startswith("scripts/"), mesure
        if "sortie" in bloc:
            assert bloc["sortie"].startswith("data/"), mesure  # noqa: chemin-relatif (FORMAT de sortie)


# ═══════════════════ sorties versionnées == référence ════════════════════════════════

def test_entree_progressive_conforme_a_la_reference():
    s = _sortie("entree_progressive")
    assert s["observations"] == REFERENCE["entree_progressive"]["observations"]


def test_renforcement_conforme_a_la_reference():
    s = _sortie("renforcement")
    assert s["observations"] == REFERENCE["renforcement"]["observations"]
    assert s["seuil"] == pytest.approx(REFERENCE["renforcement"]["seuil"])
    assert s["tranches"] == REFERENCE["renforcement"]["tranches"]


def test_rebalancement_conforme_a_la_reference():
    s = _sortie("rebalancement")
    for mode, attendu in REFERENCE["rebalancement"]["medianes_10_ans"].items():
        assert s["medianes"][mode]["10"] == pytest.approx(attendu), mode


def test_detachements_conforme_a_la_reference():
    s = _sortie("detachements")
    for champ in ("n", "baisse_mediane_pct", "capture_mediane_pct",
                  "perte_pct_cas", "ratio_signal_bruit"):
        assert s[champ] == pytest.approx(REFERENCE["detachements"][champ]), champ


# ═══════════════════ documents == référence (la chaîne de décision) ══════════════════

def test_l_invariant_b1_cite_le_chiffre_re_mesure():
    """L'invariant B1 est aligné sur la mesure re-mesurée (hiérarchie des sources :
    la source perdante est mise à jour, jamais laissée divergente)."""
    invariant = (RACINE / "docs" / "INVARIANTS-METIER.md").read_text(encoding="utf-8")
    ligne_b1 = next((l for l in invariant.splitlines() if l.startswith("| B1 |")), "")
    assert "42,9 pt" in ligne_b1, "B1 doit citer la re-mesure du 13/10 après le lot 9 (42,9 pt)"
    assert REFERENCE["attribution"]["normalise_vs_noyau_pt"]["paliers"] == pytest.approx(-42.9)


def test_le_document_de_verification_cite_les_valeurs_cles():
    """Le document qui acte la re-mesure doit citer les mêmes chiffres que la référence
    (une divergence document ↔ mesure casse ici). Les anciens chiffres (45,4 / 49,0 /
    +26,7) restent exigés : l'historique daté ne disparaît pas."""
    for chemin, motifs in (
        ("audit/chiffres_publies_verifies.md",
         (r"43\s227", r"5\s196", r"182\s+cas", r"45,4", r"49,0", r"42,9", r"16,1")),
        ("docs/RAPPORT-VALIDATION-28-ANS.md",
         (r"43\s227", r"5\s196", r"45,4", r"49,0", r"\+26,7", r"42,9", r"16,1")),
    ):
        texte = (RACINE / chemin).read_text(encoding="utf-8")
        for motif in motifs:
            assert re.search(motif, texte), f"{chemin} : chiffre manquant ({motif})"


# ═══════════════════ le rejeu complet (lent, à la demande) ═══════════════════════════

@pytest.mark.preuve
def test_rejeu_complet_des_chiffres_publies():
    """Relance les 6 scripts de mesure et compare à la référence (~15 min).

    Lancer : `pytest -m preuve -s`. Un écart => sortie 1 du script => test rouge :
    c'est la version automatisée de la vérification manuelle du 12/10/2026."""
    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts" / "verifier_chiffres_publies.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RACINE), timeout=3600,
    )
    assert r.returncode == 0, (
        "écart détecté par le rejeu — voir le rapport dans audit/preuves/ :\n" + r.stdout[-4000:])
