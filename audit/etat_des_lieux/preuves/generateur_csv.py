"""Générateur des CSV de l'état des lieux — PÉRIMÈTRE BRIDGE BANK UNIQUEMENT (mission du 13/10/2026).

Re-cadrage du 13/10 (précision LEO) : la mission sert à décider l'orchestration du système
d'alerte BRVM → périmètre = les agents/tâches/fichiers/fournisseurs UTILISÉS PAR Bridge Bank.
L'inventaire machine complet (tous projets) reste archivé dans `_archive_machine_complete/`
(ne pas le confondre avec ce périmètre). LECTURE SEULE : aucune donnée inventée ; chaque ligne
cite sa preuve (preuves/ ou commande).
"""
import csv
from pathlib import Path

D = Path(__file__).resolve().parent.parent  # audit/etat_des_lieux
H = r"C:\Users\LEO\AppData\Local\hermes"
PR = r"C:\Users\LEO\projects\Bridge Bank"


def ecrire(nom, entetes, lignes):
    with (D / nom).open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(entetes)
        w.writerows(lignes)
    print(nom, ":", len(lignes), "lignes")


# ── 1. inventaire_agents.csv — agents UTILISÉS PAR Bridge Bank ──────────────
ent = ["id", "nom", "role_pour_bridge_bank", "modele_configure", "modele_reel_state_db", "config",
       "regles_prompt", "outils_permissions", "plafonds", "cle_api", "dernier_run", "comportement_echec", "preuve"]
A = [
 ["desktop-default", "Hermes desktop (profil default)",
  "Agent interactif de LEO sur Bridge Bank : audits, corrections, analyses, ce chantier",
  "deepseek-flash / deepseek (model.default) ; ATTENTION providers.default=anthropic (ecart E4)",
  "deepseek-v4-flash/deepseek 239 sess. (dont les sessions Bridge Bank)",
  H + r"\config.yaml",
  H + r"\SOUL.md (525 l) + memories\MEMORY.md (44 697 o, 98%) + memories\USER.md + skill brvm-value-investing (978 l)",
  "Tous outils (desktop)",
  "agent.max_turns=90 ; tool_loop_guardrails warn-only (hard_stop_enabled=false, ecart E6) ; code_execution max_tool_calls=50",
  "DEEPSEEK_API_KEY (presente, doctor OK)", "2026-10-13 01:15 (session en cours)", "n/a (interactif)",
  "state.db sessions ; hermes status ; config_masque.yaml"],
 ["delegation", "Sous-agents delegues (delegate_task)",
  "Audits et taches paralleles Bridge Bank (ex. audit multi-modeles, lots de corrections)",
  "deepseek-v4-pro / deepseek ; max_iterations=250 ; reasoning medium",
  "deepseek-v4-pro/deepseek 112 sess.", "config.yaml (section delegation)",
  "Herite du parent (pas de regles propres)", "Herites du parent", "max_iterations=250 (pas de plafond $)",
  "DEEPSEEK_API_KEY", "divers (usage agrege state.db)", "remonte au parent",
  "config_masque.yaml ; state_db_sessions.txt"],
 ["vision", "Auxiliaire vision",
  "Lecture des avis PDF / captures dans les workflows Bridge Bank",
  "auxiliary.vision: model='' provider=auto", "gemini-2.5-flash/gemini (2 sess., 3 appels)",
  "config.yaml (section auxiliary.vision)", "n/a", "n/a", "n/a",
  "GEMINI_API_KEY (presente, doctor OK)", "2026-10-12 (usage constate)", "erreur remontee a l'appelant",
  "config_plafonds.txt ; state_db_usage.txt"],
 ["job-274a6f528f1a", "BridgeBank check quotidien (09h00)", "Check quotidien : alertes, soutenabilite, etats",
  "aucun (script, no_agent)", "n/a", "cron/jobs.json + script bridgebank_daily.py (421 o)",
  "Le SCRIPT est la tache ; livraison par le notifier interne du projet",
  "terminal (interpreteur = .venv projet)", "Herites du cron (pas de LLM)", "DEEPSEEK_API_KEY (via notifier)",
  "2026-10-12 17:05 (completed)", "echec = failed + last_error", "cronjob_manage list ; executions.db"],
 ["job-a4f2b2fb2a93", "BridgeBank rapport mensuel (1er 09h00)", "Rapport mensuel BRVM",
  "aucun (script, no_agent)", "n/a", "cron/jobs.json + bridgebank_report.py (401 o)", "le script est la tache",
  "terminal (.venv projet)", "-", "DEEPSEEK_API_KEY", "2026-10-01 09:01 (ok)", "echec = failed",
  "cronjob_manage list"],
 ["job-c3a1b9de4df9", "BridgeBank backup git hebdo (dim 09h00)", "Backup git du projet (dimanche)",
  "aucun (script, no_agent)", "n/a", "cron/jobs.json + bridgebank_backup.py (330 o) -> scripts/git_backup.py",
  "le script est la tache", "terminal (.venv projet) ; reseau (git push)", "-",
  "credential git du PC (egnonisse)",
  "2026-10-05 13:01 (error 'Repository not found' ; credential corrige le 12/10 — a confirmer dim 18/10)",
  "echec = failed + last_error (bruyant)", "cronjob_manage list ; executions.db"],
 ["job-e8974cd7337d", "BridgeBank veille radar 09h45", "Rapport POURQUOI ca bouge (L1) + veille (L2) + envoi",
  "Suit le modele principal (non pinne) ; monitor bridgebank_radar_monitor.py", "NON VERIFIE par job",
  "cron/jobs.json", "Prompt 2 496 car. + monitor (gating) ; etape ENVOI par notifier_envoyer.py (13/10)",
  "web, terminal, file", "Herites ; monitor = 0 LLM si sortie inchangee", "DEEPSEEK_API_KEY",
  "2026-10-13 00:24 (completed, no_change)", "echec = failed + last_error", "cronjob_manage list ; jobs.json"],
 ["job-9bf21948f66b", "BridgeBank analyse value 09h30", "Enrichir les opportunites value du jour + envoi",
  "Suit le modele principal (non pinne)", "NON VERIFIE par job", "cron/jobs.json",
  "Prompt 3 961 car. ; etape ENVOI par notifier_envoyer.py (13/10)", "web, terminal, file",
  "Herites", "DEEPSEEK_API_KEY", "2026-10-13 00:22 (completed ; repare — 5 echecs du 07 au 12/10)",
  "echec = failed + last_error visible", "cronjob_manage list ; executions.db"],
 ["job-c45e3c1bb21c", "BridgeBank veille spe 09h50", "Fiches spe (3 schemas calibres) + envoi",
  "aucun (script, no_agent)", "n/a", "cron/jobs.json + bridgebank_specveille.py (485 o)", "le script est la tache",
  "terminal (.venv projet)", "-", "DEEPSEEK_API_KEY", "2026-10-12 16:45 (ok)", "echec = failed",
  "cronjob_manage list"],
]
ecrire("inventaire_agents.csv", ent, A)

# ── 2. inventaire_fichiers_config.csv — fichiers QUI SERVENT Bridge Bank ────
ent2 = ["chemin", "role_pour_bridge_bank", "taille_octets", "date_modif", "agent_concerne", "preuve"]
F = [
 [H + r"\config.yaml", "Config Hermes : modele des agents BRVM, plafonds, delegation, MCP", "10252",
  "2026-10-12 03:39", "desktop, jobs, delegation", "scan_fichiers.txt"],
 [H + r"\SOUL.md", "Regles de travail de LEO (s'appliquent a tous les chantiers Bridge Bank) — 525 l", "7254",
  "2026-08-04 16:45", "desktop", "scan_fichiers.txt"],
 [H + r"\memories\MEMORY.md", "Memoire persistante (porte le contexte Bridge Bank) — 98% du plafond", "44697",
  "2026-10-12 01:36", "desktop, jobs", "scan_fichiers.txt"],
 [H + r"\memories\USER.md", "Profil de LEO (objectifs, seuils, historique BRVM)", "19683", "2026-10-12 22:48",
  "desktop, jobs", "scan_fichiers.txt"],
 [H + r"\.env",
  "Cles des fournisseurs des agents BRVM (DEEPSEEK, GEMINI, ANTHROPIC, GITHUB...) — contenu jamais lu", "25492",
  "2026-10-09 02:24", "desktop, jobs", "liste des noms uniquement (masquage)"],
 [H + r"\cron\jobs.json", "Les 12 taches (dont les 6 de Bridge Bank)", "33399", "2026-10-13 00:58", "jobs",
  "jobs_prompts_config_projet.txt"],
 [H + r"\gateway_state.json",
  "Gateway SANS plateforme (platforms={}) — pourquoi les jobs BRVM livrent par notifier interne", "600",
  "2026-10-13 01:13", "jobs", "skills_scripts_projets.txt"],
 [H + r"\state.db", "Sessions/usages/couts (dont les sessions Bridge Bank)", "1032519680", "2026-10-13 01:13",
  "tous", "state_db_sessions.txt"],
 [H + r"\skills\finance\brvm-value-investing\SKILL.md",
  "Skill Bridge Bank (978 lignes — risque troncature, ecart E2) + 38 references", "95285", "2026-10-12 23:40",
  "desktop", "skills_scripts_projets.txt"],
 [H + r"\scripts\bridgebank_daily.py", "Script du check quotidien", "421", "2026-08-13 01:17", "job-274a",
  "skills_scripts_projets.txt"],
 [H + r"\scripts\bridgebank_report.py", "Script du rapport mensuel", "401", "2026-08-18 11:59", "job-a4f2",
  "skills_scripts_projets.txt"],
 [H + r"\scripts\bridgebank_backup.py", "Script du backup hebdo", "330", "2026-08-22 20:52", "job-c3a1",
  "skills_scripts_projets.txt"],
 [H + r"\scripts\bridgebank_radar_monitor.py", "Monitor du radar (gating)", "786", "2026-09-01 17:30",
  "job-e897", "skills_scripts_projets.txt"],
 [H + r"\scripts\bridgebank_specveille.py", "Script de la veille spe", "485", "2026-09-18 19:00", "job-c45e",
  "skills_scripts_projets.txt"],
 [PR + r"\config.yaml", "Config du projet (watchlist, noyau, alerts ; telegram vide — .env fournit)", "615",
  "2026-10-09 06:34", "jobs BridgeBank", "jobs_prompts_config_projet.txt"],
 [PR + r"\.env", "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (notifier interne des jobs) — contenu jamais lu", "94",
  "2026-08-12 16:31", "jobs BridgeBank", "liste des noms uniquement"],
 [PR + r"\pyproject.toml", "Projet Python (markers pytest, addopts)", "856", "2026-10-12 23:08", "dev",
  "scan_fichiers.txt"],
 [PR + r"\requirements.txt", "Dependances", "66", "2026-10-12 16:59", "dev", "scan_fichiers.txt"],
 [PR + r"\README.md", "Documentation principale", "20178", "2026-09-03 10:23", "dev", "scan_fichiers.txt"],
 [PR + r"\.github\workflows\ci.yml", "CI GitHub Actions (filets du projet)", "2803", "2026-10-09 02:57", "CI",
  "scan_fichiers.txt"],
 [PR + r"\docs\INVARIANTS-METIER.md", "Invariants metier (dont B1 — les regles de vente)", "9640",
  "2026-10-13 01:07", "desktop", "scan_fichiers.txt"],
 [PR + r"\docs\IPS.md", "Politique d'investissement", "13435", "2026-10-12 01:22", "desktop",
  "scan_fichiers.txt"],
 [PR + r"\docs\RAPPORT-VALIDATION-28-ANS.md", "Rapport de validation (chiffres publies)", "16619",
  "2026-10-13 01:08", "desktop", "scan_fichiers.txt"],
 [PR + r"\docs\AUDIT-CONSTANTES.md", "Instantane des 217 constantes (filet pre-push)", "23225",
  "2026-10-13 00:36", "CI", "scan_fichiers.txt"],
]
ecrire("inventaire_fichiers_config.csv", ent2, F)

# ── 3. fournisseurs_modeles.csv — ceux UTILISÉS par Bridge Bank ─────────────
ent3 = ["fournisseur", "cle_api", "etat_doctor", "usage_pour_bridge_bank", "modele_associe", "notes", "preuve"]
P = [
 ["DeepSeek", "DEEPSEEK_API_KEY (presente)", "OK",
  "LE fournisseur des agents BRVM : sessions desktop (v4-flash 239), jobs cron, delegation (v4-pro 112)",
  "deepseek-flash (defaut) ; deepseek-v4-pro (delegation)", "provider reel des sessions Bridge Bank",
  "hermes_doctor.txt ; state_db_usage.txt"],
 ["Anthropic", "ANTHROPIC_API_KEY (presente, DUPLIQUEE dans .env)", "OK",
  "providers.default=anthropic (contradiction avec le reel DeepSeek) ; sessions ponctuelles claude-opus-5",
  "claude-opus-5 (5 sess.)", "ecart de config a trancher (E4)", "config_masque.yaml ; hermes_doctor.txt"],
 ["Google / Gemini", "GEMINI_API_KEY (presente)", "OK",
  "Vision : lecture des avis PDF / captures des workflows BRVM", "gemini-2.5-flash (3 appels)", "vision OK",
  "hermes_doctor.txt ; state_db_usage.txt"],
 ["GitHub", "GITHUB_TOKEN (presente)", "OK", "Repo bridge-bank : backup git hebdo + CI GitHub Actions", "-",
  "utilise par le job backup et la CI", "hermes_doctor.txt"],
 ["OpenRouter", "OPENROUTER_API_KEY (presente)", "OK",
  "Audits multi-modeles Bridge Bank (mistral-large-4-0, claude, gemini-3.1-pro — sessions d'audit)", "-",
  "HTTP 402 Insufficient Balance (job D2D 01/10) — plafond 5 $ atteint : bloque les futurs audits multi-modeles",
  "hermes_doctor.txt ; state_db_usage.txt ; cronjob_manage list"],
]
ecrire("fournisseurs_modeles.csv", ent3, P)

# ── 4. taches_planifiees.csv — les 6 jobs Bridge Bank ───────────────────────
ent4 = ["id", "nom", "horaire", "type", "livraison", "statut", "dernier_run", "dernier_resultat",
        "ecrit_dans_data", "preuve"]
T = [
 ["274a6f528f1a", "BridgeBank check quotidien", "0 9 * * * (09h00)", "script (no_agent)",
  "notifier interne", "scheduled", "2026-10-12 17:05", "completed", "OUI (value_new_state, etats)",
  "cronjob_manage list ; executions.db"],
 ["9bf21948f66b", "BridgeBank analyse value 09h30", "30 9 * * * (09h30)", "agent LLM",
  "notifier interne (13/10)", "scheduled", "2026-10-13 00:22", "completed (repare ; 5 echecs avant)",
  "OUI (lecture)", "cronjob_manage list ; executions.db"],
 ["e8974cd7337d", "BridgeBank veille radar 09h45", "45 9 * * * (09h45)", "agent LLM + monitor",
  "notifier interne (13/10)", "scheduled", "2026-10-13 00:24", "completed (no_change)", "OUI (etats radar)",
  "cronjob_manage list"],
 ["c45e3c1bb21c", "BridgeBank veille spe 09h50", "50 9 * * * (09h50)", "script (no_agent)",
  "notifier interne", "scheduled", "2026-10-12 16:45", "completed", "OUI (etats spe)", "cronjob_manage list"],
 ["a4f2b2fb2a93", "BridgeBank rapport mensuel", "0 9 1 * * (1er du mois)", "script (no_agent)",
  "notifier interne", "scheduled", "2026-10-01 09:01", "completed", "OUI", "cronjob_manage list"],
 ["c3a1b9de4df9", "BridgeBank backup git hebdo", "0 9 * * 0 (dimanche)", "script (no_agent)",
  "notifier interne", "scheduled", "2026-10-05 13:01", "ERROR (repo not found ; credential corrige depuis)",
  "OUI (git push)", "cronjob_manage list ; executions.db"],
]
ecrire("taches_planifiees.csv", ent4, T)

# ── 5. ecarts.csv — ceux qui concernent Bridge Bank (directs + partages) ────
ent5 = ["id", "gravite", "portee", "description", "impact_bridge_bank", "preuve"]
E = [
 ["E1", "moyenne", "Bridge Bank (direct)",
  "Backup git : 'Repository not found' (run du 05/10) ; credential corrige le 12/10 — prochain run dim 18/10.",
  "Si non corrige : aucun backup git automatique du projet",
  "cronjob_manage list (c3a1b9de4df9) ; executions.db"],
 ["E2", "moyenne", "Bridge Bank (direct)",
  "Skill brvm-value-investing : SKILL.md de 978 lignes (90 484 car.) + 38 references ; prompt systeme ~101 000 car.",
  "Regles BRVM potentiellement tronquees a l'execution (non verifiable sans rejouer une session)",
  "skills_scripts_projets.txt ; state.db system_prompts"],
 ["E3", "faible", "Bridge Bank (direct)",
  "Radar : monitor inchange depuis le 17/09 — aucun rapport radar envoye depuis 26 j (par design : l'agent ne tourne que si la sortie du monitor change).",
  "Absence de rapport = aucun code L1/L2 ; pas une panne, mais a savoir",
  "cronjob_manage list (monitor_state.last_changed_at 2026-09-17)"],
 ["E4", "moyenne", "Plateforme partagee — indirect",
  "Contradiction de config : providers.default=anthropic MAIS model.default=deepseek-flash/deepseek (reel des sessions : DeepSeek).",
  "Ambiguite sur le modele des agents BRVM en cas de changement", "config_masque.yaml ; state_db_sessions.txt"],
 ["E5", "moyenne", "Plateforme partagee — indirect",
  "ANTHROPIC_API_KEY presente DEUX FOIS dans %HERMES_HOME%\\.env.",
  "Selon l'ordre de lecture, une valeur obsolete peut gagner", "liste des noms du .env (masquage)"],
 ["E6", "moyenne", "Plateforme partagee — indirect",
  "tool_loop_guardrails : hard_stop_enabled=false — les garde-fous de boucle avertissent sans jamais arreter.",
  "Boucles longues possibles (constate : hermes verify > 10 min)", "config_masque.yaml (tool_loop_guardrails)"],
 ["E7", "moyenne", "Plateforme partagee — indirect",
  "MEMORY.md a 98% du plafond (43 347 / 44 000 car.) — la memoire qui porte tout le contexte Bridge Bank.",
  "Perte de contexte BRVM si la memoire ne peut plus s'ecrire",
  "config.yaml (memory_char_limit) ; taille du fichier"],
 ["E8", "faible", "Plateforme partagee — indirect",
  "session_reset.mode='both' n'est plus applique (plugin hermes-session-reset-policy manquant).",
  "Sessions Bridge Bank non reinitialisees (cout/context)", "hermes_doctor.txt (issue 5)"],
 ["E9", "faible", "Plateforme partagee — indirect",
  "doctor : 20 vulnerabilites npm (browser tools 3, web 8, ui-tui 6) + setup incomplet.",
  "Surface de risque des outils locaux", "hermes_doctor.txt"],
 ["E10", "info", "Bridge Bank (direct)",
  "Jobs value + radar : 5 echecs du 07 au 12/10 (blocked_config, delivery supprimee) — CORRIGES le 13/10 (notifier interne).",
  "Resolu — conserve pour tracabilite", "executions.db ; registre_desaccords.md (LOT 4)"],
]
ecrire("ecarts.csv", ent5, E)
print("OK — 5 CSV ecrits (perimetre Bridge Bank unique).")
