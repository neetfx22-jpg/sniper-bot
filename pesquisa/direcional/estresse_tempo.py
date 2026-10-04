"""Estresse da versão 'choque + saída por tempo' (uma entrada por choque, segura h horas, trava de catástrofe)."""
import itertools
import numpy as np
import pandas as pd
from multiprocessing import Pool
import balancas as BAL
import motor as MT

P = pd.read_pickle("../dados5m/prep.pkl")
Dm = {"open": P["D"]["open"], "high": P["D"]["high"], "low": P["D"]["low"], "close": P["D"]["close_dec"], "atrp": P["D"]["atrp"]}
QV = pd.read_pickle("../dados5m/base5m.pkl")["qvol"].set_axis(P["D"]["close_dec"].index)
VAR = {m: BAL.choque_v(P["D"]["close_dec"], 4.0, 12, m, QV) for m in ("base", "volume")}
BASE = {"SEM_TP": True, "TRAVA_K": 10.0, "TRAVA_MAX": 0.08, "REENTRA": False, "TEMPO_MAX": 144}
CEN = {"MEXC 0,01% + slip 0,02%": {"TAXA": 0.0001},
       "MEXC + slip 0,05%": {"TAXA": 0.0001, "SLIP": 0.0005},
       "MEXC + slip 0,10%": {"TAXA": 0.0001, "SLIP": 0.001},
       "Binance 0,05% + slip 0,02%": {"TAXA": 0.0005},
       "Binance + slip 0,05%": {"TAXA": 0.0005, "SLIP": 0.0005}}

def run(a):
    modo, cn, lv = a
    p = {**BASE, **CEN[cn], "LEV_TETO": lv}
    SL, SS = VAR[modo]
    ops, curva, info = MT.simular(Dm, SL, SS, P["U"]["top30"], p, ini="2025-02-01", fim="2026-09-30")
    m = curva.resample("ME").last(); rm = m.pct_change().fillna(m.iloc[0] / 100 - 1)
    return dict(modo=modo, cenario=cn, alav=lv or "real", final=round(float(curva.iloc[-1]), 1),
                pior_queda=round(float((curva / curva.cummax() - 1).min()), 2), meses_pos=f"{(rm > 0).sum()}/{len(rm)}",
                ops=len(ops), acerto=round(float((ops.pnl > 0).mean()), 2), taxas=round(float(ops.taxas.sum()), 1),
                liquidou=str(info["liquidou"])[:10] if info["liquidou"] else "-", _m=rm)

if __name__ == "__main__":
    tarefas = list(itertools.product(VAR, CEN, (5, 10, None)))
    with Pool(4) as pool:
        R = pool.map(run, tarefas, chunksize=1)
    T = pd.DataFrame([{k: v for k, v in r.items() if k != "_m"} for r in R])
    pd.set_option("display.width", 220)
    print("== 20 meses (fev/2025-set/2026), 100 USDT, top 30, choque >= 4 desvios, segura 12h ==")
    print(T.to_string(index=False))
    for r in R:
        if r["modo"] == "volume" and r["cenario"].startswith("MEXC 0,01") and r["alav"] in (5, 10):
            print(f"\nmês a mês (volume, {r['alav']}x, MEXC):")
            print(" ".join(f"{d:%y-%m}:{v:+.0%}" for d, v in r["_m"].items()))
    T.to_csv("saida/estresse_tempo.csv", index=False)
