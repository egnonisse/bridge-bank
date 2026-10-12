"""Tests du parseur de fondamentaux historiques (point-in-time).

Contexte : audit technique du 12/10/2026, findings **A3-01** (colonne TTM jamais écartée
→ BPA décalés d'un an, signature : deux exercices consécutifs au montant exactement égal)
et **A3-02** (BPA supposé publié dès le 01/01 au lieu de ~fin juin → look-ahead de 3-6 mois).

Les fixtures reproduisent la STRUCTURE RÉELLE vérifiée en direct sur stockanalysis.com :
en-têtes « Fiscal Year | TTM | FY 2025 | … | FY 2021 », ligne « Earnings Per Share » dans
des cellules (la colonne TTM peut contenir un NOMBRE — pas seulement un tiret).
"""
from src.analyse.fondamentaux_historiques import (
    TitreFondamentaux,
    bpa_connu,
    bpa_public_avant,
    extraire_bpa,
    fondamentaux_a_la_date,
)


def _html(annees, valeurs, avec_ttm=True):
    """HTML minimal fidèle à la structure réelle (th d'en-têtes + ligne EPS en cellules)."""
    ths = "<th>Fiscal Year</th>"
    if avec_ttm:
        ths += "<th>TTM</th>"
    ths += "".join(f"<th>FY {a}</th>" for a in annees)
    tds = "".join(f"<td><div>{v}</div></td>" for v in valeurs)
    return (f"<table><thead><tr>{ths}</tr></thead><tbody>"
            f"<tr><td>Earnings Per Share</td>{tds}</tr></tbody></table>")


ANNEES = ["2025", "2024", "2023", "2022", "2021"]


# ═════════════════════════════ A3-01 — le TTM et les positions ═══════════════════════

def test_ttm_numerique_est_ecarte_pas_les_exercices():
    """Le cas ABJC : TTM NUMÉRIQUE (121.98) == FY2025 (121.98) — l'ancien parseur
    associait [TTM, FY2025, FY2024, ...] à [2025, 2024, 2023, ...] : doublon exact
    ET décalage d'un an. Corrigé : le TTM est écarté PAR POSITION."""
    html = _html(ANNEES, ["121.98", "121.98", "138.84", "124.45", "-", "-"])
    out = extraire_bpa(html)
    assert out == {"2025": 121.98, "2024": 138.84, "2023": 124.45}, out
    assert out["2024"] != out["2025"], "le doublon exact signature du bug est revenu !"


def test_ttm_tiret_cas_snts():
    """Le cas SNTS : TTM='-' — les 5 exercices doivent être lus SANS perdre la dernière
    année (l'ancien code était juste par accident, on le gèle exprès)."""
    html = _html(ANNEES, ["-", "3419.63", "3287.50", "2794.00", "2359.00", "2110.00"])
    out = extraire_bpa(html)
    assert out == {"2025": 3419.63, "2024": 3287.50, "2023": 2794.00,
                   "2022": 2359.00, "2021": 2110.00}, out


def test_cellule_vide_au_milieu_preserve_les_positions():
    """Une cellule '-' au MILIEU ne doit plus décaler les suivantes : la position est
    préservée (None) et l'exercice manquant est simplement absent du résultat."""
    html = _html(ANNEES, ["-", "100.0", "-", "80.0", "70.0", "60.0"])
    out = extraire_bpa(html)
    assert out == {"2025": 100.0, "2023": 80.0, "2022": 70.0, "2021": 60.0}, out
    assert "2024" not in out  # pas de valeur → pas d'année inventée


def test_sans_colonne_ttm_lecture_directe():
    html = _html(ANNEES, ["3419.63", "3287.50", "2794.00", "2359.00", "2110.00"],
                 avec_ttm=False)
    out = extraire_bpa(html)
    assert out == {"2025": 3419.63, "2024": 3287.50, "2023": 2794.00,
                   "2022": 2359.00, "2021": 2110.00}, out


def test_structure_incoherente_refusee():
    """Pas assez de cellules pour les en-têtes : on REFUSE ({}), on n'approxime pas."""
    html = _html(ANNEES, ["121.98", "138.84", "124.45"])  # 3 cellules pour 6 colonnes
    assert extraire_bpa(html) == {}


def test_sortie_vide_sans_eps():
    assert extraire_bpa("") == {}
    assert extraire_bpa("<table><thead><tr><th>FY 2025</th></tr></thead></table>") == {}


# ═════════════════════════════ A3-02 — la date de publication ════════════════════════

def test_bpa_public_avant_frontiere_30_juin():
    """Frontière explicite : un BPA d'exercice N n'est publié qu'au 30 juin N+1."""
    assert not bpa_public_avant(2024, "2025-01-01")
    assert not bpa_public_avant(2024, "2025-03-31")
    assert not bpa_public_avant(2024, "2025-06-29")
    assert bpa_public_avant(2024, "2025-06-30")
    assert bpa_public_avant(2024, "2025-07-01")


def test_bpa_connu_ne_fuit_pas_avant_publication():
    """bpa_connu : en mars 2025, le BPA 2024 (publié fin juin) est INVISIBLE."""
    t = TitreFondamentaux(code="X", bpa={"2024": 100.0, "2023": 90.0})
    assert bpa_connu(t, "2025-03-31") == ("2023", 90.0)   # seul 2023 est publié
    assert bpa_connu(t, "2025-06-30") == ("2024", 100.0)  # 2024 publié le 30/06
    assert bpa_connu(t, "2024-01-15") is None             # rien de publié début 2024


def test_per_indisponible_avant_publication():
    """Le PER point-in-time n'existe PAS avant la publication des comptes (le cœur du
    module : refuser de trancher plutôt que trancher faux)."""
    t = TitreFondamentaux(code="X", bpa={"2024": 100.0}, bpa_fiable=True)
    janvier = fondamentaux_a_la_date(t, "2025-01-15", cours=1500.0)
    assert "per" not in janvier and "bpa" not in janvier
    juillet = fondamentaux_a_la_date(t, "2025-07-01", cours=1500.0)
    assert juillet["bpa"] == 100.0
    assert juillet["per"] == 15.0
    assert juillet["annee_bpa"] == "2024"
