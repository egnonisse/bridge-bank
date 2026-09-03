"""Check de clôture (16h) : candidats spéculation « en conscience ».

Détecte les candidats validés à la clôture du jour et alerte « à jouer DEMAIN
à l'ouverture ». Chaque alerte est NÉOPHYTE-COMPRÉHENSIBLE (règle LEO 03/09) :
  1. ce qui se passe, en langage courant ;
  2. ⚠️ TOUJOURS en tête : ce que nos 9 ans de données disent (l'analyse) ;
  3. 💰 une PROPOSITION de plafond de poche (calculée, LEO décide) ;
  4. 📋 l'action chiffrée si LEO décide de jouer quand même ;
  5. 🚫 la règle d'or des poches étanches.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def propose_plafond(total: float) -> int:
    """Plafond de poche proposé : ~10 % du portefeuille, arrondi à 10 000 F."""
    if total <= 0:
        return 70_000
    return max(10_000, int(round(total * 0.10 / 10_000) * 10_000))


def main() -> None:
    import logging

    from src.bsapi import BSApi
    from src.live import ORDER_CUTOFF_BSTRADE
    from src.main import get_notifier, load_config, load_dotenv
    from src.portfolio import load_portfolio
    from src.speculation import (
        MIN_SIGNALS,
        STOP_LOSS,
        TAKE_1,
        TAKE_2,
        TAKE_3,
        detect_new_candidates,
    )
    from src.report import load_state  # cash du portefeuille

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()

    api = BSApi()
    new = detect_new_candidates(api, min_signals=MIN_SIGNALS)
    if not new:
        print("Aucun nouveau candidat spéculatif à la clôture.")
        return

    # Portefeuille réel pour la proposition de plafond
    try:
        positions = [p for p in load_portfolio() if not p.closed]
        state = load_state()
        total = sum(p.quantity * p.entry_price for p in positions) + float(state.get("cash", 0.0))
    except Exception:
        total = 0.0
    plafond = propose_plafond(total)
    win_min = 150_000  # seuil où l'espérance redevient positive (épreuve 26/08)

    notifier = get_notifier(load_config())
    for c in new:
        last = c["last"]
        qty = max(1, int(plafond // last)) if last > 0 else 1
        limit = round(last * 1.03)
        stop = round(last * (1 - STOP_LOSS))
        t1 = round(last * (1 + TAKE_1))
        t2 = round(last * (1 + TAKE_2))
        t3 = round(last * (1 + TAKE_3))
        msg = (
            f"🎲 PARI RAPIDE — {c['name']} ({c['code']})\n\n"
            f"Ce qui se passe : le prix vient de dépasser son plus haut des\n"
            f"20 derniers jours ({c['count']} signaux convergents). Certains y\n"
            f"voient le début d'une montée. Cours de clôture : {last:,.0f} F.\n\n"
            f"⚠️ CE QUE DISENT NOS 9 ANS DE DONNÉES (toujours, avant de décider) :\n"
            f"   • « Beaucoup d'acheteurs » ne prédit rien : avec ce signal,\n"
            f"     32 % de réussite… sans ce signal aussi 32 %.\n"
            f"   • Avec un pari de {plafond:,.0f} F, en moyenne tu perds ~7 F\n"
            f"     pour 1 000 F misés (les frais te mangent le gain).\n"
            f"   • Aucune de nos 5 façons de parier n'a battu le simple\n"
            f"     hasard, une fois les frais payés.\n\n"
            f"💰 MONTANT SUGGÉRÉ POUR CE PARI (tu décides) :\n"
            f"   → Plafond proposé : {plafond:,.0f} F (~10 % de ton portefeuille).\n"
            f"     Perte maximale possible ≈ {int(plafond * STOP_LOSS):,.0f} F,\n"
            f"     mais à ce montant le pari est perdant en moyenne.\n"
            f"   → Pour un pari gagnant en moyenne : ≥ {win_min:,.0f} F\n"
            f"     (~20 % de ton portefeuille — plus risqué).\n\n"
            f"📋 SI TU DÉCIDES DE JOUER :\n"
            f"   • Ordre d'achat : {qty} action(s) {c['code']}, prix max {limit:,.0f} F\n"
            f"   • Si ça monte de 20 % ({t1:,.0f} F) → vends 1 action sur 3\n"
            f"   • Si ça monte de 35 % ({t2:,.0f} F) → vends encore 1 sur 3\n"
            f"   • Si ça monte de 50 % ({t3:,.0f} F) → vends le reste\n"
            f"   • Si ça baisse de 15 % ({stop:,.0f} F) → vends TOUT, sans discuter\n"
            f"   • Passe l'ordre DEMAIN matin avant {ORDER_CUTOFF_BSTRADE:%Hh%M}.\n"
            f"   • L'occasion ne dure qu'une journée : si demain le prix n'est\n"
            f"     plus au rendez-vous, on laisse tomber.\n\n"
            f"🚫 Règle d'or : un pari perdant ne devient JAMAIS un investissement."
        )
        print(msg)
        if notifier.enabled:
            notifier.send(msg)


if __name__ == "__main__":
    main()
