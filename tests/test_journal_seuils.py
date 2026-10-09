"""Tests du journal des seuils — append-only et traçabilité des changements.

POURQUOI CE FICHIER EXISTE
--------------------------
Le journal répond à une réserve explicite de LEO (08/10/2026) : **git ne suffit pas**. Il
dit quand le CODE a changé — pas quand un SEUIL a changé pendant l'exécution, ni pourquoi.
Un seuil recalibré automatiquement peut basculer sans qu'aucun commit n'apparaisse.

Un journal non testé serait pire qu'aucun journal : il donnerait l'illusion d'une trace
sans en garantir l'intégrité. Ces tests vérifient ce qui compte — qu'une entrée écrite ne
peut plus disparaître, et que les sept informations exigées sont bien là.
"""
import json
from pathlib import Path

import pytest

from src.calibration import seuils_vente as sv


@pytest.fixture
def journal(tmp_path):
    return tmp_path / "seuils_journal.jsonl"


def test_journal_sept_informations(journal):
    """Les sept informations exigées par LEO doivent toutes être présentes."""
    e = sv.journaliser("SNTS", avant=0.13, apres=0.10, motif="test", origine="manuelle",
                       test={"down_prob": 86, "borne_basse": 49, "episodes": 7},
                       chemin=journal)

    for champ in ("horodatage", "titre", "avant", "apres", "motif", "origine",
                  "methode"):
        assert champ in e, f"champ manquant : {champ}"
    assert e["titre"] == "SNTS"
    assert e["avant"] == 0.13 and e["apres"] == 0.10
    assert e["origine"] == "manuelle"
    # 7e information : le résultat du test statistique
    assert e["test"]["borne_basse"] == 49


def test_journal_est_append_only(journal):
    """Écrire une entrée ne doit JAMAIS toucher aux précédentes."""
    sv.journaliser("SNTS", 0.13, 0.10, "premier", "manuelle", chemin=journal)
    sv.journaliser("SGBC", 0.10, 0.08, "deuxieme", "manuelle", chemin=journal)
    sv.journaliser("SNTS", 0.10, 0.13, "troisieme", "manuelle", chemin=journal)

    lignes = journal.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 3, "chaque appel doit ajouter UNE ligne"
    motifs = [json.loads(l)["motif"] for l in lignes]
    assert motifs == ["premier", "deuxieme", "troisieme"], "l'ordre d'écriture est perdu"


def test_une_ligne_corrompue_ne_perd_pas_le_reste(journal):
    """Un octet abîmé ne doit pas rendre l'historique entier illisible.

    C'est l'argument décisif pour le format ligne-par-ligne plutôt qu'un JSON unique :
    une écriture interrompue n'emporte que sa propre ligne.
    """
    sv.journaliser("SNTS", None, 0.13, "avant", "manuelle", chemin=journal)
    with journal.open("a", encoding="utf-8") as f:
        f.write("{ceci n'est pas du json\n")
    sv.journaliser("SNTS", 0.13, 0.10, "apres", "manuelle", chemin=journal)

    hist = sv.lire_journal("SNTS", chemin=journal)
    assert [e["motif"] for e in hist] == ["avant", "apres"]


def test_lire_journal_filtre_par_titre(journal):
    sv.journaliser("SNTS", None, 0.13, "a", "manuelle", chemin=journal)
    sv.journaliser("SGBC", None, 0.10, "b", "manuelle", chemin=journal)

    assert len(sv.lire_journal(chemin=journal)) == 2
    assert [e["motif"] for e in sv.lire_journal("SNTS", chemin=journal)] == ["a"]


def test_dernier_changement_est_le_plus_recent(journal):
    """Sert à justifier une alerte : il faut la DERNIÈRE version, pas la première."""
    sv.journaliser("SNTS", None, 0.13, "ancien", "manuelle", chemin=journal)
    sv.journaliser("SNTS", 0.13, 0.10, "recent", "automatique", chemin=journal)

    dernier = sv.dernier_changement("SNTS", chemin=journal)
    assert dernier["motif"] == "recent"
    assert dernier["origine"] == "automatique"


def test_journal_absent_ne_plante_pas(tmp_path):
    """Un premier démarrage n'a pas d'historique : ce n'est pas une erreur."""
    assert sv.lire_journal(chemin=tmp_path / "inexistant.jsonl") == []
    assert sv.dernier_changement("SNTS", chemin=tmp_path / "inexistant.jsonl") is None


def test_le_dossier_est_cree_si_absent(tmp_path):
    cible = tmp_path / "sous" / "dossier" / "journal.jsonl"
    sv.journaliser("SNTS", None, 0.13, "test", "manuelle", chemin=cible)
    assert cible.exists()


def test_calibrage_automatique_journalise_le_test_statistique(journal, monkeypatch):
    """Un calibrage écrit au journal DOIT porter son résultat statistique.

    Sans cette information, on saurait qu'un seuil a changé sans savoir sur quelle base
    — c'est-à-dire qu'on n'aurait rien appris.
    """
    monkeypatch.setattr(sv, "JOURNAL_FILE", journal)

    # Assez de séances pour produire des épisodes à plusieurs seuils candidats.
    closes = [100.0]
    for i in range(400):
        closes.append(closes[-1] * (1.02 if i % 3 else 0.97))

    info = sv.calibrer("TEST", closes)
    assert info is not None, "un historique de 400 séances doit produire un candidat"

    sv.journaliser("TEST", avant=None, apres=info["threshold"],
                   motif=sv.MOTIF_CALIBRAGE, origine=sv.ORIGINE_AUTO,
                   test={k: info[k] for k in ("down_prob", "borne_basse", "episodes",
                                              "significatif", "mode")})

    e = sv.lire_journal("TEST", chemin=journal)[-1]
    assert e["origine"] == "automatique"
    assert "down_prob" in e["test"]
    assert "borne_basse" in e["test"]
    assert "significatif" in e["test"]
    assert e["methode"], "la méthode de calibration doit être tracée"


def test_resume_justification_trace_l_origine(tmp_path, monkeypatch):
    """La version minimale de la traçabilité : l'alerte dit d'où vient son seuil."""
    seuils = tmp_path / "seuils.json"
    seuils.write_text(json.dumps({
        "SNTS": {"threshold": 0.13, "down_prob": 86, "episodes": 7,
                 "mode": "informatif"}
    }), encoding="utf-8")
    journal = tmp_path / "journal.jsonl"
    sv.journaliser("SNTS", None, 0.13, "calibrage initial", "automatique", chemin=journal)

    monkeypatch.setattr(sv, "SEUILS_FILE", seuils)
    monkeypatch.setattr(sv, "JOURNAL_FILE", journal)

    ligne = sv.resume_justification("SNTS")
    assert "13 %" in ligne, "le seuil appliqué doit apparaître"
    assert "86 %" in ligne and "7 cas" in ligne, "la justification doit apparaître"
    assert "automatique" in ligne, "l'origine du seuil doit apparaître"


def test_resume_justification_vide_si_titre_inconnu(tmp_path, monkeypatch):
    monkeypatch.setattr(sv, "SEUILS_FILE", tmp_path / "vide.json")
    assert sv.resume_justification("INCONNU") == ""
