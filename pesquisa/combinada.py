"""Carteiras combinadas + alavancagem com pior caso dentro da hora (pavios).

Liquidação: em cada hora, a perda dentro da vela é estimada pelo pior extremo de cada
par contra a posição (máxima para vendido, mínima para comprado). Se a perda alavancada
dentro da hora atingir o patrimônio, a conta é liquidada (zera).
"""
import numpy as np
import pandas as pd
import estrategias2 as E
import motor as M

C, H, Lo, R, FR = M.montar(pd.read_pickle("dados/base.pkl"))
CUSTO = 0.0004   # 0,01% taxa MEXC + 0,03% de slippage por lado (conservador)
CAP = 500.0
P0 = C.shift(1)
adv_long = (Lo / P0 - 1).fillna(0)    # pior movimento p/ comprado na hora
adv_short = (H / P0 - 1).fillna(0)    # pior movimento p/ vendido na hora

PECAS = {
    "choque": E.choque(C, R, z=3.5, h=12, seguir=True),
    "xs_mom": E.xs_mom(C, R, L=336, reb=24, k=5),
    "res_mom": E.xs_resid(C, R, L=336, reb=24, k=5),
    "mom_long_btc": E.mom_long_filtro(C, R, L=336, reb=24, k=5, M=720),
}
RET = {n: M.rodar(W, R, FR, taxa=CUSTO).loc["2023-03-01":] for n, W in PECAS.items()}
print("correlação diária entre as peças:")
D = pd.DataFrame({n: (1 + r).groupby(r.index.floor("D")).prod() - 1 for n, r in RET.items()})
print(D.corr().round(2).to_string())

CARTEIRAS = {
    "só choque": {"choque": 1.0},
    "só xs_mom": {"xs_mom": 1.0},
    "choque+xs_mom (50/50)": {"choque": 0.5, "xs_mom": 0.5},
    "choque+res_mom+xs_mom": {"choque": 1 / 3, "res_mom": 1 / 3, "xs_mom": 1 / 3},
    "todas (25% cada)": {k: 0.25 for k in PECAS},
}

def simular(Wt, a):
    Wp = (Wt.shift(1).fillna(0) * a).loc["2023-03-01":]
    r = M.rodar(Wt * a, R, FR, taxa=CUSTO).loc["2023-03-01":]
    pior = (Wp.clip(lower=0) * adv_long.loc[Wp.index] + Wp.clip(upper=0) * adv_short.loc[Wp.index]).sum(axis=1)
    eq, liq = CAP, None
    serie = np.empty(len(r))
    for i, (ri, pi) in enumerate(zip(r.values, pior.values)):
        if eq > 0 and eq * (1 + pi) <= eq * 0.0 + eq * 0.005:   # perda intrabar >= ~99,5% do patrimônio
            eq, liq = 0.0, r.index[i]
        elif eq > 0:
            eq *= 1 + ri
        serie[i] = eq
    s = pd.Series(serie, index=r.index)
    return s, liq

print(f"\n== 500 USDT, mar/2023–set/2026, custo {CUSTO:.2%}/lado, liquidação pelos pavios ==")
print(f"{'carteira':<24}{'alav':>5}{'final':>12}{'lucro/mês 12m finais':>22}{'pior queda':>11}{'liquidou':>12}")
for nome, pesos in CARTEIRAS.items():
    Wt = sum(PECAS[k] * v for k, v in pesos.items())
    for a in (1, 2, 3, 5, 8, 10):
        s, liq = simular(Wt, a)
        dd = (s / s.cummax() - 1).min()
        ult = s.loc["2025-10-01":]
        lucro12 = (ult.iloc[-1] - ult.iloc[0]) / 12 if ult.iloc[0] > 0 else 0
        print(f"{nome:<24}{a:>5}{s.iloc[-1]:>12.0f}{lucro12:>22.0f}{dd:>11.0%}{str(liq.date()) if liq is not None else '-':>12}")
