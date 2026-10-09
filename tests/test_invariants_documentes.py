"""Vérifie que la documentation des invariants ne cite QUE des tests qui existent.

POURQUOI CE TEST EXISTE
-----------------------
En rédigeant `docs/INVARIANTS-METIER.md`, une majorité des noms de tests cités ont été
écrits **de mémoire** et ne correspondaient à rien : le document affirmait « cet invariant
est protégé par tel test » alors que ce test n'existait pas.

C'est le pire état possible pour une documentation de sécurité : elle **rassure à tort**.
Un test absent se voit ; un test fictif cité en référence, non.

Ce test relit le document et confronte chaque nom cité au contenu réel de `tests/`. Un
renommage fait désormais échouer la suite — le document ne peut plus dériver en silence.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOC = RACINE / "docs" / "INVARIANTS-METIER.md"
TESTS = RACINE / "tests"

# Un nom de test cité dans le document : entre accents graves, et commençant par `test_`.
CITATION = re.compile(r"`(test_[a-z0-9_]+)`")


def _tests_reellement_definis() -> set[str]:
    """Tous les noms de tests définis dans tests/, lus depuis la source."""
    definis: set[str] = set()
    for f in TESTS.glob("test_*.py"):
        for m in re.finditer(r"^def (test_[a-z0-9_]+)", f.read_text(encoding="utf-8"),
                             flags=re.MULTILINE):
            definis.add(m.group(1))
    return definis


def _tests_cites() -> set[str]:
    if not DOC.exists():
        pytest.fail(f"document absent : {DOC}")
    return set(CITATION.findall(DOC.read_text(encoding="utf-8")))


def test_le_document_cite_au_moins_un_test():
    """Garde-fou du garde-fou : si l'extraction casse, on le saurait autrement jamais."""
    assert len(_tests_cites()) >= 15, (
        "le document devrait citer au moins 15 tests ; l'extraction est probablement cassée")


def test_chaque_test_cite_existe_reellement():
    """LE test : aucune référence inventée ou périmée dans la documentation."""
    manquants = sorted(_tests_cites() - _tests_reellement_definis())
    assert not manquants, (
        "ces tests sont cités dans docs/INVARIANTS-METIER.md mais n'existent pas "
        "(nom inventé, ou test renommé depuis) :\n  " + "\n  ".join(manquants) +
        "\n\nCorriger le document, ou écrire le test manquant.")


def test_les_invariants_cles_sont_couverts():
    """Les invariants critiques doivent être cités — sinon la liste a un trou silencieux."""
    cites = _tests_cites()
    for nom in ("test_les_frais_ne_sont_pas_confondus",
                "test_aucune_regle_redefinie_ailleurs",
                "test_journal_est_append_only",
                "test_un_titre_sans_cote_ne_fabrique_pas_de_drawdown"):
        assert nom in cites, f"invariant critique absent du document : {nom}"


def test_le_nombre_d_invariants_annonce_est_exact():
    """Le tableau de couverture annonce un total : il ne doit pas être décoratif."""
    if not DOC.exists():
        pytest.skip("document absent")
    texte = DOC.read_text(encoding="utf-8")
    # Lignes du type « | A1 | ... | » dans les tableaux d'invariants.
    codes = re.findall(r"^\| ([A-E]\d+) \|", texte, flags=re.MULTILINE)
    assert len(codes) == 23, (
        f"le document décrit {len(codes)} invariants, mais la couverture annonce 23 — "
        "mettre à jour le tableau de couverture")
    assert len(set(codes)) == len(codes), "un code d'invariant est utilisé deux fois"
