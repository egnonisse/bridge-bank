"""Capture les SORTIES du noyau dividende — référence AVANT le découpage (lot 5).

POURQUOI CE SCRIPT EXISTE
-------------------------
Un déplacement se vérifie par les constantes et les tests. Un DÉCOUPAGE, non : les mêmes valeurs
peuvent produire des messages différents si une fonction est recopiée de travers, si un texte est
réécrit au passage ou si un appelant reçoit un autre objet. Ce script fige donc les SORTIES
RÉELLES du code déjà validé (messages d'alerte, niveaux, lignes d'historique, renforcements) dans
un fichier de référence versionné ; `tests/test_sorties_invariables.py` recalcule et compare.

Tant que la comparaison est verte, le découpage n'a rien changé au comportement métier.

CE QUI EST FIGÉ — ET POURQUOI
-----------------------------
- **un portefeuille FIXTURE**, jamais le vrai : la référence doit être reproductible ailleurs
  que sur cette machine ;
- **une HORLOGE FIGÉE** : les messages portent une date de prochaine vérification et une durée de
  détention. Sans horloge figée, la référence changerait chaque jour et ne prouverait rien ;
- **des SEUILS et un PROFIL DE RETOURNEMENT FIXTURES** : le fichier réel bouge avec les décisions
  de LEO. Une référence qui casse quand il change un seuil ne serait pas une référence de CODE.

CE QUI N'EST PAS FIGÉ (assumé)
------------------------------
`explication()` et `resume_justification()` viennent de `seuils_vente` et sont REMPLACÉES par des
textes d'emplacement : elles ont leurs propres tests, et les figer ici couplerait cette référence
aux décisions de calibrage. La référence couvre l'ASSEMBLAGE fait par `portfolio.py`.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.calibration import seuils_vente  # noqa: E402
from src.infrastructure.paths import RACINE as RACINE_PROJET  # noqa: E402
from src.portefeuille import format_fr  # noqa: E402
from src import portfolio  # noqa: E402

SORTIE = RACINE_PROJET / "tests" / "fixtures" / "sorties_reference.json"
HORLOGE = datetime(2026, 10, 9, 10, 0, 0)

# Références RÉELLES, prises À L'IMPORT — donc avant tout remplacement par une fixture.
# Sans cela, une fonction que le contexte remplace plus loin serait capturée à travers son
# bouchon : la référence figerait « une valeur constante » au lieu du comportement, et elle
# resterait verte quoi qu'il arrive à la vraie fonction. C'est le même piège que l'empreinte
# calculée sur des fichiers introuvables.
_REELLES = {"is_cooldown_active": portfolio.is_cooldown_active}

# Seuils fixtures : SNTS et SLBC DÉCLENCHENT, SGBC et PALC informent seulement.
SEUILS = {
    "SNTS": {"threshold": 0.13, "down_prob": 86, "borne_basse": 49, "episodes": 56,
             "significatif": True, "mode": "declencheur"},
    "SGBC": {"threshold": 0.10, "down_prob": 63, "borne_basse": 46, "episodes": 30,
             "significatif": False, "mode": "informatif"},
    "SLBC": {"threshold": 0.05, "down_prob": 54, "borne_basse": 36, "episodes": 41,
             "significatif": True, "mode": "declencheur"},
    "PALC": {"threshold": 0.05, "down_prob": 45, "borne_basse": 34, "episodes": 56,
             "significatif": False, "mode": "informatif"},
}
PROFILS = {
    "SNTS": {"seuil_pct": 13, "episodes": 56, "pct_down_20j": 86, "significatif": True,
             "median_20j": -8.4, "trough_delay_median": 12, "trough_depth_median": -11.2},
    "SGBC": {"seuil_pct": 10, "episodes": 30, "pct_down_20j": 63, "significatif": False,
             "median_20j": -5.1, "trough_delay_median": 9, "trough_depth_median": -8.0},
    "SLBC": {"seuil_pct": 5, "episodes": 3, "pct_down_20j": 54, "significatif": False,
             "median_20j": -4.2, "trough_delay_median": 7, "trough_depth_median": -6.5},
    "PALC": {"seuil_pct": 21, "episodes": 56, "pct_down_20j": 45, "significatif": False,
             "median_20j": -3.3, "trough_delay_median": 11, "trough_depth_median": -7.1},
}


class HorlogeFigee:
    """Remplace `portfolio.datetime` : les sorties portent des dates, la référence doit être stable."""

    @staticmethod
    def now() -> datetime:
        return HORLOGE

    @staticmethod
    def fromisoformat(valeur: str) -> datetime:
        return datetime.fromisoformat(valeur)


# Noms, cours et fondamentaux fixtures des titres utilisés par la capture.
NOMS = {"SNTS": "Sonatel", "SGBC": "Société Générale Côte d'Ivoire", "SLBC": "Solibra",
        "PALC": "Palmci", "BOAS": "Bank of Africa CI", "SOGC": "Sogb"}
COURS = {"SNTS": 36500.0, "SGBC": 33000.0, "SLBC": 39000.0, "PALC": 12000.0,
         "BOAS": 28000.0, "SOGC": 6500.0}
FONDAMENTAUX = {
    "SNTS": {"dps": 1977.0, "per": 6.2},
    "SGBC": {"dps": 3000.0, "per": 8.1},
    "SLBC": {"dps": 1400.0, "per": 12.4},
    "PALC": {"dps": 400.0, "per": 9.5},
    "BOAS": {"dps": 1500.0, "per": 7.5},
    "SOGC": {"dps": 300.0, "per": 11.0},
}


class _FauxSnapshot:
    def __init__(self, cours: dict) -> None:
        self._cours = cours

    def by_code(self, code):
        cle = (code or "").strip().upper()
        if cle not in self._cours:
            return None
        return SimpleNamespace(code=cle, name=NOMS.get(cle, cle), last=self._cours[cle])


class FausseApi:
    """Remplace `main.BSApi` : un snapshot figé, aucun appel réseau."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def market_snapshot(self):
        return _FauxSnapshot(COURS)


class _NotifierMuët:
    """Remplace le notificateur : une capture ne doit JAMAIS envoyer de Telegram."""

    enabled = False

    def send(self, texte: str) -> bool:            # noqa: D102
        return False


def _positions() -> list[portfolio.DividendPosition]:
    """Portefeuille fixture : 4 titres, dont un détenu depuis plus de 3 ans (échéance)."""
    return [
        portfolio.DividendPosition(code="SNTS", name="Sonatel", entry_price=32000.0, quantity=9,
                                   dps=1977.0, per_open=6.2, opened_at="2026-01-15T09:00:00"),
        portfolio.DividendPosition(code="SGBC", name="Société Générale Côte d'Ivoire",
                                   entry_price=39000.0, quantity=3, dps=3000.0, per_open=8.1,
                                   opened_at="2026-02-02T09:00:00"),
        portfolio.DividendPosition(code="SLBC", name="Solibra", entry_price=37500.0, quantity=4,
                                   dps=1400.0, per_open=12.4, opened_at="2026-03-10T09:00:00"),
        portfolio.DividendPosition(code="PALC", name="Palmci", entry_price=8900.0, quantity=12,
                                   dps=400.0, per_open=9.5, opened_at="2023-06-01T09:00:00"),
    ]


def _grille(pos: portfolio.DividendPosition) -> list[float]:
    """Prix capturés : autour de l'entrée, PLUS les deux bornes qui déclenchent une sortie."""
    base = pos.entry_price
    prix = [round(base * f, 2) for f in (0.80, 0.88, 0.95, 1.00, 1.05, 1.13, 1.20, 1.40)]
    for borne in (pos.exit_price, pos.entry_price_ref):
        if borne > 0:
            prix.append(round(borne, 2))
    return sorted(set(prix))


@contextlib.contextmanager
def _fixtures_posees():
    """Branche `portfolio`, `seuils_vente` et `main` sur les fixtures — PUIS RESTAURE TOUT.

    La restauration n'est pas une politesse : ce module est appelé DEPUIS LES TESTS. Laisser
    `portfolio.load_profit_thresholds` remplacé par une fixture ferait échouer d'autres tests
    selon l'ordre d'exécution — une pollution d'état qui ne se voit que certains jours, et
    jamais en local quand on lance un seul fichier.
    """
    from tempfile import TemporaryDirectory

    from src.collecte import fundamentals as mod_fundamentals
    from src.strategie import speculation as mod_speculation
    from src import main as mod_main

    cibles = [
        (portfolio, ("REVERSAL_FILE", "datetime", "load_profit_thresholds",
                     "profit_threshold_for", "load_portfolio", "save_portfolio",
                     "load_alert_state", "save_alert_state", "is_cooldown_active")),
        (seuils_vente, ("est_declencheur", "explication", "resume_justification")),
        (mod_main, ("BSApi", "get_notifier")),
        (mod_fundamentals, ("get_fundamentals",)),
        (mod_speculation, ("load_positions",)),
    ]
    sauves = [(mod, [(nom, getattr(mod, nom)) for nom in noms]) for mod, noms in cibles]
    try:
        with TemporaryDirectory() as dossier:
            profils = Path(dossier) / "reversal.json"
            profils.write_text(json.dumps(PROFILS), encoding="utf-8")
            portfolio.REVERSAL_FILE = profils
            portfolio.datetime = HorlogeFigee
            portfolio.load_profit_thresholds = lambda: copy.deepcopy(SEUILS)
            portfolio.profit_threshold_for = lambda code: SEUILS.get(code.upper(), {}).get("threshold", 0.13)
            portfolio.load_portfolio = lambda: copy.deepcopy(_positions())
            portfolio.save_portfolio = lambda positions: None      # JAMAIS data/portfolio.json
            portfolio.load_alert_state = lambda: {}
            portfolio.save_alert_state = lambda state: None
            portfolio.is_cooldown_active = lambda state, code: False
            seuils_vente.est_declencheur = lambda info: bool(info) and info.get("mode") == "declencheur"
            seuils_vente.explication = lambda info: "   <explication du seuil — fournie par seuils_vente>"
            seuils_vente.resume_justification = lambda code: "   <justification du seuil — seuils_vente>"
            mod_main.BSApi = FausseApi
            mod_main.get_notifier = lambda cfg: _NotifierMuët()
            mod_fundamentals.get_fundamentals = lambda code: dict(FONDAMENTAUX.get(code.upper(), {}))
            mod_speculation.load_positions = lambda: []
            yield
    finally:
        for mod, paires in sauves:
            for nom, valeur in paires:
                setattr(mod, nom, valeur)


def _capturer_position(pos, out: dict) -> None:
    """Toutes les sorties d'UNE position : modèle, niveaux, alertes, historique."""
    for prix in _grille(pos):
        cle = f"|{pos.code}|prix={prix:g}"
        out["status_level" + cle] = list(portfolio.status_level(pos, prix))
        alerts = portfolio.check_dividend_position(copy.deepcopy(pos), prix, pos.dps, pos.per_open)
        out["check_dividend_position" + cle] = [
            [a.level, a.message, a.code] for a in alerts
        ]
        out["profit_info_alert" + cle] = _alerte(portfolio._profit_info_alert(pos, prix))
        out["double_option_alert" + cle] = _alerte(portfolio._double_option_alert(pos, prix))
        out["loss_coverage_alert" + cle] = _alerte(portfolio._loss_coverage_alert(pos, prix))
        out["info_alert" + cle] = _alerte(portfolio._info_alert(pos, prix))
        out["payout_ratio" + cle] = portfolio.payout_ratio(pos.dps, prix, pos.per_open)
        out["soutenabilite" + cle] = _alerte(
            portfolio._soutenabilite_alert(pos, pos.dps, pos.per_open, prix)
        )
        out["history_line" + cle] = portfolio._history_line(pos)
    # Modèle + calculs purs (indépendants du prix courant)
    out[f"modele|{pos.code}"] = {
        "exit_price": pos.exit_price, "entry_price_ref": pos.entry_price_ref,
        "invested": pos.invested, "yield_pct": pos.yield_pct(pos.entry_price),
        "net_yield_pct": pos.net_yield_pct(pos.entry_price),
        "sell_profit_net_13": list(portfolio._sell_profit_net(pos, pos.entry_price * 1.13, 1 / 3)),
        "dividende_annuel_net": portfolio._dividend_annual_net(pos),
    }
    # Enregistrement d'un dividende (mutation → on capture le retour ET l'état résultant)
    copie = copy.deepcopy(pos)
    cash, actions, residu = portfolio.record_dividend(copie, copie.entry_price)
    out[f"record_dividend|{pos.code}"] = {
        "retour": [cash, actions, residu], "quantity": copie.quantity,
        "dividends_earned": copie.dividends_earned, "cash_residual": copie.cash_residual,
    }


def _alerte(a) -> list | None:
    return None if a is None else [a.level, a.message, a.code]


def _capturer_renforcements(out: dict) -> None:
    """Les 4 niveaux du verrou de concentration + le contexte de marché (3 régimes)."""
    prix, per = 30000.0, 6.2
    scenarios = {
        "libre": (30, 9, 1_000_000.0),          # B dilue les achats ; poids marché 27 %
        "limite": (30, 9, 600_000.0),           # poids marché 45 %, achats 20 %
        "en_conscience": (3, 9, 1_000_000.0),   # achats 71 % de la poche
        "maximum": (30, 9, 400_000.0),          # poids marché 68 %
    }
    for nom, (qte_b, qte_a, total) in scenarios.items():
        positions = [
            portfolio.DividendPosition(code="SNTS", name="Sonatel", entry_price=32000.0,
                                       quantity=qte_a, dps=1977.0, per_open=6.2,
                                       opened_at="2026-01-15T09:00:00"),
            portfolio.DividendPosition(code="SGBC", name="Société Générale Côte d'Ivoire",
                                       entry_price=39000.0, quantity=qte_b, dps=3000.0,
                                       per_open=8.1, opened_at="2026-02-02T09:00:00"),
        ]
        for regime_nom, regime in (("aucun", None), ("baissier", {"etat": "BAISSIER"}),
                                   ("haussier", {"etat": "HAUSSIER"})):
            hits, blocked = portfolio.reinforcement_messages(
                positions, lambda c: prix, lambda c: per, total, regime=regime
            )
            out[f"renforcement|{nom}|{regime_nom}"] = {"hits": hits, "blocked": blocked}


def _capturer_commandes(out: dict) -> None:
    """Les commandes CLI qui TRAVERSENT `portfolio.py` — figées sur les fixtures.

    POURQUOI CES SIX-LÀ, ET PAS D'AUTRES : `report`, `filet` et `limits` ont été vérifiées dans
    le code — elles ne passent PAS par `portfolio.py` (report → `report`/`orders`/`speculation` ;
    filet → `speculation` ; limits → `orders`/`collecte`). Les capturer n'apprendrait rien sur le
    découpage du noyau dividende, alors que `portf` et `sustain` en dépendent entièrement.
    """
    from src import main

    def capturer_commande(nom: str, fonction, **champs) -> None:
        args = argparse.Namespace(**{
            "action": None, "code": None, "amount": 100000.0, "dps": None, "per": None,
            "target": 4.0, "_actions": None, **champs,
        })
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            fonction(args)
        out[f"commande|{nom}"] = tampon.getvalue()

    capturer_commande("portf status", main.cmd_portf, action="status")
    capturer_commande("portf check — sans cooldown", main.cmd_portf, action="check",
                      _actions=["(plan vide)"])
    portfolio.is_cooldown_active = lambda state, code: True      # 2e branche : cooldown actif
    capturer_commande("portf check — cooldown actif", main.cmd_portf, action="check")
    portfolio.is_cooldown_active = lambda state, code: False
    capturer_commande("portf open — sans --dps/--per", main.cmd_portf, action="open", code="BOAS")
    capturer_commande("portf open — BOAS", main.cmd_portf, action="open", code="BOAS",
                      dps=1500.0, per=7.5)
    capturer_commande("portf dividend — SNTS", main.cmd_portf, action="dividend", code="SNTS")
    capturer_commande("portf close — SGBC", main.cmd_portf, action="close", code="SGBC")
    capturer_commande("sustain", main.cmd_sustain)
    out["heartbeat|rien à signaler"] = main._build_heartbeat(
        [("BOC", True), ("Annonces BRVM", True), ("Filet spéculation", True)]
    )
    out["heartbeat|avec plan d'action"] = main._build_heartbeat(
        [("BOC", True), ("Déclencheurs de sortie", False)],
        ["Vends 1 sur 3 de SNTS", "Décision sur PALC"],
    )


def capturer() -> dict:
    """Rejoue toutes les sorties du module et renvoie la référence complète."""
    out: dict = {}
    with _fixtures_posees():
        for pos in _positions():
            _capturer_position(pos, out)
        _capturer_renforcements(out)
        out["msg_regime|aucun"] = portfolio._msg_regime(None)
        out["msg_regime|baissier"] = portfolio._msg_regime({"etat": "BAISSIER"})
        out["msg_regime|haussier"] = portfolio._msg_regime({"etat": "HAUSSIER"})
        out["cooldown|absent"] = _REELLES["is_cooldown_active"]({}, "SNTS")
        out["cooldown|récent"] = _REELLES["is_cooldown_active"](
            {"SNTS": "2026-10-08T09:00:00"}, "SNTS"
        )
        out["cooldown|périmé"] = _REELLES["is_cooldown_active"](
            {"SNTS": "2026-09-01T09:00:00"}, "SNTS"
        )
        out["format_fr|fcfa"] = format_fr.fcfa(-1234567.0, signe=True)
        out["format_fr|pct"] = format_fr.pct(8.4321, signe=True)
        _capturer_commandes(out)
    return out


def normaliser(valeur):
    """Rend la référence comparable : dates remplacées, ordre stable.

    Deux formats de date apparaissent dans les sorties : « 09/10/2026 » (prochaine vérification)
    et « 09/10 10:00 » (résumé quotidien — qui, lui, importe `datetime` localement et échappe donc
    à l'horloge figée). Les deux sont remplacés par `<DATE>` : la référence doit être reproductible
    à l'octet, sinon elle ne prouve rien. En contrepartie, un changement de FORMAT de date ne
    serait pas détecté — c'est un détail d'affichage, visible en relecture.

    Les TUPLES comptent aussi : JSON les réécrit en listes, donc sans cette conversion la
    comparaison verrait une différence de TYPE là où le contenu est identique.
    """
    if isinstance(valeur, str):
        valeur = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "<DATE>", valeur)
        return re.sub(r"\b\d{2}/\d{2} \d{2}:\d{2}\b", "<DATE>", valeur)
    if isinstance(valeur, dict):
        return {k: normaliser(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, (list, tuple)):
        return [normaliser(v) for v in valeur]
    return valeur


def main() -> int:
    resultat = normaliser(capturer())
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(resultat, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"référence écrite : {SORTIE.relative_to(RACINE)}")
    print(f"  {len(resultat)} sorties capturées")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
