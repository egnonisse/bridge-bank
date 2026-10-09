"""Garde-fou : les règles métier ne doivent exister qu'à UN SEUL endroit.

POURQUOI CE TEST
----------------
L'audit du 08/10/2026 a trouvé 194 définitions pour 159 notions : le PER maximum dans
4 fichiers, le payout dans 3, l'IRVM sous 2 noms, et « combien de cas faut-il pour
valider un seuil » avec DEUX réponses (6 et 8). Ces duplications ne cassent rien le jour
où elles apparaissent — elles divergent des mois plus tard, quand quelqu'un modifie une
copie et pas les autres.

Une charte ne suffit pas : une charte se perd à la première réécriture. Ce test refuse la
réapparition d'une valeur littérale pour une règle déjà cataloguée dans `src/regles.py`.

CE QU'IL AUTORISE
-----------------
- l'import et l'alias : `from .regles import PER_MAX as PER_MAX_NOYAU`
- la dérivation : `FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_SENS`
- les constantes propres à un module (un chemin de fichier, un timeout, une URL)

CE QU'IL REFUSE
---------------
- `PER_MAX = 14.0` réécrit dans un module, même avec la bonne valeur : c'est la copie
  qui est dangereuse, pas la valeur du jour.
"""
import ast
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
CATALOGUE = SRC / "regles.py"

# Règles métier cataloguées : définies UNE fois, dans src/regles.py.
REGLES_CENTRALISEES = {
    "PER_MAX", "PAYOUT_MAX", "PAYOUT_TIGHT", "PAYOUT_CRITICAL", "PER_ABSURD",
    "IRVM", "FRAIS_PAR_SENS", "FRAIS_ALLER_RETOUR", "FRAIS_MINIMUM",
    "RENDEMENT_NET_MIN", "RENDEMENT_NET_ENTREE", "RENDEMENT_NET_SORTIE",
    "EPISODES_MIN", "BORNE_BASSE_MIN",
    "PROFIT_ALERT_THRESHOLD", "SELL_FRACTION", "LOSS_ALERT_THRESHOLD",
    "MAX_POSITION_WEIGHT", "MAX_BUY_WEIGHT", "MAX_MARKET_WEIGHT",
}

# Noms LOCAUX créés par `from .regles import X as Y` dans les modules consommateurs.
# Ils ne vivent pas dans le catalogue, mais ils ne doivent pas non plus être réécrits
# en dur : c'est exactement la duplication qu'on cherche à empêcher.
ALIAS_LOCAUX = {"MIN_EPISODES", "PROFIT_MIN_EPISODES", "PER_MAX_NOYAU"}

TOUS_LES_NOMS = REGLES_CENTRALISEES | ALIAS_LOCAUX


def _definitions_litterales(chemin: Path) -> list[tuple[str, int]]:
    """Noms assignés à une valeur LITTERALE dans ce fichier (pas un import, pas un calcul)."""
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for noeud in arbre.body:
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name) and cible.id in TOUS_LES_NOMS:
                out.append((cible.id, noeud.lineno))
    return out


def test_le_catalogue_existe_et_est_complet():
    """Les règles doivent toutes être présentes dans le catalogue."""
    import src.regles as regles

    manquantes = [n for n in REGLES_CENTRALISEES if not hasattr(regles, n)]
    assert not manquantes, f"absentes du catalogue : {manquantes}"


def test_aucune_regle_redefinie_ailleurs():
    """Aucune règle du catalogue ne doit être réécrite en dur dans un autre module."""
    fautes = []
    for f in sorted(SRC.glob("*.py")):
        if f.name == CATALOGUE.name:
            continue          # le catalogue EST la source
        for nom, ligne in _definitions_litterales(f):
            fautes.append(f"{f.name}:{ligne} redéfinit `{nom}`")
    assert not fautes, (
        "ces règles doivent être importées de src/regles.py :\n  " + "\n  ".join(fautes))


def test_les_frais_ne_sont_pas_confondus():
    """`FRAIS_PAR_SENS` et `FRAIS_ALLER_RETOUR` ont des SENS différents.

    C'est le piège le plus dangereux de l'audit : confondre les deux DOUBLE les frais,
    silencieusement. Le test verrouille le rapport de 2 entre les deux.
    """
    import src.regles as regles

    assert regles.FRAIS_PAR_SENS == pytest.approx(0.014)
    assert regles.FRAIS_ALLER_RETOUR == pytest.approx(0.028)
    assert regles.FRAIS_ALLER_RETOUR == pytest.approx(2 * regles.FRAIS_PAR_SENS)


def test_les_frais_viennent_du_courtage_reel():
    """0,014 n'est pas arbitraire : c'est courtage + TVA + frais BRVM."""
    from src.taxation import BROKERAGE_FEE

    import src.regles as regles

    assert regles.FRAIS_PAR_SENS == pytest.approx(BROKERAGE_FEE)


def test_une_seule_reponse_au_nombre_de_cas_requis():
    """« Combien de cas faut-il ? » avait DEUX réponses (6 et 8). Il n'en reste qu'une."""
    import src.regles as regles

    from src import portfolio

    assert regles.EPISODES_MIN == 8
    # portfolio expose le nom historique — il doit pointer sur LA MÊME valeur.
    assert portfolio.PROFIT_MIN_EPISODES == regles.EPISODES_MIN


def test_coherence_fiscale():
    """L'IRVM doit être identique partout (fiscalité CI)."""
    from src.taxation import IRVM_DIVIDEND_TAX

    import src.regles as regles

    assert regles.IRVM == IRVM_DIVIDEND_TAX == pytest.approx(0.12)


def test_seuils_de_rendement_coherents_avec_la_taxation():
    """Les objectifs de rendement viennent de taxation.py, pas de copies."""
    import src.regles as regles
    from src.taxation import TARGET_NET_YIELD_ENTRY, TARGET_NET_YIELD_EXIT

    assert regles.RENDEMENT_NET_ENTREE == TARGET_NET_YIELD_ENTRY
    assert regles.RENDEMENT_NET_SORTIE == TARGET_NET_YIELD_EXIT
