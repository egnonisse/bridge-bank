"""Suivi des annonces officielles BRVM (communiqués, dividendes, AG…).

La BRVM publie chaque annonce émetteur sous forme de PDF au nom normalisé :
    <YYYYMMDD>_-_<type>_-_<societe>_<pays>.pdf
(ex. 20260806_-_avis_ndeg231_brvmdg_-_paiement_de_dividendes_exercice_2025_-_societe_generale_ci.pdf)

Ce module scrape les pages d'annonces, parse ces noms (date + société), mappe la
société vers son code BRVM, filtre sur le noyau dividende et détecte les nouveautés
via un état persisté. C'est la source des déclencheurs fondamentaux (dividende
annoncé/coupé, AG, changement de dirigeants, notation).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

STATE_FILE = DATA_DIR / "news_state.json"

# Pages d'annonces émetteurs à surveiller (clé = type d'événement).
BRVM_ANNOUNCE_PAGES = {
    "dividendes": "https://www.brvm.org/fr/esv/paiement-de-dividendes",
    "communiques": "https://www.brvm.org/fr/emetteurs/type-annonces/communiques",
    "ag": "https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales",
    "dirigeants": "https://www.brvm.org/fr/emetteurs/type-annonces/changements-de-dirigeants",
    "notations": "https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres",
}

# Mapping slug de société (dans le nom de PDF) -> code BRVM, pour le noyau.
# À compléter au fil des avis observés (nomenclature brvm.org).
COMPANY_HINTS = {
    "bank_of_africa_sn": "BOAS",
    "societe_generale": "SGBC",
    "boa_senegal": "BOAS",
    "sonatel": "SNTS",
    "solibra": "SLBC",
    "boa_sn": "BOAS",
    "palm": "PALC",
    "sgci": "SGBC",
    "sogb": "SOGC",
}


def parse_date(filename: str) -> str | None:
    """Extrait la date ISO (YYYY-MM-DD) d'un nom de PDF daté, sinon None."""
    m = re.match(r"^(\d{8})", filename)
    if not m:
        return None
    d = m.group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def parse_society(filename: str) -> str:
    """Extrait le slug de société d'un nom de PDF, en minuscules."""
    base = filename[:-4] if filename.lower().endswith(".pdf") else filename
    parts = base.split("_-_")
    slug = parts[-1] if len(parts) > 1 else base
    slug = re.sub(r"_\d+$", "", slug)  # compteur de duplicata (sonatel_sn_0)
    return slug.strip("_-").lower()


def match_code(slug: str) -> str | None:
    """Mappe un slug de société vers son code BRVM, sinon None."""
    for key in sorted(COMPANY_HINTS, key=len, reverse=True):
        if key in slug:
            return COMPANY_HINTS[key]
    return None


def fetch_announcements() -> list[dict]:
    """Scrape toutes les pages d'annonces et retourne la liste des avis datés."""
    out: list[dict] = []
    for ptype, url in BRVM_ANNOUNCE_PAGES.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=25, verify=False)
            r.raise_for_status()
        except requests.RequestException:
            continue  # source indisponible = couverture inconnue, pas une erreur fatale
        pdfs = list(dict.fromkeys(re.findall(r'href="([^"]+\.pdf)"', r.text, re.I)))
        for p in pdfs:
            filename = p.split("/")[-1]
            date = parse_date(filename)
            if not date:
                continue
            slug = parse_society(filename)
            out.append({
                "date": date,
                "type": ptype,
                "society": slug,
                "code": match_code(slug),
                "filename": filename,
                "url": p if p.startswith("http") else "https://www.brvm.org" + p,
            })
    out.sort(key=lambda a: a["date"], reverse=True)
    return out


def filter_codes(announcements: list[dict], codes: list[str]) -> list[dict]:
    """Filtre les annonces sur une liste de codes BRVM (noyau)."""
    wanted = {c.strip().upper() for c in codes}
    return [a for a in announcements if a.get("code") in wanted]


# -------------------------------------------------------------- état / nouveautés
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"seen_urls": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"seen_urls": []}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def detect_new(announcements: list[dict], codes: list[str]) -> list[dict]:
    """Retourne les annonces du noyau jamais vues, puis avance l'état.

    L'état stocke TOUTES les URLs vues (pas seulement le noyau) pour que la
    détection soit stable même si la liste des titres change.
    """
    state = load_state()
    seen = set(state.get("seen_urls", []))
    wanted = {c.strip().upper() for c in codes}
    new = [a for a in announcements if a.get("code") in wanted and a["url"] not in seen]
    state["seen_urls"] = [a["url"] for a in announcements]
    save_state(state)
    return new
