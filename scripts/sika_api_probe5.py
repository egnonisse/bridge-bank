"""Sonde n°5 : page de cotation sikafinance.com — endpoints AJAX / source des cours."""
import requests, re
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.sikafinance.com"

r = requests.get(BASE + "/marches/cotation_BRVMFI", headers=HEADERS, timeout=30, verify=False)
t = r.text
print("URL finale :", r.url)

# URLs AJAX / iframes / websocket
urls = set(re.findall(r"[\"'](https?://[^\"']+|/[A-Za-z0-9_./?=&-]+)[\"']", t))
cands = [u for u in urls if re.search(r"(ajax|api|json|xml|cours|cotation|data|ws|iframe|feed)", u, re.I)]
print("\nCandidats AJAX/API/iframe :")
for u in sorted(cands)[:25]:
    print(" ", u[:110])

# iframes spécifiquement
frames = re.findall(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", t)
print("\nIframes :", frames[:6])
