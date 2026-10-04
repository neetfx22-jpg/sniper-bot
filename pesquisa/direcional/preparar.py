"""Calcula indicadores, balanças e universos (por volume) e grava dados/prep.pkl (float32)."""
import numpy as np
import pandas as pd
import indicadores as IND
import balancas as BAL

B = pd.read_pickle("../dados5m/base5m.pkl")
I = IND.calcular(B)
fecho = I["5m"]["close"].index
D = {k: B[k].set_axis(fecho).astype("float32") for k in ("open", "high", "low", "close")}
# o motor decide no fecho da vela t e opera a partir da vela t+1: desloca O/H/L/C para a vela seguinte
D = {k: v.shift(-1) for k, v in D.items()}
D["close_dec"] = I["5m"]["close"].astype("float32")          # preço no instante da decisão
D["atrp"] = (I["5m"]["atr"] / I["5m"]["close"]).astype("float32")
# volume em USDT das últimas 24h, ranking por hora
qv = B["qvol"].set_axis(fecho).rolling(288, min_periods=144).sum()
qh = qv[qv.index.minute == 0]
rk = qh.rank(axis=1, ascending=False)
ok = qh >= 50e6
U = {}
for nome, (a, b) in {"top20": (1, 20), "top30": (1, 30), "top40": (1, 40), "21a40": (21, 40)}.items():
    U[nome] = ((rk >= a) & (rk <= b) & ok).reindex(fecho, method="ffill").fillna(False)
S = {}
S["original"] = BAL.original(I)
S["choque"] = BAL.choque(I)
for nome in U:
    S[f"momento|{nome}"] = BAL.momento(I, univ=U[nome])
    S[f"mom_gatilho|{nome}"] = BAL.mom_gatilho(I, univ=U[nome])
S = {k: (a.astype("float32"), b.astype("float32")) for k, (a, b) in S.items()}
pd.to_pickle({"D": D, "U": U, "S": S}, "../dados5m/prep.pkl")
print("pares por universo (média):", {k: round(float(v.sum(axis=1).mean()), 1) for k, v in U.items()})
for k, (a, b) in S.items():
    print(k, "sinais de entrada por dia (L ou S >= 75 e dif >= 10):",
          round(float((((np.maximum(a, b) >= 75) & ((a - b).abs() >= 10)) & U["top20"]).sum().sum() / (len(a) / 288)), 1))
