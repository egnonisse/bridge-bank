"""Schema et evaluation SURE des hypotheses du challenge multi-modeles.

POURQUOI UN DSL PLUTOT QU'UN EVAL
---------------------------------
Les hypotheses viennent de modeles de langage. Executer leur texte avec
`eval()` serait une porte ouverte (injection, acces disque/reseau, boucles
infinies). On definit donc un langage restreint :
  - un vocabulaire FERME d'indicateurs, calcules par le code ;
  - trois operateurs logiques (`et`, `ou`, `non`) et six comparateurs ;
  - une expression reguliere stricte : aucune fonction, aucun appel, aucune
    assignation ne peut passer.

Toute expression non conforme est REJETEE avec un motif clair. Une hypothese
rejetee n'est pas une erreur du modele a corriger en silence : elle est
comptee comme telle dans le verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
#  VOCABULAIRE FERME DES INDICATEURS
# ---------------------------------------------------------------------------

INDICATEURS = {
    # Rendements passes (fractions : 0.15 = +15 %)
    "r5": "rendement sur 5 seances",
    "r20": "rendement sur 20 seances",
    "r60": "rendement sur 60 seances",
    "r120": "rendement sur 120 seances",
    "r250": "rendement sur 250 seances",
    # Risque
    "vol60": "volatilite annualisee sur 60 seances",
    "dd250": "distance au plus haut des 250 seances (negatif)",
    "dd_atl": "drawdown depuis le plus haut historique (negatif)",
    # Position dans la fourchette 5 ans (0 = plus bas, 1 = plus haut)
    "pos5a": "position dans la fourchette 5 ans",
    # Tendance
    "prix_vs_mm50": "cours / moyenne mobile 50 seances - 1",
    "prix_vs_mm200": "cours / moyenne mobile 200 seances - 1",
    # Liquidite
    "vol_ratio": "volume du jour / volume median 60 seances - 1",
    # Fondamentaux (constants sur la periode, fournis par la source)
    "per": "PER (cours / benefice par action)",
    "net_yield": "rendement net du dividende",
    "payout": "dividende / benefice",
}

COMPARATEURS = ("<=", ">=", "<", ">", "==", "!=")
OPERATEURS = ("et", "ou")

# Indicateurs dont la valeur est celle d'AUJOURD'HUI, appliquee a tout
# l'historique. Une regle qui les utilise ne teste donc pas « etait-ce bon a
# l'epoque ? » mais « est-ce bon maintenant ? » : c'est une fuite du futur.
# Elle peut etre interessante a explorer, mais elle ne prouve RIEN sur la
# capacite de la regle a decider en temps reel — on la classe a part.
FONDAMENTAUX_BIAISES = ("per", "net_yield", "payout")

# Un terme : <indicateur> <comparateur> <nombre>
TERME = re.compile(r"^\s*([a-z_0-9]+)\s*(<=|>=|<|>|==|!=)\s*(-?[0-9]*\.?[0-9]+)\s*$")


@dataclass
class Hypothese:
    """Une hypothese soumise par un modele."""

    id: str
    nom: str
    achat: str
    vente: str = ""
    duree_max: int = 120
    rationale: str = ""
    source: str = ""
    brut: dict = field(default_factory=dict)

    # Verdict de validation syntaxique
    valide: bool = True
    motifs: list[str] = field(default_factory=list)
    # Marqueur de fuite du futur. Depuis la reconstitution point-in-time des
    # fondamentaux, il reste False : une regle « per < 15 » teste bien la
    # situation de l'epoque. Il ne se reactive que si le cache historique est
    # absent (fondamentaux_pti=False).
    biaisee: bool = False
    # Indicateurs fondamentaux utilises (tracabilite, sans exclusion)
    utilise_fond: list[str] = field(default_factory=list)


def _decouper(expr: str) -> list[str]:
    """Separe une expression sur les 'et' / 'ou' de premier niveau.

    On accepte aussi les equivalents anglais (`and`, `or`) : les modeles les
    ecrivent naturellement, et refuser une hypothese entiere pour une question
    de langue fait perdre une idee valable (cas observe : Gemini a vu sa regle
    « Tendance haussiere confirmee » rejetee pour un simple `and`).
    """
    return re.split(r"\s+(?:et|ou|and|or)\s+", expr.strip(), flags=re.I)


def _verifier_terme(terme: str) -> str | None:
    """Verifie un terme simple. Retourne un motif d'erreur ou None."""
    t = terme.strip().strip("()")
    m = TERME.match(t)
    if not m:
        return f"terme illisible : « {t} » (attendu : <indicateur> <comparateur> <nombre>)"
    ind = m.group(1)
    if ind not in INDICATEURS:
        return (f"indicateur inconnu : « {ind} » "
                f"(disponibles : {', '.join(sorted(INDICATEURS))})")
    return None


def valider_expression(expr: str, nom_champ: str) -> list[str]:
    """Verifie une expression complete. Retourne la liste des motifs d'echec."""
    motifs = []
    if not expr or not expr.strip():
        return motifs  # vide = autorise (ex. pas de condition de vente)

    e = expr.strip()
    if any(c in e for c in "()[]{}\"'`;\\"):
        motifs.append(f"{nom_champ} : parentheses, guillemets et points-virgules interdits")
        return motifs

    bas = e.lower()
    for mot in ("import", "exec", "eval", "lambda", "open", "os.", "sys.", "__"):
        if mot in bas:
            motifs.append(f"{nom_champ} : mot reserve interdit « {mot} »")
            return motifs

    termes = _decouper(e)
    if not termes:
        motifs.append(f"{nom_champ} : expression vide apres decoupage")
        return motifs

    for t in termes:
        err = _verifier_terme(t)
        if err:
            motifs.append(f"{nom_champ} : {err}")
    return motifs


def utilise_fondamentaux(expr: str) -> list[str]:
    """Retourne les indicateurs biaises utilises dans une expression."""
    if not expr:
        return []
    trouves = []
    for ind in FONDAMENTAUX_BIAISES:
        if re.search(rf"\b{ind}\b", expr):
            trouves.append(ind)
    return trouves


def valider_hypothese(h: Hypothese, fondamentaux_pti: bool = True) -> Hypothese:
    """Valide une hypothese : expressions + duree, et trace l'usage des fondamentaux.

    `fondamentaux_pti` : les trois indicateurs fondamentaux sont-ils reconstitues
    historiquement (point-in-time) ? Depuis la reconstitution
    (src/fondamentaux_historiques.py), c'est le cas : une regle « per < 15 »
    teste bien « etait-ce bon a l'epoque ? ». Le marquage `biaisee` — qui
    excluait ces regles du classement — n'a donc plus lieu d'etre par defaut.

    Il est CONSERVE : si un jour le cache fondamental manque, l'appelant passe
    `fondamentaux_pti=False` et le garde-fou se reactive automatiquement. Mieux
    vaut une protection qui existe et ne sert pas qu'une protection absente.
    """
    motifs = []
    motifs += valider_expression(h.achat, "achat")
    motifs += valider_expression(h.vente, "vente")
    if not h.achat or not h.achat.strip():
        motifs.append("achat : condition d'achat obligatoire")
    try:
        d = int(h.duree_max)
        if not 5 <= d <= 500:
            motifs.append(f"duree_max : {d} hors bornes (5 a 500 seances)")
        h.duree_max = d
    except (TypeError, ValueError):
        motifs.append(f"duree_max : « {h.duree_max} » n'est pas un entier")

    # Usage des fondamentaux : information de tracabilite, plus un motif
    # d'exclusion tant que le point-in-time est actif.
    inds = utilise_fondamentaux(h.achat) + utilise_fondamentaux(h.vente)
    h.utilise_fond = inds
    h.biaisee = bool(inds) and not fondamentaux_pti

    h.motifs = motifs
    h.valide = not motifs
    return h


def compiler(expr: str):
    """Compile une expression en structure evaluable SANS regex ni parsing.

    Retourne une liste de blocs ; chaque bloc est une liste de triplets
    (indicateur, operateur, valeur). Un bloc est une conjonction (« et »),
    les blocs sont relies par « ou ». `None` signifie : aucun terme valide.

    C'est cette compilation qui rend le challenge jouable : l'expression est
    analysee UNE fois, puis evaluee des centaines de milliers de fois.
    """
    if not expr or not expr.strip():
        return None
    blocs = []
    for bloc in re.split(r"\s+(?:ou|or)\s+", expr.strip(), flags=re.I):
        termes = []
        for t in re.split(r"\s+(?:et|and)\s+", bloc.strip(), flags=re.I):
            m = TERME.match(t.strip().strip("()"))
            if m:
                termes.append((m.group(1), m.group(2), float(m.group(3))))
        if termes:
            blocs.append(termes)
    return blocs or None


def evaluer_compilee(compilation, indicateurs: dict) -> bool:
    """Evalue une expression compilee. « ou » entre blocs, « et » dans un bloc."""
    if not compilation:
        return False
    get = indicateurs.get
    for bloc in compilation:
        ok = True
        for ind, op, val in bloc:
            x = get(ind)
            if x is None:
                ok = False
                break
            if op == ">":
                if not x > val:
                    ok = False
                    break
            elif op == "<":
                if not x < val:
                    ok = False
                    break
            elif op == ">=":
                if not x >= val:
                    ok = False
                    break
            elif op == "<=":
                if not x <= val:
                    ok = False
                    break
            elif op == "==":
                if abs(x - val) >= 1e-9:
                    ok = False
                    break
            elif op == "!=":
                if abs(x - val) < 1e-9:
                    ok = False
                    break
        if ok:
            return True
    return False


def evaluer(expr: str, indicateurs: dict) -> bool:
    """Evalue une expression complete (version lente, pour usage ponctuel).

    Dans une boucle, utiliser `compiler()` une fois puis `evaluer_compilee()`.
    """
    return evaluer_compilee(compiler(expr), indicateurs)


def indicateurs_du_champ() -> str:
    """Texte lisible listant les indicateurs disponibles (pour les prompts)."""
    return "\n".join(f"  - {k} : {v}" for k, v in sorted(INDICATEURS.items()))
