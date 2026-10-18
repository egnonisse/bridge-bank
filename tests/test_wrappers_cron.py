"""Garde-fou B2-08 : les lanceurs de cron sont versionnés, UNIFORMES et bien câblés.

Un lanceur installé vit HORS du dépôt : il doit découvrir la racine seul (env,
position, root.txt, défaut) et ÉCHOUER BRUYAMMENT si elle est introuvable — jamais
un traceback nu, jamais un silence. Ici on verrouille : présence des 6 fichiers, bloc
de découverte identique dans les 6, cibles existantes, et le comportement d'échec.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CRON = RACINE / "scripts" / "cron"
TACHES = ("backup", "close", "daily", "radar_monitor", "report", "specveille")
DEBUT, FIN = "# ==== bloc commun", "# ==== fin du bloc commun ===="


def _bloc(tache: str) -> str:
    texte = (CRON / f"bridgebank_{tache}.py").read_text(encoding="utf-8")
    assert DEBUT in texte and FIN in texte, f"marqueurs du bloc commun absents ({tache})"
    # On jette la fin de la ligne du marqueur : le bloc commence à la ligne suivante.
    return texte.split(DEBUT, 1)[1].split("\n", 1)[1].split(FIN, 1)[0]


def test_les_6_lanceurs_sont_versionnes():
    for tache in TACHES:
        assert (CRON / f"bridgebank_{tache}.py").exists(), f"bridgebank_{tache}.py manquant"


def test_bloc_de_decouverte_identique_dans_les_6():
    """L'uniformité est PROUVÉE, pas supposée : une correction doit toucher les 6."""
    blocs = {t: _bloc(t) for t in TACHES}
    reference = blocs[TACHES[0]]
    for tache, bloc in blocs.items():
        assert bloc == reference, f"bloc de découverte différent dans {tache}"


def test_le_bloc_porte_les_quatre_candidats_et_l_echec_bruyant():
    bloc = _bloc("daily")
    assert "BRIDGEBANK_ROOT" in bloc              # 1. variable d'environnement
    assert "parent.parent.parent" in bloc         # 2. position du fichier
    assert "bridgebank_root.txt" in bloc          # 3. fichier voisin
    assert 'r"DEFAUT_INSTALLE"' in bloc           # 4. défaut inscrit à l'installation
    assert "sys.exit(2)" in bloc                  # échec bruyant
    assert "INERTE" in bloc                       # le message dit l'état, pas un traceback


def test_les_cibles_des_lanceurs_existent():
    """Chaque lanceur pointe une cible réelle du dépôt (aucun chemin mort)."""
    for tache in TACHES:
        texte = (CRON / f"bridgebank_{tache}.py").read_text(encoding="utf-8")
        cibles = re.findall(r'"scripts" / "([a-z_]+\.py)"', texte)
        if cibles:  # daily/close/report/backup/radar : script direct
            for cible in cibles:
                assert (RACINE / "scripts" / cible).exists(), f"{tache} -> {cible} absent"
        else:       # specveille : -m src.main
            assert '"src.main"' in texte and (RACINE / "src" / "main.py").exists()


def test_racine_introuvable_echoue_bruyamment(monkeypatch, capsys, tmp_path):
    """Installer le bloc dans un dossier vide SANS root.txt ni défaut valide : il doit
    sortir en code 2 avec un message qui dit quoi corriger — pas un traceback."""
    code = _bloc("daily").replace('r"DEFAUT_INSTALLE"', 'r"C:/inexistant/bridge"')
    fichier_simule = tmp_path / "bridgebank_daily.py"
    fichier_simule.write_text("", encoding="utf-8")
    monkeypatch.delenv("BRIDGEBANK_ROOT", raising=False)
    espace: dict = {"__file__": str(fichier_simule)}
    exec(compile(code, "bloc_simule", "exec"), espace)  # définit _racine / _python
    with pytest.raises(SystemExit) as exc:
        espace["_racine"]()
    assert exc.value.code == 2
    sortie = capsys.readouterr().err
    assert "INERTE" in sortie and "BRIDGEBANK_ROOT" in sortie


def test_racine_trouvee_dans_le_depot(monkeypatch):
    """Exécuté depuis le dépôt, le bloc découvre la racine par sa position."""
    monkeypatch.delenv("BRIDGEBANK_ROOT", raising=False)
    espace: dict = {"__file__": str(CRON / "bridgebank_daily.py")}
    exec(compile(_bloc("daily"), "bloc_reel", "exec"), espace)
    assert espace["_racine"]() == RACINE
