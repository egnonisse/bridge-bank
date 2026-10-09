"""Fondamentaux HISTORIQUES — reconstitution point-in-time.

PROBLEME RESOLU
---------------
Le challenge utilisait `per`, `net_yield` et `payout` avec les valeurs
d'AUJOURD'HUI appliquees a tout l'historique. Une regle « acheter les PER < 15 »
selectionnait donc en realite les titres dont le PER est bon EN 2026 —
information indisponible au moment de la decision. C'est une fuite du futur,
et elle rendait ces regles intestables.

Ce module reconstitue, pour chaque titre :
  - les DIVIDENDES avec leur date de detachement (quand l'info devient publique)
  - le BPA (benefice par action) par exercice

et fournit `fondamentaux_a_la_date()` qui ne retourne QUE ce qui etait
reellement connu a une date donnee.

SOURCE
------
stockanalysis.com — pages publiques `dividend/` et `financials/`.
L'historique des dividendes est dans un JSON embarque
(`history:[{dt, amt, record, pay}]`), donc l'extraction est fiable : pas de
lecture approximative de HTML.

REGLES DE TIMING (le point crucial)
-----------------------------------
  - un dividende est connu a sa DATE DE DETACHEMENT (`dt`) ;
  - un BPA d'exercice N est considere connu a partir de l'annee N+1
    (publication des etats financiers, ~avril).
Sans ces regles, on remplace un look-ahead par un autre.

COUVERTURE MESUREE
------------------
38/48 titres avec >= 3 dividendes dates, 35/48 avec >= 3 exercices de BPA.
La source ne remonte pas avant 2021 : la periode exploitable est 2022-2026.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
import urllib3
from .infrastructure.paths import RACINE  # chemins centralisés (lot 0 du plan docs/architecture.md)

urllib3.disable_warnings()

CACHE = RACINE / "data" / "fondamentaux_historiques.json"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://stockanalysis.com/quote/brvm/{}/{}"

# Un BPA d'exercice N est publie vers avril N+1. On applique ce decalage.
DECALAGE_PUBLICATION_BPA = 1


@dataclass
class TitreFondamentaux:
    """Historique fondamental d'un titre."""

    code: str
    dividendes: list[dict] = field(default_factory=list)   # {ex_date, montant, ...}
    bpa: dict[str, float] = field(default_factory=dict)    # {"2025": 2786.0, ...}
    source_ok: bool = False
    notes: list[str] = field(default_factory=list)
    # Fiabilite du BPA, etablie par CONTROLE CROISE (voir valider_bpa)
    bpa_fiable: bool = False
    ecart_per_pct: float | None = None


# Tolerance du controle croise : au-dela, le BPA est declare inexploitable.
TOLERANCE_PER_PCT = 40.0


def valider_bpa(t: TitreFondamentaux, cours_actuel: float | None,
                per_reference: float | None) -> TitreFondamentaux:
    """Verifie le BPA en confrontant le PER recalcule au PER de reference.

    POURQUOI CE CONTROLE
    --------------------
    Le parseur lit la ligne « Earnings Per Share » d'un tableau financier. Sur
    la plupart des titres il tombe juste (SGBC ecart 0 %, PALC -1 %, CFAC 0 %),
    mais deux cas mesures montrent qu'il peut se tromper du tout au tout :
      - NTLC : BPA extrait 20,7 fois trop grand — exactement le ratio de sa
        division de nominal de 2017. La source publie le BPA sur l'ancien
        nombre d'actions.
      - BICC : BPA 2,3 fois trop petit.
    Un BPA faux produit des PER absurdes (NTLC a donne 0,90), donc des regles
    fondamentales qui n'ont aucun sens.

    Le PER de reference (source officielle) sert de juge : si le PER recalcule
    s'en ecarte de plus de TOLERANCE_PER_PCT, le BPA du titre est declare
    inexploitable et ses regles fondamentales sont desactivees. On verifie sur
    l'exercice le plus recent, le seul ou la reference existe ; si l'alignement
    des colonnes est juste pour celui-la, il l'est pour les precedents.
    """
    if not t.bpa or not cours_actuel or not per_reference:
        t.bpa_fiable = False
        t.notes.append("BPA non verifiable (donnee de reference absente)")
        return t

    annee_max = max(t.bpa, key=lambda a: int(a) if a.isdigit() else 0)
    bpa = t.bpa[annee_max]
    if not bpa or bpa <= 0:
        t.bpa_fiable = False
        t.notes.append(f"BPA {annee_max} nul ou negatif")
        return t

    per_calc = cours_actuel / bpa
    ecart = (per_calc / per_reference - 1) * 100
    t.ecart_per_pct = round(ecart, 1)

    if abs(ecart) <= TOLERANCE_PER_PCT:
        t.bpa_fiable = True
        t.notes.append(f"BPA verifie (PER recalcul {per_calc:.2f} vs "
                       f"reference {per_reference:.2f}, ecart {ecart:+.1f} %)")
    else:
        t.bpa_fiable = False
        t.notes.append(
            f"BPA ECARTE : PER recalcul {per_calc:.2f} vs reference "
            f"{per_reference:.2f} ({ecart:+.1f} %) — le BPA publie ne correspond "
            f"pas au nombre d'actions actuel")
    return t


# ---------------------------------------------------------------------------
#  EXTRACTION
# ---------------------------------------------------------------------------

def extraire_dividendes(html: str) -> list[dict]:
    """Extrait l'historique des dividendes du JSON embarque.

    Structure visee :
      history:[{dt:"2026-08-21",amt:"2,606.000 XOF",record:"...",pay:"..."},...]
    `dt` = date de detachement : c'est la date a laquelle l'information est
    publique et le cours decale. C'est donc LA date a utiliser.
    """
    if not html:
        return []
    i = html.find("history:[{")
    if i < 0:
        return []
    bloc = html[i:i + 12000]
    out = []
    motif = (r'\{dt:"(\d{4}-\d{2}-\d{2})",\s*amt:"([0-9.,]+)\s*([A-Z]{3})"'
             r'(?:,\s*dec:"[^"]*")?(?:,\s*record:"([^"]*)")?(?:,\s*pay:"([^"]*)")?\}')
    for m in re.finditer(motif, bloc):
        try:
            val = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if val <= 0:
            continue
        out.append({
            "ex_date": m.group(1),
            "montant": val,
            "devise": m.group(3),
            "record": m.group(4) or None,
            "paiement": m.group(5) or None,
        })
    out.sort(key=lambda x: x["ex_date"])
    return out


def extraire_bpa(html: str) -> dict[str, float]:
    """Extrait le BPA (EPS) par exercice depuis le tableau financier.

    Le tableau porte des colonnes « FY 2025 ... FY 2021 ». On lit d'abord ces
    en-tetes (source de verite de l'ordre des colonnes), puis on cherche la
    ligne « Earnings Per Share » et on associe les valeurs dans CET ordre :
    se fier a l'ordre des nombres sans lire les en-tetes est la cause classique
    d'un decalage d'une annee.
    """
    if not html:
        return {}

    # 1. Les en-tetes d'exercice, dans l'ordre du document
    annees = re.findall(r"FY\s*(20\d{2})", html)
    if not annees:
        return {}
    # Dedupliquer en conservant l'ordre (le libelle apparait souvent 2 fois)
    vues, ordre = set(), []
    for a in annees:
        if a not in vues:
            vues.add(a)
            ordre.append(a)
    if not ordre:
        return {}

    # 2. La ligne EPS : on cherche la cellule de titre puis les valeurs voisines
    m = re.search(r"Earnings Per Share", html, re.I)
    if not m:
        return {}
    fenetre = html[m.start(): m.start() + 4000]

    valeurs = []
    for cellule in re.findall(r"<td[^>]*>(.*?)</td>", fenetre, re.S | re.I):
        txt = re.sub(r"<[^>]+>", "", cellule).strip()
        txt = txt.replace(",", "").replace("\u00a0", "")
        if not txt:
            continue
        mm = re.match(r"^(-?[0-9]+(?:\.[0-9]+)?)$", txt)
        if mm:
            try:
                valeurs.append(float(mm.group(1)))
            except ValueError:
                continue
        if len(valeurs) >= len(ordre):
            break

    if not valeurs:
        return {}

    # Le premier nombre de la ligne EPS est le TTM : on l'ecarte si on a
    # exactement une valeur de plus que d'annees.
    if len(valeurs) == len(ordre) + 1:
        valeurs = valeurs[1:]

    out = {}
    for annee, val in zip(ordre, valeurs):
        out[annee] = val
    return out


# ---------------------------------------------------------------------------
#  COLLECTE ET CACHE
# ---------------------------------------------------------------------------

def _get(url: str, essais: int = 2) -> str | None:
    for i in range(essais):
        try:
            r = requests.get(url, headers=H, timeout=40, verify=False)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        if i < essais - 1:
            time.sleep(1.5)
    return None


def collecter_titre(code: str, cours_actuel: float | None = None,
                    per_reference: float | None = None) -> TitreFondamentaux:
    """Recupere dividendes et BPA pour un titre, puis verifie le BPA.

    `cours_actuel` et `per_reference` servent au controle croise : sans eux, le
    BPA est recupere mais declare NON fiable (on ne peut pas le verifier).
    """
    t = TitreFondamentaux(code=code)
    html_div = _get(BASE.format(code, "dividend/"))
    if html_div:
        t.dividendes = extraire_dividendes(html_div)
    time.sleep(0.4)
    html_fin = _get(BASE.format(code, "financials/"))
    if html_fin:
        t.bpa = extraire_bpa(html_fin)
    t.source_ok = bool(t.dividendes) or bool(t.bpa)
    if not t.dividendes:
        t.notes.append("aucun dividende daté")
    if not t.bpa:
        t.notes.append("aucun BPA extrait")
    valider_bpa(t, cours_actuel, per_reference)
    return t


def charger_cache(chemin: Path | None = None) -> dict[str, TitreFondamentaux]:
    """Charge le cache disque."""
    chemin = Path(chemin) if chemin else CACHE
    if not chemin.exists():
        return {}
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    out = {}
    for code, d in brut.items():
        out[code] = TitreFondamentaux(
            code=code,
            dividendes=d.get("dividendes", []),
            bpa={k: float(v) for k, v in (d.get("bpa") or {}).items()},
            source_ok=d.get("source_ok", False),
            notes=d.get("notes", []),
            bpa_fiable=d.get("bpa_fiable", False),
            ecart_per_pct=d.get("ecart_per_pct"),
        )
    return out


def sauver_cache(titres: dict[str, TitreFondamentaux], chemin: Path | None = None):
    chemin = Path(chemin) if chemin else CACHE
    chemin.parent.mkdir(parents=True, exist_ok=True)
    data = {
        code: {
            "dividendes": t.dividendes,
            "bpa": t.bpa,
            "source_ok": t.source_ok,
            "notes": t.notes,
            "bpa_fiable": t.bpa_fiable,
            "ecart_per_pct": t.ecart_per_pct,
        }
        for code, t in titres.items()
    }
    chemin.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
#  POINT-IN-TIME — le cœur du dispositif
# ---------------------------------------------------------------------------

def dernier_dividende_connu(t: TitreFondamentaux, date: str) -> dict | None:
    """Dernier dividende dont la date de detachement est <= `date`."""
    connu = [d for d in t.dividendes if d["ex_date"] <= date]
    return connu[-1] if connu else None


def bpa_connu(t: TitreFondamentaux, date: str) -> tuple[str, float] | None:
    """Dernier BPA PUBLIE a la date donnee.

    Un BPA d'exercice N n'est connu qu'apres la publication des comptes, soit
    l'annee N+DECALAGE. Sans ce decalage, on utiliserait un resultat avant sa
    publication — fuite du futur.
    """
    annee = int(date[:4])
    candidats = []
    for a_str, val in t.bpa.items():
        try:
            a = int(a_str)
        except ValueError:
            continue
        if a + DECALAGE_PUBLICATION_BPA <= annee:
            candidats.append((a, val))
    if not candidats:
        return None
    a, val = max(candidats, key=lambda x: x[0])
    return str(a), val


def fondamentaux_a_la_date(t: TitreFondamentaux, date: str,
                           cours: float | None = None) -> dict:
    """Valeurs fondamentales REELLEMENT connues a cette date.

    Retourne {"per", "net_yield", "payout", "dps", "bpa", "annee_bpa",
             "ex_date_dividende"} — les cles absentes signifient « inconnu a
    cette date » (et non « zero »), ce qui permet au juge de refuser de
    trancher plutot que de trancher faux.

    `net_yield` est NET d'IRVM (12 %) et de frais de conservation (0,8 pt),
    conformement au modele du projet.
    """
    out: dict = {}

    d = dernier_dividende_connu(t, date)
    if d:
        out["dps"] = d["montant"]
        out["ex_date_dividende"] = d["ex_date"]
        if cours:
            brut = d["montant"] / cours
            out["net_yield"] = round(brut * 0.88 - 0.008, 6)

    # Le BPA n'est utilise QUE s'il a passe le controle croise : un BPA faux
    # produit un PER absurde et une regle qui n'a aucun sens.
    if t.bpa_fiable:
        b = bpa_connu(t, date)
        if b:
            annee_bpa, val = b
            out["bpa"] = val
            out["annee_bpa"] = annee_bpa
            if cours and val > 0:
                out["per"] = round(cours / val, 4)
            if val > 0 and out.get("dps") is not None:
                out["payout"] = round(out["dps"] / val, 6)

    return out
