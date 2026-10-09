"""Tests de l'empreinte de version (`src/infrastructure/empreinte.py`).

Ce qui est verrouille ici : l'empreinte est STABLE (deux appels dans la meme minute donnent la
meme valeur), elle CHANGE quand un contenu change, elle distingue un fichier renomme, et elle ne
leve JAMAIS — une empreinte impossible doit rester une empreinte, pas une panne d'alerte.
"""
from __future__ import annotations

import re

import pytest

from src.infrastructure import empreinte


def test_sha256_du_meme_contenu_est_stable(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"x": 1}', encoding="utf-8")
    assert empreinte._sha256_fichiers([f]) == empreinte._sha256_fichiers([f])


def test_sha256_change_avec_le_contenu(tmp_path):
    a, b = tmp_path / "regles.py", tmp_path / "autre.py"
    a.write_text("PER_MAX = 14", encoding="utf-8")
    b.write_text("PER_MAX = 15", encoding="utf-8")
    assert empreinte._sha256_fichiers([a]) != empreinte._sha256_fichiers([b])


def test_le_nom_du_fichier_compte_dans_l_empreinte(tmp_path):
    """Renommer un fichier de regles change le sens du projet : l'empreinte doit le voir."""
    a = tmp_path / "regles.py"
    a.write_text("PER_MAX = 14", encoding="utf-8")
    avant = empreinte._sha256_fichiers([a])
    a.rename(tmp_path / "regles_anciennes.py")
    assert empreinte._sha256_fichiers([tmp_path / "regles_anciennes.py"]) != avant


def test_fichier_absent_ne_leve_pas(tmp_path):
    """Un fichier de regles absent doit donner une empreinte (et un avertissement), pas une erreur."""
    assert empreinte._sha256_fichiers([tmp_path / "inexistant.py"])
    assert empreinte._sha256_fichiers([])


def test_git_indisponible_ne_leve_pas(monkeypatch):
    def explose(*_a, **_k):
        raise OSError("git absent")

    monkeypatch.setattr(empreinte.subprocess, "run", explose)
    assert empreinte._git("rev-parse", "--short", "HEAD") is None


def test_code_sans_depot_git(monkeypatch):
    monkeypatch.setattr(empreinte, "commit", lambda: None)
    assert empreinte.empreinte_code() == "inconnu"


def test_arbre_modifie_marque_le_code(monkeypatch):
    """Le cas que le SHA seul ne verrait jamais : un parametre edite sans commit."""
    monkeypatch.setattr(empreinte, "commit", lambda: "abc1234")
    monkeypatch.setattr(empreinte, "arbre_modifie", lambda: True)
    assert empreinte.empreinte_code() == "abc1234*"


def test_arbre_propre_ne_marque_pas(monkeypatch):
    monkeypatch.setattr(empreinte, "commit", lambda: "abc1234")
    monkeypatch.setattr(empreinte, "arbre_modifie", lambda: False)
    assert empreinte.empreinte_code() == "abc1234"


def test_le_drapeau_ignore_les_journaux(monkeypatch):
    """Un journal append-only qui s'allonge n'est pas un changement de regles.

    Sans cette exclusion, chaque alerte marquerait l'arbre comme modifie (le journal qu'elle
    vient d'ecrire), et le drapeau perdrait toute signification.
    """
    vus: list[str] = []

    class Faux:
        returncode = 0
        stdout = ""

    def faux_run(arguments, **_k):
        vus.extend(arguments)
        return Faux()

    monkeypatch.setattr(empreinte.subprocess, "run", faux_run)
    empreinte.arbre_modifie()
    assert any("exclude" in a for a in vus)


def test_les_fichiers_surveilles_existent_vraiment():
    """LE test qui empêche une empreinte constante.

    Une empreinte calculée sur des fichiers introuvables ne change JAMAIS : elle aurait l'air
    d'une empreinte parfaitement stable alors que les règles bougeraient. C'est exactement le
    genre de panne silencieuse que ce projet traque — et elle a été commise une fois, ici, en
    écrivant ce module (`regles.py` était supposé dans `src/domaine/`, il était à `src/`).
    """
    surveilles = [*empreinte.FICHIERS_REGLES, *empreinte.FICHIERS_SEUILS, *empreinte.FICHIERS_CONFIG]
    absents = [str(f) for f in surveilles if not f.exists()]
    assert absents == [], f"fichiers surveillés introuvables (empreinte aveugle) : {absents}"


def test_carte_complete_et_lisible():
    c = empreinte.carte()
    assert set(c) == {"code", "regles", "seuils", "config"}
    for cle, valeur in c.items():
        assert isinstance(valeur, str) and valeur, f"{cle} vide"
    assert re.fullmatch(r"[0-9a-f]{7,40}\*?|inconnu", c["code"]), c["code"]
    for cle in ("regles", "seuils", "config"):
        assert re.fullmatch(r"[0-9a-f]{12}", c[cle]), (cle, c[cle])


def test_deux_appels_donnent_la_meme_carte():
    assert empreinte.carte() == empreinte.carte()


def test_l_empreinte_des_seuils_suit_le_fichier_des_seuils(monkeypatch, tmp_path):
    """Modifier les seuils doit changer l'empreinte des seuils — et RIEN d'autre."""
    f = tmp_path / "profit_thresholds.json"
    f.write_text('{"SNTS": {"threshold": 0.05}}', encoding="utf-8")
    monkeypatch.setattr(empreinte, "FICHIERS_SEUILS", (f,))
    avant = empreinte.carte()
    f.write_text('{"SNTS": {"threshold": 0.05, "mode": "declencheur"}}', encoding="utf-8")
    apres = empreinte.carte()
    assert avant["seuils"] != apres["seuils"]
    assert (avant["regles"], avant["config"]) == (apres["regles"], apres["config"])


if __name__ == "__main__":                   # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
