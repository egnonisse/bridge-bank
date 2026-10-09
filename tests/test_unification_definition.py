"""L'unification de définition garantit : UNE mesure, UN chiffre.

POURQUOI CE FICHIER EXISTE
--------------------------
Le seuil de vente et le profil de retournement mesuraient le même phénomène avec deux
définitions différentes — hausse entre 13 % et 65 % espacée de 10 séances d'un côté, hausse
≥ seuil du titre espacée de 20 de l'autre. SNTS affichait donc « 86 % sur 7 cas » puis
« 90 % sur 10 cas » pour la même question.

Ce fichier verrouille la condition n° 1 de la décision : **même définition du phénomène**.
Il ne teste pas un chiffre, il teste que les deux mesures ne PEUVENT PAS diverger.
"""
import json

import pytest

from src import seuils_vente as sv
from src.infrastructure.paths import DATA_DIR
from scripts.export_reversal_profiles import _profil_titre


def _serie(graine: int = 7, n: int = 700) -> list[float]:
    """Série synthétique reproductible avec des vagues (hausses puis replis)."""
    import random

    rng = random.Random(graine)
    prix, out = 1000.0, []
    for i in range(n):
        # Alternance de poussées et de replis, avec du bruit.
        derive = 0.004 if (i // 30) % 2 == 0 else -0.003
        prix *= 1 + derive + rng.uniform(-0.012, 0.012)
        out.append(round(prix, 2))
    return out


# ── 1. Même définition → mêmes chiffres ───────────────────────────────────────

def test_profil_et_seuil_donnent_le_meme_taux():
    """LE test de l'unification : les deux mesures affichent le même chiffre."""
    closes = _serie()
    for seuil in (0.05, 0.10, 0.13):
        profil = _profil_titre(closes, seuil)
        if not profil:
            continue
        ep = sv.episodes(closes, seuil)
        n = len(ep)
        attendu = round(sum(1 for r in ep if r < 0) / n * 100)

        assert profil["episodes"] == n, "les deux mesures comptent le même nombre de cas"
        assert profil["pct_down_20j"] == attendu, (
            f"seuil {seuil*100:.0f} % : le profil dit {profil['pct_down_20j']} %, "
            f"le seuil de vente mesure {attendu} % — la divergence est revenue")


def test_profil_et_seuil_utilisent_la_meme_liste_d_episodes():
    """Le profil ne doit pas recalculer ses propres indices : il doit les DEMANDER."""
    closes = _serie()
    idx = sv.indices_episodes(closes, 0.10)
    profil = _profil_titre(closes, 0.10)
    assert profil["episodes"] == len(idx)


# ── 2. La définition elle-même : fenêtres disjointes ─────────────────────────

def test_les_episodes_ne_se_chevauchent_pas():
    """Fenêtres disjointes : deux épisodes sont espacés d'au moins 20 séances.

    C'est le cœur du choix méthodologique — deux épisodes à 10 séances d'écart partagent la
    moitié de leur fenêtre et ne sont pas indépendants. Espacer moins gonfle le nombre de
    cas sans apporter d'information.
    """
    closes = _serie()
    idx = sv.indices_episodes(closes, 0.05)
    assert len(idx) > 5, "la série de test doit produire des épisodes"
    ecarts = [b - a for a, b in zip(idx, idx[1:])]
    assert all(e >= 20 for e in ecarts), f"fenêtres chevauchantes : {min(ecarts)} séances"


def test_aucune_borne_haute():
    """Une hausse de +200 % compte autant qu'une hausse de +15 % pour la mesure.

    L'alerte se déclenche dès que le seuil est franchi, quelle que soit l'ampleur : plafonner
    la mesure à +65 % décrirait une autre situation que celle observée par l'utilisateur.
    """
    # Trois sauts consécutifs de +25 % = environ +95 % en 20 séances, puis on laisse
    # retomber : la série contient donc des hausses bien au-delà de 65 %.
    closes = [100.0]
    for i in range(600):
        if i % 90 in (0, 1, 2):
            closes.append(closes[-1] * 1.25)
        else:
            closes.append(closes[-1] * 0.998)

    idx = sv.indices_episodes(closes, 0.13)
    hausses = [closes[i] / closes[i - 20] - 1 for i in idx]
    assert any(h > 0.65 for h in hausses), (
        "la série de test doit contenir une hausse > 65 % pour que le test ait du sens")
    assert len(idx) > 0, "aucune borne haute : ces épisodes doivent être retenus"


# ── 3. Transparence statistique ──────────────────────────────────────────────

def test_significatif_exige_assez_de_cas_et_une_borne_solide():
    """`significatif` = au moins 8 cas ET borne basse ≥ 50 % — jamais l'un sans l'autre."""
    closes = _serie()
    profil = _profil_titre(closes, 0.05)
    p, borne, _ = sv.intervalle_wilson(
        round(profil["pct_down_20j"] / 100 * profil["episodes"]), profil["episodes"])

    attendu = (profil["episodes"] >= sv.MIN_EPISODES
               and round(borne * 100) >= sv.BORNE_BASSE_MIN * 100)
    assert profil["significatif"] == attendu
    assert profil["borne_basse"] == round(borne * 100), "la borne basse doit être publiée"


def test_un_taux_eleve_sur_peu_de_cas_n_est_pas_significatif():
    """Davantage de cas n'est PAS une meilleure preuve — et peu de cas ne conclut pas.

    Un taux de 100 % sur 3 cas a une borne basse très éloignée de 100 % : il ne doit jamais
    être présenté comme fiable.
    """
    profil = _profil_titre(_serie(n=200), 0.30)
    if profil and profil["episodes"] < sv.MIN_EPISODES:
        assert profil["significatif"] is False


def test_le_profil_porte_son_seuil():
    """Chaque profil dit à QUEL seuil il a été mesuré — sinon l'affichage ne peut pas
    détecter qu'un profil est périmé."""
    profil = _profil_titre(_serie(), 0.10)
    assert profil["seuil_pct"] == 10
    assert profil is not None


# ── 4. Le fichier exporté est cohérent ───────────────────────────────────────

def test_le_fichier_exporte_decrit_sa_definition():
    """Le fichier doit documenter sa propre méthode, pour qu'on ne puisse pas la confondre
    avec une autre plus tard."""
    f = DATA_DIR / "reversal_profiles.json"
    if not f.exists():
        pytest.skip("profils non générés")
    data = json.loads(f.read_text(encoding="utf-8"))
    meta = data.get("_meta", {})
    assert meta.get("espacement") == 20
    assert meta.get("borne_haute") is None
    assert "fenetres disjointes" in meta.get("definition", "")


def test_chaque_profil_exporte_est_mesure_a_son_seuil():
    """Aucun profil du fichier ne doit porter le seuil d'un autre titre.

    C'est la régression exacte qui a motivé ce chantier : tous les profils portaient +13 %.
    """
    f = DATA_DIR / "reversal_profiles.json"
    if not f.exists():
        pytest.skip("profils non générés")
    data = json.loads(f.read_text(encoding="utf-8"))
    seuils = sv.charger()

    for code, profil in data.items():
        if code.startswith("_"):
            continue
        attendu = round(float(seuils.get(code, {}).get("threshold", 0.13)) * 100)
        assert profil["seuil_pct"] == attendu, (
            f"{code} : profil mesuré à {profil['seuil_pct']} % alors que son seuil est "
            f"{attendu} %")
