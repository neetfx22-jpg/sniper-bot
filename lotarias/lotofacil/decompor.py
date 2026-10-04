"""Decompõe o retorno de 2026 das combinações do usuário: quanto vem dos 2 jackpots (sorte)
e quanto vem do excesso de 14 pontos. Testa se o excesso de 14 é significativo ou aglomerado."""
import csv
import numpy as np
import base as B

jogos = []
with open("top_combinacoes.csv") as f:
    for row in csv.DictReader(f):
        jogos.append(sum(1 << (int(row[f"D{i}"]) - 1) for i in range(1, 16)))
jogos = np.array(jogos, dtype=np.int64)
idx = B.indices("2026-01-01")
N = len(jogos)

# por sorteio: contagem de cada faixa e prémio
p14 = np.zeros(len(idx)); p15 = np.zeros(len(idx)); prem = np.zeros(len(idx))
for j, i in enumerate(idx):
    ac = B.popcount(jogos & B.D[i])
    p14[j] = (ac == 14).sum(); p15[j] = (ac == 15).sum(); prem[j] = B.PR[i, ac].sum()
custo = N * B.PRECO[idx].mean() * len(idx)

print(f"2026: {len(idx)} sorteios, {N} jogos fixos, custo total R$ {custo:,.0f}".replace(",", "."))
print(f"retorno total: {prem.sum()/custo:.3f}")
# remove o prémio dos 15 pontos
prem15 = sum(B.PR[i, 15] * p15[j] for j, i in enumerate(idx))
print(f"   só os 2 jackpots (15 pts) valeram R$ {prem15:,.0f} = {prem15/custo:.3f} do retorno".replace(",", "."))
print(f"   retorno SEM os jackpots: {(prem.sum()-prem15)/custo:.3f}  (o teto teórico do jogo é 0.417)")

# o excesso de 14 pontos é real ou veio de poucos sorteios?
esp14 = N / 21792
print(f"\n14 pontos: {int(p14.sum())} no total | esperado por acaso {esp14*len(idx):.0f} | por sorteio: média {p14.mean():.2f} vs esperado {esp14:.2f}")
print(f"   sorteios que concentraram os 14: top 5 =", sorted(p14.astype(int))[-5:])
z = (p14.sum() - esp14*len(idx)) / np.sqrt(esp14*len(idx))
print(f"   significância do excesso de 14 pts: {z:+.1f} sigma")

# TESTE JUSTO: um 15 pontos faz LUCRO ou só reduz o prejuízo? E o retorno é estável mês a mês?
import pandas as pd
m = pd.DataFrame({"data": B.datas[idx], "prem": prem, "custo": N*B.PRECO[idx]}).set_index("data").resample("ME").sum()
m["retorno"] = m.prem/m.custo
print("\nretorno mês a mês em 2026 (jogos fixos do usuário):")
print("  " + " | ".join(f"{d:%b}:{v:.2f}" for d, v in m.retorno.items()))
print(f"meses com retorno >= 1,00 (lucro): {(m.retorno>=1).sum()} de {len(m)} | lucro total no ano: R$ {m.prem.sum()-m.custo.sum():,.0f}".replace(",", "."))
