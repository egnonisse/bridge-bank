"""Filtres noyau appliqués à un candidat — verdict + alerte d'achat QUALIFIÉE.

Pipeline d'achat légitime : radar (mouvement) → veille (pourquoi) → CES FILTRES.
Aucune alerte d'achat sans les 4 filtres : dividende officiel > 0, PER ≤ 14,
payout ≤ 80 %, rendement net ≥ 4 % (sinon ordre limite au prix d'entrée).

Verdicts :
  'opportunity' : tous les filtres passent AU COURS ACTUEL → alerte d'achat.
  'limit'       : fondamentaux sains mais cours trop haut → ordre limite au repli.
  None          : filtres ratés → silence total (le radar reste de la veille).
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

from ..collecte.fundamentals import get_fundamentals
from ..taxation import TARGET_NET_YIELD_ENTRY, entry_price_for_net, net_yield  # noqa: E402
from ..taxation import IRVM_DIVIDEND_TAX  # noqa: E402  (C4 : plus de 0,88 en dur, 12/10)

# Filtres d'entrée : définis dans src/regles.py (catalogue unique).
from ..regles import PAYOUT_TIGHT, PER_MAX  # noqa: E402
from ..regles import (  # noqa: E402  (30/10/2026 : position du prix dans l'historique)
    POINT_ENTREE_CROISSANCE_AN,
    POINT_ENTREE_PERCENTILE_CHER,
    POINT_ENTREE_PERCENTILE_PRUDE,
)
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)
from ..infrastructure.ecriture import ecrire_json_atomique  # P7-01 : ecriture atomique
from ..portefeuille.format_fr import fcfa, nombre  # format FR (invariant E1, correction C1)
NET_MAX = 0.10          # borne haute anti-mirage (décision 25/09) : net ≤ 10 %
REFERENCE_AMOUNT = 100_000.0  # taille standard de ligne noyau (pour le calcul d'exemple)

PREP_WATCH_FILE = DATA_DIR / "prep_watch_state.json"  # *_state.json exclu par .gitignore
PREP_REALERT_DOWN_PCT = 0.03  # re-alerte si le prix s'améliore de ≥ 3 % sous la limite


def load_prep_watchlist() -> dict:
    """{code: {"limit": prix_limite, "name": libellé, "alerted_at": date|None}}."""
    try:
        return json.loads(PREP_WATCH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_prep_watchlist(watch: dict) -> None:
    ecrire_json_atomique(PREP_WATCH_FILE, watch)  # P7-01 : écriture atomique


def point_entree(code: str, price: float, hist: dict | None) -> dict | None:
    """Où se situe ce prix dans l'HISTORIQUE du titre — et que vaut ce point d'entrée ?

    Constat du 30/10/2026 : PALC a été acheté au 78e percentile d'un titre PLAT (+1,3 %/an),
    alors que les 8 filtres du noyau ne regardaient QUE le dividende. Coût mesuré : au prix
    médian, le même capital achetait 36 actions au lieu de 26 (+4 518 F/an, +39 % de loyer).

    Le percentile BRUT serait trompeur seul : sur un titre en croissance, un prix haut dans
    sa distribution est NORMAL (SGBC 98e à +11,2 %/an, SNTS 99e à +6,0 %/an). D'où un
    verdict à deux étages : d'abord la TENDANCE, ensuite la position.

    Retourne None si l'historique est trop court (< 250 séances) — jamais d'extrapolation.
    """
    barres = (hist or {}).get(code) or []
    prix = [float(b.close) for b in barres if getattr(b, "close", 0)]
    if len(prix) < 250 or price <= 0:
        return None
    percentile = sum(1 for p in prix if p < price) / len(prix) * 100
    debut, fin = str(barres[0].date)[:10], str(barres[-1].date)[:10]
    annees = max(0.5, (date(int(fin[:4]), int(fin[5:7]), int(fin[8:10]))
                       - date(int(debut[:4]), int(debut[5:7]), int(debut[8:10]))).days / 365.25)
    tendance = ((prix[-1] / prix[0]) ** (1 / annees) - 1) * 100
    if tendance >= POINT_ENTREE_CROISSANCE_AN:
        verdict = "normal"
        phrase = ("titre en croissance : un prix haut dans son historique est la norme, "
                  "pas un signal de cherté")
    elif percentile >= POINT_ENTREE_PERCENTILE_CHER:
        verdict = "cher"
        phrase = ("ACHAT TARDIF : titre plat/cyclique acheté haut dans sa distribution — "
                  "un repli améliorerait nettement le loyer")
    elif percentile >= POINT_ENTREE_PERCENTILE_PRUDE:
        verdict = "prude"
        phrase = "titre plat/cyclique : point d'entrée moyen-haut, sans excès"
    elif percentile >= 50:
        verdict = "normal"
        phrase = "titre plat/cyclique : milieu de sa distribution (rien d'alarmant)"
    else:
        verdict = "normal"
        phrase = "titre plat/cyclique acheté dans la moitié basse de son historique"
    return {"percentile": percentile, "mediane": statistics.median(prix), "ath": max(prix),
            "tendance": tendance, "debut": debut, "verdict": verdict, "phrase": phrase}


def bloc_point_entree(pe: dict | None, dps: float, price: float) -> str:
    """Les lignes « point d'entrée » prêtes à coller dans une alerte (vide si trop court).

    ⚠️ On n'affiche PAS « le loyer qu'on aurait eu au prix médian » : ce calcul appliquerait
    le dps d'AUJOURD'HUI à un prix d'il y a huit ans (SGBC : 16 % de « loyer » fictif, le
    dps de 2018 était bien plus faible). On donne l'ÉCART AU PRIX MÉDIAN — factuel et utile.
    """
    if not pe:
        return ""
    icone = {"normal": "📍", "prude": "🟡", "cher": "🚩"}[pe["verdict"]]
    loyer_ici = net_yield(dps / price) * 100 if price else 0.0
    ecart = (price / pe["mediane"] - 1) * 100 if pe["mediane"] else 0.0
    croissance = pe["tendance"] >= POINT_ENTREE_CROISSANCE_AN
    nature = "croissance" if croissance else "plat/cyclique"
    return (
        f"{icone} Point d'entrée : {pe['percentile']:.0f}e percentile depuis {pe['debut'][:4]} "
        f"(médiane {fcfa(pe['mediane'], signe=False)}, ATH {fcfa(pe['ath'], signe=False)})\n"
        f"   Tendance du titre : {pe['tendance']:+.1f} %/an ({nature})\n"
        f"   Loyer ici {loyer_ici:.1f} % net — ce prix est {ecart:+.0f} % vs la médiane historique\n"
        f"   → {pe['phrase']}\n"
    )


def evaluate_noyau_candidate(code: str, price: float, name: str = "",
                             hist: dict | None = None) -> dict | None:
    """Évalue un candidat contre les filtres noyau. None = rien à faire.

    Filtres (décision 25/09, challenge croisé 3 IA) :
      1. dividende > 0 · 2. net ≥ 4 % · 3. PER ≤ 14 · 4. payout ≤ 80 %
      5. net ≤ 10 % (borne haute anti-mirage)
      6. régularité ≥ 4/5 ans · 7. croissance ≥ −10 %/an · 8. liquidité ≥ 5 M F/j
    hist : cache {code: bars} pour la liquidité (None = non vérifiée).
    """
    code = code.upper()
    if price <= 0:
        return None
    fund = get_fundamentals(code)
    dps = fund.get("dps")
    per = fund.get("per")
    if not dps or dps <= 0 or not per or per <= 0 or per > PER_MAX:
        return None
    payout = dps * per / price
    if payout > PAYOUT_TIGHT:
        return None  # dividende tendu : jamais d'alerte d'achat
    gross = dps / price
    net = net_yield(gross)
    if net > NET_MAX:
        return None  # rendement mirage (FTSC 93 %) : jamais d'alerte d'achat
    entry = entry_price_for_net(dps)
    label = name or code

    # nouveaux filtres (régularité, croissance, liquidité) — décision LEO 25/09
    from ..collecte.dividend_history import dividend_filters

    extra = dividend_filters(code, hist)
    extra_lines = "\n".join(f"      • {n}" for n in extra["notes"]) if extra["notes"] else ""
    if not extra["ok"]:
        # filtres ratés : log local (le radar reste de la veille), jamais d'alerte
        print(f"[noyau-check] {code} rejeté par les filtres de fiabilité : "
              f"{'; '.join(extra['reasons'])}")
        return None

    # Position du prix dans l'historique (30/10/2026) : une INFORMATION, jamais un blocage.
    # Les 8 filtres ci-dessus vérifient le dividende ; ils ne disaient rien du PRIX.
    pe = point_entree(code, price, hist)
    bloc_pe = f"{bloc_point_entree(pe, dps, price)}\n" if pe else ""

    if net >= TARGET_NET_YIELD_ENTRY:
        margin = (entry / price - 1) * 100 if price > 0 else 0.0
        qty = max(1, int(REFERENCE_AMOUNT // price))
        net_annual = qty * dps * (1 - IRVM_DIVIDEND_TAX)
        payout_note = ""
        if payout > 0.75:
            payout_note = f" ⚠️ frontière (limite 80 %) — re-vérifier au prochain résultat"
        msg = (
            f"🎯 OPPORTUNITÉ NOYAU — {code} ({label})\n\n"
            f"💰 Cours : {fcfa(price, signe=False)} — marge vs seuil d'achat ({fcfa(entry, signe=False)}) : {margin:+.1f} %\n\n"
            f"✅ Filtres noyau :\n"
            f"   • Rendement net : {net*100:.1f} % (exigé ≥ 4 %)\n"
            f"   • PER : {per:.1f} (limite 14)\n"
            f"   • Payout : {payout*100:.0f} %{payout_note}\n"
            f"   • Dividende : {fcfa(dps, signe=False)} brut/action\n"
            f"   • Fiabilité :\n{extra_lines}\n\n"
            f"{bloc_pe}"
            f"📋 Ordre : ACHAT {code} ≤ {fcfa(entry, signe=False)}\n"
            f"   → {qty} action(s) ≈ {fcfa(qty*price, signe=False)} · dividende net ≈ {fcfa(net_annual, signe=False)}/an\n\n"
            f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
        )
        return {"verdict": "opportunity", "message": msg}

    payout_note = f" (payout {payout*100:.0f} %)" if payout > 0.75 else ""
    extra_txt = f"\n   • Fiabilité :\n{extra_lines}" if extra_lines else ""
    msg = (
        f"📉 À PRÉPARER — {code} ({label})\n\n"
        f"💰 Cours : {fcfa(price, signe=False)} — rendement net actuel {net*100:.1f} % (< 4 %)\n\n"
        f"✅ Fondamentaux : PER {per:.1f} (≤ 14), dividende {fcfa(dps, signe=False)} brut{payout_note}{extra_txt}\n\n"
        f"{bloc_pe}"
        f"📋 Ordre limite à poser : ≤ {fcfa(entry, signe=False)} (dps ÷ 5,45 % ÷ 1,014 — frais inclus)\n"
        f"   → si le titre revient dans ta zone : ≥ 4 % net COUVERT\n"
        f"   → sinon : tu l'as regardé passer, sans perdre un franc.\n\n"
        f"🚫 Rappel : veille + décision LEO — l'outil ne passe jamais d'ordre."
    )
    return {"verdict": "limit", "message": msg, "limit_price": entry}


def prep_watch_alerts(watch: dict, price_of) -> tuple[list[str], dict]:
    """Surveille les ordres limites « À PRÉPARER ». Retourne (alertes, watch mise à jour).

    Alerte UNE fois quand le prix passe sous la limite (« 🎯 TON ORDRE LIMITE EST PRÊT »),
    puis re-alerte si le prix s'améliore encore de ≥ 3 % sous le prix déjà signalé.
    Les candidats au-dessus de leur limite restent silencieux.
    """
    from datetime import datetime

    alerts: list[str] = []
    today = datetime.now().isoformat()
    # (02/11/2026) Le bloc « point d'entrée » n'est PAS ajouté ici, volontairement : cette
    # alerte ne fait que confirmer qu'un ordre limite DÉJÀ CHOISI par LEO est atteignable,
    # et le bloc exigerait un appel au fondamental par titre (réseau) dans un chemin
    # quotidien — mesuré : +128 s sur la suite de tests quand le site ne répond pas.
    # Le point d'entrée est publié là où il décide : OPPORTUNITÉ, À PRÉPARER, RENFORCE.
    for code, info in list(watch.items()):
        limit = info.get("limit", 0.0)
        price = price_of(code)
        if not price or price <= 0 or price > limit:
            continue
        last = info.get("alerted_price")
        if last is None or price <= last * (1 - PREP_REALERT_DOWN_PCT):
            info["alerted_at"] = today
            info["alerted_price"] = price
            alerts.append(
                f"🎯 TON ORDRE LIMITE EST PRÊT — {code} ({info.get('name', '')})\n\n"
                f"💰 Cours : {fcfa(price, signe=False)} — sous ta limite de {fcfa(limit, signe=False)}.\n"
                f"→ À ce prix, ton loyer garanti est ≥ 4 % net par an.\n"
                f"→ Si tu veux profiter : passe l'ordre ACHAT {code} ≤ {fcfa(limit, signe=False)}.\n"
                f"→ Sinon : tu laisses courir, l'ordre limite reste en veille.\n\n"
                f"🚫 Rappel : décision LEO — l'outil ne passe jamais d'ordre."
            )
    return alerts, watch
