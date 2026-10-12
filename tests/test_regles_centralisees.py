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
    """Noms assignés à une valeur LITTERALE dans ce fichier (pas un import, pas un calcul).

    B1-12 (12/10) : couvre aussi les assignations ANNOTÉES (`cash_cible: float = 0.15`)
    que l'ancien scan (`ast.Assign` seul) ne voyait pas.
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign):
            cibles = noeud.targets
        elif isinstance(noeud, ast.AnnAssign) and noeud.value is not None:
            cibles = [noeud.target]
        else:
            continue
        for cible in cibles:
            if isinstance(cible, ast.Name) and cible.id in TOUS_LES_NOMS:
                out.append((cible.id, noeud.lineno))
    return out


def test_le_catalogue_existe_et_est_complet():
    """Les règles doivent toutes être présentes dans le catalogue."""
    import src.regles as regles

    manquantes = [n for n in REGLES_CENTRALISEES if not hasattr(regles, n)]
    assert not manquantes, f"absentes du catalogue : {manquantes}"


def test_aucune_regle_redefinie_ailleurs():
    """Aucune règle du catalogue ne doit être réécrite en dur dans un autre module.

    B1-12/A3-06 (12/10) : le scan était LIMITÉ aux fichiers de `src/` racine — les
    sous-dossiers (strategie/, analyse/, collecte/, backtesting/, calibration/) lui
    étaient INVISIBLES. Il balaie désormais tout l'arbre source.
    """
    fautes = []
    for f in sorted(SRC.rglob("*.py")):
        if f.name == CATALOGUE.name or "__pycache__" in f.parts:
            continue          # le catalogue EST la source
        for nom, ligne in _definitions_litterales(f):
            fautes.append(f"{f.relative_to(RACINE)}:{ligne} redéfinit `{nom}`")
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


def test_max_buy_weight_confirme_et_inscrit_dans_l_ips():
    """Le plafond de poids d'ACHAT (0,40) : confirmé par LEO le 12/10/2026 et INSCRIT
    dans l'IPS — il détermine un nombre d'actions conseillé (`max_qty` dans l'alerte),
    donc il ne peut pas vivre seulement dans le code (question Q4 de l'audit)."""
    import src.regles as regles

    assert regles.MAX_BUY_WEIGHT == pytest.approx(0.40)
    # L'inscription dans l'IPS est verrouillée ici : si l'un des deux bouge, le test casse.
    ips = (RACINE / "docs" / "IPS.md").read_text(encoding="utf-8")
    assert "MAX_BUY_WEIGHT" in ips, "la règle doit être inscrite dans docs/IPS.md (décision Q4)"
    assert "0,40" in ips, "la valeur doit figurer dans docs/IPS.md (décision Q4)"


# Valeurs fiscales à ne JAMAIS recopier : la liste est volontairement courte et
# SPECIFIQUE (0,88 = 1 − IRVM ; 0,008 = conservation annuelle en points) — un simple
# « 0,12 » serait trop générique (probabilités, seuils divers).
VALEURS_FISCALES_EN_DUR = {
    0.88: "net d'IRVM — utiliser IRVM_DIVIDEND_TAX ou net_yield()",
    0.008: "conservation 0,80 %/an — utiliser CUSTODY_ANNUAL ou net_yield()",
}


def test_aucun_litteral_fiscal_en_dur():
    """C4 (A3-06, corrigé le 12/10/2026) : `brut * 0.88 - 0.008` était recopié dans
    6 modules — le jour où l'IRVM change (il a fait 10 % → 15 % → 12 %), ces copies
    seraient restées muettes. Le scan couvre TOUT l'arbre source, taxation.py excepté."""
    fautes = []
    for f in sorted(SRC.rglob("*.py")):
        if f.name == "taxation.py" or "__pycache__" in f.parts:
            continue          # la source fiscale EST taxation.py
        try:
            arbre = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, float)
                    and noeud.value in VALEURS_FISCALES_EN_DUR):
                fautes.append(
                    f"{f.relative_to(RACINE)}:{noeud.lineno} : {noeud.value} — "
                    f"{VALEURS_FISCALES_EN_DUR[noeud.value]}")
    assert not fautes, (
        "ces taux doivent venir de src/taxation.py :\n  " + "\n  ".join(fautes))


def test_pour_na_pas_de_defaut_litteral():
    """B1-12 : le défaut du seuil de vente (« 0,13 ») doit venir du catalogue."""
    import inspect

    import src.regles as regles

    from src.calibration import seuils_vente

    assert inspect.signature(seuils_vente.pour).parameters["defaut"].default is None
    # Un code totalement inconnu reçoit le défaut central — jamais une copie.
    assert seuils_vente.pour("INCONNU_XYZ") == pytest.approx(regles.PROFIT_ALERT_THRESHOLD)
