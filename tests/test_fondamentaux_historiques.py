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


# ═════════════════════════════ A3-11 — dividende courant (âge + cumul) ════════════════

def _titre(*versements, bpa=100.0):
    """Titre point-in-time avec un historique de versements [(ex_date, montant), ...]."""
    return TitreFondamentaux(
        code="X",
        dividendes=[{"ex_date": d, "montant": m} for d, m in versements],
        bpa={"2024": bpa}, bpa_fiable=True,
    )


def test_dividende_perime_est_inconnu_pas_fictif():
    """A3-11 : un dividende coupé depuis 3 ans ne donne NI dps NI rendement (avant le fix,
    ce titre affichait un « 4 % » fictif, scénario BNBC)."""
    t = _titre(("2023-05-01", 200.0))
    out = fondamentaux_a_la_date(t, "2026-06-01", cours=5000.0)
    assert "dps" not in out and "net_yield" not in out and "ex_date_dividende" not in out


def test_dividende_de_13_mois_reste_connu():
    """Un détachement annuel décalé d'un mois (13 mois) décrit encore le présent."""
    t = _titre(("2025-05-01", 200.0))
    out = fondamentaux_a_la_date(t, "2026-06-01", cours=5000.0)
    assert out["dps"] == 200.0
    assert out["ex_date_dividende"] == "2025-05-01"
    assert out["net_yield"] == round(200.0 / 5000.0 * 0.88 - 0.008, 6)


def test_dividende_au_dela_de_15_mois_perime():
    """Frontière de péremption : 456 jours (15 mois) — au-delà, « inconnu »."""
    t = _titre(("2025-03-01", 200.0))
    assert fondamentaux_a_la_date(t, "2026-05-31", cours=5000.0)["dps"] == 200.0   # 456 j
    t2 = _titre(("2025-02-28", 200.0))
    out = fondamentaux_a_la_date(t2, "2026-05-31", cours=5000.0)                   # 457 j
    assert "dps" not in out


def test_dps_cumule_acompte_et_solde_de_l_annee():
    """A3-11 : le dps = SOMME des versements de l'année écoulée (acompte + solde), plus
    jamais le seul dernier versement (sous-estimation du rendement et du payout)."""
    t = _titre(("2026-01-10", 100.0), ("2026-07-10", 150.0))
    out = fondamentaux_a_la_date(t, "2026-08-01", cours=5000.0)
    assert out["dps"] == 250.0
    assert out["net_yield"] == round(250.0 / 5000.0 * 0.88 - 0.008, 6)
    assert out["payout"] == 2.5                      # 250 / BPA 100 : cohérent annuel/annuel


def test_versement_hors_fenetre_non_cumule():
    """Un versement antérieur à l'année écoulée ne gonfle pas le dps courant."""
    t = _titre(("2024-06-01", 50.0), ("2026-07-10", 150.0))
    out = fondamentaux_a_la_date(t, "2026-08-01", cours=5000.0)
    assert out["dps"] == 150.0


def test_dernier_valide_hors_fenetre_reste_le_seul_revenu():
    """Entre 12 et 15 mois, le dernier versement est valide mais hors fenêtre de cumul :
    il reste le seul revenu connu (pas de dps à zéro)."""
    t = _titre(("2025-06-01", 90.0))
    out = fondamentaux_a_la_date(t, "2026-07-01", cours=5000.0)   # 395 jours
    assert out["dps"] == 90.0
