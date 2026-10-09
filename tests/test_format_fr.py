"""Tests du formatage des nombres à la française.

Le piège que ces tests verrouillent : Python écrit `3,784` pour trois mille sept cent
quatre-vingt-quatre. Un lecteur francophone y lit trois francs. Sur une alerte destinée
à quelqu'un qui n'a jamais touché à la bourse, c'est une erreur de lecture qui peut
provoquer une mauvaise décision.
"""
from src.portefeuille.format_fr import fcfa, nombre

ESPACE = "\u202f"      # espace fine insécable utilisée comme séparateur de milliers


def test_montant_simple():
    assert fcfa(3784) == f"3{ESPACE}784 F"


def test_grand_montant():
    assert fcfa(699718) == f"699{ESPACE}718 F"
    assert fcfa(1528508) == f"1{ESPACE}528{ESPACE}508 F"


def test_aucune_virgule_dans_les_francs():
    """Le cœur du problème : jamais de virgule comme séparateur de milliers."""
    for valeur in (1000, 16000, 699718, 1234567):
        assert "," not in fcfa(valeur)


def test_signe_forcé_pour_les_gains():
    assert fcfa(16000, signe=True) == f"+16{ESPACE}000 F"
    assert fcfa(16000) == f"16{ESPACE}000 F"


def test_montant_negatif():
    assert fcfa(-16000) == f"-16{ESPACE}000 F"


def test_petits_montants_sans_separateur():
    assert fcfa(0) == "0 F"
    assert fcfa(500) == "500 F"


def test_nombre_sans_unite():
    assert nombre(1234) == f"1{ESPACE}234"
