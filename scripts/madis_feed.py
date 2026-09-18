"""Feed d'actualités Madis Invest — branchement sans API ni clé.

Le site expose des sitemaps XML publics mis à jour quotidiennement :
  - sitemap-news.xml     : actualités boursières/économiques
  - sitemap-conseil.xml  : conseils
Le titre de chaque news est lisible dans l'URL (slug en clair).

Usage : python scripts/madis_feed.py [--limit N] [--check]
  --check  : ne garde que les URLs jamais vues (état dans data/madis_seen_state.json)
Sans --check : liste les news récentes (filtrées sur les mots-clés d'intérêt).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://madisinvest.com"
SITEMAPS = ["sitemap-news.xml", "sitemap-conseil.xml"]

# Mots-clés d'intérêt pour le portefeuille BRVM de LEO
KEYWORDS = [
    "brvm", "bourse", "dividende", "suspension", "opcvm",
    "solibra", "sonatel", "palm", "sgbci", "sgb", "ecobank",
    "cote d'ivoire", "côte d'ivoire", "ivoire", "uemoa", "bceao",
]

DATA = Path(__file__).resolve().parents[1] / "data"
STATE = DATA / "madis_seen_state.json"


def slug_title(url: str) -> str:
    """Titre lisible reconstruit depuis le slug de l'URL."""
    m = re.search(r"/actualites/[^/]+/([^/]+)-[A-Za-z0-9]{20}$", url)
    if not m:
        return url
    slug = m.group(1).replace("-", " ")
    return slug


def fetch_items() -> list[tuple[str, str]]:
    """Retourne [(url, titre)] depuis les sitemaps, news d'abord."""
    items = []
    for sm in SITEMAPS:
        try:
            r = requests.get(f"{BASE}/{sm}", headers=HEADERS, timeout=30, verify=False)
            urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
            for u in urls:
                items.append((u, slug_title(u)))
        except Exception as e:
            print(f"[madis_feed] {sm} : {e}", file=sys.stderr)
    return items


def load_seen() -> set:
    if STATE.exists():
        try:
            return set(json.loads(STATE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: set) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


def relevant(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--check", action="store_true",
                    help="mode veille : n'affiche que les URL jamais vues (et les mémorise)")
    ap.add_argument("--all", action="store_true", help="affiche aussi les news hors mots-clés")
    args = ap.parse_args()

    items = fetch_items()
    if not items:
        print("Aucune URL récupérée — sitemap injoignable.")
        sys.exit(1)

    if args.check:
        seen = load_seen()
        new = [(u, t) for u, t in items if u not in seen]
        save_seen(seen | {u for u, _ in items})
        if not new:
            print("Aucune nouvelle news Madis.")
            return
        print(f"🆕 {len(new)} nouvelle(s) news Madis :")
        for u, t in new[: args.limit]:
            print(f"  • {t}")
            print(f"    {u}")
        return

    shown = 0
    for u, t in items:
        if not args.all and not relevant(t):
            continue
        print(f"• {t}")
        print(f"  {u}")
        shown += 1
        if shown >= args.limit:
            break
    print(f"\n({shown} affichées sur {len(items)} URLs dans les sitemaps)")


if __name__ == "__main__":
    main()
