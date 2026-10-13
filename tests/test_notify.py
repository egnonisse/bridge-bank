"""Tests du notifier Telegram — découpage des longs messages et journal des envois.

Pourquoi : l'API Telegram refuse > 4096 caractères par message. Sans découpage, un
rapport long (radar, analyse value) était PERDU au moment de l'envoi (constat du
13/10/2026 — B2-07). Le découpage vit dans le point de passage unique (`src/notify.py`).
"""
import pytest

from src.notify import (
    LIMITE_TELEGRAM,
    MARGE_DECOUPE,
    TelegramNotifier,
    _decouper,
    _sans_token,  # P7-02 : assainissement des messages d'erreur
)

LIMITE = LIMITE_TELEGRAM - MARGE_DECOUPE


@pytest.fixture(autouse=True)
def _journal_neutre(monkeypatch):
    """N'écrit jamais dans le VRAI journal des alertes (traçabilité de production)."""
    monkeypatch.setattr("src.notify.journal_alertes.enregistrer", lambda *a, **k: None)


# ═════════════════════════════════ _decouper ════════════════════════════════════════

def test_texte_court_non_decoupe():
    t = "🎯 OPPORTUNITÉ NOYAU\nligne 2"
    assert _decouper(t) == [t]


def test_texte_long_decoupe_aux_frontieres_de_lignes():
    lignes = [f"ligne {i:04d} " + "x" * 90 for i in range(80)]   # ~8000 chars
    texte = "\n".join(lignes)
    morceaux = _decouper(texte)
    assert len(morceaux) >= 2
    assert all(len(m) <= LIMITE for m in morceaux)
    # Aucune ligne de contenu n'est perdue ni coupée en deux.
    recompose = "\n".join(morceaux)
    for ligne in lignes:
        assert ligne in recompose


def test_ligne_unique_plus_longue_que_la_limite_coupee_brutalement():
    texte = "y" * (LIMITE * 2 + 10)
    morceaux = _decouper(texte)
    assert all(len(m) <= LIMITE for m in morceaux)
    assert "".join(morceaux) == texte


def test_texte_vide_reste_un_morceau_vide():
    assert _decouper("") == [""]


# ═════════════════════════════════ _envoyer (mock réseau) ════════════════════════════

class _Reponse:
    def __init__(self, code=200):
        self.status_code = code
        self.text = ""


def test_envoyer_decoupe_en_plusieurs_posts(monkeypatch):
    appels = []

    def faux_post(url, json=None, timeout=None):
        appels.append(json["text"])
        return _Reponse(200)

    monkeypatch.setattr("src.notify.requests.post", faux_post)
    n = TelegramNotifier("token", "chat")
    texte = "\n".join(f"ligne {i} " + "z" * 90 for i in range(60))   # > 4096 chars
    assert n.send(texte) is True
    assert len(appels) >= 2
    assert all(len(t) <= LIMITE_TELEGRAM for t in appels)


def test_envoyer_echoue_si_un_morceau_refuse(monkeypatch):
    appels = []

    def faux_post(url, json=None, timeout=None):
        appels.append(json["text"])
        return _Reponse(200 if len(appels) == 1 else 400)   # le 2e morceau échoue

    monkeypatch.setattr("src.notify.requests.post", faux_post)
    n = TelegramNotifier("token", "chat")
    texte = "\n".join(f"ligne {i} " + "z" * 90 for i in range(60))
    assert n.send(texte) is False                            # l'échec est RAPPORTÉ


def test_notifier_desactive_ne_poste_rien(monkeypatch):
    def interdit(*a, **k):                                    # pragma: no cover
        raise AssertionError("aucun post attendu sans configuration")

    monkeypatch.setattr("src.notify.requests.post", interdit)
    assert TelegramNotifier("", "").send("test") is False


def test_message_derreur_logge_sans_token():
    """P7-02 : l'exception `requests` inclut l'URL — donc le token — dans son message.
    Ce qui part au log doit être assaini."""
    brut = (
        "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded "
        "with url: /bot8123456789:AAH_SECRET-xyz_789/sendMessage (Caused by ConnectTimeout)"
    )
    nettoye = _sans_token(brut)
    assert "AAH_SECRET-xyz_789" not in nettoye
    assert "/bot***/sendMessage" in nettoye
