"""Exploração da balança de choque: variantes x saídas x alavancagem, só no TREINO (fev-dez/2025).
As melhores vão para a prova em 2026 (prova.py)."""
import itertools, json, sys
import numpy as np
import pandas as pd
from multiprocessing import Pool
import balancas as BAL
import motor as MT

P = pd.read_pickle("../dados5m/prep.pkl")
Dm = {"open": P["D"]["open"], "high": P["D"]["high"], "low": P["D"]["low"], "close": P["D"]["close_dec"], "atrp": P["D"]["atrp"]}
B = pd.read_pickle("../dados5m/base5m.pkl")
QV = B["qvol"].set_axis(P["D"]["close_dec"].index)
VAR = {}
for modo in ("base", "residuo", "volume", "btc"):
    for z, h in ((3.0, 6), (3.5, 6), (3.5, 12), (4.0, 12)):
        VAR[(modo, z, h)] = BAL.choque_v(P["D"]["close_dec"], z, h, modo, QV)
SAIDAS = {
    "script": {},
    "script_1x": {"REENTRA": False},
    "tempo": {"SEM_TP": True, "TRAVA_K": 10.0, "TRAVA_MAX": 0.08, "REENTRA": False},   # segura h horas
    "tempo_trava3": {"SEM_TP": True, "REENTRA": False},
}
INI, FIM = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("2025-02-01", "2025-12-31")

def run(a):
    (modo, z, h), sn, lv, uni = a
    SL, SS = VAR[(modo, z, h)]
    p = {"TAXA": 0.0001, "LEV_TETO": lv, **SAIDAS[sn]}
    if sn.startswith("tempo"):
        p["TEMPO_MAX"] = h * 12
    ops, curva, info = MT.simular(Dm, SL, SS, P["U"][uni], p, ini=INI, fim=FIM)
    return dict(modo=modo, z=z, h=h, saida=sn, alav=lv, universo=uni, final=round(float(curva.iloc[-1]), 1),
                pior_queda=round(float((curva / curva.cummax() - 1).min()), 2), ops=len(ops),
                taxas=round(float(ops.taxas.sum()), 1), liquidou=bool(info["liquidou"]))

if __name__ == "__main__":
    tarefas = list(itertools.product(VAR, SAIDAS, (5, 10), ("top20", "top30")))
    with Pool(4) as pool:
        R = pd.DataFrame(pool.map(run, tarefas, chunksize=2))
    R.to_csv(f"saida/exploracao_{INI[:7]}_{FIM[:7]}.csv", index=False)
    pd.set_option("display.width", 220)
    print(len(R), "simulações | período", INI, FIM)
    print(R.sort_values("final", ascending=False).head(25).to_string(index=False))
    print("\nmediana do final por variante e por saída:")
    print(R.pivot_table(index="modo", columns="saida", values="final", aggfunc="median").round(0).to_string())
