"""Perfil CH na semana de 28/09 a 03/10/2026: carteira fictícia de 100 USDT, operação a operação.
Usa o histórico mensal (até 30/09) + arquivos diários da Binance (01-03/10)."""
import glob, io, sys, zipfile
import numpy as np
import pandas as pd
import indicadores as IND
import balancas as BAL
import motor as MT

ALAV = int(sys.argv[1]) if len(sys.argv) > 1 else 5
B = pd.read_pickle("../dados5m/base5m.pkl")
B = {k: v.loc["2026-07-01":] for k, v in B.items()}
cols = ["time", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb"]
novos = {}
for f in sorted(glob.glob("../dados5m/dia/*-5m-*.zip")):
    par = f.split("/")[-1].split("-")[0]
    with zipfile.ZipFile(f) as z:
        txt = z.read(z.namelist()[0]).decode()
    df = pd.read_csv(io.StringIO(txt), header=0 if not txt[:1].isdigit() else None).iloc[:, :10]
    df.columns = cols
    novos.setdefault(par, []).append(df)
idx_novo = None
for k in ("open", "high", "low", "close", "vol", "qvol", "tb"):
    extra = {}
    for par, partes in novos.items():
        d = pd.concat(partes).drop_duplicates("time")
        d.index = pd.to_datetime(d["time"].astype("int64"), unit="ms", utc=True)
        extra[par] = d[k].astype("float32")
    E = pd.DataFrame(extra).sort_index()
    B[k] = pd.concat([B[k], E[B[k].columns.intersection(E.columns)].reindex(columns=B[k].columns)]).sort_index()
    B[k] = B[k][~B[k].index.duplicated(keep="last")]
print("dados até", B["close"].index.max())

I = IND.calcular(B)
fecho = I["5m"]["close"].index
D = {k: B[k].set_axis(fecho).shift(-1) for k in ("open", "high", "low")}
D["close"] = I["5m"]["close"]; D["atrp"] = I["5m"]["atr"] / I["5m"]["close"]
qv = B["qvol"].set_axis(fecho)
q24 = qv.rolling(288, min_periods=144).sum(); qh = q24[q24.index.minute == 0]
U = ((qh.rank(axis=1, ascending=False) <= 30) & (qh >= 50e6)).reindex(fecho, method="ffill").fillna(False)
SL, SS = BAL.choque_v(D["close"], 4.0, 12, "volume", qv)
P = {"TAXA": 0.0001, "LEV_TETO": ALAV, "SEM_TP": True, "TRAVA_K": 10.0, "TRAVA_MAX": 0.08, "REENTRA": False, "TEMPO_MAX": 144}
# começa a operar na segunda 28/09 às 00:00 UTC (posições só abrem a partir daí)
ops, curva, info = MT.simular(D, SL, SS, U, P, ini="2026-09-28 00:00", fim="2026-10-03 23:50")
pd.set_option("display.width", 250)
print(f"\n=== Perfil CH ({ALAV}x, taxa 0,01%, slippage 0,02%) | 100 USDT | 28/09 00:00 a 03/10 23:55 UTC ===")
if len(ops):
    o = ops.copy()
    o["entrada"] = o.entrada_t.dt.strftime("%a %d/%m %H:%M"); o["saída"] = o.saida_t.dt.strftime("%a %d/%m %H:%M")
    o["lado"] = o.lado.map({"L": "LONG", "S": "SHORT"})
    o["mov_%"] = ((o.preco_sai / o.preco_ent - 1) * np.where(o.lado == "LONG", 100, -100)).round(2)
    o["ROI_%"] = (o.pnl / o.margem * 100).round(1)
    print(o[["entrada", "saída", "par", "lado", "preco_ent", "preco_sai", "mov_%", "margem", "alav", "pnl", "taxas", "ROI_%", "motivo"]]
          .round({"preco_ent": 5, "preco_sai": 5, "margem": 2, "pnl": 3, "taxas": 3}).to_string(index=False))
    print(f"\noperações fechadas: {len(o)} | ganhas: {(o.pnl > 0).sum()} | perdidas: {(o.pnl <= 0).sum()} | "
          f"PnL fechado: {o.pnl.sum():+.2f} USDT | taxas pagas: {o.taxas.sum():.2f} USDT")
else:
    print("nenhuma operação fechada")
for a in info["abertas"]:
    print(f"ABERTA no fim: {a['par']} {a['lado']} desde {a['entrada_t']:%a %d/%m %H:%M} | PnL aberto {a['pnl_aberto']:+.3f}")
dia = curva.resample("D").last()
print("\nsaldo no fim de cada dia (com posições abertas a preço de mercado):")
print("  " + " | ".join(f"{d:%a %d/%m}: {v:.2f}" for d, v in dia.items()))
print(f"\nresultado da semana: 100.00 -> {curva.iloc[-1]:.2f} USDT ({curva.iloc[-1] - 100:+.2f}) | pior momento {curva.min():.2f}")
