"""Robustez da balança 'choque' (top30, MEXC): parâmetros vizinhos, slippage maior, cada ano em separado."""
import itertools
import numpy as np
import pandas as pd
from multiprocessing import Pool
import balancas as BAL
import motor as MT

P = pd.read_pickle("../dados5m/prep.pkl")
Dm = {"open": P["D"]["open"], "high": P["D"]["high"], "low": P["D"]["low"], "close": P["D"]["close_dec"], "atrp": P["D"]["atrp"]}
I = {"5m": {"close": P["D"]["close_dec"]}}
VAR = {(z, h): BAL.choque(I, z=z, h=h) for z in (3.0, 3.5, 4.0) for h in (6, 12, 24)}

def run(a):
    (z, h), lv, slip, uni, ini, fim = a
    SL, SS = VAR[(z, h)]
    ops, curva, info = MT.simular(Dm, SL, SS, P["U"][uni], {"TAXA": 0.0001, "LEV_TETO": lv, "SLIP": slip}, ini=ini, fim=fim)
    return dict(z=z, horas=h, alav=lv, slip=slip, universo=uni, periodo=f"{ini[:7]}..{fim[:7]}", final=round(float(curva.iloc[-1]), 1),
                pior_queda=round(float((curva / curva.cummax() - 1).min()), 2), ops=len(ops), liquidou=bool(info["liquidou"]))

tarefas = [((z, h), lv, 0.0002, "top30", "2025-02-01", "2026-09-30") for (z, h) in VAR for lv in (5, 10)]
tarefas += [((3.5, 12), lv, s, "top30", "2025-02-01", "2026-09-30") for lv in (5, 10) for s in (0.0005, 0.001)]
tarefas += [((3.5, 12), lv, 0.0002, u, a, b) for lv in (5, 10) for u in ("top20", "top30") for a, b in
            (("2025-02-01", "2025-12-31"), ("2026-01-01", "2026-09-30"))]
with Pool(4) as pool:
    R = pd.DataFrame(pool.map(run, tarefas, chunksize=1))
pd.set_option("display.width", 200)
print("== vizinhos dos parâmetros (top30, 20 meses) ==")
print(R.iloc[:18].pivot_table(index=["z", "horas"], columns="alav", values="final").to_string())
print("\n== slippage maior (z3.5, 12h, top30) ==")
print(R.iloc[18:22][["alav", "slip", "final", "pior_queda", "liquidou"]].to_string(index=False))
print("\n== cada ano começando de 100 (z3.5, 12h) ==")
print(R.iloc[22:][["alav", "universo", "periodo", "final", "pior_queda", "liquidou"]].to_string(index=False))
R.to_csv("saida/robustez.csv", index=False)
