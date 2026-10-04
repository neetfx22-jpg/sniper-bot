"""Roda TODAS as combinações de parâmetros e grava o retorno horário de cada uma (2 taxas)."""
import os, json, time
import numpy as np
import pandas as pd
import estrategias2 as E
import motor as M

base = pd.read_pickle("dados/base.pkl")
C, H, Lo, R, FR = M.montar(base)
Ls = (24, 72, 168, 336, 720, 1440)
G = []
G += [("xs_mom", dict(L=L, reb=rb, k=k, skip=sk)) for L in Ls for rb in (8, 24, 72) for k in (3, 5, 8) for sk in (0, 24) if sk < L]
G += [("xs_rev", dict(L=L, reb=rb, k=k, inverso=True)) for L in (1, 4, 12, 24, 72) for rb in (1, 4, 12, 24) for k in (3, 5, 8) if rb <= max(L, 4)]
G += [("res_mom", dict(L=L, reb=rb, k=k)) for L in (72, 168, 336, 720) for rb in (24, 72) for k in (3, 5, 8)]
G += [("res_rev", dict(L=L, reb=rb, k=k, inverso=True)) for L in (1, 4, 12, 24) for rb in (1, 4, 12) for k in (3, 5, 8) if rb <= max(L, 4)]
G += [("ts_trend", dict(L=L, reb=rb)) for L in Ls for rb in (8, 24, 72)]
G += [("ema_cross", dict(fast=f, slow=s, reb=rb)) for f, s in ((12, 48), (24, 96), (48, 192), (96, 384), (168, 720), (336, 1440)) for rb in (1, 24)]
G += [("breakout", dict(N=N)) for N in (24, 72, 168, 336, 720, 1440)]
G += [("choque", dict(z=z, h=h, seguir=sg)) for z in (2.5, 3.5, 5.0) for h in (1, 4, 12, 24) for sg in (True, False)]
G += [("carry", dict(L=L, reb=rb, k=k)) for L in (24, 72, 168, 336) for rb in (8, 24, 72) for k in (3, 5, 8)]
G += [("mom_long_btc", dict(L=L, reb=rb, k=k, M=Mm)) for L in (168, 336, 720) for rb in (24, 72) for k in (3, 5, 8) for Mm in (168, 720)]

def pesos(nome, p):
    if nome in ("xs_mom", "xs_rev"):  return E.xs_mom(C, R, **p)
    if nome in ("res_mom", "res_rev"): return E.xs_resid(C, R, **p)
    if nome == "ts_trend":  return E.ts_trend(C, R, **p)
    if nome == "ema_cross": return E.ema_cross(C, R, **p)
    if nome == "breakout":  return E.breakout(C, H, Lo, R, **p)
    if nome == "choque":    return E.choque(C, R, **p)
    if nome == "carry":     return E.carry(FR, **p)
    if nome == "mom_long_btc": return E.mom_long_filtro(C, R, **p)

print(len(G), "combinações")
out = {"binance": {}, "mexc": {}}
giro = {}
t0 = time.time()
for i, (nome, p) in enumerate(G):
    W = pesos(nome, p)
    chave = nome + " " + json.dumps(p, sort_keys=True)
    for tx, v in (("binance", M.TAXA_BINANCE), ("mexc", M.TAXA_MEXC)):
        out[tx][chave] = M.rodar(W, R, FR, taxa=v).astype("float32")
    Wp = W.shift(1).fillna(0)
    giro[chave] = float((Wp - Wp.shift(1).fillna(0)).abs().sum(axis=1).mean() * 24)
    if i % 50 == 0:
        print(i, f"{time.time() - t0:.0f}s", chave, flush=True)
for tx in out:
    pd.DataFrame(out[tx]).to_pickle(f"saida/ret_{tx}.pkl")
pd.Series(giro).to_pickle("saida/giro.pkl")
print("ok", f"{time.time() - t0:.0f}s")
