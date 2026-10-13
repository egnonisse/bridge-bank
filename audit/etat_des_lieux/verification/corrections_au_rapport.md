# Corrections à apporter au rapport `etat_des_lieux.md` (et ses CSV)

Conséquence des vérifications V1-V8. **Le rapport n'a PAS été modifié** (mission lecture seule) — voici les reformulations proposées.

## 1. Clé Anthropic — erreur factuelle (V2)

**Texte actuel** (section a, « Modèles et fournisseurs des agents BRVM ») :
> « … clés présentes et valides : DeepSeek, Gemini, GitHub, OpenRouter (⚠️ plafond 5 $ atteint), Anthropic (⚠️ dupliquée dans `.env`). »

**Problème** : la clé Anthropic est **INVALIDE** (`✗ Anthropic API (invalid API key)`) — le doctor de l'inventaire le disait déjà (ligne 94), non relevé. Les deux occurrences du `.env` ont des **valeurs différentes** (longueurs 108/108).

**Texte proposé** :
> « … clés présentes : DeepSeek, Gemini, GitHub, OpenRouter — **Anthropic : clé INVALIDE (doctor) et dupliquée dans `.env` (deux valeurs différentes)**. Aucun fournisseur de repli n'est configuré (`fallback list` vide) : si le modèle principal échoue, pas de repli automatique. »

**Fichiers CSV concernés** : `fournisseurs_modeles.csv` — ligne Anthropic : `etat_doctor` `OK` → **`INVALIDE (invalid API key)`** ; `ecarts.csv` — descriptif E4 à compléter (« clé associée invalide »).

## 2. OpenRouter — préciser l'écart de sources (V8)

**Texte actuel** : « OpenRouter (⚠️ plafond 5 $ atteint) ».
**Proposé** : « OpenRouter : **estimation locale 4,05 $ ; annonce du 09/10 : 4,82 $ — écart non tranché ; solde réel non consulté** (l'API de crédits n'a pas été interrogée). »

## 3. Écart E2 (skill 978 lignes) — re-cadrer le risque (V1)

**Texte actuel** (ecarts.csv E2) : « Regles BRVM potentiellement tronquees a l'execution. »
**Proposé** : « Le skill n'est **PAS intégré au prompt système** (index = 87 B) : il est **chargé à la demande** (`skill_view`) — le risque de troncature du PROMPT est écarté ; le risque résiduel porte sur la **lecture intégrale au moment de l'appel** (non mesurable sans rejouer une session). Contexte : prompt système ≈ 99,6 KB (mémoire 44,9 KB + profil 19,9 KB + outils 68,0 KB). »

## 4. Écart E1 (backup) — ajouter l'angle mort de notification (V5)

**Texte actuel** : « Si non corrige : aucun backup git automatique du projet. »
**Proposé** : ajouter : « **et l'échec du 05/10 n'a été signalé par AUCUN canal actif** : le job est en `deliver: origin` (→ `delivery_outcome: not_configured`, livraison impossible sans plateforme) et son message d'échec est resté dans la sortie du job — aucune entrée correspondante dans `alertes_journal.jsonl`. »

## 5. Ajouts recommandés (constats V1-V8 pas encore dans le rapport)

- **MoA** : `moa.enabled: true` avec agrégateur `claude-opus-5 / anthropic` → **clé invalide** ; aucun job BRVM ne l'appelle ; jamais utilisé dans les sessions enregistrées. À signaler comme piège (si activé en session : dégradation « loud »).
- **Coût** : sessions cron des 6 derniers jours = **0,0185 $ au total** (< 1 centime/jour) ; les jobs BRVM scriptés = 0 $ LLM.
- **Mémoire** : Bridge Bank = **3 entrées / 1 528 car. ≈ 4 %** de MEMORY.md (le reste = e-commerce/pharma/machine).
- **Prompt système** : 99,6 KB dont mémoire 44,9 KB — la ligne « plafond mémoire 98 % » reste valide et gagnerait à préciser sa part réelle (≈ 45 % du prompt).
