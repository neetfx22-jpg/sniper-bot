"""Testes de estresse nas candidatas: a vantagem sobrevive a condições piores?"""
import numpy as np
import pandas as pd
import estrategias2 as E
import motor as M

C, H, Lo, R, FR = M.montar(pd.read_pickle("dados/base.pkl"))
CAND = {
    "choque seguir z3.5 h4":  lambda C, R: E.choque(C, R, z=3.5, h=4, seguir=True),
    "choque seguir z3.5 h12": lambda C, R: E.choque(C, R, z=3.5, h=12, seguir=True),
    "choque seguir z5 h24":   lambda C, R: E.choque(C, R, z=5.0, h=24, seguir=True),
    "mom_long_btc 336/24/5/720": lambda C, R: E.mom_long_filtro(C, R, L=336, reb=24, k=5, M=720),
    "res_mom 336/24/5":       lambda C, R: E.xs_resid(C, R, L=336, reb=24, k=5),
    "xs_mom 336/24/5":        lambda C, R: E.xs_mom(C, R, L=336, reb=24, k=5),
}
CEN = {  # nome: (taxa, atraso_h, teto_por_par)
    "base mexc":          (0.0001, 0, None),
    "taxa binance":       (0.0005, 0, None),
    "slip 0,2%/lado":     (0.0021, 0, None),
    "entrada +1h":        (0.0001, 1, None),
    "teto 25% por par":   (0.0001, 0, 0.25),
}
rng = np.random.default_rng(7)
metades = [sorted(rng.choice(C.columns, size=len(C.columns) // 2, replace=False)) for _ in range(4)]

def sh(r):
    r = r.loc["2023-03-01":]
    return r.mean() / r.std() * np.sqrt(8760) if r.std() > 0 else 0

def mm(r):
    r = r.loc["2023-03-01":]
    return ((1 + r).groupby(r.index.tz_localize(None).to_period("M")).prod() - 1).mean()

linhas = []
for nome, f in CAND.items():
    W = f(C, R)
    lin = {"estrategia": nome}
    for cn, (tx, atraso, teto) in CEN.items():
        Wc = W.shift(atraso).fillna(0) if atraso else W
        if teto:
            Wc = Wc.clip(-teto, teto)
        r = M.rodar(Wc, R, FR, taxa=tx)
        lin[cn] = f"{sh(r):+.2f} / {mm(r):+.1%}"
    shs = []
    for cols in metades:   # recalcula a estratégia só com metade das moedas (BTC sempre incluso)
        cc = sorted(set(cols) | {"BTCUSDT"})
        r = M.rodar(f(C[cc], R[cc]), R[cc], FR[cc], taxa=0.0001)
        shs.append(sh(r))
    lin["metades (sharpe)"] = " ".join(f"{x:+.2f}" for x in shs)
    linhas.append(lin)
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 40)
print("sharpe / lucro médio por mês, mar/2023–set/2026, exposição 1x")
print(pd.DataFrame(linhas).to_string(index=False))
