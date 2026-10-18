"""Rendement net des lignes du noyau : au prix payé vs au cours du jour.

Cours = relevé BSTrade du 13/10/2026 (donnée LEO) ; dps = portfolio.json ;
formule officielle du projet (src/taxation.py) : net = brut × (1 − 12 %) − 0,80 pt.
Exemple « ton objectif est d'au moins 4 % » : snapshot LIVE, lecture seule.
"""

def net(gross):
    return gross * 0.88 - 0.008

# code, quantité, prix payé (CMP), dps, cours du jour
POSITIONS = [
    ("SGBC", 7, 38966.57, 2606.0, 39000.0),
    ("SLBC", 5, 38124.00, 2127.0, 37600.0),
    ("SNTS", 3, 32436.00, 1977.0, 44900.0),
    ("PALC", 26, 8641.00, 501.596, 7785.0),
]

print(f"{'Titre':6} {'net au prix payé':>16} {'net au cours':>13} {'div. net/an':>12} "
      f"{'valeur ligne':>13} {'cours sortie 2%':>15} {'cours entrée 4%':>15}")
tot_cmp = tot_cours = div_tot = 0.0
pond_cmp = pond_cours = 0.0
for code, q, cmp_, dps, cours in POSITIONS:
    n_cmp = net(dps / cmp_) * 100
    n_cours = net(dps / cours) * 100
    div = q * dps * 0.88
    val_cmp = q * cmp_
    val_cours = q * cours
    sortie2 = dps * 0.88 / (0.02 + 0.008)
    entree4 = dps * 0.88 / (0.04 + 0.008)
    tot_cmp += val_cmp
    tot_cours += val_cours
    div_tot += div
    pond_cmp += val_cmp * n_cmp
    pond_cours += val_cours * n_cours
    print(f"{code:6} {n_cmp:15.2f}% {n_cours:12.2f}% {div:12,.0f} {val_cours:13,.0f} "
          f"{sortie2:15,.0f} {entree4:15,.0f}")

print()
print(f"Portefeuille noyau (4 lignes) :")
print(f"  au PRIX PAYÉ  : {pond_cmp / tot_cmp:.2f} % net  (capital {tot_cmp:,.0f} F)")
print(f"  au COURS DU JOUR : {pond_cours / tot_cours:.2f} % net  (valeur {tot_cours:,.0f} F)")
print(f"  dividendes nets annuels : {div_tot:,.0f} F")
print()
# Le cas SNTS en clair
dps, cmp_, cours = 1977.0, 32436.0, 44900.0
print(f"SNTS : payé {cmp_:,.0f} → {net(dps / cmp_) * 100:.2f} % net ; "
      f"cours du jour {cours:,.0f} → {net(dps / cours) * 100:.2f} % net")
print(f"  le cours où le loyer de SNTS tombe à 2 % : "
      f"{dps * 0.88 / 0.028:,.0f} F (+{(dps * 0.88 / 0.028 / cours - 1) * 100:.0f} % "
      f"depuis {cours:,.0f})")
print(f"  pour que SNTS redevienne un achat ≥ 4 % net : {dps * 0.88 / 0.048:,.0f} F")
