"""AUDIT DES CONSTANTES METIER — inventaire, doublons, et SNAPSHOT DE REFERENCE.

POURQUOI CE SCRIPT
------------------
196 constantes vivent dans 35 fichiers, et certaines regles y sont definies plusieurs fois
(PER <= 14 dans 3 modules, le taux d'IRVM dans 3, les frais dans 4). Le danger n'est pas
le desordre : c'est qu'une COPIE peut diverger sans que rien ne le signale. Deux cas
reels constates le 08/10/2026 :
  - « combien de cas faut-il pour valider un seuil » avait DEUX reponses (6 et 8) ;
  - `FRAIS = 0.028` (aller-retour) et `FRAIS_PAR_SENS = 0.014` portent le meme mot
    « FRAIS » avec des sens differents — les confondre double les frais en silence.

CE QUE PRODUIT CE SCRIPT
------------------------
1. `data/constantes_snapshot.json` — la VALEUR EFFECTIVE de chaque constante, lue en
   executant le module. C'est la reference de non-regression : apres une centralisation,
   on relit ce fichier et on compare. Aucune valeur ne doit avoir bouge.
2. `docs/AUDIT-CONSTANTES.md` — l'inventaire lisible, groupe par domaine, avec les
   doublons signales.

POURQUOI UN SNAPSHOT AVANT DE TOUCHER AU CODE
---------------------------------------------
Centraliser des constantes est une operation mecanique, et c'est exactement le genre
d'operation dont on croit qu'elle ne change rien. Le snapshot transforme cette croyance en
preuve : si la valeur effective d'une seule constante bouge, la comparaison le dit.

On lit les valeurs en IMPORTANT les modules (pas en analysant le texte), parce que c'est
la valeur effective qui compte — celle que le code utilise vraiment, y compris quand elle
est derivee d'une autre constante.
"""
import argparse
import ast
import importlib
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

SRC = RACINE / "src"
SNAPSHOT = RACINE / "data" / "constantes_snapshot.json"
RAPPORT = RACINE / "docs" / "AUDIT-CONSTANTES.md"

# Domaines fonctionnels. Sert uniquement a REGROUPER l'inventaire pour la lecture.
DOMAINES = {
    "filtres_entree": ("PER_MAX", "PAYOUT", "RENDEMENT", "YIELD", "DIV_YIELD", "TARGET_NET"),
    "fiscalite_frais": ("IRVM", "FRAIS", "COURTAGE", "TAX", "CONSERVATION"),
    "sorties_alertes": ("SELL", "PROFIT", "LOSS", "THRESHOLD", "EPISODE", "BORNE", "ALERT"),
    "concentration": ("MAX_POSITION", "MAX_BUY", "MAX_MARKET", "CONCENTRATION"),
    "speculation": ("STOP", "PALIER", "SPEC", "TRACK"),
    "allocation": ("TARGET_STOCK", "TARGET_BOND", "TARGET_CASH", "TARGET_SPEC"),
    "technique": ("CACHE", "TIMEOUT", "WORKER", "URL", "FILE", "DIR", "HEADERS", "MAX_AGE"),
}


def _serialisable(valeur):
    """Rend une constante comparable. None = impossible, on garde le type."""
    if isinstance(valeur, (int, float, str, bool)) or valeur is None:
        return valeur
    if isinstance(valeur, (list, tuple)):
        return [_serialisable(v) for v in valeur]
    if isinstance(valeur, dict):
        return {str(k): _serialisable(v) for k, v in valeur.items()}
    if isinstance(valeur, Path):
        # Le dossier du projet ne porte PAS le même nom sur toutes les machines : en intégration
        # continue le dépôt est cloné dans « bridge-bank », ailleurs dans « Bridge Bank ». Un
        # chemin absolu stocké tel quel ferait échouer le filet pour une raison qui n'a rien à
        # voir avec une dérive de règle — un faux écart qui apprend à ignorer l'alerte.
        if valeur == RACINE:
            return "<Path .>"
        return f"<Path {valeur.name}>"
    if isinstance(valeur, (set, frozenset)):
        return sorted(_serialisable(v) for v in valeur)
    return f"<{type(valeur).__name__}>"


def _est_constante(nom: str) -> bool:
    return nom.isupper() and len(nom) > 2 and not nom.startswith("_")


def nom_module(f: Path) -> str:
    """Nom pointé d'un module, à TOUT niveau : src/collecte/bsapi.py -> src.collecte.bsapi.

    Sans cela, déplacer un module dans un domaine le ferait sortir de l'inventaire — et le
    contrôle des constantes cesserait silencieusement de le surveiller. Les fichiers
    `__init__.py` ne sont pas des constantes : ils sont ignorés par `_est_constante`.
    """
    return ".".join(f.relative_to(RACINE).with_suffix("").parts)


def scanner_module(chemin: Path) -> dict:
    """Extrait les constantes module-level SANS executer le fichier (analyse AST).

    Sert a inventorier, y compris les modules qui ne s'importent pas proprement
    (dependances reseau, effets de bord a l'import).
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        return {"_erreur": str(e)}
    out = {}
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and _est_constante(cible.id):
                    try:
                        out[cible.id] = ast.literal_eval(noeud.value)
                    except (ValueError, SyntaxError):
                        out[cible.id] = f"<expression: {ast.unparse(noeud.value)[:60]}>"
    return out


# Sentinelle : « cette constante n'a PAS pu être lue » (module inimportable, nom absent).
# À NE PAS confondre avec None, qui est une valeur parfaitement légitime. Les deux étaient
# confondus, et les deux usages SAUTAIENT la ligne en silence : le contrôle annonçait
# « OK — 189 valeurs identiques au snapshot » alors que 120 d'entre elles n'étaient même pas
# lues (interpréteur sans les dépendances : requests, pyyaml, pymupdf).
ILLISIBLE = object()


def lire_valeur_effective(nom_module: str, constante: str, motifs: list | None = None):
    """Lit la valeur REELLE en important le module. `ILLISIBLE` si la lecture est impossible."""
    try:
        mod = importlib.import_module(nom_module)
    except Exception as exc:                                   # noqa: BLE001
        if motifs is not None:
            motifs.append(f"{nom_module} non importable ({type(exc).__name__}: {exc})")
        return ILLISIBLE
    if not hasattr(mod, constante):
        if motifs is not None:
            motifs.append(f"{nom_module}.{constante} absente du module")
        return ILLISIBLE
    return _serialisable(getattr(mod, constante))


# Familles SEMANTIQUES : des notions qui portent des noms differents selon le module.
# C'est l'angle mort du detecteur par nom — et c'est precisement la ou se cache le piege
# le plus dangereux du projet : `FRAIS = 0.028` (aller-retour) et `FRAIS_PAR_SENS = 0.014`
# portent le meme mot « FRAIS » avec des SENS DIFFERENTS. Un module qui copie l'un en
# croyant l'autre double les frais, sans qu'aucun test ne s'en apercoive.
FAMILLES = {
    "frais de courtage": ("FRAIS",),
    "retenue a la source": ("IRVM",),
    "prix maximum paye": ("PER_MAX", "MAX_PER", "PER_ABSURD", "PER_NOYAU"),
    "part du benefice versee": ("PAYOUT",),
    "rendement minimum exige": ("RENDEMENT_NET", "TARGET_NET_YIELD", "DIV_YIELD"),
    "seuil de vente sur gain": ("PROFIT", "SELL_FRACTION", "EPISODE", "BORNE_BASSE"),
    "sortie de secours": ("STOPOUT", "LOSS_ALERT"),
    "tranches d'achat": ("TRANCHE", "ESPACEMENT"),
    "reserve de liquidites": ("TARGET_CASH", "CASH_ALERT"),
    "limites de concentration": ("MAX_POSITION", "MAX_BUY", "MAX_MARKET",
                                 "CONCENTRATION_WARN"),
}


def familles_semantiques(inventaire: dict) -> dict[str, list[tuple[str, dict]]]:
    """Regroupe les constantes par NOTION, pas par nom."""
    out: dict[str, list[tuple[str, dict]]] = {}
    for nom, defs in inventaire.items():
        for famille, motifs in FAMILLES.items():
            if any(m in nom for m in motifs):
                out.setdefault(famille, []).append((nom, defs[0]))
                break
    return {f: sorted(v) for f, v in out.items() if len(v) > 1}


def domaine_de(nom: str) -> str:
    for domaine, prefixes in DOMAINES.items():
        if any(p in nom for p in prefixes):
            return domaine
    return "autre"


def auditer():
    # rglob : l'inventaire doit suivre les modules jusque dans leurs domaines (src/collecte/…).
    fichiers = sorted(
        p for p in SRC.rglob("*.py")
        if not p.name.startswith("_")
        and "__pycache__" not in p.parts
        and not any(part.startswith(".") for part in p.parts)
    )
    inventaire: dict[str, dict] = {}
    for f in fichiers:
        module = nom_module(f)
        for nom, valeur in scanner_module(f).items():
            if nom.startswith("_"):
                continue
            inventaire.setdefault(nom, []).append(
                {"module": module, "fichier": f.name, "valeur": _serialisable(valeur)})
    return inventaire, fichiers


def detecter_doublons(inventaire: dict) -> list[dict]:
    """Constantes definies dans PLUSIEURS modules — le vrai danger du projet.

    On distingue les REGLES METIER des constantes TECHNIQUES : `STATE_FILE` vaut
    legitimement un chemin different dans chaque module (`alerts_state.json`,
    `boc_state.json`...), alors que deux valeurs differentes pour `PER_MAX` seraient
    un defaut. Sans cette distinction, le rapport noie les vrais problemes.
    """
    out = []
    for nom, defs in inventaire.items():
        if len(defs) < 2:
            continue
        valeurs = {json.dumps(d["valeur"], sort_keys=True) for d in defs}
        out.append({
            "constante": nom,
            "occurrences": len(defs),
            "coherent": len(valeurs) == 1,
            "metier": nom in TOUS_LES_NOMS_METIER,
            "modules": [d["module"] for d in defs],
            "valeurs": sorted({str(d["valeur"]) for d in defs}),
        })
    # Les regles metier incoherentes d'abord : c'est ce qu'il faut regarder.
    return sorted(out, key=lambda x: (not x["metier"], x["coherent"], -x["occurrences"]))


# Noms de regles metier (catalogue src/regles.py + alias locaux). Sert a distinguer une
# divergence INQUIETANTE d'une divergence NORMALE dans le rapport.
TOUS_LES_NOMS_METIER = {
    "PER_MAX", "PER_MAX_NOYAU", "PAYOUT_MAX", "PAYOUT_TIGHT", "PAYOUT_CRITICAL",
    "PER_ABSURD", "IRVM", "FRAIS_PAR_SENS", "FRAIS_ALLER_RETOUR", "FRAIS_MINIMUM",
    "RENDEMENT_NET_MIN", "RENDEMENT_NET_ENTREE", "RENDEMENT_NET_SORTIE",
    "EPISODES_MIN", "MIN_EPISODES", "BORNE_BASSE_MIN", "PROFIT_ALERT_THRESHOLD",
    "SELL_FRACTION", "LOSS_ALERT_THRESHOLD", "MAX_POSITION_WEIGHT", "MAX_BUY_WEIGHT",
    "MAX_MARKET_WEIGHT", "PROFIT_MIN_EPISODES",
}


def ecrire_snapshot(inventaire: dict, fichiers: list[Path]) -> int:
    """Valeurs EFFECTIVES (modules importes). REFUSE d'ecrire un snapshot PARTIEL.

    Un snapshot qui retrecit en silence est un filet qui se raccourcit : la comparaison
    suivante ne porte plus que sur ce qui restait lisible, et elle annonce « OK ». Retourne
    le nombre de valeurs illisibles (0 = snapshot ecrit).
    """
    snap = {}
    illisibles: list[str] = []
    for f in fichiers:
        module = nom_module(f)
        constantes = list(inventaire.keys())
        for nom in constantes:
            if not any(d["module"] == module for d in inventaire[nom]):
                continue
            motifs: list[str] = []
            v = lire_valeur_effective(module, nom, motifs)
            if v is ILLISIBLE:
                illisibles.append(f"{module}.{nom} — {motifs[0] if motifs else 'illisible'}")
                continue
            snap[f"{module}.{nom}"] = v
    if illisibles:
        print(f"\n  ARRET : {len(illisibles)} constante(s) illisible(s) — snapshot NON ecrit.")
        for ligne in illisibles[:10]:
            print(f"    {ligne}")
        if len(illisibles) > 10:
            print(f"    … et {len(illisibles) - 10} autre(s)")
        print("  Dependances manquantes ? Un snapshot partiel ferait taire le controle")
        print("  sur tout ce qui manque, tout en affichant « OK ».")
        return len(illisibles)
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True),
                        encoding="utf-8")
    return 0


def ecrire_rapport(inventaire: dict, doublons: list[dict], familles: dict) -> None:
    par_domaine: dict[str, list[tuple[str, dict]]] = {}
    for nom, defs in inventaire.items():
        par_domaine.setdefault(domaine_de(nom), []).append((nom, defs[0]))

    incoherents = [d for d in doublons if not d["coherent"]]
    lignes = [
        "# Audit des constantes métier — inventaire, doublons et familles",
        "",
        f"**{sum(len(d) for d in inventaire.values())} définitions** pour "
        f"**{len(inventaire)} constantes distinctes**.",
        "",
        "---",
        "",
        "## 1. ⚠️ La même NOTION sous plusieurs noms — le piège le plus dangereux",
        "",
        "Le détecteur par nom ne voit rien ici : les constantes s'appellent différemment",
        "alors qu'elles parlent de la même chose. **Un module qui copie l'une en croyant",
        "l'autre produit un chiffre faux sans qu'aucun test ne s'en aperçoive.**",
        "",
    ]
    for famille, entrees in sorted(familles.items()):
        lignes += [f"### {famille}", "", "| Constante | Valeur | Module |",
                   "|---|---|---|"]
        for nom, d in entrees:
            lignes.append(f"| `{nom}` | `{d['valeur']}` | {d['module']} |")
        lignes.append("")

    lignes += ["---", "",
               "## 2. Doublons incohérents — même nom, valeurs différentes", ""]
    metier_incoherents = [d for d in incoherents if d["metier"]]
    tech_incoherents = [d for d in incoherents if not d["metier"]]

    if metier_incoherents:
        lignes += ["### ⚠️ Règles MÉTIER en divergence — à corriger en priorité", "",
                   "| Règle | Valeurs | Modules |", "|---|---|---|"]
        for d in metier_incoherents:
            lignes.append(f"| `{d['constante']}` | {' · '.join(d['valeurs'])} | "
                          f"{' · '.join(d['modules'])} |")
    else:
        lignes.append("**Aucune règle métier en divergence.** ✅")

    if tech_incoherents:
        lignes += ["", "### Constantes techniques — divergence NORMALE", "",
                   "Ces constantes portent le même nom générique dans plusieurs modules",
                   "avec des valeurs différentes **par conception** (`STATE_FILE` vaut un",
                   "chemin distinct dans chaque module). Rien à corriger.", "",
                   "| Constante | Valeurs | Modules |", "|---|---|---|"]
        for d in tech_incoherents:
            lignes.append(f"| `{d['constante']}` | {' · '.join(v[:40] for v in d['valeurs'])} | "
                          f"{' · '.join(d['modules'])} |")

    lignes += ["", "---", "",
               "## 3. Doublons cohérents (même valeur, plusieurs endroits)", "",
               "| Constante | Fois | Modules |", "|---|---|---|"]
    for d in [x for x in doublons if x["coherent"]]:
        lignes.append(f"| `{d['constante']}` | {d['occurrences']} | "
                      f"{' · '.join(d['modules'])} |")

    lignes += ["", "---", "", "## 4. Inventaire complet par domaine", ""]
    for domaine in sorted(par_domaine):
        lignes += [f"### {domaine} ({len(par_domaine[domaine])})", "",
                   "| Constante | Valeur | Module |", "|---|---|---|"]
        for nom, d in sorted(par_domaine[domaine]):
            lignes.append(f"| `{nom}` | `{d['valeur']}` | {d['module']} |")
        lignes.append("")

    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text("\n".join(lignes), encoding="utf-8")


def comparer() -> int:
    """Compare les valeurs effectives courantes au snapshot. 0 = aucune derive.

    Une valeur ILLISIBLE est un ECHEC, jamais une raison d'ignorer la ligne : un contrôle qui
    saute ce qu'il n'arrive pas à lire annonce une couverture qu'il n'a pas.
    """
    if not SNAPSHOT.exists():
        print("Aucun snapshot — lancer l'audit d'abord.")
        return 1
    ancien = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    ecarts = []
    illisibles: list[str] = []
    for cle, valeur in ancien.items():
        module, _, nom = cle.rpartition(".")
        motifs: list[str] = []
        courante = lire_valeur_effective(module, nom, motifs)
        if courante is ILLISIBLE:
            illisibles.append(f"{cle} — {motifs[0] if motifs else 'illisible'}")
            continue
        if json.dumps(courante, sort_keys=True) != json.dumps(valeur, sort_keys=True):
            ecarts.append((cle, valeur, courante))

    lues = len(ancien) - len(illisibles)
    if illisibles:
        print(f"{len(illisibles)} VALEUR(S) ILLISIBLE(S) — le controle n'a verifie que "
              f"{lues}/{len(ancien)} valeurs :")
        for ligne in illisibles[:10]:
            print(f"  {ligne}")
        if len(illisibles) > 10:
            print(f"  … et {len(illisibles) - 10} autre(s)")
        print("  -> dependances manquantes ? installer requirements.txt, puis relancer.")
        return 1
    if not ecarts:
        print(f"OK — {lues} valeurs effectives identiques au snapshot.")
        return 0
    print(f"{len(ecarts)} VALEUR(S) MODIFIEE(S) :")
    for cle, av, ap in ecarts:
        print(f"  {cle} : {av!r} -> {ap!r}")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparer", action="store_true",
                    help="compare les valeurs effectives au snapshot")
    args = ap.parse_args()

    if args.comparer:
        raise SystemExit(comparer())

    inventaire, fichiers = auditer()
    doublons = detecter_doublons(inventaire)
    familles = familles_semantiques(inventaire)
    manquants = ecrire_snapshot(inventaire, fichiers)
    if manquants:
        raise SystemExit(1)          # pas de rapport non plus : il serait partiel lui aussi
    ecrire_rapport(inventaire, doublons, familles)

    total = sum(len(d) for d in inventaire.values())
    incoherents = [d for d in doublons if not d["coherent"]]
    print(f"  {total} definitions · {len(inventaire)} constantes distinctes "
          f"· {len(fichiers)} fichiers")
    print(f"  {len(doublons)} constantes definies plusieurs fois, "
          f"dont {len(incoherents)} avec des valeurs DIFFERENTES")
    print()
    print(f"  FAMILLES SEMANTIQUES (meme notion, noms differents) : {len(familles)}")
    for famille, entrees in sorted(familles.items()):
        valeurs = {str(d["valeur"]) for _, d in entrees}
        marque = "  <-- VALEURS DIVERGENTES" if len(valeurs) > 1 else ""
        print(f"    {famille}{marque}")
        for nom, d in entrees:          # TOUTES les entrees : tronquer cachait un doublon
            print(f"        {nom:<28} = {d['valeur']}   ({d['module']})")
    print(f"\n  Snapshot : {SNAPSHOT.relative_to(RACINE)}")
    print(f"  Rapport  : {RAPPORT.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
