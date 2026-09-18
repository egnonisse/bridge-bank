"""Sonde n°2 : domaines backend + fetch/axios dans tous les chunks trouvables."""
import requests, re, os
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.sika.finance"
OUT = os.path.join(os.path.dirname(__file__), "sika_js")
os.makedirs(OUT, exist_ok=True)

# 1. lister les chunks référencés sur la page dashboard / explorer les routes
r = requests.get(BASE, headers=HEADERS, timeout=60, verify=False)
scripts = re.findall(r"src=\"([^\"]+\.js[^\"]*)\"", r.text)
print(f"{len(scripts)} chunks sur la home")

# 2. chercher des domaines/URLs backend dans tous les chunks déjà téléchargés
url_pat = re.compile(r"https?://[a-zA-Z0-9.\-]+(?:\.[a-z]{2,}){1,2}[^\"' )]*")
api_like = set()
domains = {}
for fn in os.listdir(OUT):
    t = open(os.path.join(OUT, fn), encoding="utf-8", errors="ignore").read()
    for m in url_pat.finditer(t):
        u = m.group(0).rstrip(".,;)]")
        host = re.match(r"https?://([^/]+)", u).group(1)
        domains[host] = domains.get(host, 0) + 1
        if re.search(r"(api|graphql|/v[0-9]/|/api/)", u, re.I) and "sika" not in u.lower():
            api_like.add(u[:110])
print("Domaines référencés :", sorted(domains, key=lambda d: -domains[d])[:12])
print("URLs ressemblant à une API externe :")
for u in sorted(api_like)[:15]:
    print(" ", u)
