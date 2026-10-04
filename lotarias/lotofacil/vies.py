"""O viés de frequência das dezenas é real e EXPLORÁVEL? Teste fora da amostra:
montar jogos com as dezenas mais frequentes no treino e medir o retorno no teste."""
import itertools
import numpy as np
import base as B

n = len(B.D)
saiu = np.array([[(int(B.D[i]) >> (d-1)) & 1 for d in range(1, 26)] for i in range(n)])

# 1) significância: cada dezena vs. o esperado
esp = n * 15 / 25
std = (n * 0.6 * 0.4) ** 0.5
tot = saiu.sum(0)
z = (tot - esp) / std
print(f"esperado por dezena: {esp:.0f} | desvio-padrão (se independente): {std:.0f}")
print("dezenas fora de ±2,5 sigma:", ", ".join(f"{d+1}({z[d]:+.1f}σ)" for d in range(25) if abs(z[d]) > 2.5) or "nenhuma")
print("(o sorteio tira sempre 15 de 25, então há dependência; isto é indicativo, não exato)\n")

# 2) persistência real: treino = metade antiga, teste = metade recente
meio = n // 2
hot = np.argsort(-saiu[:meio].sum(0))     # dezenas mais frequentes na 1ª metade
freq2 = saiu[meio:].mean(0)
print("As 8 'mais quentes' da 1ª metade saíram, na 2ª metade, em média",
      f"{freq2[hot[:8]].mean():.1%} dos sorteios; as 8 'mais frias', {freq2[hot[-8:]].mean():.1%}. "
      f"(diferença de {(freq2[hot[:8]].mean()-freq2[hot[-8:]].mean())*100:.1f} pontos)\n")

# 3) O TESTE QUE IMPORTA: isto dá lucro? Jogos fixos feitos das dezenas quentes vs. aleatórios, fora da amostra
treino = B.indices("2003-01-01", "2024-12-31")
teste = B.indices("2025-01-01")
quentes = np.argsort(-saiu[treino].sum(0))[:18] + 1     # 18 dezenas mais frequentes no treino
T = B.todas_combinacoes()
pc = B.popcount
def retorno(jogos, idx):
    g = c = 0.0
    for i in idx:
        ac = pc(jogos & B.D[i]); g += B.PR[i, ac].sum(); c += len(jogos) * B.PRECO[i]
    return g / c
# todos os fechamentos de 15 dentro das 18 quentes
fech_quentes = np.array([sum(1 << (d-1) for d in c) for c in itertools.combinations(quentes, 15)], dtype=np.int64)
rng = np.random.default_rng(0)
aleat = [retorno(np.array([sum(1 << d for d in rng.choice(25, 15, replace=False)) for _ in range(len(fech_quentes))], dtype=np.int64), teste) for _ in range(200)]
print(f"TESTE fora da amostra (jogos escolhidos com dados até 2024, medidos em 2025-2026, {len(teste)} sorteios):")
print(f"   fechamento das 18 dezenas mais QUENTES ({len(fech_quentes)} jogos): retorno {retorno(fech_quentes, teste):.3f} por real")
print(f"   jogos aleatórios (média de 200 conjuntos):                         retorno {np.mean(aleat):.3f} por real")
print(f"   diferença: {(retorno(fech_quentes, teste)-np.mean(aleat))*100:+.1f} pontos — e o break-even seria 1,000 (100%).")
