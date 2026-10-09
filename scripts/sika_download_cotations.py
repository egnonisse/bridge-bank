"""Telecharge l'historique des cotations BRVM depuis Sika Finance.

Le formulaire de Sika exige :
  - dtFrom / dtTo (dates)
  - un jeton __RequestVerificationToken (anti-CSRF)

On fait donc un GET pour recuperer le jeton, puis un POST authentique.
Verification importante : les cours renvoyes sont-ils AJUSTES des divisions
de nominal ? On compare avec les valeurs connues (SGBC 117 600 -> 12 000).
"""
import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # racine du projet

from src.infrastructure.paths import DATA_DIR   # noqa: E402  (import après le bootstrap sys.path)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.sikafinance.com"
PAGE = f"{BASE}/marches/download/BRVMFI"

SORTIE = DATA_DIR / "sika_cotations.csv"
SORTIE.parent.mkdir(parents=True, exist_ok=True)

# Session avec cookies (le jeton est lie au cookie de session)
cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "fr-FR,fr;q=0.9")]


def get(url):
    with opener.open(url, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


print("=" * 78)
print("  TELECHARGEMENT DES COTATIONS — SIKA FINANCE")
print("=" * 78)

# --- 1. Recuperer le formulaire et son jeton ---------------------------
print("\n  [1/3] recuperation du formulaire...")
html = get(PAGE)
print(f"        page : {len(html)} caracteres")

jetons = re.findall(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
if not jetons:
    print("        ECHEC : jeton anti-CSRF introuvable")
    sys.exit(1)
jeton = jetons[0]
print(f"        jeton : {len(jeton)} caracteres")

# --- 2. POST avec les dates ---------------------------------------------
print("\n  [2/3] envoi de la requete (2016-01-01 -> aujourd'hui)...")
donnees = {
    "dtFrom": "2016-01-01",
    "dtTo": "2026-09-30",
    "__RequestVerificationToken": jeton,
}
corps = urllib.parse.urlencode(donnees).encode("utf-8")

req = urllib.request.Request(PAGE, data=corps, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
req.add_header("Referer", PAGE)
req.add_header("Origin", BASE)

try:
    with opener.open(req, timeout=120) as r:
        contenu = r.read()
        ctype = r.headers.get("Content-Type", "")
        cdisp = r.headers.get("Content-Disposition", "")
except Exception as e:
    print(f"        ERREUR : {str(e)[:120]}")
    sys.exit(1)

print(f"        recu : {len(contenu)} octets")
print(f"        type : {ctype}")
if cdisp:
    print(f"        disposition : {cdisp[:80]}")

# --- 3. Analyse ----------------------------------------------------------
print("\n  [3/3] analyse du contenu...")
texte = contenu.decode("utf-8", errors="replace")

if "<html" in texte[:500].lower():
    print("        -> HTML (pas de fichier) — le POST n'a pas abouti")
    # Chercher un message d'erreur
    corps_texte = re.sub(r"<script.*?</script>|<style.*?</style>", " ", texte,
                         flags=re.S | re.I)
    corps_texte = re.sub(r"<[^>]+>", " ", corps_texte)
    corps_texte = re.sub(r"\s+", " ", corps_texte).strip()
    print(f"        extrait : {corps_texte[:300]}")
    sys.exit(1)

# Fichier CSV recu
SORTIE.write_bytes(contenu)
lignes = texte.splitlines()
print(f"        fichier ecrit : {SORTIE.name}")
print(f"        lignes : {len(lignes)}")
print("\n        --- 4 premieres lignes ---")
for l in lignes[:4]:
    print(f"          {l[:120]}")

# --- 4. Verifier si les cours sont AJUSTES ------------------------------
print("\n" + "=" * 78)
print("  VERIFICATION : LES COURS SONT-ILS AJUSTES DES DIVISIONS ?")
print("=" * 78)

# Repere connus : SGBC passait de 117 600 F (aout 2017) a 12 000 F (division 1:10)
# Si le fichier est ajuste, on ne doit PAS voir 117 600 F.
for code_test in ("SGBC", "BOAC", "STAC", "SIVC"):
    val = [l for l in lignes if l.upper().startswith(code_test + ";")
           or f";{code_test};" in l.upper()]
    if not val:
        print(f"\n  {code_test} : absent du fichier")
        continue
    # Extraire les cours (dernier champ numerique de chaque ligne)
    cours = []
    for l in val:
        champs = re.split(r"[;,]", l)
        for c in reversed(champs):
            c = c.strip().replace('"', "")
            try:
                v = float(c)
                if v > 0:
                    cours.append(v)
                    break
            except ValueError:
                continue
    if cours:
        print(f"\n  {code_test} : {len(val)} lignes")
        print(f"    premier cours : {cours[0]:>12,.0f} F")
        print(f"    dernier cours : {cours[-1]:>12,.0f} F")
        print(f"    max           : {max(cours):>12,.0f} F")
        ajuste = "PROBABLEMENT AJUSTE" if max(cours) < 50000 else "NON AJUSTE (ou a verifier)"
        print(f"    -> {ajuste}")

print("\n" + "=" * 78)
