"""Cobrir TODAS as 139.838.160 combinações do Euromilhões paga-se? (teto do jackpot = 250 M€)"""
from math import comb

TOTAL = comb(50, 5) * comb(12, 2)
PRECO = 2.50
CUSTO = TOTAL * PRECO
print(f"combinações: {TOTAL:,} | cobrir tudo = {TOTAL:,} x 2,50 € = {CUSTO/1e6:,.1f} M€".replace(",", "."))
print(f"teto máximo do jackpot: 250 M€  ->  já é MENOS de metade do custo.\n")

# quantos bilhetes premiados eu teria em cada sorteio, tendo TODAS as combinações
# categoria (n números de 5, e estrelas de 2): nº de combos = C(5,n)C(45,5-n) x C(2,e)C(10,2-e)
premios_tipicos = {  # valor médio europeu aproximado por categoria (€), categorias que pagam
    (5,2): 0, (5,1): 300000, (5,0): 25000, (4,2): 2500, (4,1): 150, (4,0): 60,
    (3,2): 80, (3,1): 12, (3,0): 10, (2,2): 20, (2,1): 7, (1,2): 8, (2,0): 0,
}
def qtd(n, e):
    return comb(5,n)*comb(45,5-n) * comb(2,e)*comb(10,2-e)

print("se eu cobrir tudo, ganho em cada sorteio (fora o jackpot):")
total_menores = 0
for (n,e), v in premios_tipicos.items():
    if (n,e)==(5,2) or v==0: continue
    q = qtd(n,e); g = q*v; total_menores += g
    print(f"   {n} nºs + {e} estrelas: {q:>7,} bilhetes x ~{v:>7,}€ = {g/1e6:>6.1f} M€".replace(",", "."))
print(f"   soma das categorias menores: ~{total_menores/1e6:.0f} M€ (valores médios; na prática o rateio divide com outros)\n")

for J in (17, 100, 250):
    imposto = J*1e6 - 0.20*max(0, J*1e6 - 5000)  # 20% acima de 5.000€
    # cenário otimista: sou o ÚNICO a acertar o jackpot (raro num sorteio cheio)
    total_otim = imposto + total_menores
    print(f"jackpot {J:>3} M€: mesmo sendo o ÚNICO vencedor -> ganho ~{total_otim/1e6:.0f} M€ | gastei {CUSTO/1e6:.0f} M€ | resultado {(total_otim-CUSTO)/1e6:+.0f} M€")
print("\nE há o problema real: num sorteio de jackpot alto vendem-se 100+ milhões de apostas,")
print("então o jackpot quase sempre é DIVIDIDO. Com 2-3 vencedores, recebe metade ou um terço.")
print("Além disso, registar 140 milhões de apostas antes do sorteio é fisicamente impossível.")
