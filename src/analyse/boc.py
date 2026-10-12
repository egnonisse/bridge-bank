"""Veille des annonces de dividendes BRVM — 3 sources croisées.

Sources (dans l'ordre de préférence) :
  1. brvm.org (OFFICIEL)  : boc_YYYYMMDD_2.pdf
  2. nsiacapital.com (SGI) : BOC-DU-JJ-MOIS.pdf  (relais secondaire)
  3. sikafinance.com (média indépendant) : page /marches/dividendes

Le BOC contient les paiements de dividendes à venir (émetteur, montant, date) —
y compris les RECTIFICATIFS que les pages ESV brvm.org ne listent pas.
sikafinance sert de source de croisement : si son montant diffère du BOC, la
divergence est signalée dans l'événement (champ `cross_sika`).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pymupdf
import requests
from urllib3.exceptions import InsecureRequestWarning
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

BRVM_BOC_URL = "https://www.brvm.org/sites/default/files/boc_{yyyymmdd}_2.pdf"
NSIA_BOC_URL = ("https://nsiacapital.com/wp-content/uploads/{yyyy}/{mm}/"
                "BOC-DU-{dd}-{MOIS}.pdf")
SIKA_DIV_URL = "https://www.sikafinance.com/marches/dividendes"

MOIS_FR = {
    1: "JANVIER", 2: "FEVRIER", 3: "MARS", 4: "AVRIL", 5: "MAI", 6: "JUIN",
    7: "JUILLET", 8: "AOUT", 9: "SEPTEMBRE", 10: "OCTOBRE", 11: "NOVEMBRE", 12: "DECEMBRE",
}

STATE_FILE = DATA_DIR / "boc_state.json"

# Mapping nom d'émetteur -> code BRVM, pour le noyau.
COMPANY_HINTS = {
    "sgb": "SGBC", "sgci": "SGBC", "societe generale": "SGBC",
    "sonatel": "SNTS",
    "solibra": "SLBC",
    "palm": "PALC", "palmci": "PALC",
    "sogb": "SOGC",
    "boa senegal": "BOAS", "bank of africa senegal": "BOAS",
}


def match_code(name: str) -> str | None:
    n = name.lower().strip()
    for key in sorted(COMPANY_HINTS, key=len, reverse=True):
        if key in n:
            return COMPANY_HINTS[key]
    return None


# ---------------------------------------------------------------- téléchargement
def _boc_urls(date: datetime) -> list[tuple[str, str]]:
    """Les URLs BOC du jour, dans l'ordre de préférence (brvm.org puis nsiacapital)."""
    return [
        ("brvm", BRVM_BOC_URL.format(yyyymmdd=date.strftime("%Y%m%d"))),
        ("nsiacapital", NSIA_BOC_URL.format(
            yyyy=date.year, mm=f"{date.month:02d}", dd=f"{date.day:02d}",
            MOIS=MOIS_FR[date.month],
        )),
    ]


def fetch_boc_text(date: datetime) -> tuple[str, str] | None:
    """Télécharge le BOC d'une date, essaie les sources dans l'ordre.

    Retourne (texte, source) ou None si aucune source ne répond.
    """
    for source, url in _boc_urls(date):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and r.content.startswith(b"%PDF"):
                doc = pymupdf.open(stream=r.content, filetype="pdf")
                return "\n".join(page.get_text() for page in doc), source
        except Exception:
            continue
    return None


def fetch_latest_boc(max_back: int = 4) -> tuple[str, datetime, str] | None:
    """BOC le plus récent disponible (essaie aujourd'hui puis les jours précédents)."""
    for i in range(max_back):
        d = datetime.now() - timedelta(days=i)
        result = fetch_boc_text(d)
        if result:
            text, source = result
            return text, d, source
    return None


# -------------------------------------------------------------------- parsing
def parse_operations(text: str) -> list[dict]:
    """Extrait les paiements de dividendes à venir (émetteur, montant, date, code)."""
    m = re.search(r"OPERATIONS EN COURS(.*?)(?:AVIS|COMMUNIQUES)", text, re.DOTALL)
    if not m:
        return []
    section = re.sub(r"\s+", " ", m.group(1))
    ops: list[dict] = []
    for em, montant, date in re.findall(
        r"([A-Z][A-ZÀ-ÿ .&'-]+?)\s+Paiement de dividendes de\s+([\d., ]+?)\s+F CFA"
        r".*?le\s+(\d{2}/\d{2}/\d{4})",
        section,
    ):
        em = em.strip()
        if not em or em.lower() in ("emetteur", "operation"):
            continue
        try:
            amount = float(montant.replace(" ", "").replace(",", "."))
        except ValueError:
            continue
        ops.append({
            "emetteur": em,
            "montant": amount,
            "date_paiement": date,
            "code": match_code(em),
        })
    return ops


# ------------------------------------------------------ croisement sikafinance
def fetch_sikafinance_dividendes() -> dict[str, float]:
    """Dividendes sikafinance (source indépendante) → {code: montant}."""
    try:
        r = requests.get(SIKA_DIV_URL, headers=HEADERS, timeout=30)
        clean = re.sub(r"<[^>]+>", " ", r.text)
        clean = re.sub(r"\s+", " ", clean)
    except requests.RequestException:
        return {}
    out: dict[str, float] = {}
    for nom, montant in re.findall(
        r"([A-ZÀ-ÿ][A-ZÀ-ÿ .&'-]+?)\s+(\d[\d.,]*)\s+\d+,\d+\s*%",
        clean,
    ):
        code = match_code(nom)
        if code is None:
            continue
        try:
            out[code] = float(montant.replace(" ", "").replace(",", "."))
        except ValueError:
            continue
    return out


# --------------------------------------------------------- état / nouveautés
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"operations": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"operations": {}}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def detect_events(text: str, date: datetime, codes: list[str]) -> list[dict]:
    """Événements dividendes du noyau : annonce/rectification + croisement sikafinance."""
    ops = parse_operations(text)
    sika = fetch_sikafinance_dividendes()
    state = load_state()
    ops_seen = state.get("operations", {})
    events: list[dict] = []
    for op in ops:
        code = op["code"]
        if code not in codes:
            continue
        prev = ops_seen.get(code)
        ev: dict | None = None
        if prev is None:
            ev = {"type": "dividende", "code": code, "action": "ANNONCÉ",
                  "montant": op["montant"], "date": op["date_paiement"], "emetteur": op["emetteur"]}
        elif prev != op["montant"]:
            ev = {"type": "dividende", "code": code, "action": "RECTIFIÉ",
                  "montant": op["montant"], "date": op["date_paiement"],
                  "ancien": prev, "emetteur": op["emetteur"]}
        ops_seen[code] = op["montant"]
        if ev is None:
            continue
        sika_montant = sika.get(code)
        if sika_montant is not None and abs(sika_montant - op["montant"]) > 1:
            ev["cross_sika"] = sika_montant  # divergence entre les sources
        events.append(ev)

    state["operations"] = ops_seen
    save_state(state)
    return events
