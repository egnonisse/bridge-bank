"""Check de clôture (16h) : candidats spéculation validés à la clôture du jour.

Complète le check de 09h (qui voit la clôture de la veille, parfois veille-1 si
l'API est en retard). À 16h, la clôture du jour est disponible : les candidats
détectés ici sont alertés « à jouer DEMAIN à l'ouverture » — fenêtre réelle
d'action, au lieu de courir après un signal déjà éventé.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    import logging

    from src.bsapi import BSApi
    from src.live import ORDER_CUTOFF_BSTRADE
    from src.main import get_notifier, load_config, load_dotenv
    from src.speculation import (
        MIN_SIGNALS,
        STOP_LOSS,
        TAKE_1,
        TAKE_2,
        TAKE_3,
        detect_new_candidates,
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()

    api = BSApi()
    new = detect_new_candidates(api, min_signals=MIN_SIGNALS)
    if not new:
        print("Aucun nouveau candidat spéculatif à la clôture.")
        return

    notifier = get_notifier(load_config())
    for c in new:
        last = c["last"]
        qty = max(1, int(70000 // last)) if last > 0 else 1
        limit = round(last * 1.03)
        stop = round(last * (1 - STOP_LOSS))
        t1 = round(last * (1 + TAKE_1))
        t2 = round(last * (1 + TAKE_2))
        t3 = round(last * (1 + TAKE_3))
        msg = (
            f"🌅 SPÉCULATION — CANDIDAT DE CLÔTURE (à jouer DEMAIN à l'ouverture)\n\n"
            f"🟢 ACHÈTE {c['name']} ({c['code']})\n"
            f"   Signaux ({c['count']}) : {', '.join(c['signals'])}\n"
            f"   Cours de clôture : {last:,.0f} F\n\n"
            f"   📋 Ordre : ACHAT {qty} act. {c['code']} à ≤ {limit:,.0f} F (limite +3 %)\n"
            f"      → investi ≈ {qty * last:,.0f} F (poche spéculation ~70 000 F)\n\n"
            f"   🛑 Stop −15 % : {stop:,.0f} F → vends tout\n"
            f"   🎯 Paliers : +20 % ({t1:,.0f}) vends ⅓ → stop remonte à {last:,.0f}\n"
            f"               +35 % ({t2:,.0f}) vends ⅓ → stop suiveur\n"
            f"               +50 % ({t3:,.0f}) clôture\n\n"
            f"   ⏰ Passe l'ordre DEMAIN matin avant {ORDER_CUTOFF_BSTRADE:%Hh%M}.\n"
            f"   ⚠️ Le setup vit 24h : vérifie le cours d'ouverture (brvm.org) avant\n"
            f"      d'envoyer l'ordre — si le volume du jour meurt, renonce."
        )
        print(msg)
        if notifier.enabled:
            notifier.send(msg)


if __name__ == "__main__":
    main()
