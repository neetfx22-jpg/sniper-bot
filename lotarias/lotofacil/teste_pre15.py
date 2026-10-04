"""Teste do filtro 'Pré-15' do finallotofácil.py: escolhe combinações pelos sorteios de 2025
(>= 4 vezes 12 pontos, nunca 13/14/15, no máximo 35 vezes 11) e mede o desempenho delas em 2026."""
import itertools
import numpy as np
from backtest import H, D, PR, PRECO

anos = np.array([int(h["data"][-4:]) for h in H])
LUT = np.array([bin(i).count("1") for i in range(1 << 13)], dtype=np.int8)
def pc(x):
    return LUT[x & 0x1FFF] + LUT[(x >> 13) & 0x1FFF]

todas = np.fromiter((sum(1 << d for d in c) for c in itertools.combinations(range(25), 15)), dtype=np.int64, count=3268760)
cnt = np.zeros((len(todas), 16), dtype=np.int16)
i25 = np.where(anos == 2025)[0]; i26 = np.where(anos == 2026)[0]
for i in i25:
    ac = pc(todas & D[i]); np.add.at(cnt, (np.arange(len(todas)), ac), 1) if False else None
    for k in (11, 12, 13, 14, 15):
        cnt[:, k] += (ac == k)
sel = (cnt[:, 12] >= 4) & (cnt[:, 13] == 0) & (cnt[:, 14] == 0) & (cnt[:, 15] == 0) & (cnt[:, 11] <= 35)
print(f"sorteios de 2025: {len(i25)} | combinações 'pré-15' escolhidas pelo filtro: {sel.sum():,} de {len(todas):,}".replace(",", "."))
# desempenho em 2026 (fora da amostra): prémio médio por aposta e frequência de 13/14/15
def desempenho(m):
    ganho = np.zeros(m.sum()); c = {k: 0 for k in (11, 12, 13, 14, 15)}
    sub = todas[m]
    for i in i26:
        ac = pc(sub & D[i]); ganho += PR[i, ac]
        for k in c: c[k] += int((ac == k).sum())
    n = m.sum() * len(i26)
    return ganho.sum() / (PRECO[i26].mean() * n), {k: v / n for k, v in c.items()}
r_sel, f_sel = desempenho(sel)
r_all, f_all = desempenho(np.ones(len(todas), bool))
print(f"\nem 2026 ({len(i26)} sorteios), por aposta:")
print(f"   'pré-15' : retorno {r_sel:.4f} por real | 13 pts: 1 em {1 / f_sel[13]:.0f} | 14 pts: 1 em {1 / max(f_sel[14], 1e-12):,.0f} | 15 pts: {f_sel[15] * sel.sum() * len(i26):.0f} vezes".replace(",", "."))
print(f"   todas    : retorno {r_all:.4f} por real | 13 pts: 1 em {1 / f_all[13]:.0f} | 14 pts: 1 em {1 / f_all[14]:,.0f} | 15 pts: 1 em {1 / f_all[15]:,.0f}".replace(",", "."))
print(f"   teórico  : 13 pts 1 em 692 | 14 pts 1 em 21.792 | 15 pts 1 em 3.268.760")
