"""Matemática das lotarias oficiais em Portugal (Jogos Santa Casa): probabilidades exatas,
valor esperado do jackpot com divisão entre vencedores e imposto do selo (20% acima de 5.000 €)."""
from math import comb, exp

def euromilhoes():
    total = comb(50, 5) * comb(12, 2)
    linhas = []
    for n in range(5, -1, -1):
        for e in range(2, -1, -1):
            casos = comb(5, n) * comb(45, 5 - n) * comb(2, e) * comb(10, 2 - e)
            premiado = (n >= 2) or (n == 1 and e == 2)
            if premiado:
                linhas.append((f"{n} números + {e} estrelas", total / casos))
    return total, linhas

def eurodreams():
    total = comb(40, 6) * 5
    linhas = []
    for n in range(6, 1, -1):
        for d in (1, 0):
            if n < 6 and d == 1:
                continue
            casos = comb(6, n) * comb(34, 6 - n) * ((1 if d else 4) if n == 6 else 5)   # abaixo de 6, o sonho não conta
            linhas.append((f"{n} números" + (" + sonho" if d else ""), total / casos))
    return total, linhas

def totoloto():
    total = comb(49, 5) * 13
    linhas = []
    for n in range(5, 1, -1):
        for s in (1, 0):
            casos = comb(5, n) * comb(44, 5 - n) * (1 if s else 12)
            linhas.append((f"{n} números" + (" + nº da sorte" if s else ""), total / casos))
    # só o Número da Sorte (com 0 ou 1 número): reembolso da aposta
    casos = (comb(44, 5) + comb(5, 1) * comb(44, 4)) * 1
    linhas.append(("só o nº da sorte (reembolso)", total / casos))
    return total, linhas

def imposto(p):
    return p - 0.20 * max(0.0, p - 5000)

def ev_jackpot(J, prob_inv, apostas_outras):
    """Valor esperado da parte do jackpot para UMA aposta: J líquido x P(acertar) x fator de divisão (Poisson)."""
    lam = apostas_outras / prob_inv
    divisao = (1 - exp(-lam)) / lam if lam > 0 else 1.0
    return imposto(J) / prob_inv * divisao, divisao

if __name__ == "__main__":
    for nome, f in (("EUROMILHÕES (5 de 50 + 2 de 12)", euromilhoes), ("EURODREAMS (6 de 40 + 1 de 5)", eurodreams), ("TOTOLOTO (5 de 49 + 1 de 13)", totoloto)):
        total, L = f()
        print(f"\n== {nome}: {total:,} combinações ==".replace(",", "."))
        for d, inv in L:
            print(f"   {d:<24} 1 em {inv:>14,.0f}".replace(",", "."))
        print(f"   qualquer prémio:          1 em {1 / sum(1 / x for _, x in L):.1f}")
    print("\n== Euromilhões: quanto vale o JACKPOT por aposta de 2,50 € (líquido de imposto, com divisão) ==")
    for J, vendas in ((17e6, 30e6), (50e6, 40e6), (100e6, 60e6), (130e6, 80e6), (200e6, 120e6), (250e6, 160e6)):
        ev, div = ev_jackpot(J, comb(50, 5) * comb(12, 2), vendas)
        print(f"   jackpot {J/1e6:>4.0f} M€, ~{vendas/1e6:.0f} M de apostas no sorteio: vale {ev:.2f} € por aposta (divisão esperada x{div:.2f})")
    print("\n== EuroDreams: prémio principal 20.000 €/mês x 30 anos ==")
    nominal = 20000 * 360
    for taxa in (0.0, 0.02, 0.03, 0.05):
        r = (1 + taxa) ** (1 / 12) - 1
        vp = nominal if taxa == 0 else 20000 * (1 - (1 + r) ** -360) / r
        print(f"   valor presente a {taxa:.0%}/ano: {vp/1e6:.2f} M€ -> {vp / 19191900:.3f} € por aposta de 2,50 € (antes de imposto)")
    print("\n== Tempo médio até ao 1º prémio, jogando 2 apostas por semana ==")
    for nome, inv, preco in (("Euromilhões", 139838160, 2.50), ("EuroDreams", 19191900, 2.50), ("Totoloto", 24789492, 1.00)):
        anos = inv / 2 / 52
        print(f"   {nome:<12}: {anos:,.0f} anos | gasto até lá: {inv * preco / 1e6:,.1f} M€".replace(",", "."))
