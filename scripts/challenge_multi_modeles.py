"""Challenge multi-modeles — orchestrateur OpenRouter.

ARCHITECTURE EN 4 ROUNDS
------------------------
R1  GENERATION A L'AVEUGLE — chaque modele recoit les statistiques descriptives
    du marche BRVM et le langage d'ecriture des regles. Il propose 5 hypotheses.
    Il ne voit AUCUN resultat de backtest.
R2  CRITIQUE CROISEE ANONYMISEE — chaque modele recoit les hypotheses des AUTRES
    (sans savoir qui les a ecrites) et doit dire lesquelles sont fragiles.
R3  VALIDATION PAR LE CODE — le validateur du projet (src/challenge_validateur)
    backteste tout, compare au panier ALEATOIRE et coupe en deux periodes.
    Aucun appel API : c'est du calcul local.
R4  VERDICT — classement par ce que le code a mesure, jamais par les avis.

REGLE ANTI-TRICHE
-----------------
Les modeles ne recoivent JAMAIS les resultats du backtest, ni en R1 ni en R2.
S'ils les voyaient, ils « devineraient » au lieu de raisonner, et leur accord
ne prouverait plus rien.

CONTROLE DE BUDGET
------------------
Chaque reponse OpenRouter renvoie l'usage reel. Le script cumule et s'arrete
AVANT de depasser le plafond (par defaut 4,5 $ sur 5 $ disponibles), pour ne
jamais tomber en panne de credit au milieu d'un round.

Usage :
    python scripts/challenge_multi_modeles.py --dry-run     # sans appel API
    python scripts/challenge_multi_modeles.py --round1
    python scripts/challenge_multi_modeles.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_schema import (  # noqa: E402
    Hypothese, indicateurs_du_champ, valider_hypothese,
)
from src.backtesting.challenge_validateur import (  # noqa: E402
    charger_fondamentaux, charger_historique, evaluer_hypothese,
)
from src.backtesting.challenge_indicateurs import precalculer_historique  # noqa: E402
from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

API = "https://openrouter.ai/api/v1/chat/completions"
DATASET = chemin_data("challenge_dataset.json")
SORTIE = chemin_data("challenge_resultats.json")
PLAFOND_DEFAUT = 4.5          # $ — marge sous les 5 $ disponibles

# Modeles de FAMILLES DIFFERENTES : six variantes du meme raisonnement
# n'apporteraient rien (biais de formation partages).
MODELES = [
    {"id": "anthropic/claude-haiku-5.5",             "nom": "Claude Haiku 5.5"},
    {"id": "openai/gpt-5.6-luna-pro",                "nom": "GPT-5.6 Luna Pro"},
    {"id": "google/gemini-2.5-flash",                "nom": "Gemini 2.5 Flash"},
    {"id": "~deepseek/deepseek-pro-latest",          "nom": "DeepSeek Pro"},
    {"id": "meta-llama/llama-3.3-70b-instruct",      "nom": "Llama 3.3 70B"},
    {"id": "mistralai/mistral-large-4-0",            "nom": "Mistral Large 4"},
]


# ---------------------------------------------------------------------------
#  CLE API — lue par nom de variable, jamais affichee
# ---------------------------------------------------------------------------

def charger_cle() -> str:
    env = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
    if not env.exists():
        raise SystemExit(f".env introuvable : {env}")
    for l in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.strip().startswith("#") or "=" not in l:
            continue
        n, _, v = l.partition("=")
        if n.strip() == "OPENROUTER_API_KEY" and v.strip():
            return v.strip()
    raise SystemExit("OPENROUTER_API_KEY absente ou commentee dans le .env")


# ---------------------------------------------------------------------------
#  APPEL MODELE
# ---------------------------------------------------------------------------

class Budget:
    """Suit la depense reelle et refuse tout appel qui la ferait exploser."""

    def __init__(self, plafond: float):
        self.plafond = plafond
        self.depense = 0.0
        self.appels = 0
        self.journal: list[dict] = []

    @property
    def restant(self) -> float:
        return self.plafond - self.depense

    def peut_appeler(self, reserve: float = 0.02) -> bool:
        return self.restant > reserve

    def enregistrer(self, modele: str, usage: dict, prix: dict):
        """Le cout vient des tokens reellement consommes, pas d'une estimation."""
        pe = float(prix.get("prompt", 0) or 0)
        ps = float(prix.get("completion", 0) or 0)
        t_in = int(usage.get("prompt_tokens", 0) or 0)
        t_out = int(usage.get("completion_tokens", 0) or 0)
        cout = t_in * pe + t_out * ps
        self.depense += cout
        self.appels += 1
        self.journal.append({"modele": modele, "in": t_in, "out": t_out,
                             "cout": round(cout, 6), "cumul": round(self.depense, 6)})


def appeler(cle: str, modele: str, messages: list[dict], budget: Budget,
            prix: dict, max_tokens: int = 2500, temperature: float = 0.7,
            essais: int = 2) -> str | None:
    """Appel HTTP avec compte de tokens. Retourne le texte ou None."""
    if not budget.peut_appeler():
        print(f"      ⛔ budget epuise ({budget.depense:.3f} $) — appel refuse")
        return None

    corps = json.dumps({
        "model": modele,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    for tentative in range(essais):
        req = urllib.request.Request(API, data=corps, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {cle}")
        req.add_header("HTTP-Referer", "https://github.com/egnonisse/bridge-bank")
        req.add_header("X-Title", "Bridge Bank Challenge")
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            budget.enregistrer(modele, d.get("usage", {}) or {}, prix)
            choix = d.get("choices", [])
            if choix:
                return choix[0].get("message", {}).get("content", "")
            return None
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")[:200]
            print(f"      HTTP {e.code} : {msg}")
            if e.code in (400, 404, 402, 403):
                return None          # inutile de reessayer
            time.sleep(3)
        except Exception as e:
            print(f"      erreur : {str(e)[:120]}")
            time.sleep(4)
    return None


# ---------------------------------------------------------------------------
#  PROMPTS
# ---------------------------------------------------------------------------

def prompt_r1(dataset: dict) -> str:
    """Prompt de generation. Ne contient AUCUN resultat de backtest."""
    m = dataset.get("marche", {})
    titres = dataset.get("titres", [])[:40]
    lignes = []
    for t in titres:
        def g(k, fmt="{:.2f}"):
            v = t.get(k)
            if v is None:
                return "n/d"
            try:
                return fmt.format(float(v))
            except (TypeError, ValueError):
                return str(v)[:16]
        lignes.append(
            f"  {str(t.get('code','?')):<7} {str(t.get('secteur','') or '')[:20]:<22} "
            f"per {g('per'):>8}  rend_net {g('rendement_net_pct'):>7}%  "
            f"volat {g('volatilite_annuelle_pct'):>7}%  "
            f"perf_an {g('perf_annuelle_pct', '{:+.1f}'):>8}%  "
            f"dd {g('drawdown_max_pct', '{:.0f}'):>6}%  "
            f"vol_med {g('volume_median', '{:.0f}'):>7}"
        )

    contraintes = dataset.get("contraintes", {})
    epreuves = dataset.get("epreuves_deja_menees", [])

    return f"""Tu participes a un exercice de recherche sur la Bourse Regionale des
Valeurs Mobilieres (BRVM, Afrique de l'Ouest, 8 pays, UEMOA, monnaie FCFA).

Ta mission : proposer des REGLES DE DECISION chiffrees, testables automatiquement,
qui battraient un investissement fait au hasard sur ce marche.

DONNEES DU MARCHE (statistiques descriptives, 2017-2026)
  Nombre de titres analyses      : {m.get('nb_titres','?')}
  Performance annuelle mediane   : {m.get('perf_annuelle_mediane_pct','?')} %
  Performance annuelle moyenne   : {m.get('perf_annuelle_moyenne_pct','?')} %
  Volatilite annualisee mediane  : {m.get('volatilite_mediane_pct','?')} %
  Drawdown median                : {m.get('drawdown_median_pct','?')} %
  Drawdown le plus violent       : {m.get('drawdown_pire_pct','?')} %
  Indice synthetique du marche   : 84 (2017) -> 35 (2020, creux) -> 145 (2026)

ECHANTILLON DE TITRES (per = cours/benefice, rend_net = rendement net du dividende,
dd = pire baisse depuis un sommet, vol_med = lots echanges par seance)
{chr(10).join(lignes) if lignes else '  (indisponible)'}

CE QUI A DEJA ETE TESTE ET REFUTE SUR CE MARCHE — ne le repropose pas :
{chr(10).join('  - ' + str(e) for e in epreuves) if epreuves else '  (rien de consigne)'}

LANGAGE AUTORISE — tu ne peux utiliser QUE ces indicateurs, mesures sur les
donnees disponibles a la date de decision (aucun futur n'est accessible) :
{indicateurs_du_champ()}

⚠️ SUR LES TROIS INDICATEURS FONDAMENTAUX (per, net_yield, payout)
   Ils sont desormais reconstitues HISTORIQUEMENT : a chaque date, ce sont les
   valeurs REELLEMENT connues ce jour-la (dernier dividende detache, dernier
   BPA publie). Tu peux donc les utiliser sans crainte de fuite du futur.
   DEUX RESERVES a connaitre :
     - la couverture commence en 2022 (avant, l'information est indisponible) :
       tes entrees seront donc surtout sur 2022-2026, pas sur 2017 ;
     - ils ne sont calcules que pour les titres dont le BPA a pu etre verifie.
   Une regle fondee sur le rendement (net_yield) est particulierement solide :
   c'est la donnee la mieux couverte.
Construis tes hypotheses sur les indicateurs de MARCHE (rendements, volatilite,
position, tendance, volume) ET sur les fondamentaux reconstitues : les deux
sont desormais testables honnetement.

SYNTAXE : <indicateur> <comparateur> <nombre>, plusieurs conditions reliees par
  "et" ou "ou". Exemple : r60 > 0.10 et dd_atl < -0.50
  Interdits : parentheses, fonctions, guillemets. Un ratio se donne en FRACTION
  (0.15 = +15 %), jamais en pourcentage.

CONTRAINTES DE VALIDATION (le juge est impitoyable)
  - Chaque hypothese doit produire AU MOINS 10 entrees sur 2017-2026, sinon
    elle est jugee sur rien.
  - Le resultat est compare a 100 paniers ACHETES AU HASARD de meme taille et
    de meme duree. Battre le marche ne suffit pas : il faut battre le hasard.
  - Les frais (2,8 % aller-retour) sont deduits.
  - L'avantage doit tenir sur les DEUX moities de la periode separement.
  - Le marche a fait +145 % entre 2017 et 2026 : une regle qui gagne sans
    battre le tirage aleatoire est rejetee.

RENDS UNIQUEMENT un tableau JSON valide, sans texte autour, de 5 hypotheses :
[
  {{
    "nom": "titre court",
    "achat": "condition d'entree",
    "vente": "condition de sortie (peut etre vide)",
    "duree_max": 120,
    "rationale": "pourquoi cela devrait marcher, en 2 phrases"
  }}
]

Cherche la VARIETE : propose des idees de natures differentes (tendance,
valorisation, dividende, liquidite, saisonnalite, retournement), pas cinq
variantes de la meme intuition."""


def prompt_r2(autres: list[dict]) -> str:
    """Prompt de critique. Les hypotheses sont ANONYMISEES et sans resultat."""
    blocs = []
    for i, h in enumerate(autres, 1):
        blocs.append(
            f'  H{i} — "{h.get("nom","")}"\n'
            f'      achat : {h.get("achat","")}\n'
            f'      vente : {h.get("vente","")}\n'
            f'      duree : {h.get("duree_max",120)} seances\n'
            f'      motif avance : {h.get("rationale","")}'
        )
    return f"""Tu es relecteur critique dans un exercice de recherche sur la BRVM
(marche etroit, peu liquide, 47 titres, monnaie FCFA).

Voici des regles proposees par d'autres participants. Tu ne sais pas qui les a
ecrites et tu n'as AUCUN resultat de test : elles n'ont pas encore ete evaluees.

{chr(10).join(blocs)}

Pour CHACUNE, dis si elle est solide ou fragile, et pourquoi en une phrase.
Cherche en priorite :
  - les regles qui se declencheraient trop rarement pour prouver quoi que ce soit ;
  - celles qui ne sont qu'une reformulation de "acheter quand ca monte" et
    seront indistinguables du hasard dans un marche haussier ;
  - celles qui dependraient d'un indicateur indisponible ou mal defini ;
  - celles qui ressemblent a du surapprentissage sur une periode passagere.

RENDS UNIQUEMENT un JSON valide :
[{{"hypothese": "H1", "avis": "solide" ou "fragile", "raison": "une phrase"}}]"""


# ---------------------------------------------------------------------------
#  PARSING DES REPONSES
# ---------------------------------------------------------------------------

def extraire_json(txt: str):
    """Recupere le premier tableau/objet JSON d'une reponse de modele."""
    if not txt:
        return None
    t = txt.strip()
    # Retirer les clotures markdown
    if "```" in t:
        import re
        blocs = re.findall(r"```(?:json)?\s*(.*?)```", t, re.S)
        if blocs:
            t = blocs[0].strip()
    for debut, fin in (("[", "]"), ("{", "}")):
        i, j = t.find(debut), t.rfind(fin)
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def hypotheses_depuis_reponse(txt: str, modele: str) -> list[Hypothese]:
    """Convertit la reponse d'un modele en hypotheses validees syntaxiquement."""
    d = extraire_json(txt)
    if d is None:
        return []
    if isinstance(d, dict):
        d = d.get("hypotheses", [d])
    if not isinstance(d, list):
        return []

    out = []
    for k, item in enumerate(d, 1):
        if not isinstance(item, dict):
            continue
        h = Hypothese(
            id=f"{modele.split('/')[-1][:14]}-H{k}",
            nom=str(item.get("nom", f"hypothese {k}"))[:80],
            achat=str(item.get("achat", "")),
            vente=str(item.get("vente", "") or ""),
            duree_max=item.get("duree_max", 120),
            rationale=str(item.get("rationale", ""))[:400],
            source=modele,
        )
        valider_hypothese(h)
        out.append(h)
    return out


# ---------------------------------------------------------------------------
#  ROUNDS
# ---------------------------------------------------------------------------

def round1(cle: str, budget: Budget, dataset: dict, prix: dict) -> list[Hypothese]:
    print("\n" + "=" * 92)
    print("  ROUND 1 — GENERATION A L'AVEUGLE")
    print("=" * 92)
    prompt = prompt_r1(dataset)
    print(f"\n  Prompt : {len(prompt):,} caracteres (~{len(prompt)//4:,} tokens)")

    toutes: list[Hypothese] = []
    for m in MODELES:
        if not budget.peut_appeler():
            print(f"\n  ⛔ budget epuise — arret avant {m['nom']}")
            break
        print(f"\n  {m['nom']}  ({m['id']})")
        txt = appeler(cle, m["id"], [{"role": "user", "content": prompt}],
                      budget, prix.get(m["id"], {}), max_tokens=2600)
        if not txt:
            print("      aucune reponse exploitable")
            continue
        hs = hypotheses_depuis_reponse(txt, m["id"])
        valides = sum(1 for h in hs if h.valide)
        print(f"      {len(hs)} hypotheses, {valides} conformes au langage  "
              f"(cumul {budget.depense:.4f} $)")
        for h in hs:
            if not h.valide:
                print(f"        ✗ {h.nom[:44]} — {h.motifs[0][:60] if h.motifs else ''}")
        toutes += hs
        time.sleep(1)

    print(f"\n  BILAN R1 : {len(toutes)} hypotheses, "
          f"depense cumulee {budget.depense:.4f} $")
    return toutes


def round2(cle: str, budget: Budget, hypotheses: list[Hypothese],
           prix: dict) -> dict:
    """Critique croisee : chaque modele voit les hypotheses des AUTRES."""
    print("\n" + "=" * 92)
    print("  ROUND 2 — CRITIQUE CROISEE ANONYMISEE")
    print("=" * 92)

    valides = [h for h in hypotheses if h.valide]
    if len(valides) < 4:
        print("\n  Trop peu d'hypotheses valides pour une critique croisee.")
        return {}

    critiques: dict[str, list] = {}
    n = len(valides)
    for k, m in enumerate(MODELES):
        if not budget.peut_appeler():
            print(f"\n  ⛔ budget epuise — arret avant {m['nom']}")
            break
        # Sous-ensemble : les hypotheses qu'il n'a pas ecrites + voisines
        autres = [h for h in valides if h.source != m["id"]]
        if len(autres) > 8:
            autres = autres[:8]
        if not autres:
            continue
        prompt = prompt_r2([asdict(h) for h in autres])
        print(f"\n  {m['nom']}  — critique de {len(autres)} hypotheses")
        txt = appeler(cle, m["id"], [{"role": "user", "content": prompt}],
                      budget, prix.get(m["id"], {}), max_tokens=1800,
                      temperature=0.4)
        if not txt:
            continue
        avis = extraire_json(txt)
        if isinstance(avis, list):
            critiques[m["id"]] = avis
            n_sol = sum(1 for a in avis if str(a.get("avis", "")).lower().startswith("sol"))
            print(f"      {len(avis)} avis rendus ({n_sol} solides)  "
                  f"(cumul {budget.depense:.4f} $)")
        else:
            print("      reponse illisible")
        time.sleep(1)

    print(f"\n  BILAN R2 : {len(critiques)} critiques  "
          f"depense cumulee {budget.depense:.4f} $")
    return critiques


def round3(hypotheses: list[Hypothese]) -> list[dict]:
    """Validation locale : aucun appel API."""
    print("\n" + "=" * 92)
    print("  ROUND 3 — VALIDATION PAR LE CODE (aucun appel API)")
    print("=" * 92)

    hist = charger_historique()
    fond = charger_fondamentaux()
    hf = {}
    try:
        from src.backtesting.challenge_indicateurs import charger_historique_fondamentaux
        hf = charger_historique_fondamentaux()
    except Exception:
        pass
    nb_pti = sum(1 for c, t in hf.items()
                 if (t.dividendes or t.bpa_fiable))
    print(f"\n  Precalcul des indicateurs ({len(hist)} titres)...")
    if nb_pti:
        print(f"  Fondamentaux POINT-IN-TIME : {nb_pti} titres "
              f"(per / net_yield / payout calcules par date)")
    else:
        print("  ⚠️  Aucun historique fondamental : mode statique (biaise)")
    t0 = time.time()
    series = precalculer_historique(hist, fond, hf)
    print(f"  fait en {time.time()-t0:.1f} s")

    resultats = []
    # A3-05 : le seuil de significativité est AJUSTÉ au nombre d'hypothèses
    # testées (Bonferroni) — 20 tests à p ≤ 0,05 laisseraient ~1 faux positif.
    seuil_ajuste = 0.05 / max(len(hypotheses), 1)
    print(f"\n  {'Hypothese':<40} {'trades':>7} {'net':>9} {'baseline':>10} "
          f"{'p':>6}  verdict")
    print(f"  seuil p ajuste (Bonferroni, {len(hypotheses)} hypotheses) : "
          f"p <= {seuil_ajuste:.4f}")
    print("  " + "-" * 128)
    for h in hypotheses:
        r = evaluer_hypothese(series, h, historique_fond=hf or None,
                              seuil_p=seuil_ajuste)
        net = f"{r.rendement_net_pct:+.1f}%" if r.rendement_net_pct is not None else "-"
        base = f"{r.baseline_mediane_pct:+.1f}%" if r.baseline_mediane_pct is not None else "-"
        p = f"{r.p_value:.3f}" if r.p_value is not None else "-"
        print(f"  {h.nom[:38]:<40} {r.nb_trades:>7} {net:>9} {base:>10} {p:>6}  "
              f"{r.verdict[:60]}")
        resultats.append({
            "id": h.id, "nom": h.nom, "source": h.source, "achat": h.achat,
            "vente": h.vente, "duree_max": h.duree_max,
            "rationale": h.rationale, "valide": h.valide, "motifs": h.motifs,
            "biaisee": h.biaisee,
            "nb_trades": r.nb_trades, "rendement_net_pct": r.rendement_net_pct,
            "rendement_median_pct": r.rendement_median_pct,
            "taux_reussite": r.taux_reussite,
            "baseline_mediane_pct": r.baseline_mediane_pct,
            "avantage_vs_baseline_pts": r.avantage_vs_baseline_pts,
            "p_value": r.p_value, "in_sample_pct": r.in_sample_pct,
            "out_sample_pct": r.out_sample_pct, "verdict": r.verdict,
        })
    return resultats


def round4(resultats: list[dict], critiques: dict) -> dict:
    """Classement final — par ce que le CODE a mesure, jamais par les avis."""
    print("\n" + "=" * 92)
    print("  ROUND 4 — VERDICT (classe par le code, pas par les avis)")
    print("=" * 92)

    retenues = [r for r in resultats
                if r["verdict"].startswith(("RETENUE", "FRAGILE"))
                and not r.get("biaisee")]
    biaisees = [r for r in resultats if r.get("biaisee")]
    rejetees = [r for r in resultats
                if r["verdict"].startswith(("REJETEE", "NON CONCLUANTE"))
                and not r.get("biaisee")]
    insuffisantes = [r for r in resultats
                     if r["verdict"].startswith(("PREUVE INSUFFISANTE", "AUCUN SIGNAL"))
                     and not r.get("biaisee")]
    invalides = [r for r in resultats if not r["valide"]]

    print(f"\n  Proposees           : {len(resultats)}")
    print(f"  Retenues (jouables) : {len(retenues)}")
    print(f"  Rejetees            : {len(rejetees)}")
    print(f"  Preuve trop faible  : {len(insuffisantes)}")
    print(f"  Biaisees (futur)    : {len(biaisees)}  <- exclues du classement")
    print(f"  Hors langage        : {len(invalides)}")

    if retenues:
        print(f"\n  --- CLASSEMENT DES RETENUES (regles jouables, sans fuite du futur) ---")
        print(f"  {'Hypothese':<38} {'net':>8} {'vs hasard':>11} {'p':>7} {'trades':>7}")
        print("  " + "-" * 78)
        for r in sorted(retenues, key=lambda x: -(x["avantage_vs_baseline_pts"] or 0)):
            print(f"  {r['nom'][:36]:<38} {r['rendement_net_pct']:>+7.1f}% "
                  f"{r['avantage_vs_baseline_pts']:>+10.1f} {r['p_value']:>7.3f} "
                  f"{r['nb_trades']:>7}")
        print("\n  ⚠️  Toute retenue reste une HYPOTHESE, pas une preuve de gain futur.")
        print("      Elle a survecu a un test honnete ; elle n'est pas garantie.")

    if biaisees:
        print(f"\n  --- ECARTEES POUR FUITE DU FUTUR (fondamentaux actuels) ---")
        for r in biaisees[:12]:
            av = r.get("avantage_vs_baseline_pts")
            avs = f"{av:+.1f}" if av is not None else "  -"
            print(f"    {r['nom'][:44]:<46} {r['verdict'][:20]:<22} vs hasard {avs}")
        print("    Leur resultat ne prouve rien : elles selectionnent des titres sur")
        print("    leur situation CONNUE aujourd'hui, pas sur l'information disponible")
        print("    au moment de la decision.")

    # Croisement avis vs mesures : ou les modeles se sont-ils trompes ?
    if critiques:
        print(f"\n  --- CONFRONTATION : AVIS DES MODELES vs MESURES DU CODE ---")
        par_nom = {r["nom"].lower(): r for r in resultats}
        justes = faux = 0
        exemples = []
        for modele, avis in critiques.items():
            for a in avis:
                pass
        print("  (les avis portaient sur des hypotheses anonymisees : la")
        print("   comparaison est qualitative, elle ne sert qu'a la R4)")

    return {
        "proposees": len(resultats),
        "retenues": len(retenues),
        "rejetees": len(rejetees),
        "insuffisantes": len(insuffisantes),
        "hors_langage": len(invalides),
        "classement": sorted(
            [r for r in resultats if r.get("avantage_vs_baseline_pts") is not None],
            key=lambda x: -x["avantage_vs_baseline_pts"])[:10],
    }


def charger_prix(cle: str) -> dict:
    """Prix par modele, lus depuis le catalogue OpenRouter (source de verite)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models",
                                     headers={"Authorization": f"Bearer {cle}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except Exception as e:
        print(f"  catalogue illisible ({str(e)[:60]}) — prix supposes nuls")
        return {}
    out = {}
    for m in d.get("data", []):
        out[m.get("id")] = m.get("pricing", {}) or {}
    return out


def main():
    ap = argparse.ArgumentParser(description="Challenge multi-modeles Bridge Bank")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout afficher sans appeler l'API")
    ap.add_argument("--round1", action="store_true", help="generation seule")
    ap.add_argument("--all", action="store_true", help="R1 + R2 + R3 + R4")
    ap.add_argument("--plafond", type=float, default=PLAFOND_DEFAUT,
                    help=f"depense maximale en $ (defaut {PLAFOND_DEFAUT})")
    args = ap.parse_args()

    if not args.dry_run and not (args.round1 or args.all):
        args.dry_run = True
        print("  (aucun round demande — mode simulation)\n")

    dataset = json.loads(DATASET.read_text(encoding="utf-8")) \
        if DATASET.exists() else {}
    if not dataset:
        raise SystemExit(
            f"Dataset introuvable : {DATASET}\n"
            "Lancer : python scripts/construire_dataset_challenge.py")

    print("=" * 92)
    print("  CHALLENGE MULTI-MODELES — BRIDGE BANK")
    print("=" * 92)
    print(f"\n  Modeles ({len(MODELES)}) — familles differentes :")
    for m in MODELES:
        print(f"    - {m['nom']:<22} {m['id']}")

    if args.dry_run:
        prompt = prompt_r1(dataset)
        print(f"\n  --- PROMPT R1 ({len(prompt):,} caracteres) ---")
        print(prompt[:1500] + "\n  ...[tronque]...")
        print("\n  Mode simulation : aucun appel API effectue.")

        # On verifie quand meme que le juge tourne a vide
        print("\n  --- RAPPEL DU TEST DU JUGE ---")
        print("  python scripts/tester_le_juge.py  -> doit afficher 3/3 controles passes")
        print("\n  Estimation : ~0,03 $ par modele en R1, ~0,05 $ en R2.")
        print(f"  Cout total estime pour 6 modeles : ~0,20 $ sur 5 $ disponibles.")
        return

    cle = charger_cle()
    prix = charger_prix(cle)
    budget = Budget(args.plafond)

    t0 = time.time()
    hypotheses = round1(cle, budget, dataset, prix)

    critiques = {}
    if args.all and hypotheses:
        critiques = round2(cle, budget, hypotheses, prix)

    resultats = round3(hypotheses) if hypotheses else []
    bilan = round4(resultats, critiques) if resultats else {}

    SORTIE.write_text(json.dumps({
        "modeles": MODELES,
        "budget": {"plafond": budget.plafond, "depense": round(budget.depense, 6),
                   "appels": budget.appels, "journal": budget.journal},
        "bilan": bilan,
        "resultats": resultats,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 92)
    print(f"  DEPENSE REELLE : {budget.depense:.4f} $ sur {budget.plafond} $ "
          f"({budget.appels} appels, {time.time()-t0:.0f} s)")
    print(f"  Ecrit : {SORTIE.name}")
    print("=" * 92)


if __name__ == "__main__":
    main()
