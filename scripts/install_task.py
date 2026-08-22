"""Crée la tâche planifiée Windows « BridgeBank-Daily » (check quotidien à 09:00).

Exécution : python scripts/install_task.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "daily_check.py"

cmd = [
    "schtasks", "/Create", "/TN", "BridgeBank-Daily",
    "/TR", f'"{sys.executable}" "{SCRIPT}"',
    "/SC", "DAILY", "/ST", "09:00", "/F",
]

r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("exit:", r.returncode)
print(r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr)
