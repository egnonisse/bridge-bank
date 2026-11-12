"""Non-régression du SIGNAL et de son AFFICHAGE (contrat d'audit, 12/11/2026).

Ce fichier ne teste que des PROPRIÉTÉS — jamais un chiffre calibré figé :
le RSI, les bornes (inclusives/exclusives) des schémas, la zone min-max,
le comportement du filtre volume, les seuils du niveau visuel et la
cohérence entre la couleur affichée et le taux annoncé.

Le bug réel qui motive ce fichier : une zone affichait 🔴 « défavorable »
en annonçant 66 % de réussite — une couleur qui contredit le chiffre
qu'elle accompagne. `format_verdict_prix` doit désormais dériver la couleur
du taux mesuré, et c'est ce que `test_format_verdict_prix_couleur_jamais_contradictoire`
vérifie exhaustivement (taux de 0 à 100 par pas de 5).

Aucun appel réseau, aucun fichier de données modifié, aucune valeur calibrée
codée en dur : tout taux attendu est relu dans data/spec_profiles.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.strategie.spec_profiles import (  # noqa: E402
    PROFILES_FILE,
    detect_schemas,
    load_profiles,
    rsi,
    zone_of,
)
from src.strategie.spec_fiche import (  # noqa: E402
    SEUIL_CAS_ZONE,
    _niveau_mesure,
    _texte_zone,
    build_fiche,
    format_verdict_prix,
)


@pytest.fixture(autouse=True)
def _aucun_appel_reseau(monkeypatch):
    """Aucun test ne touche le réseau (leçon du 30/10/2026) : `build_fiche`
    interroge le fondamental ; ici il est remplacé par « fondamental inconnu »."""
    from src.collecte import fundamentals

    monkeypatch.setattr(fundamentals, "get_fundamentals", lambda code: {})
    monkeypatch.setattr(fundamentals, "get_dps", lambda code: None)


# ═══════════════════════════ RSI — propriétés, pas de chiffre figé ══════════════════

def test_rsi_montee_continue_vaut_100():
    """Aucune perte dans la série -> RSI = 100 (le maximum), pour toutes les
    séances calculées (pas seulement la dernière)."""
    up = [100.0 + i for i in range(30)]
    out = rsi(up)
    assert out[-1] == 100.0
    assert all(v == 100.0 for v in out[14:])  # out[0..13] sont None (amorçage)


def test_rsi_descente_continue_vaut_zero():
    """Aucun gain -> RSI = 0 (le minimum)."""
    down = [100.0 - i for i in range(30)]
    out = rsi(down)
    assert out[-1] == 0.0


def test_rsi_serie_plate_vaut_100_sans_division():
    """CAS PARTICULIER documenté : une série parfaitement plate ne lève aucune
    exception (pas de 0/0) et renvoie 100 — la branche `avg_l == 0` du code
    assimile « aucune perte » au maximum, même sans aucun gain. Ce n'est ni 50
    ni « indéfini » : c'est le comportement RÉEL du code, fixé ici comme
    garde-fou de non-régression."""
    flat = [100.0] * 25
    out = rsi(flat)
    assert out[-1] == 100.0
    assert all(v == 100.0 for v in out[14:])


# ═══════════════ Bornes des schémas — inclusives/exclusives telles que le code les fait ═══

def _serie_creux60(creux: float, dernier: float) -> list:
    """260 séances : 199 plates à 100, puis 60 au `creux`, puis la dernière à
    `dernier`. Le creux des 60 séances précédant la dernière vaut donc `creux`,
    ce qui permet de fixer le rapport dernier/creux à une valeur exacte."""
    return [100.0] * 199 + [creux] * 60 + [dernier]


def test_eveil_seuil_plus_10_pct_inclusif():
    """Le code compare `closes[-1] / creux60 - 1 >= 0.10` : un rapport qui vaut
    EXACTEMENT +10 % déclenche EVEIL (borne inclusive). C'est le test le plus
    important : il documente le comportement réel à la borne."""
    # creux 50, dernier 55 -> rapport exactement 1.10 -> EVEIL allumé
    schemas = detect_schemas(_serie_creux60(50.0, 55.0))
    assert "EVEIL" in schemas
    # isolement : ni cassure (55 < plafond 100), ni panique (rebond -> RSI 100)
    assert schemas == ["EVEIL"]


def test_eveil_sous_le_seuil_non_detecte():
    """+8 % depuis le creux des 60 séances : en deçà de +10 %, pas d'EVEIL."""
    assert "EVEIL" not in detect_schemas(_serie_creux60(50.0, 54.0))


def test_cassure_borne_strictement_superieure():
    """Le code compare `closes[-1] > max(closes[-251:-1])` : un dernier cours
    ÉGAL au plus haut des 250 séances n'est PAS une cassure (borne EXCLUSIVE),
    un cours strictement au-dessus l'est."""
    assert "CASSURE" not in detect_schemas([100.0] * 300 + [100.0])
    assert "CASSURE" in detect_schemas([100.0] * 300 + [100.5])


# ═════════════════════════════════ zone_of (position min-max) ════════════════════════

def test_zone_of_zero_au_plus_bas():
    assert zone_of([30.0, 20.0, 10.0]) == 0.0


def test_zone_of_un_au_plus_haut():
    assert zone_of([10.0, 20.0, 30.0]) == 1.0


def test_zone_of_fenetre_plate_sans_division_par_zero():
    """Une fenêtre de valeurs identiques ne divise jamais par zéro : hi <= lo
    renvoie 0.0 — y compris une série d'un seul élément."""
    assert zone_of([5.0, 5.0, 5.0]) == 0.0
    assert zone_of([7.0]) == 0.0


# ═══════════════════════════ filtre volume (absent / nul / panique) ═════════════════

def test_volumes_absents_n_activent_pas_le_filtre():
    """Sans volumes (None), la détection se fait sur le seul prix : la cassure
    se confirme d'office, sans exception."""
    closes = [100.0] * 300 + [150.0]
    assert "CASSURE" in detect_schemas(closes)
    assert "CASSURE" in detect_schemas(closes, None)


def test_volumes_nuls_ne_levent_pas_et_ne_confirment_pas():
    """COMPORTEMENT RÉEL documenté (B1-10, 13/10/2026) : une médiane de volumes
    NULLE ne confirme plus rien d'office — la cassure ET l'éveil sont bloqués.
    Attention : contrairement au cas « absent », une liste de zéros ACTIVE le
    filtre (med = 0 -> vol_ok = False). Aucune exception n'est levée."""
    closes = [100.0] * 300 + [150.0]
    volumes_nuls = [0.0] * len(closes)
    res = detect_schemas(closes, volumes_nuls)  # ne doit pas lever
    assert "CASSURE" not in res
    assert "EVEIL" not in res


def test_panique_ignore_le_filtre_volume():
    """PANIQUE n'a pas de filtre volume : même avec des volumes nuls, un RSI 14
    sous 30 signale. Le filtre ne porte que sur CASSURE et EVEIL."""
    closes = [100.0] * 260 + [100.0 - 2 * i for i in range(1, 20)]
    assert "PANIQUE" in detect_schemas(closes, [0.0] * len(closes))


# ═══════════════════════════ _niveau_mesure — les seuils visuels ════════════════════

@pytest.mark.parametrize("win,n,emoji,mot", [
    (0.60, 20, "✅", "favorable"),    # 60 % exactement -> favorable (borne inclusive)
    (0.75, 20, "✅", "favorable"),
    (0.55, 20, "🟡", "neutre"),
    (0.50, 20, "🟡", "neutre"),       # 50 % exactement -> neutre (borne inclusive)
    (0.4999, 20, "🔴", "défavorable"),
    (0.0, 20, "🔴", "défavorable"),
])
def test_niveau_mesure_seuils(win, n, emoji, mot):
    assert _niveau_mesure(win, n) == (emoji, mot)


@pytest.mark.parametrize("n", [0, 3, SEUIL_CAS_ZONE - 1])
def test_niveau_mesure_non_concluant_meme_a_100_pct(n):
    """Sous SEUIL_CAS_ZONE cas, le niveau est ⚪ MÊME si le taux est de 100 % :
    aucune conclusion chiffrée ne sort d'un échantillon trop mince."""
    assert _niveau_mesure(1.0, n) == ("⚪", "non concluant")


def test_niveau_mesure_seuil_d_effectif_exact():
    """À n == SEUIL_CAS_ZONE exactement, on n'est PLUS « non concluant »."""
    emoji, mot = _niveau_mesure(0.0, SEUIL_CAS_ZONE)
    assert emoji != "⚪"
    assert mot != "non concluant"


# ═══════════════ format_verdict_prix — la couleur ne contredit jamais le chiffre ═════

def test_format_verdict_prix_couleur_jamais_contradictoire():
    """LE test de non-régression central : pour chaque taux de 0 à 100 par pas
    de 5, la couleur affichée est CELLE du taux annoncé — jamais une couleur
    qui contredit le chiffre (le bug : 🔴 « défavorable » sur 66 % de réussite)."""
    for pct in range(0, 101, 5):
        out = format_verdict_prix({
            "zone_label": "MILIEU",
            "zone_stats": {"n": 40, "win_12m": pct / 100.0, "median_net_12m": 0.05},
        })
        # le chiffre affiché est bien le taux d'entrée, sans « correction » en douce
        assert f"{pct} % de réussite" in out
        # la couleur est dérivée de ce taux
        emoji, mot = _niveau_mesure(pct / 100.0, 40)
        assert f"{emoji} Verdict prix : {mot}" in out
        # aucune couleur contradictoire ne cohabite
        for c in ({"✅", "🟡", "🔴"} - {emoji}):
            assert c not in out


def test_le_defaut_66_pct_defavorable_est_mort():
    """Le bug exact : la zone 60-80 affichait 🔴 « défavorable » en annonçant
    66 % de réussite. Aujourd'hui 66 % -> ✅ favorable, quelle que soit la zone."""
    out = format_verdict_prix({
        "zone_label": "HAUT_FRAGILE",   # la zone du bug d'origine
        "zone_stats": {"n": 30, "win_12m": 0.66, "median_net_12m": 0.12},
    })
    assert "✅" in out and "favorable" in out
    assert "🔴" not in out and "défavorable" not in out
    assert "66 % de réussite" in out


def test_format_verdict_prix_non_concluant_n_affiche_aucun_taux():
    """Sous SEUIL_CAS_ZONE cas, la ligne s'abstient : aucun pourcentage affiché."""
    out = format_verdict_prix({
        "zone_label": "BAS_SOLIDE",
        "zone_stats": {"n": 3, "win_12m": 1.0, "median_net_12m": 0.88},
    })
    assert "⚪ Verdict prix : non concluant" in out
    assert "% de réussite" not in out


# ═══════════════════════ _texte_zone — même règle d'effectif ════════════════════════

def test_texte_zone_respecte_le_seuil_d_effectif():
    """À n == SEUIL_CAS_ZONE on affiche le taux ; en deçà on s'abstient et on
    annonce l'effectif (jamais le taux d'une autre population)."""
    au_seuil = _texte_zone("BAS_SOLIDE", {"n": SEUIL_CAS_ZONE, "win_12m": 1.0,
                                           "median_net_12m": 0.88})
    assert "100 % de réussite sur 10 cas" in au_seuil
    sous_seuil = _texte_zone("BAS_SOLIDE", {"n": SEUIL_CAS_ZONE - 1, "win_12m": 1.0,
                                             "median_net_12m": 0.88})
    assert "cas seulement POUR CE SCHÉMA" in sous_seuil
    assert "% de réussite" not in sous_seuil


# ═══════════════ charger_profiles / repli — aucune valeur calibrée figée ═════════════

def test_load_profiles_renvoie_le_fichier_sans_fallback():
    """Le chargeur lit le fichier calibré TEL QUEL : on compare au fichier, pas à
    une constante (le calibrage est rejouable et ses effectifs évoluent)."""
    expected = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    got = load_profiles()
    assert got == expected
    assert "_fallback" not in got


def test_fallback_marque_quand_fichier_absent(monkeypatch, tmp_path):
    """Fichier absent -> repli SIGNALÉ par `_fallback`, sans inventer de zone."""
    import src.strategie.spec_profiles as sp

    monkeypatch.setattr(sp, "PROFILES_FILE", tmp_path / "absent.json")
    prof = sp.load_profiles()
    assert prof.get("_fallback") is True
    for schema in ("CASSURE", "EVEIL", "PANIQUE"):
        assert schema in prof


def test_fallback_marque_quand_fichier_illisible(monkeypatch, tmp_path):
    """Fichier illisible (un dossier) -> même repli signalé, jamais d'exception."""
    import src.strategie.spec_profiles as sp

    dossier = tmp_path / "pas_un_json"
    dossier.mkdir()
    monkeypatch.setattr(sp, "PROFILES_FILE", dossier)
    assert sp.load_profiles().get("_fallback") is True


def test_build_fiche_branche_les_stats_de_zone_sur_le_fichier_calibre():
    """La fiche affiche les stats de zone DU SCHÉMA COURANT, relues du fichier
    calibré — pas d'une table en dur. (CASSURE + zone FORCE -> tranche 80-100.)"""
    closes = [100.0] * 300 + [150.0]
    f = build_fiche("TEST", "Test", closes)
    assert f is not None
    prof_file = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    expected = prof_file["CASSURE"]["zones"]["80-100"]
    assert f.blocks["zone_stats"] == expected
    assert f.blocks["stats_fallback"] is False
