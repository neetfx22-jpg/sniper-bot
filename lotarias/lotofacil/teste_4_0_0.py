"""Testa as combinações 'Pré-15 / 4.0.0' do usuário (top_combinacoes.csv), geradas a partir de 2025,
nos sorteios que vieram DEPOIS (2026). O filtro escolhe combos que fizeram muito 12 e nunca 13/14/15 em 2025."""
import csv
import numpy as np
import base as B

# combinações do usuário
jogos = []
with open("top_combinacoes.csv") as f:
    for row in csv.DictReader(f):
        jogos.append(sum(1 << (int(row[f"D{i}"]) - 1) for i in range(1, 16)))
jogos = np.array(jogos, dtype=np.int64)
print(f"combinações no top_combinacoes.csv: {len(jogos)}")

def desempenho(js, idx):
    c = {k: 0 for k in (11, 12, 13, 14, 15)}; g = cu = 0.0
    for i in idx:
        ac = B.popcount(js & B.D[i])
        for k in c: c[k] += int((ac == k).sum())
        g += B.PR[i, ac].sum(); cu += len(js) * B.PRECO[i]
    return g / cu, c, g, cu

# 2025 = período de onde foram escolhidas (dentro da amostra). 2026 = fora da amostra.
for rotulo, idx in (("2025 (de onde foram escolhidas)", B.indices("2025-01-01", "2025-12-31")),
                    ("2026 (fora da amostra, nunca visto)", B.indices("2026-01-01"))):
    r, c, g, cu = desempenho(jogos, idx)
    n = len(idx)
    print(f"\n{rotulo}: {n} sorteios")
    print(f"   custo R$ {cu:,.0f} | prémios R$ {g:,.0f} | retorno {r:.3f} por real | lucro R$ {g-cu:,.0f}".replace(",", "."))
    print(f"   acertos totais: 11={c[11]} | 12={c[12]} | 13={c[13]} | 14={c[14]} | 15={c[15]}")
    print(f"   média por sorteio: 14 pontos {c[14]/n:.3f} vezes | 15 pontos {c[15]/n:.4f} vezes")

# comparação: as MESMAS 10.000, mas escolhidas ao acaso
rng = np.random.default_rng(3)
idx26 = B.indices("2026-01-01")
amost = []
for _ in range(50):
    js = np.array([sum(1 << d for d in rng.choice(25, 15, replace=False)) for _ in range(len(jogos))], dtype=np.int64)
    r, c, g, cu = desempenho(js, idx26)
    amost.append((r, c[14], c[15]))
amost = np.array(amost)
print(f"\n10.000 combinações ALEATÓRIAS (média de 50 conjuntos) em 2026:")
print(f"   retorno {amost[:,0].mean():.3f} por real | 14 pontos {amost[:,1].mean():.0f} no total | 15 pontos {amost[:,2].mean():.1f}")
print(f"\nesperado por puro acaso em 2026 ({len(idx26)} sorteios, 10.000 jogos):")
print(f"   14 pontos: {10000*len(idx26)/21792:.0f}  | 15 pontos: {10000*len(idx26)/3268760:.2f}")
