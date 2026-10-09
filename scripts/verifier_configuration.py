"""Vérifie la CONFIGURATION du projet — ce qui doit être vrai avant que le système tourne.

POURQUOI CE CONTRÔLE EXISTE
---------------------------
Les tests vérifient le comportement, `verifier_chemins.py` les chemins calculés à la main,
`auditer_constantes.py` les valeurs effectives. Reste ce qui est lu AU DÉMARRAGE et que
aucun test ne couvre directement : le fichier des seuils calibrés et `config.yaml`. Deux
dangers concrets, tous les deux déjà observés ailleurs dans le projet :

  - un `data/profit_thresholds.json` non conforme fait retomber le système sur la table de
    départ, tout en `informatif` — plus aucune vente proposée, et rien ne le dit ;
  - un secret recopié dans un fichier SUIVI par git part chez l'hébergeur, et c'est
    définitif.

CE QUI EST VÉRIFIÉ (aucun accès réseau)
---------------------------------------
  1. seuils      : schéma conforme (`src/schema_seuils.py`) + au moins une entrée ;
  2. instantané  : `data/constantes_snapshot.json` présent et non vide (le filet 2 en vit) ;
  3. config.yaml : lisible, `noyau.codes` non vide ;
  4. secrets     : aucun `.env` versionné, `telegram.bot_token` vide.

    python scripts/verifier_configuration.py     # code de sortie 1 si un contrôle échoue
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.calibration import seuils_vente as sv            # noqa: E402
from src.calibration.schema_seuils import valider         # noqa: E402

CONFIG = RACINE / "config.yaml"
SNAPSHOT = RACINE / "data" / "constantes_snapshot.json"
FICHIERS_SECRETS = (".env", ".env.local", ".env.production")
# Clés qui ne doivent JAMAIS être renseignées dans un fichier suivi par git.
CLES_SECRETES = (("telegram", "bot_token"), ("telegram", "token"))


def _controle_chemins_suivis() -> list[str]:
    """Un fichier de secrets ne doit pas être versionné."""
    try:
        suivi = subprocess.run(["git", "ls-files"], cwd=str(RACINE), capture_output=True,
                               text=True, timeout=30, check=True).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"git indisponible pour lister les fichiers suivis ({exc}) — contrôle ignoré"]
    return [f"{nom} est VERSIONNÉ : un secret poussé sur un dépôt distant est définitif"
            for nom in suivi if Path(nom).name in FICHIERS_SECRETS]


def _controle_seuils() -> list[str]:
    try:
        donnees = sv.charger()
    except sv.SeuilsInvalides as exc:
        return [f"seuils non conformes — {exc}"]
    if not donnees:
        return ["aucun seuil calibré : le système retomberait sur la table de départ"]
    erreurs, avertissements = valider(donnees)
    problemes = [f"seuils : {e}" for e in erreurs]
    problemes += [f"seuils (avertissement) : {a}" for a in avertissements]
    return problemes


def _controle_snapshot() -> list[str]:
    if not SNAPSHOT.exists():
        return [f"{SNAPSHOT.name} absent : le filet des constantes ne peut rien comparer"]
    try:
        donnees = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{SNAPSHOT.name} illisible ({exc})"]
    if not donnees:
        return [f"{SNAPSHOT.name} vide : la comparaison ne vérifierait rien"]
    return []


def _controle_config() -> list[str]:
    if not CONFIG.exists():
        return ["config.yaml absent"]
    try:
        import yaml
    except ImportError:
        return ["pyyaml manquant — installer requirements.txt"]
    try:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"config.yaml illisible ({exc})"]
    if not isinstance(config, dict):
        return ["config.yaml devrait contenir un objet clé/valeur"]

    problemes = []
    codes = (config.get("noyau") or {}).get("codes") or []
    if not codes:
        problemes.append("config.yaml : « noyau.codes » est vide — aucune règle de noyau à appliquer")
    for section, cle in CLES_SECRETES:
        valeur = (config.get(section) or {}).get(cle)
        if valeur:
            problemes.append(f"config.yaml : « {section}.{cle} » est RENSEIGNÉ et le fichier est "
                             f"versionné — déplacer la valeur dans .env (non suivi par git)")
    return problemes


def main() -> int:
    print("=" * 78)
    print("  CONFIGURATION DU PROJET")
    print("=" * 78)
    print()

    controles = (
        ("seuils calibrés", _controle_seuils()),
        ("instantané des constantes", _controle_snapshot()),
        ("config.yaml", _controle_config()),
        ("secrets", _controle_chemins_suivis()),
    )
    problemes: list[str] = []
    for nom, trouves in controles:
        etat = "ok" if not trouves else f"{len(trouves)} probleme(s)"
        print(f"  {nom:28s} : {etat}")
        problemes += trouves

    print()
    if not problemes:
        print("  Configuration conforme.")
        return 0
    print(f"  {len(problemes)} PROBLEME(S) :")
    for p in problemes:
        print(f"    - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
