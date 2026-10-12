"""Le verdict de `tester_revenu_vs_hasard.py` suit-il ses propres chiffres ?

AUDIT DU 12/10/2026 — LE DEFAUT REPRODUIT ICI
---------------------------------------------
Le script affichait « avantage : +2,23 pts » puis concluait « ❌ le hasard apporte plus de
revenu ». La faute n'etait pas le calcul mais la ligne de verdict : un `else` fourre-tout
attrapait le cas « le noyau est DEVANT mais l'avantage n'est pas etabli » et imprimait la
conclusion inverse de ses propres chiffres. Un lecteur presse en tirait le contraire de la
realite.

Ces tests figent les quatre situations possibles (amplitude x significativite) et, surtout,
interdisent la seule conclusion qui mentait.
"""
from scripts.tester_revenu_vs_hasard import verdict_revenu


def texte(lignes):
    return " ".join(lignes)


def test_devant_et_etabli_annonce_l_avantage():
    v = verdict_revenu(10.0, 8.0, 3, 4)
    t = texte(v)
    assert "APPORTE PLUS DE REVENU" in t
    assert "PAS ETABLI" not in t
    assert "3/4" in t


def test_devant_mais_non_etabli_ne_dit_jamais_le_contraire():
    """Le cas reel du 12/10/2026 : +2,23 pt, significatif sur 1/4 seulement."""
    v = verdict_revenu(10.35, 8.12, 1, 4)
    t = texte(v)
    assert "APPORTE PLUS DE REVENU" in t
    assert "PAS ETABLI" in t
    assert "1/4" in t
    # LE BUG CORRIGE : le verdict ne doit jamais annoncer le hasard vainqueur
    # alors que les chiffres montrent le noyau devant.
    assert "LE HASARD APPORTE PLUS" not in t


def test_ecart_negligeable_est_dit_tel_quel():
    t = texte(verdict_revenu(9.0, 8.8, 0, 4))
    assert "PAS DE DIFFERENCE NOTABLE" in t
    assert "APPORTE PLUS" not in t


def test_hasard_vraiment_devant_le_dit():
    t = texte(verdict_revenu(7.0, 9.0, 0, 4))
    assert "LE HASARD APPORTE PLUS" in t
    assert "NOYAU APPORTE PLUS" not in t


def test_le_seuil_de_significativite_est_la_moitie_des_cohortes():
    """2/4 suffit a etablir, 1/4 ne suffit pas — la frontiere est explicite."""
    assert "PAS ETABLI" not in texte(verdict_revenu(10.0, 8.0, 2, 4))
    assert "PAS ETABLI" in texte(verdict_revenu(10.0, 8.0, 1, 4))
