"""Analyse du releve de trades REEL — deduction de la strategie appliquee.

SOURCE : releve Bridge Bank 01/01/2025 -> 08/10/2026 (compte titres LEO).

ATTENTION AUX VIRGULES
----------------------
Dans ce releve, la virgule SEPARE LES MILLIERS pour les gros montants
(250 000.000 = 250 000 F) et sert de DECIMALE pour les petits
(9.754 = 9,754 F de droits de garde). On tranche par la coherence :
un dividende de 9 093 F pour 9 901 actions ECOBANK est credible (~0,92 F/action),
un dividende de 9,078 F ne l'est pas.

Ce script etablit les FAITS, puis en deduit la strategie reellement appliquee.
Il ne juge pas : il compare ensuite aux mesures du projet.
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
L = "-" * 78


def titre(t: str):
    print("\n" + "=" * 78)
    print(f"  {t}")
    print("=" * 78)


def main():
    titre("1. FLUX DU COMPTE")

    depots = [
        ("17/04/2026", "especes", 250_000),
        ("15/05/2026", "virement", 100_000),
        ("10/08/2026", "virement", 100_000),
        ("11/08/2026", "virement", 100_000),
        ("10/09/2026", "virement", 100_000),
        ("05/10/2026", "virement", 990),
        ("06/10/2026", "especes", 699_900),
    ]
    tot_depots = sum(m for _, _, m in depots)
    print(f"\n  DEPOTS ({len(depots)})")
    for d, src, m in depots:
        print(f"    {d}   {src:<9} {m:>10,.0f} F")
    print(f"    {L}")
    print(f"    TOTAL      {tot_depots:>10,.0f} F")

    frais = [
        ("Frais acces WEB (15 x 1 100)", 1_100 * 15),
        ("Tenue de compte (3 x 2 750)", 2_750 * 3),
        ("Droits de garde", 9.754 + 40.883 + 69.687 + 55.659 + 125.889 + 330.972),
        ("Commissions de valorisation", 24.807 + 54.159),
    ]
    tot_frais = sum(m for _, m in frais)
    print(f"\n  FRAIS ({tot_frais:,.2f} F soit {tot_frais/tot_depots*100:.2f} % des depots)")
    for n, m in frais:
        print(f"    {n:<34} {m:>10,.2f} F")

    # ------------------------------------------------------------------
    titre("2. ECOBANK (ETI) — un aller-retour court")

    q_ach = 6_500 + 3_401
    m_ach = 184_548 + 100_009
    cmp_ecob = m_ach / q_ach
    p_vente = 419_784 / q_ach
    gain = 419_784 - m_ach
    div_ecob = 9_093

    print(f"""
    achat 24/04 : 6 500 actions a {184_548/6500:>7.2f} F  = {184_548:>10,.0f} F
    achat 18/05 : 3 401 actions a {100_009/3401:>7.2f} F  = {100_009:>10,.0f} F
    {L}
    position    : {q_ach} actions  CMP {cmp_ecob:.2f} F  = {m_ach:>10,.0f} F
    DIVIDENDE 01/07 : {div_ecob:>10,.0f} F
    vente   01/07 : {q_ach} actions a {p_vente:>7.2f} F  = 419 784 F

    plus-value seule : {gain:+,.0f} F   ({(419_784/m_ach-1)*100:+.1f} %)
    dividende inclus : {gain+div_ecob:+,.0f} F   ({((419_784+div_ecob)/m_ach-1)*100:+.1f} %)
    duree de detention : 68 jours (24/04 -> 01/07)""")

    # ------------------------------------------------------------------
    titre("3. SONATEL — ventes par FRACTIONS, en gains croissants")

    q_sn = 9
    m_sn = 129_730 + 162_190
    cmp_sn = m_sn / q_sn
    print(f"\n    achat 18/08 : 9 actions   CMP {cmp_sn:.2f} F   = {m_sn:,} F")
    print(f"    {L}")
    for d, q, m in [("02/09", 3, 112_404), ("08/09", 2, 76_908), ("21/09", 1, 41_600)]:
        px = m / q
        print(f"    vente {d} : {q} action(s) a {px:>9,.0f} F  = {m:>8,} F"
              f"   ({(px/cmp_sn-1)*100:+.1f} %)")
    vendues = 3 + 2 + 1
    encaisse = 112_404 + 76_908 + 41_600
    print(f"    {L}")
    print(f"    vendu : {vendues}/9 actions pour {encaisse:,} F")
    print(f"    reste : 3 actions, cours 44 990 F = {3*44990:,} F")
    print(f"    plus-value realisee (sur les 6 vendues) : "
          f"{encaisse - cmp_sn*vendues:+,.0f} F")
    print(f"    plus-value latente  (sur les 3 gardees) : "
          f"{3*44990 - cmp_sn*3:+,.0f} F")

    # ------------------------------------------------------------------
    titre("4. PALM CI — accumulation a la BAISSE")

    achats = [(1, 8_908), (1, 8_908), (4, 35_631), (2, 17_816),
              (5, 44_539), (9, 76_658), (3, 24_336), (1, 7_859)]
    qp = sum(q for q, _ in achats)
    mp = sum(m for _, m in achats)
    cmp_palm = mp / qp
    cours_palm = 7_750
    print(f"\n    {len(achats)} achats successifs, du 08/09 au 08/10 :")
    for q, m in achats:
        print(f"        {q:>2} action(s) a {m/q:>8,.0f} F  = {m:>8,} F")
    print(f"    {L}")
    print(f"    {qp} actions pour {mp:,} F   CMP {cmp_palm:,.2f} F")
    print(f"    cours actuel {cours_palm:,} F  ->  "
          f"{cours_palm*qp - mp:+,.0f} F  ({(cours_palm/cmp_palm-1)*100:+.1f} %)")
    prix = [m / q for q, m in achats]
    print(f"    prix d'achat : {prix[0]:,.0f} -> {prix[-1]:,.0f} F "
          f"(pente {'DESCENDANTE' if prix[-1] < prix[0] else 'montante'})")
    print(f"    => il RENFORCE alors que le cours baisse (moyenne a la baisse)")

    # ------------------------------------------------------------------
    titre("5. DIVIDENDES ENCAISSES")

    inv_sgb = 7 * 38_966.57
    print(f"""
    ECOBANK 01/07 : {div_ecob:>8,} F  sur {m_ach:>9,.0f} F investis
                     rendement {div_ecob/m_ach*100:.2f} % (detention 2,5 mois)
                     par action : {div_ecob/q_ach:.2f} F  ->  {div_ecob/q_ach/cmp_ecob*100:.1f} % du CMP
    SGB     26/08 : {6_896:>8,} F  sur {inv_sgb:>9,.0f} F investis
                     par action : {6896/7:,.0f} F  ->  {6896/7/38966.57*100:.2f} % du CMP
    {L}
    TOTAL : {div_ecob + 6896:,} F  sur {tot_depots:,} F deposes = """
          f"{(div_ecob+6896)/tot_depots*100:.2f} %")

    # ------------------------------------------------------------------
    titre("6. PORTEFEUILLE AU 08/10/2026")

    pos = [
        ("PALM CI", 26, 8_640.577, 7_750, 201_500, 24.27),
        ("SGB CI", 7, 38_966.571, 39_250, 274_750, 33.09),
        ("SMB CI", 2, 17_238.000, 16_000, 32_000, 3.85),
        ("SOLIBRA CI", 5, 38_124.400, 37_400, 187_000, 22.52),
        ("SONATEL SN", 3, 32_435.556, 44_990, 134_970, 16.25),
    ]
    print(f"\n    {'Titre':<12}{'Qte':>4}{'CMP':>12}{'Cours':>10}{'+/-Value':>12}"
          f"{'Poids':>8}{'Valeur':>11}")
    print("    " + "-" * 70)
    tot_act = 0
    plus = 0
    for n, q, cmp_, c, val, p in pos:
        pv = (c - cmp_) * q
        plus += pv
        tot_act += val
        print(f"    {n:<12}{q:>4}{cmp_:>12,.0f}{c:>10,}{pv:>+12,.0f}{p:>7.1f}%{val:>11,}")
    print("    " + "-" * 70)
    liq = 699_717.522
    print(f"    Actions : {tot_act:>10,} F   (+/- value totale {plus:+,.0f} F)")
    print(f"    Liquidites : {liq:>7,.0f} F   ({liq/(tot_act+liq)*100:.1f} % du total)")
    print(f"    TOTAL : {tot_act+liq:>13,.0f} F")
    print(f"\n    Concentrations : SGB {274_750/(tot_act+liq)*100:.1f} %  "
          f"PALM {201_500/(tot_act+liq)*100:.1f} %  "
          f"SOLIBRA {187_000/(tot_act+liq)*100:.1f} %  "
          f"SONATEL {134_970/(tot_act+liq)*100:.1f} %")

    # ------------------------------------------------------------------
    titre("7. CAPITAL ENGAGE vs DEPOSE")

    achats_tot = (m_ach + m_sn + mp + 118_638 + 152_100 + 38_522 + 77_064
                  + 77_064 + 34_476)
    ventes_tot = 419_784 + 112_404 + 76_908 + 41_600
    print(f"""
    depots           : {tot_depots:>10,.0f} F
    total achete     : {achats_tot:>10,.0f} F
    total vendu      : {ventes_tot:>10,.0f} F
    frais            : {tot_frais:>10,.2f} F
    dividendes       : {div_ecob + 6896:>10,.0f} F
    {L}
    verif : depots - frais + ventes - achats + dividendes
          = {tot_depots - tot_frais + ventes_tot - achats_tot + div_ecob + 6896:,.2f} F
    solde du releve  : 699 717.52 F""")

    print("\n" + "=" * 78)
    print("  FAITS ETABLIS — voir la reponse pour l'interpretation")
    print("=" * 78)


if __name__ == "__main__":
    main()
