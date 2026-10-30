"""Divisions de nominal BRVM — source OFFICIELLE et retro-ajustement.

PROBLEME RESOLU
---------------
L'historique brut melange cours pre et post-division. Une division de nominal
N pour 1 divise le cours par N : la « chute » est artificielle et fausse
toute mesure de performance ou de drawdown (constat : -96 % de drawdown median
sur 47 titres, impossible sur un marche obligataire-action peu volatil).

POURQUOI PAS UNE DETECTION AUTOMATIQUE
--------------------------------------
Une detection par les cours echoue sur :
  - les petites parites (1:2) : indistinguables d'une vraie chute de -50 %
  - les ratios hors liste courante (1:25, 1:40, 1:64)
  - les divisions en plusieurs etapes
Constate sur les donnees : 12 titres ajustes sur 15 necessaires.

SOURCE
------
`data/divisions_officielles.json` — date et parite relevees sur les fiches
societe publiees par la BRVM. Aucune estimation.

REGLE DE PERIMETRE
------------------
Seules les divisions POSTERIEURES au debut de l'historique sont appliquees :
une division de 2013 n'affecte pas un historique qui commence en 2017, car le
cours de depart est deja post-division.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, replace
from pathlib import Path
from ..infrastructure.paths import DIVISIONS_OFFICIELLES  # chemins centralisés (lot 0 du plan docs/architecture.md)

FICHIER = DIVISIONS_OFFICIELLES  # défini dans paths.py (P6-01 : plus de redéfinition locale)


@dataclass(frozen=True)
class Operation:
    """Une operation de nominal.

    facteur = nouvelles / anciennes. Les cours ANTERIEURS a la date sont
    divises par ce facteur :
      - division     (facteur > 1) : 10 nouvelles pour 1 ancienne -> /10
      - regroupement (facteur < 1) : 1 nouvelle pour 2 anciennes  -> x2
    """

    code: str
    date: str          # AAAA-MM-JJ
    facteur: float     # nouvelles / anciennes
    nouvelles: int
    anciennes: int

    @property
    def sens(self) -> str:
        return f"{self.nouvelles} nouvelles pour {self.anciennes} ancienne(s)"

    @property
    def type(self) -> str:
        return "division" if self.facteur > 1 else "regroupement"


def charger(chemin: Path | None = None) -> dict[str, list[Operation]]:
    """Charge les operations de nominal, groupees par code de titre."""
    chemin = Path(chemin) if chemin else FICHIER
    if not chemin.exists():
        raise FileNotFoundError(
            f"Reference des operations introuvable : {chemin}\n"
            "Indispensable : sans elle, les performances sont fausses."
        )
    with open(chemin, encoding="utf-8") as fh:
        donnees = json.load(fh)

    par_code: dict[str, list[Operation]] = {}
    for d in donnees.get("divisions", []):
        # B2-16 (30/10/2026) — ÉCHEC BRUYANT sur une fiche incomplète.
        # Une fiche écrite avec les clés `n`/`m` (schéma des opérations ANTÉRIEURES,
        # section `ignorees_anterieures`) était IGNORÉE EN SILENCE : la division n'était
        # pas appliquée, la série gardait sa cassure, puis le nettoyeur d'aberrantes
        # « réparait » la nouvelle base (cas SNTS 26/10/2026 : 4 700 -> 42 000, ligne
        # valorisée ×10). Une opération de nominal invisible fausse les cours, les
        # rendements et les valorisations : elle doit arrêter le calcul, jamais passer.
        if "nouvelles" not in d or "anciennes" not in d:
            raise ValueError(
                "Operation de nominal mal formee "
                f"({d.get('code', '?')} {d.get('date', '?')}) : cles attendues "
                "« nouvelles » + « anciennes » (+ « facteur »). Cles recues : "
                f"{sorted(k for k in d if not k.startswith('_'))}. "
                "Les operations anterieures a l'historique vont dans la section "
                "`ignorees_anterieures` (jamais lue). Une fiche ignoree en silence "
                "fausse les series de cours.")
        n = int(d.get("nouvelles") or 0)
        m = int(d.get("anciennes") or 1)
        if n <= 0 or m <= 0:
            raise ValueError(
                "Operation de nominal invalide "
                f"({d.get('code', '?')} {d.get('date', '?')}) : "
                f"nouvelles={n}, anciennes={m} — les deux doivent etre > 0.")
        facteur = float(d.get("facteur") or (n / m if m else 1))
        if facteur == 1.0:
            continue  # neutre : aucun effet sur les cours
        op = Operation(
            code=str(d["code"]).upper(),
            date=d["date"],
            facteur=facteur,
            nouvelles=n,
            anciennes=m,
        )
        par_code.setdefault(op.code, []).append(op)

    for code in par_code:
        par_code[code].sort(key=lambda x: x.date)
    return par_code


def cours_reels(chemin: Path | None = None) -> dict[str, int]:
    """Cours de cloture publies (07/10/2026) — sert au controle de coherence."""
    chemin = Path(chemin) if chemin else FICHIER
    if not chemin.exists():
        return {}
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    bruts = donnees.get("cours_reels_07_10_2026", {})
    out = {}
    for k, v in bruts.items():
        try:
            out[k] = int(str(v).replace(" ", "").replace("\u00a0", ""))
        except (TypeError, ValueError):
            continue
    return out


def utiles(divisions: list[Operation], date_debut: str) -> list[Operation]:
    """Operations posterieures au debut de l'historique (les seules actives)."""
    debut = (date_debut or "")[:10]
    return [d for d in divisions if not debut or d.date > debut]


def appliquer(barres: list, operations: list[Operation]) -> int:
    """Retro-ajuste les barres SUR PLACE. Retourne le nombre d'operations.

    Pour chaque operation (date D, facteur F) : toute barre ANTERIEURE a D voit
    son cours divise par F, son volume multiplie par F.
    """
    if not operations or not barres:
        return 0
    for op in sorted(operations, key=lambda x: x.date):
        for i, b in enumerate(barres):
            d = str(getattr(b, "date", ""))[:10]
            if not d or d >= op.date:
                continue
            maj = {}
            c = getattr(b, "close", None)
            if c:
                maj["close"] = round(float(c) / op.facteur, 6)
            for champ in ("open", "high", "low"):
                v = getattr(b, champ, None)
                if v:
                    maj[champ] = round(float(v) / op.facteur, 6)
            vol = getattr(b, "volume", None)
            if vol:
                maj["volume"] = int(float(vol) * op.facteur)
            if not maj:
                continue
            try:
                barres[i] = replace(b, **maj)
            except TypeError:
                for k, v in maj.items():
                    setattr(b, k, v)
    return len(operations)


def ajuster_barres(barres: list, operations: list[Operation], date_debut: str | None = None) -> list:
    """Copie retro-ajustee des barres. L'entree n'est jamais modifiee."""
    resultat = copy.deepcopy(barres)
    if not resultat:
        return resultat
    debut = date_debut if date_debut is not None else str(getattr(resultat[0], "date", ""))[:10]
    appliquer(resultat, utiles(operations, debut))
    return resultat


def ajuster_historique(hist: dict, chemin: Path | None = None) -> dict:
    """Ajuste tout un historique {code: [barres]}.

    L'entree n'est pas modifiee. Retourne :
      {"historique": <ajuste>, "rapport": [...], "sans_division": [...],
       "nb_titres_ajustes": n}
    """
    try:
        par_code = charger(chemin)
    except FileNotFoundError:
        # B2-05 (corrigé le 13/10/2026) : NE PLUS avaler l'absence du fichier de divisions.
        # L'ancien repli silencieux (`par_code = {}`) retournait un historique BRUT, non
        # ajusté — la classe exacte de l'incident du 21/08/2026 (faux drawdowns de −96 %).
        # La docstring de `charger()` le dit : « Indispensable : sans elle, les performances
        # sont fausses ». L'échec doit être bruyant, comme dans `charger()`.
        raise FileNotFoundError(
            f"Fichier des divisions officielles introuvable ({chemin or 'chemin par défaut'}) : "
            "un historique non ajusté serait FAUX (drawdowns, performances). "
            "Vérifier data/divisions_officielles.json avant de relancer."
        ) from None

    ajuste: dict = {}
    rapport: list[dict] = []
    sans_division: list[str] = []

    for code, barres in hist.items():
        if not barres:
            ajuste[code] = barres
            continue
        ops = par_code.get(str(code).upper(), [])
        debut = str(getattr(barres[0], "date", ""))[:10]
        actives = utiles(ops, debut)

        copie = copy.deepcopy(barres)
        appliquer(copie, actives)
        ajuste[code] = copie

        if actives:
            cumul = 1.0
            for d in actives:
                cumul *= d.facteur
            rapport.append({
                "code": code,
                "debut_historique": debut,
                "facteur_cumule": round(cumul, 6),
                "operations": [
                    {"date": d.date, "facteur": d.facteur, "type": d.type,
                     "sens": d.sens} for d in actives
                ],
            })
        elif not ops:
            sans_division.append(code)

    return {
        "historique": ajuste,
        "rapport": rapport,
        "sans_division": sans_division,
        "nb_titres_ajustes": len(rapport),
    }


def ajuster_titre(barres: list, code: str | None = None, chemin: Path | None = None) -> list:
    """Ajuste les barres d'UN titre identifie par son code."""
    if not barres:
        return barres
    code = code or getattr(barres[0], "code", None) or getattr(barres[0], "symbol", None)
    if not code:
        return copy.deepcopy(barres)
    divs = charger(chemin).get(str(code).upper(), [])
    return ajuster_barres(barres, divs)


def resume(rapport: list[dict]) -> str:
    """Rendu lisible du rapport d'ajustement."""
    lignes = []
    for r in sorted(rapport, key=lambda x: x["code"]):
        det = " + ".join(
            f"{o['facteur']:.4g}x ({o['date']}, {o['type']})" for o in r["operations"]
        )
        lignes.append(f"  {r['code']:7} cumul {r['facteur_cumule']:<10.4g} {det}")
    return "\n".join(lignes)
