"""Test : extraction du corps d'article madisinvest.com (payloads RSC complets)."""
import requests, re, json
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
u = "https://madisinvest.com/actualites/boursiere/brvm-27-actions-terminent-dans-le-rouge-dans-un-marche-en-consolidation-zF3QOJjYpRday5dB6y8M"
r = requests.get(u, headers=HEADERS, timeout=60, verify=False)
t = r.text

def dec(s):
    try:
        return s.encode("utf-8").decode("unicode_escape", errors="ignore")
    except Exception:
        return s

# découper sur la vraie structure : self.__next_f.push([1,"..."])\n
parts = re.split(r"self\.__next_f\.push\(\[1,\"", t)
print("payloads RSC :", len(parts))
full_texts = []
for p in parts[1:]:
    end = p.find('"])')
    if end == -1:
        continue
    frag = dec(p[:end])
    # garder les payloads contenant du contenu éditorial
    if any(k in frag for k in ("séance", "Séance", "actions", "BRVM", "marché", "indice", "Unilever", "consolidation", "rouge")):
        txt = re.sub(r"<[^>]+>", " ", frag)
        txt = re.sub(r"\s+", " ", txt)
        full_texts.append(txt)

print("payloads éditoriaux :", len(full_texts))
for ft in full_texts[:3]:
    print("---", ft[:700])
