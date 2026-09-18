"""Extraction du contenu réel de madisinvest.com/informations/apropos (RSC Next.js)."""
import requests, re, json
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get("https://madisinvest.com/informations/apropos", headers=HEADERS, timeout=60, verify=False)
t = r.text

def decode(s):
    try:
        return s.encode("utf-8").decode("unicode_escape", errors="ignore")
    except Exception:
        return s

texts = []
for m in re.finditer(r"self\.__next_f\.push\(\[1,\"(.{0,20000}?)\"\]\)", t):
    frag = decode(m.group(1))
    if any(k in frag for k in ("mission", "Mission", "MADIS", "partenaire", "analyse")):
        txt = re.sub(r"<[^>]+>", " ", frag)
        txt = re.sub(r"\s+", " ", txt)
        texts.append(txt)

full = " ".join(texts)
print("Caractères de texte extrait :", len(full))
print(full[:3500])
