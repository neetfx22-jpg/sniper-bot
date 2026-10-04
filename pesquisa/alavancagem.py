"""Quanto a alavancagem muda o resultado da melhor estratégia (momento entre pares).

1) histórico real (jan/2025–set/2026) com alavancagem 1x..50x;
2) simulação: 12 meses sorteados em blocos de 7 dias do histórico real (2.000 caminhos),
   capital 500 USDT; conta 'quebrada' se o patrimônio cair a 5% do inicial (liquidação).
"""
import os
import numpy as np
import pandas as pd
import estrategias as E
import motor as M

base = pd.read_pickle(os.path.join(os.path.dirname(__file__), "dados", "base.pkl"))
C, H, Lo, R, FR = M.montar(base)
W = E.momento_cruzado(C, R, L=336, reb=24, k=5)
CAP = 500.0
ALAVS = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50]

print("== Histórico real, taxa MEXC, 500 USDT iniciais ==")
print(f"{'alav':>5} {'final 2025':>11} {'final set/26':>13} {'lucro/mês médio':>16} {'pior queda':>11} {'quebrou?':>9}")
for a in ALAVS:
    r = M.rodar(W, R, FR, taxa=M.TAXA_MEXC, alav=a).loc["2025-01-15":]
    eq = CAP * (1 + r.clip(lower=-1)).cumprod()
    quebra = (eq <= CAP * 0.05).any()
    if quebra:
        eq[eq.index >= eq[eq <= CAP * 0.05].index[0]] = 0.0
    mens = eq.resample("ME").last()
    lucro_mes = mens.diff().fillna(mens.iloc[0] - CAP)
    dd = (eq / eq.cummax() - 1).min()
    print(f"{a:>5} {eq.loc[:'2025-12-31'].iloc[-1]:>11.0f} {eq.iloc[-1]:>13.0f} {lucro_mes.mean():>16.0f} {dd:>11.0%} {'SIM' if quebra else 'não':>9}")

# simulação por blocos
r1 = M.rodar(W, R, FR, taxa=M.TAXA_MEXC, alav=1).loc["2025-01-15":]
dias = r1.groupby(r1.index.floor("D"))
blocos = [g.values for _, g in r1.groupby(r1.index.floor("7D"))]
rng = np.random.default_rng(42)
N, SEMANAS = 2000, 52
print("\n== 2.000 anos simulados (blocos de 7 dias do histórico real), 500 USDT ==")
print(f"{'alav':>5} {'P(quebrar)':>11} {'mediana final':>14} {'P(final>500)':>13} {'P(média>=2000/mês)':>19}")
for a in ALAVS:
    finais, quebras, meta = [], 0, 0
    for _ in range(N):
        idx = rng.integers(0, len(blocos), SEMANAS)
        rr = np.concatenate([blocos[i] for i in idx])
        # retorno com alavancagem a (custo já embutido em r1 escala ~linearmente com a)
        eq = CAP * np.cumprod(1 + np.clip(a * rr, -1, None))
        if (eq <= CAP * 0.05).any():
            quebras += 1; finais.append(0.0); continue
        finais.append(eq[-1])
        if (eq[-1] - CAP) / 12 >= 2000:
            meta += 1
    finais = np.array(finais)
    print(f"{a:>5} {quebras / N:>11.0%} {np.median(finais):>14.0f} {(finais > CAP).mean():>13.0%} {meta / N:>19.1%}")
