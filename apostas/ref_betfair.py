"""Sem Pinnacle desde meados de 2025: referência de preço justo = Betfair Exchange (fechamento).
Aposta na máxima do mercado (fechamento), odd <= 4. Banca 500, 1/4 Kelly, teto por aposta."""
import numpy as np
import pandas as pd
import estrategias as S

def apostas(lim, om=4.0):
    J = S.J; cf = [f"ec_{x}" for x in "HDA"]; co = [f"mc_{x}" for x in "HDA"]
    d = J.dropna(subset=cf + co).reset_index(drop=True)
    inv = 1 / d[cf].values; pj = inv / inv.sum(1, keepdims=True); O = d[co].values
    L = []
    for i, x in enumerate("HDA"):
        ev = O[:, i] * pj[:, i] - 1; ok = (ev > lim) & (O[:, i] <= om); s = d[ok]
        L.append(pd.DataFrame({"data": s.data.values, "odd": O[ok, i], "ev": ev[ok], "ganhou": (s.res == x).values}))
    A = pd.concat(L, ignore_index=True); A["lucro"] = np.where(A.ganhou, A.odd - 1, -1.0)
    return A.sort_values("data")

def banca(A, teto_usd, cap=500.0):
    eq, s = cap, []
    for dia, g in A.groupby("data"):
        st = np.minimum((0.25 * g.ev / (g.odd - 1)).clip(upper=0.03).values * eq, teto_usd)
        eq += float((st * g.lucro.values).sum()); s.append((dia, eq))
    s = pd.Series(dict(s)); m = s.resample("ME").last().ffill(); gm = m.diff().fillna(m.iloc[0] - cap)
    return s, gm

for lim in (0.02, 0.05):
    A = apostas(lim)
    print(f"valor>{lim:.0%}: {len(A)} apostas ({len(A) / 33:.0f}/mês), ROI {A.lucro.mean():+.1%}")
    for teto in (20, 50, 200):
        s, gm = banca(A, teto)
        print(f"   teto {teto:>4} USD: 500 -> {s.iloc[-1]:>8,.0f}  pior queda {(s / s.cummax() - 1).min():.0%}  "
              f"lucro/mês médio {gm.mean():>6,.0f}  últimos 12m {gm.iloc[-12:].mean():>6,.0f}  meses >=2000: {(gm >= 2000).mean():.0%}")
