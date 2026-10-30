"""Renvoi des alertes dont l'envoi a échoué (panne réseau du 23/10/2026).

Le journal enregistre `envoye: false` quand Telegram (ou le réseau) ne répond pas — mais
l'alerte n'était jamais retentée : elle était perdue pour de bon. Le 23/10/2026, l'alerte
« check quotidien — 7 étapes en échec, BOC : événement » est ainsi restée invisible.

Ce qui est verrouillé ici : une alerte récente non délivrée est renvoyée UNE fois,
préfixée « RATTRAPÉE » ; la reprise est journalisée avec `reprise_de` ; une alerte
périmée n'est pas ressuscitée ; les envois réussis ne sont jamais repris.
"""
import json
from datetime import datetime, timedelta

from src.alertes import journal_alertes
from src.notify import TelegramNotifier


def _notifier(monkeypatch) -> TelegramNotifier:
    """Notifier armé, sans réseau : `_envoyer` répond True."""
    notifier = TelegramNotifier("token-de-test", "chat-de-test")
    monkeypatch.setattr(TelegramNotifier, "_envoyer", lambda self, texte: True)
    return notifier


def _journal(tmp_path, monkeypatch, entrees) -> object:
    chemin = tmp_path / "alertes.jsonl"
    chemin.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entrees) + "\n",
                      encoding="utf-8")
    monkeypatch.setattr(journal_alertes, "ALERTES_JOURNAL", chemin)
    return chemin


def _entree(horodatage, message, envoye=False, **extra) -> dict:
    entree = {"horodatage": horodatage, "origine": "src.main", "envoye": envoye,
              "empreinte": {"code": "abc", "regles": "r", "seuils": "s", "config": "c"},
              "message": message}
    entree.update(extra)
    return entree


def test_une_alerte_ratee_recente_est_renvoyee(tmp_path, monkeypatch):
    hier = (datetime.now() - timedelta(hours=20)).isoformat(timespec="seconds")
    _journal(tmp_path, monkeypatch, [
        _entree(hier, "Check quotidien — 7 étape(s) en ÉCHEC — BOC : événement")])
    notifier = _notifier(monkeypatch)

    assert notifier.renvoyer_non_delivrees() == [hier]

    entrees = journal_alertes.lire()
    assert any(e.get("reprise_de") == hier for e in entrees), "la reprise doit être tracée"
    assert any("RATTRAPÉE" in e.get("message", "") for e in entrees)
    assert any(e.get("envoye") for e in entrees), "la reprise est notée comme envoyée"


def test_pas_de_double_renvoi(tmp_path, monkeypatch):
    """Deuxième exécution : RIEN. `reprise_de` verrouille l'alerte déjà rattrapée."""
    hier = (datetime.now() - timedelta(hours=20)).isoformat(timespec="seconds")
    _journal(tmp_path, monkeypatch, [_entree(hier, "alerte perdue")])
    notifier = _notifier(monkeypatch)

    assert notifier.renvoyer_non_delivrees() == [hier]
    assert notifier.renvoyer_non_delivrees() == []


def test_une_alerte_trop_ancienne_n_est_pas_ressuscitee(tmp_path, monkeypatch):
    """Au-delà de 48 h, l'alerte n'apprend plus rien : on ne la renvoie pas."""
    ancienne = (datetime.now() - timedelta(days=5)).isoformat(timespec="seconds")
    _journal(tmp_path, monkeypatch, [_entree(ancienne, "alerte périmée")])
    assert _notifier(monkeypatch).renvoyer_non_delivrees() == []


def test_une_alerte_envoyee_n_est_jamais_reprise(tmp_path, monkeypatch):
    hier = (datetime.now() - timedelta(hours=20)).isoformat(timespec="seconds")
    _journal(tmp_path, monkeypatch, [_entree(hier, "alerte bien reçue", envoye=True)])
    assert _notifier(monkeypatch).renvoyer_non_delivrees() == []


def test_plafond_par_run(tmp_path, monkeypatch):
    """8 alertes ratées → au plus 5 renvoyées dans le même run (pas de rafale)."""
    entrees = [_entree((datetime.now() - timedelta(hours=h)).isoformat(timespec="seconds"),
                       f"alerte {h}") for h in range(1, 9)]
    _journal(tmp_path, monkeypatch, entrees)
    notifier = _notifier(monkeypatch)
    assert len(notifier.renvoyer_non_delivrees()) == 5
    # le run suivant rattrape les 3 restantes
    assert len(notifier.renvoyer_non_delivrees()) == 3


def test_notifier_desactive_ne_renvoie_rien(tmp_path, monkeypatch):
    hier = (datetime.now() - timedelta(hours=20)).isoformat(timespec="seconds")
    _journal(tmp_path, monkeypatch, [_entree(hier, "alerte")])
    desactive = TelegramNotifier("", "")
    assert desactive.enabled is False
    assert desactive.renvoyer_non_delivrees() == []
