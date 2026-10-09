"""Screen value+dividende complet des 47 actions BRVM + payout (18/08/2026)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.bsapi import BSApi
from src.portfolio import payout_ratio
from src.analyse.screener import scrape_all_fundamentals, screen_value_dividend

api = BSApi()
results = screen_value_dividend(api, force=False)

print(f"\n=== SCREEN VALUE+DIVIDENDE : {len(results)} titres (PER <= 14, rendement net >= 4 %) ===")
print(f"{'Code':7s} {'Nom':22s} {'Cours':>8s} {'PER':>6s} {'DPS':>7s} {'Net':>6s} {'Payout':>7s}")
print("-" * 70)
for r in results:
    payout = payout_ratio(r["dps"], r["last"], r["per"])
    p_str = f"{payout * 100:.0f}%" if payout is not None else "n/a"
    print(
        f"{r['code']:7s} {r['name'][:21]:22s} {r['last']:>8,.0f} "
        f"{r['per']:>6.2f} {r['dps']:>7,.0f} {r['net_yield']:>6.2f}% {p_str:>7s}"
    )

# Titres du noyau détenus + candidats initiaux (même hors critères)
print("\n=== NOYAU ACTUEL + CANDIDATS INITIAUX (même hors critères) ===")
funds = scrape_all_fundamentals(api)
snap = api.market_snapshot()
for code in ["SGBC", "SLBC", "SNTS", "BOAS", "SOGC", "PALC"]:
    f = funds.get(code, {})
    q = snap.by_code(code)
    if not q or q.last <= 0 or not f.get("per") or not f.get("dps"):
        print(f"{code:7s} — données fondamentales indisponibles")
        continue
    per, dps = f["per"], f["dps"]
    yld = dps / q.last * 100
    net = yld * 0.88 - 0.8
    payout = payout_ratio(dps, q.last, per)
    p_str = f"{payout * 100:.0f}%" if payout is not None else "n/a"
    detenu = " ✅ détenu" if code in ("SGBC", "SLBC", "SNTS") else ""
    print(
        f"{code:7s} {q.name[:21]:22s} {q.last:>8,.0f} {per:>6.2f} {dps:>7,.0f} "
        f"{net:>6.2f}% {p_str:>7s}{detenu}"
    )
