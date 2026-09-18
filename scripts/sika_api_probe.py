"""Sonde des endpoints API exposés par sika.finance (Next.js SPA)."""
import requests, re, os
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.sika.finance"
OUT = os.path.join(os.path.dirname(__file__), "sika_js")
os.makedirs(OUT, exist_ok=True)

chunks = [
    "4bd1b696-c023c6e3521b1417.js", "255-21d6a692d2ce90c3.js",
    "main-app-f9b5d20365cb8be2.js", "619-ba102abea3e3d0e4.js",
    "503-4830708555afecb9.js", "733-94bbaba8ad4145f6.js",
    "543-ec1bec832000a1a1.js", "app/page-fd98f64fcf94ed2f.js",
]

api_pat = re.compile(r"[\"']((?:https?://)?[^\"' ]*(?:/api/|/v[0-9]/)[^\"' ]*)[\"']")
found = set()
for c in chunks:
    try:
        r = requests.get(f"{BASE}/_next/static/chunks/{c}", headers=HEADERS, timeout=60, verify=False)
        t = r.text
        with open(os.path.join(OUT, c.replace("/", "_")), "w", encoding="utf-8", errors="ignore") as f:
            f.write(t)
        for m in api_pat.finditer(t):
            found.add(m.group(1)[:120])
    except Exception as e:
        print("ERR", c, e)

print("Endpoints API trouvés dans le JS :")
for f in sorted(found):
    print(" ", f)
