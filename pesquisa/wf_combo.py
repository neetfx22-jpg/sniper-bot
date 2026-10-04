"""Prova honesta da carteira combinada: as peças são escolhidas trimestre a trimestre
só com os 12 meses anteriores (escolhas do walkforward.py), custo 0,04%/lado,
liquidação se a perda alavancada dentro da hora passar de 90% do patrimônio."""
import json
import numpy as np
import pandas as pd
import estrategias2 as E
import motor as M
import grade2_pesos as GP

C, H, Lo, R, FR = M.montar(pd.read_pickle("dados/base.pkl"))
CAP = 500.0
P0 = C.shift(1)
adv_l, adv_s = (Lo / P0 - 1).fillna(0), (H / P0 - 1).fillna(0)
ESC = pd.read_csv("saida/escolhas_mexc.csv")
import sys
FAMS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["choque", "xs_mom", "res_mom", "mom_long_btc"]
CUSTO = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0004

cache = {}
def W_de(chave):
    if chave not in cache:
        nome, p = chave.split(" ", 1)
        cache[chave] = GP.pesos(C, H, Lo, R, FR, nome, json.loads(p))
    return cache[chave]

partes = []
for q in pd.period_range("2024Q1", "2026Q3", freq="Q"):
    ini, fim = q.start_time.tz_localize("UTC"), q.end_time.tz_localize("UTC")
    Wq = sum(W_de(ESC[(ESC.familia == f) & (ESC.tri == str(q))].escolha.iloc[0]) for f in FAMS) / len(FAMS)
    partes.append(Wq.loc[ini:fim])
W = pd.concat(partes).reindex(C.index).fillna(0.0)

def simular(a, ini="2024-01-01"):
    Wp = (W.shift(1).fillna(0) * a).loc[ini:]
    r = M.rodar(W * a, R, FR, taxa=CUSTO).loc[ini:]
    pior = (Wp.clip(lower=0) * adv_l.loc[Wp.index] + Wp.clip(upper=0) * adv_s.loc[Wp.index]).sum(axis=1)
    eq, liq, out = CAP, None, []
    for t, ri, pi in zip(r.index, r.values, pior.values):
        if eq > 0 and pi <= -0.9:
            eq, liq = 0.0, t
        elif eq > 0:
            eq *= 1 + ri
        out.append(eq)
    return pd.Series(out, index=r.index), liq

print("== carteira combinada escolhida às cegas, jan/2024–set/2026, 500 USDT ==")
print(f"{'alav':>5}{'fim 2024':>10}{'fim 2025':>10}{'set/2026':>10}{'pior queda':>11}{'meses +':>9}{'liquidou':>12}")
for a in (1, 1.5, 2, 3, 4, 5):
    s, liq = simular(a)
    m = s.resample("ME").last()
    rm = m.pct_change().fillna(m.iloc[0] / CAP - 1)
    print(f"{a:>5}{s.loc[:'2024-12-31'].iloc[-1]:>10.0f}{s.loc[:'2025-12-31'].iloc[-1]:>10.0f}{s.iloc[-1]:>10.0f}"
          f"{(s / s.cummax() - 1).min():>11.0%}{(rm > 0).mean():>9.0%}{str(liq.date()) if liq is not None else '-':>12}")
s, _ = simular(2)
print("\nmês a mês com 2x:")
m = s.resample("ME").last(); print((m.pct_change().fillna(m.iloc[0] / CAP - 1) * 100).round(1).to_string())
