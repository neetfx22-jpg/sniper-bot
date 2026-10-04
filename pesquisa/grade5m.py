"""Pesquisa em velas de 5m (jan/2025–set/2026): famílias de curto prazo + validação por janelas.

Escolha por trimestre usando só os 6 meses anteriores; prova em 2025T3–2026T3.
Custo 0,04%/lado (taxa MEXC 0,01% + slippage 0,03%). Funding ignorado (posições curtas).
"""
import json, time
import numpy as np
import pandas as pd
import estrategias2 as E

B = pd.read_pickle("dados5m/base5m.pkl")
C, H, Lo, V = B["close"], B["high"], B["low"], B["vol"]
R = C.pct_change(fill_method=None).fillna(0.0).astype("float64")
CUSTO = 0.0004
ANO = 105120

def rodar(W):
    Wp = W.shift(1).fillna(0.0)
    return (Wp * R).sum(axis=1) - (Wp - Wp.shift(1).fillna(0.0)).abs().sum(axis=1) * CUSTO

def vol5(n=288 * 3):
    return R.rolling(n, min_periods=n // 2).std()

VOL = vol5()

def choque(z, h, seguir):
    zz = R / VOL
    s = np.sign(zz) * (zz.abs() > z)
    return E.normaliza((s if seguir else -s).rolling(h, min_periods=1).sum())

def breakout(N):
    top = H.rolling(N).max().shift(1); bot = Lo.rolling(N).min().shift(1)
    s = pd.DataFrame(np.where(C > top, 1.0, np.where(C < bot, -1.0, np.nan)), index=C.index, columns=C.columns)
    s = s.ffill(limit=N).fillna(0.0)
    return E.normaliza(s / VOL)

def xs(L, reb, k, inverso):
    s = (C / C.shift(L) - 1) / VOL
    W = E._top_bottom(s, k)
    return E.normaliza(E.rebalanceia(-W if inverso else W, reb))

def volume(x, h, seguir):
    vr = V / V.rolling(288, min_periods=144).mean()
    s = np.sign(R) * (vr > x)
    return E.normaliza((s if seguir else -s).rolling(h, min_periods=1).sum())

def sazonal(dias, tmin):
    """Hora do dia: média do retorno daquela hora nos últimos 'dias' dias; opera o sinal se |t| > tmin."""
    Rh = (1 + R).groupby(R.index.floor("h")).prod() - 1
    hr = Rh.index.hour
    sig = pd.DataFrame(0.0, index=Rh.index, columns=Rh.columns)
    for h in range(24):
        sub = Rh[hr == h]
        mu = sub.rolling(dias, min_periods=dias // 2).mean().shift(1)
        sd = sub.rolling(dias, min_periods=dias // 2).std().shift(1)
        t = mu / (sd / np.sqrt(dias))
        sig.loc[sub.index] = (np.sign(t) * (t.abs() > tmin)).values
    # sinal decidido antes da hora começar: vale para todas as velas de 5m daquela hora
    W = sig.reindex(R.index, method="ffill").shift(-1).fillna(0.0)   # alinha início da hora
    W = sig.reindex(R.index.floor("h")).set_axis(R.index)
    return E.normaliza(W.shift(1).fillna(0.0) * 0 + W)

G = []
G += [("choque5", dict(z=z, h=h, seguir=s)) for z in (3, 4, 6) for h in (6, 12, 36, 72, 144) for s in (True, False)]
G += [("breakout5", dict(N=N)) for N in (12, 48, 144, 288, 576)]
G += [("xs5", dict(L=L, reb=rb, k=k, inverso=inv)) for L in (12, 48, 144, 288) for rb in (12, 48) for k in (3, 5) for inv in (True, False)]
G += [("volume5", dict(x=x, h=h, seguir=s)) for x in (3, 5, 8) for h in (6, 36, 144) for s in (True, False)]
G += [("sazonal", dict(dias=d, tmin=t)) for d in (20, 40, 60) for t in (1.5, 2.0, 2.5)]
F = {"choque5": choque, "breakout5": breakout, "xs5": xs, "volume5": volume, "sazonal": sazonal}

t0 = time.time(); RET = {}
for i, (n, p) in enumerate(G):
    RET[n + " " + json.dumps(p, sort_keys=True)] = rodar(F[n](**p)).astype("float32")
    if i % 20 == 0: print(i, len(G), f"{time.time() - t0:.0f}s", flush=True)
RET = pd.DataFrame(RET); RET.to_pickle("saida/ret5m.pkl")
fam = pd.Series({c: c.split(" ")[0] for c in RET.columns})

def sh(r):
    return r.mean() / r.std() * np.sqrt(ANO) if r.std() > 0 else -9

# walk-forward trimestral, treino de 6 meses
oos = {}
for f in sorted(fam.unique()):
    cols = fam.index[fam == f]; partes = []
    for q in pd.period_range("2025Q3", "2026Q3", freq="Q"):
        ini, fim = q.start_time.tz_localize("UTC"), q.end_time.tz_localize("UTC")
        tr = RET.loc[ini - pd.DateOffset(months=6): ini - pd.Timedelta(minutes=5), cols].astype("float64")
        partes.append(RET.loc[ini:fim, tr.apply(sh).idxmax()].astype("float64"))
    oos[f] = pd.concat(partes)
O = pd.DataFrame(oos)
print("\n== 5m fora da amostra (2025T3–2026T3), custo 0,04%/lado, 1x ==")
for f in O.columns:
    r = O[f]; eq = (1 + r).cumprod()
    mm = ((1 + r).groupby(r.index.tz_localize(None).to_period("M")).prod() - 1)
    print(f"{f:<10} sharpe {sh(r):+.2f}  mês médio {mm.mean():+.1%}  meses+ {(mm > 0).mean():.0%}  pior queda {(eq / eq.cummax() - 1).min():.0%}")
rob = RET.astype("float64").apply(sh).groupby(fam).agg(["median", "max", lambda s: (s > 0).mean()])
rob.columns = ["sharpe_mediano", "sharpe_max", "frac_pos"]
print("\n== todas as combinações, período todo ==\n" + rob.round(2).to_string())
