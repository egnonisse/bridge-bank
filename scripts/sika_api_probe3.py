"""Sonde n°3 : routes du site + endpoints /api/ probables."""
import requests, re, os
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.sika.finance"

# 1. routes probables d'un site de données boursières
routes = ["/actions", "/cours", "/cours-actions", "/market", "/marche", "/societes",
          "/companies", "/indices", "/dashboard", "/explore", "/stocks", "/watchlist"]
api_hits = []
for rt in routes:
    try:
        r = requests.get(BASE + rt, headers=HEADERS, timeout=30, verify=False, allow_redirects=True)
        scripts = re.findall(r"src=\"([^\"]+\.js[^\"]*)\"", r.text)
        print(f"{rt:<15} {r.status_code} {len(scripts)} chunks {r.url.split('.finance')[0][-40:]}")
        if r.status_code == 200:
            api_hits += [(rt, s) for s in scripts]
    except Exception as e:
        print(f"{rt:<15} ERR {e}")

# 2. tester les endpoints Next.js /api/* courants
for ep in ["/api/stocks", "/api/quotes", "/api/market", "/api/actions", "/api/prices",
           "/api/indices", "/api/companies", "/api/health"]:
    try:
        r = requests.get(BASE + ep, headers=HEADERS, timeout=20, verify=False)
        ct = r.headers.get("Content-Type", "")
        body = r.text[:120].replace("\n", " ")
        print(f"API {ep:<16} {r.status_code} {ct[:30]:<30} {body}")
    except Exception as e:
        print(f"API {ep:<16} ERR {e}")
