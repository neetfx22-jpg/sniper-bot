"""Simulação minuto a minuto (velas de 1m) dos perfis de choque num dia, monitorando os 100 pares de maior volume.

- Balança: choque de 1h (igual ao script), recalculada a cada hora fechada.
- ATR: velas de 5m fechadas (igual ao script), usado na trava e no alvo.
- Universo: top 100 por volume (USDT) das últimas 24h, refeito a cada 5 minutos.
- Execução: decisões no fecho de cada minuto; trava/alvo verificados no caminho de preço de cada minuto.
- Alavancagem máxima: a tabela LEV_POR_PAR do script; os outros pares usam LEV_PADRAO (sem chave de API o
  script usa 20x; com chave usa a máxima real da Binance, que para muitos pares é 50x-75x).
"""
import glob, io, sys, zipfile, itertools, json
import numpy as np
import pandas as pd
import balancas as BAL
import motor as MT

def carregar():
    cols = ["time", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb"]
    M = {}
    for f in sorted(glob.glob("../dados1m/k/*-1m-*.zip")):
        par = f.split("/")[-1].split("-")[0]
        with zipfile.ZipFile(f) as z:
            t = z.read(z.namelist()[0]).decode()
        d = pd.read_csv(io.StringIO(t), header=0 if not t[:1].isdigit() else None).iloc[:, :10]
        d.columns = cols
        M.setdefault(par, []).append(d)
    out = {}
    for k in ("open", "high", "low", "close", "qvol"):
        out[k] = pd.DataFrame({p: pd.concat(v).drop_duplicates("time").set_index("time")[k].astype("float64") for p, v in M.items()})
        out[k].index = pd.to_datetime(out[k].index, unit="ms", utc=True)
        out[k] = out[k].sort_index()
    return out

def preparar(B):
    fecho = B["close"].index + pd.Timedelta(minutes=1)              # instante em que a vela de 1m fecha
    C = B["close"].set_axis(fecho)
    D = {k: B[k].set_axis(fecho).shift(-1) for k in ("open", "high", "low")}   # minuto seguinte
    D["close"] = C
    # ATR de 5m (velas fechadas) alinhado ao minuto
    o5 = B["open"].resample("5min").first(); h5 = B["high"].resample("5min").max()
    l5 = B["low"].resample("5min").min(); c5 = B["close"].resample("5min").last()
    tr = np.maximum(h5 - l5, np.maximum((h5 - c5.shift(1)).abs(), (l5 - c5.shift(1)).abs()))
    atr = tr.ewm(span=14, adjust=False).mean() / c5
    atr.index = atr.index + pd.Timedelta(minutes=5)
    D["atrp"] = atr.reindex(fecho, method="ffill")
    qv = B["qvol"].set_axis(fecho)
    q24 = qv.rolling(1440, min_periods=720).sum()
    q5 = q24[q24.index.minute % 5 == 0]
    U = (q5.rank(axis=1, ascending=False) <= 100).reindex(fecho, method="ffill").fillna(False)
    # balança de choque com 1h: usa o close de 1m nos minutos cheios e o volume de 1h (60 velas)
    ch = C[C.index.minute == 0]
    qh = qv.rolling(60, min_periods=60).sum(); qh = qh[qh.index.minute == 0]
    r = ch.pct_change(fill_method=None); zz = r / r.rolling(168, min_periods=84).std()
    forte = qh > 2 * qh.rolling(24, min_periods=12).mean().shift(1)
    up = ((zz > 4.0) & forte).astype(float).rolling(12, min_periods=1).max()
    dn = ((zz < -4.0) & forte).astype(float).rolling(12, min_periods=1).max()
    SL = (up * (1 - dn) * 100).reindex(fecho, method="ffill").fillna(0)
    SS = (dn * (1 - up) * 100).reindex(fecho, method="ffill").fillna(0)
    return D, U, SL, SS

def perfil(nome, lev_padrao):
    base = {"TAXA": 0.0005, "SLIP": 0.0002, "REENTRA": False, "TEMPO_MAX": 720, "COOLDOWN_BARRAS": 5, "PAUSA_BARRAS": 30,
            "TRAVA_MIN": 0.001, "TRAVA_MAX": 0.08, "TP_MIN": 0.0, "TP_MAX": 1000.0, "LEV_PAPER": lev_padrao,
            "IGNORA_SINAIS_INICIAIS": True}
    if nome == "CHXM 2:1":  return {**base, "TRAVA_K": 2.0, "TP_ATR_K": 4.0, "LEV_TETO": None}
    if nome == "CHXM 3:1":  return {**base, "TRAVA_K": 2.0, "TP_ATR_K": 6.0, "LEV_TETO": None}
    if nome == "CHX 10x 3:1": return {**base, "TRAVA_K": 2.0, "TP_ATR_K": 6.0, "LEV_TETO": 10}
