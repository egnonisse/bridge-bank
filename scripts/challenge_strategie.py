"""PHASE 4 (R1 et R2) — Challenge multi-modeles sur les VARIANTES de strategie.

PRINCIPE (inchange depuis le debut du projet)
---------------------------------------------
Les modeles GENERENT, le code JUGE, l'assistant ARBITRE.

CE QUE LES MODELES VOIENT
-------------------------
  - les ACTES REELS de LEO (son releve : achats par tranches, renforcements a
    la baisse, ventes par paliers) ;
  - les statistiques descriptives du marche ;
  - la LISTE des parametres disponibles et leurs bornes.

CE QU'ILS NE VOIENT PAS — REGLE ANTI-TRICHE
-------------------------------------------
  - AUCUN resultat de backtest. Ni les rendements de la premiere mesure, ni le
    fait que le renforcement a apporte +25,8 pts et les paliers -43,1 pts.
  S'ils connaissaient les reponses, ils ne produiraient pas des hypotheses mais
  des recopies, et le test ne vaudrait rien.

CE QU'ON LEUR DEMANDE
---------------------
5 variantes PARAMETREES de la methode, avec justification chiffree. Pas des
regles de trading : des REGLAGES de sa methode existante.

Sortie : data/challenge_strategie_variantes.json
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
import urllib3
from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

urllib3.disable_warnings()

RACINE = Path(__file__).resolve().parent.parent
SORTIE = chemin_data("challenge_strategie_variantes.json")
BUDGET_MAX = 12.0          # plafond de depense sur ce chantier

MODELES = [
    "anthropic/claude-haiku-5.5",
    "openai/gpt-5.6-luna-pro",
    "google/gemini-2.5-flash",
    "meta-llama/llama-3.3-70b-instruct",
    "mistralai/mistral-large-4-0",
    "deepseek/deepseek-chat",
]


def _cle() -> str:
    env = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / "hermes" / ".env"
    for ligne in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ligne.strip().startswith("OPENROUTER_API_KEY="):
            return ligne.strip().split("=", 1)[1].strip().strip('"')
    return ""


PROMPT_R1 = """Tu es analyste quantitatif. On te decrit la METHODE REELLE d'un investisseur,
puis on te demande de proposer des REGLAGES ALTERNATIFS.

=== SA METHODE (deduite de ses ordres reels, bourse de Cote d'Ivoire, 6 mois) ===

1. ENTREE PROGRESSIVE — il n'achete jamais tout d'un coup. Exemple mesure sur
   PALM CI : 8 achats etales sur 30 jours (1, 1, 4, 2, 5, 9, 3, 1 action).
   Son montant par decision est d'environ 100 000 F CFA.

2. RENFORCEMENT SUR FAIBLESSE — il ajoute quand le cours baisse. Sur PALM CI
   ses prix d'achat successifs ont ete 8 908 -> 8 518 -> 8 112 -> 7 859 F CFA,
   soit des paliers de 4 a 5 % a la baisse.

3. VENTES PAR PALIERS — il vend par fractions a des gains croissants. Sur
   SONATEL : 3 actions vendues a +15,5 %, puis 2 a +18,6 %, puis 1 a +28,3 %.
   Il conserve un tiers.

4. REBALANCEMENT — il vend un titre gagnant pour financer un titre en retard
   (ventes SONATEL suivies d'achats PALM, SMB, SOLIBRA).

5. RESERVE DE CASH — il garde une poche de liquidites (observe : jusqu'a 46 %
   apres un depot, retombe ensuite).

=== CONTEXTE DE MARCHE ===
48 valeurs cotees. Indice du marche : 84 (2017) -> 35 (2020, creux) -> 145 (2026).
Frais de courtage reels : 1,4 % par sens, avec un MINIMUM de 1 000 F CFA par
ordre. Ce minimum rend les petites tranches couteuses en proportion.
Drawdown median d'un titre : -55,7 %. Pire : -82,3 %.

=== PARAMETRES QUE TU PEUX REGLER ===
  nb_tranches              entier 1 a 10    (nombre de tranches d'achat)
  espacement_jours         entier 0 a 60    (delai entre deux tranches)
  renforcement_actif       booleen
  seuil_renforcement       fraction 0.01 a 0.15  (baisse declenchant un renfort)
  paliers_actifs           booleen
  seuils_vente             liste de [seuil, fraction]  ex. [[0.15, 0.33], [0.30, 0.33]]
  cash_cible               fraction 0.0 a 0.40  (part jamais investie)

=== TA MISSION ===
Propose 5 variantes PARAMETREES de sa methode. Chaque variante doit etre un
REGLAGE DIFFERENT, justifie par un raisonnement chiffre (cout du minimum de
frais, asymetrie des rendements, protection du capital, discipline...).

Contraintes :
  - au moins une variante qui SUPPRIME une de ses habitudes (pour mesurer son
    cout) ;
  - au moins une qui l'INTENSIFIE ;
  - au moins une qui vise la SIMPLICITE (moins d'ordres, moins de frais) ;
  - justifie chaque valeur numerique. Une valeur sans raison est sans valeur.

Reponds UNIQUEMENT par un JSON valide, sans texte autour :
[
  {
    "nom": "Nom court de la variante",
    "parametres": {
      "nb_tranches": 3,
      "espacement_jours": 20,
      "renforcement_actif": true,
      "seuil_renforcement": 0.06,
      "paliers_actifs": false,
      "seuils_vente": [],
      "cash_cible": 0.10
    },
    "rationale": "Pourquoi ces valeurs, avec un chiffre a l'appui."
  }
]
"""

PROMPT_R2 = """Voici des variantes de methode d'investissement proposees par plusieurs
analystes, presentees de facon ANONYME. Les modeles ne se voient pas entre eux.

__VARIANTES__

=== TA MISSION ===
Critique ces variantes avec rigueur. Pour chacune, dis :
  - si elle est PLAUSIBLE ou IRREALISTE, et pourquoi (chiffre a l'appui) ;
  - le PIEGE principal qu'elle comporte ;
  - si tu la GARDERAIS ou l'ECARTERAIS pour un test sur donnees reelles.

Sois direct. Une critique polie ne sert a rien. Reponds en JSON :
[
  {"id": "V1", "garde": true, "critique": "..."},
  ...
]
"""


def _appeler(modele: str, prompt: str, cle: str, max_tokens: int = 3000):
    """Appel OpenRouter. Retourne (texte, cout_estime_usd)."""
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {cle}",
                 "Content-Type": "application/json"},
        json={"model": modele,
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": max_tokens, "temperature": 0.8},
        timeout=180, verify=False)
    if r.status_code != 200:
        return None, 0.0, f"HTTP {r.status_code}: {r.text[:150]}"
    d = r.json()
    txt = d["choices"][0]["message"]["content"]
    usage = d.get("usage", {})
    cout = (usage.get("prompt_tokens", 0) * 0.5
            + usage.get("completion_tokens", 0) * 2.0) / 1_000_000
    return txt, cout, None


def _extraire_json(txt: str):
    """Recupere le premier tableau JSON d'une reponse.

    Les modeles entourent souvent leur JSON de texte ou de balises markdown
    (```json ... ```), ce qui faisait echouer le parsing brut et perdait des
    variantes entieres. On tente : bloc markdown explicite, tableau brut, puis
    objet unique converti en liste.
    """
    if not txt:
        return None
    import re as _re
    # 1. Bloc markdown ```json ... ```
    m = _re.search(r"```(?:json)?\s*(\[.*?\])\s*```", txt, _re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 2. Tableau brut
    i, j = txt.find("["), txt.rfind("]")
    if i >= 0 and j > i:
        try:
            return json.loads(txt[i:j + 1])
        except Exception:
            pass
        # 2b. Tableau tronque : on tente de fermer a la derniere accolade
        frag = txt[i:j + 1]
        k = frag.rfind("}")
        if k > 0:
            for suffixe in ("]", "}]"):
                try:
                    return json.loads(frag[:k + 1] + suffixe)
                except Exception:
                    continue
    # 3. Objet unique -> liste
    i, j = txt.find("{"), txt.rfind("}")
    if i >= 0 and j > i:
        try:
            obj = json.loads(txt[i:j + 1])
            return obj if isinstance(obj, list) else [obj]
        except Exception:
            pass
    return None


def main():
    cle = _cle()
    if not cle:
        raise SystemExit("OPENROUTER_API_KEY absente")

    print("=" * 96)
    print("  PHASE 4 — R1/R2 : VARIANTES PROPOSEES PAR LES MODELES")
    print("=" * 96)
    print(f"\n  {len(MODELES)} modeles · plafond {BUDGET_MAX} $")
    print("  REGLE ANTI-TRICHE : aucun resultat de backtest n'est transmis.\n")

    depense = 0.0
    variantes = []
    for i, modele in enumerate(MODELES, 1):
        if depense > BUDGET_MAX:
            print(f"  [{i}] plafond atteint, arret")
            break
        txt, cout, err = _appeler(modele, PROMPT_R1, cle)
        depense += cout
        if err:
            print(f"  [{i}] {modele:<42} ECHEC : {err}")
            continue
        data = _extraire_json(txt)
        if not data:
            print(f"  [{i}] {modele:<42} reponse non parsable")
            continue
        n = 0
        for v in data:
            if isinstance(v, dict) and "parametres" in v:
                v["source"] = modele
                v["id"] = f"{modele.split('/')[-1][:12]}-V{n+1}"
                variantes.append(v)
                n += 1
        print(f"  [{i}] {modele:<42} {n} variante(s)   ({cout:.4f} $)")
        time.sleep(1)

    print(f"\n  {len(variantes)} variantes collectees   cout R1 : {depense:.4f} $")

    # Sauvegarde IMMEDIATE : si R2 echoue, les variantes ne sont pas perdues.
    # (Premier essai : 20 variantes collectees puis perdues sur un crash de
    #  mise en forme — 0,045 $ repartis en fumee.)
    SORTIE.write_text(json.dumps(
        {"variantes": variantes, "critiques": {}, "cout_usd": depense},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Sauvegarde immediate : {SORTIE.name}")

    # ------------------------------------------------------------------
    #  R2 — critique croisee ANONYMISE
    # ------------------------------------------------------------------
    if variantes:
        bloc = "\n\n".join(
            f"VARIANTE V{k+1} (anonyme)\n"
            f"  parametres : {json.dumps(v.get('parametres', {}), ensure_ascii=False)}\n"
            f"  justification : {str(v.get('rationale', ''))[:500]}"
            for k, v in enumerate(variantes[:12]))
        critiques = {}
        for i, modele in enumerate(MODELES[:4], 1):
            if depense > BUDGET_MAX:
                break
            txt, cout, err = _appeler(modele,
                                      PROMPT_R2.replace("__VARIANTES__", bloc),
                                      cle, max_tokens=2500)
            depense += cout
            if err:
                print(f"  R2 [{i}] {modele:<42} ECHEC")
                continue
            data = _extraire_json(txt)
            if data:
                critiques[modele] = data
                garde = sum(1 for c in data if c.get("garde"))
                print(f"  R2 [{i}] {modele:<42} {garde}/{len(data)} gardees"
                      f"   ({cout:.4f} $)")

        SORTIE.write_text(json.dumps(
            {"variantes": variantes, "critiques": critiques, "cout_usd": depense},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  Ecrit : {SORTIE.name}")
        print(f"  COUT TOTAL : {depense:.4f} $")

    print("\n" + "=" * 96)
    print("  ETAPE SUIVANTE (R3) : le CODE juge ces variantes sur l'historique.")
    print("  Les modeles n'auront jamais acces a ces resultats.")
    print("=" * 96)


if __name__ == "__main__":
    main()
