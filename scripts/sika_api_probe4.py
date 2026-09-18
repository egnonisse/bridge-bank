"""Sonde n°4 : sikafinance.com — le portail des cotations BRVM."""
import requests, re
import urllib3
urllib3.disable_warnings()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.sikafinance.com"

# 1. page de cotation d'un titre BRVM
for page in ["/marches/cotation_PALMCI", "/marches/cotation_PALC", "/marches/cotation_SNTS",
             "/marches/cotation_SGBC", "/marches/cotation"]:
    try:
        r = requests.get(BASE + page, headers=HEADERS, timeout=30, verify=False)
        scripts = re.findall(r"src=[\"']([^\"']+\.js[^\"']*)[\"']", r.text)
        ajax = re.findall(r"(?:url|action)[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", r.text, re.I)
        fetches = re.findall(r"fetch\([\"']([^\"']+)[\"']", r.text)
        xhr = re.findall(r"\.(?:get|post)\([\"']([^\"']+)[\"']", r.text)
        print(f"{page:<32} {r.status_code} JS:{len(scripts)} ajax:{ajax[:3]} fetch:{fetches[:3]} get:{xhr[:3]}")
    except Exception as e:
        print(f"{page:<32} ERR {type(e).__name__}")
