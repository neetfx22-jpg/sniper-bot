"""Indicadores iguais aos do get_dados() do hydra_direcional_teste.py, calculados para todos os
pares de uma vez, em 5m, 15m e 1h, e alinhados ao FECHO de cada vela de 5m (só velas fechadas)."""
import numpy as np
import pandas as pd

def _ind(o, h, l, c, v, tb):
    out = {}
    out["close"] = c
    out["ema9"] = c.ewm(span=9, adjust=False).mean()
    out["ema21"] = c.ewm(span=21, adjust=False).mean()
    out["ema50"] = c.ewm(span=50, adjust=False).mean()
    out["ema200"] = c.ewm(span=200, adjust=False).mean()
    d = c.diff()
    g = d.clip(lower=0).ewm(com=13, adjust=False).mean()
    p = (-d.clip(upper=0)).ewm(com=13, adjust=False).mean()
    out["rsi"] = 100 - 100 / (1 + g / p.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    out["hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    tr = np.maximum(h - l, np.maximum((h - c.shift(1)).abs(), (l - c.shift(1)).abs()))
    out["atr"] = tr.ewm(span=14, adjust=False).mean()
    out["atr_ma"] = out["atr"].rolling(20).mean()
    out["vol_rat"] = v / v.rolling(20).mean().replace(0, np.nan)
    mid = c.rolling(20).mean(); sd = c.rolling(20).std()
    out["bb_wid"] = (4 * sd) / mid
    out["bb_wid_ma"] = out["bb_wid"].rolling(20).mean()
    lo, hi = l.rolling(14).min(), h.rolling(14).max()
    out["stoch"] = 100 * (c - lo) / (hi - lo).replace(0, np.nan)
    out["buy_ratio"] = (tb / v.replace(0, np.nan)).rolling(3).mean()
    out["open"] = o; out["high"] = h; out["low"] = l
    return out

def calcular(B):
    """B: dict de DataFrames 5m (tempo x par). Devolve dict tf -> dict indicador -> DataFrame
    indexado pelo instante de FECHO da vela de 5m (t + 5min)."""
    idx5 = B["close"].index
    fecho5 = idx5 + pd.Timedelta(minutes=5)
    res = {}
    for tf, regra in (("5m", None), ("15m", "15min"), ("1h", "1h")):
        if regra is None:
            o, h, l, c, v, tb = (B[k] for k in ("open", "high", "low", "close", "vol", "tb"))
        else:
            o = B["open"].resample(regra).first(); h = B["high"].resample(regra).max()
            l = B["low"].resample(regra).min(); c = B["close"].resample(regra).last()
            v = B["vol"].resample(regra).sum(min_count=1); tb = B["tb"].resample(regra).sum(min_count=1)
        ind = _ind(o, h, l, c, v, tb)
        passo = pd.Timedelta(minutes=5 if regra is None else (15 if tf == "15m" else 60))
        al = {}
        for k, df in ind.items():
            df = df.copy(); df.index = df.index + passo            # índice = hora em que a vela FECHA
            al[k] = df.reindex(fecho5, method="ffill") if regra else df.set_axis(fecho5)
        res[tf] = al
    return res
