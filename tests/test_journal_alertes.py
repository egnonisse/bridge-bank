"""Tests du journal des envois et de son cablage dans le transport Telegram.

Ce qui est verrouille ici : chaque envoi laisse une trace avec son empreinte ; un envoi qui
ECHOUE est trace aussi ; un journal illisible ne rend pas les autres lignes inexploitables ; et
une panne de journalisation n'empeche JAMAIS un message de partir.
"""
from __future__ import annotations

import json

import pytest

from src.alertes import journal_alertes
from src.notify import TelegramNotifier

ENTREE = {
    "horodatage": "2026-10-09T09:00:00",
    "origine": "src.main",
    "envoye": True,
    "empreinte": {"code": "abc1234*", "regles": "111111111111", "seuils": "222222222222",
                  "config": "333333333333"},
    "message": "🏦 Noyau : achat propose",
}


@pytest.fixture()
def journal(tmp_path, monkeypatch):
    """Journal isole dans un fichier temporaire : les tests n'ecrivent jamais dans data/."""
    chemin = tmp_path / "alertes_journal.jsonl"
    monkeypatch.setattr(journal_alertes, "ALERTES_JOURNAL", chemin)
    return chemin


# ── le journal lui-même ───────────────────────────────────────────────────────


def test_enregistrer_puis_relire(journal):
    assert journal_alertes.enregistrer(ENTREE, chemin=journal) is True
    entrees = journal_alertes.lire(chemin=journal)
    assert len(entrees) == 1
    assert entrees[0] == ENTREE


def test_append_only_le_plus_recent_en_tete(journal):
    journal_alertes.enregistrer({**ENTREE, "message": "premier"}, chemin=journal)
    journal_alertes.enregistrer({**ENTREE, "message": "second"}, chemin=journal)
    entrees = journal_alertes.lire(chemin=journal)
    assert [e["message"] for e in entrees] == ["second", "premier"]
    assert journal_alertes.compter(chemin=journal) == 2
    assert journal_alertes.derniere(chemin=journal)["message"] == "second"


def test_une_ligne_illisible_n_invalide_pas_le_journal(journal):
    journal.write_text(
        json.dumps(ENTREE) + "\n{ceci n'est pas du json}\n" + json.dumps({**ENTREE, "message": "ok"}) + "\n",
        encoding="utf-8",
    )
    entrees = journal_alertes.lire(chemin=journal)
    assert [e["message"] for e in entrees] == ["ok", ENTREE["message"]]


def test_journal_absent_ou_vide(journal):
    assert journal_alertes.lire(chemin=journal) == []
    assert journal_alertes.derniere(chemin=journal) is None
    assert journal_alertes.compter(chemin=journal) == 0


def test_ecriture_impossible_ne_leve_pas(tmp_path):
    """Chemin impossible (un dossier) : on retourne False et on n'interrompt rien."""
    dossier = tmp_path / "pas_un_fichier"
    dossier.mkdir()
    assert journal_alertes.enregistrer(ENTREE, chemin=dossier) is False


def test_entree_non_serialisable_ne_leve_pas(journal):
    assert journal_alertes.enregistrer({"objet": object()}, chemin=journal) is False


# ── le cablage dans le transport ──────────────────────────────────────────────


def test_un_envoi_impossible_est_trace_quand_meme(journal):
    """Telegram non configure : le message ne part pas, mais l'alerte a bien ete declenchee."""
    notifier = TelegramNotifier("", "")
    assert notifier.send("🔔 ALERTE test") is False
    entree = journal_alertes.derniere(chemin=journal)
    assert entree is not None
    assert entree["envoye"] is False
    assert entree["message"] == "🔔 ALERTE test"
    assert set(entree["empreinte"]) == {"code", "regles", "seuils", "config"}


def test_un_envoi_reussi_est_trace(journal, monkeypatch):
    class Reponse:
        status_code = 200
        text = ""

    monkeypatch.setattr("src.notify.requests.post", lambda *a, **k: Reponse())
    notifier = TelegramNotifier("jeton", "chat")
    assert notifier.send("🔔 ALERTE test") is True
    entree = journal_alertes.derniere(chemin=journal)
    assert entree["envoye"] is True
    assert entree["empreinte"]["seuils"]


def test_l_origine_est_celle_de_l_appelant(journal, monkeypatch):
    """L'origine est lue dans la pile : ici, c'est ce module de test qui a demande l'envoi."""
    monkeypatch.setattr("src.notify.requests.post", lambda *a, **k: type("R", (), {"status_code": 200})())
    TelegramNotifier("jeton", "chat").send("test")
    assert journal_alertes.derniere(chemin=journal)["origine"] == __name__


def test_le_rappel_d_empreinte_est_optionnel(journal, monkeypatch):
    """Par defaut, le message part EXACTEMENT comme avant ; le rappel est un choix."""
    envoyes: list[str] = []

    class Reponse:
        status_code = 200

    def faux_post(_url, json=None, **_k):
        envoyes.append(json["text"])
        return Reponse()

    monkeypatch.setattr("src.notify.requests.post", faux_post)

    TelegramNotifier("jeton", "chat").send("ALERTE")
    assert envoyes[-1] == "ALERTE"

    TelegramNotifier("jeton", "chat", empreinte_dans_message=True).send("ALERTE")
    assert envoyes[-1].startswith("ALERTE\n\n— v")
    assert "seuils" in envoyes[-1]
    # Le journal garde le TEXTE de l'alerte, sans la repetition de l'empreinte.
    assert journal_alertes.derniere(chemin=journal)["message"] == "ALERTE"


def test_une_panne_de_journalisation_n_empeche_pas_l_envoi(journal, monkeypatch):
    """La garantie qui compte : l'alerte passe AVANT sa trace."""
    class Reponse:
        status_code = 200

    monkeypatch.setattr("src.notify.requests.post", lambda *a, **k: Reponse())

    def explose(*_a, **_k):
        raise RuntimeError("disque plein")

    monkeypatch.setattr("src.notify.journal_alertes.enregistrer", explose)
    assert TelegramNotifier("jeton", "chat").send("ALERTE") is True


if __name__ == "__main__":                   # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
