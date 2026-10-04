"""Balanças (pontuação LONG e SHORT de 0 a 100 por par e por vela de 5m).

original  : réplica vetorizada do calcular_score() do hydra_direcional_teste.py (sem memória)
momento   : força relativa de 14 dias entre os pares (top 5 = LONG, fundo 5 = SHORT)
choque    : seguir movimentos de 1h acima de 3,5 desvios por 12 horas
mom_gatilho: momento + gatilho de tendência curta (EMA9>EMA21 em 5m e 15m no mesmo sentido)
Nenhuma usa sinais da balança K.
"""
import numpy as np
import pandas as pd

def sessao_bonus(idx):
    h = idx.hour
    b = np.select([(h >= 13) & (h < 17), (h >= 13) & (h < 22), (h >= 8) & (h < 17), (h >= 2) & (h < 9)],
                  [5, 2, 3, -5], -10)
    return pd.Series(b, index=idx)

def regime(I):
    r5, r15 = I["5m"], I["15m"]
    caos = (r5["vol_rat"] > 3.5) | (((r5["high"] - r5["low"]) / (r5["close"] - r5["open"]).abs().replace(0, np.nan)) > 4) \
        | ((r5["close"] / r5["close"].shift(1) - 1).abs() * 100 > 3)
    bull = 2 * (r5["close"] > r5["ema200"]) + (r5["ema9"] > r5["ema21"]) + (r5["ema21"] > r5["ema50"]) + \
        (r15["ema9"] > r15["ema21"]) + (r5["rsi"] > 50) + (r15["rsi"] > 50) + (r5["hist"] > 0)
    bear = 2 * (r5["close"] < r5["ema200"]) + (r5["ema9"] < r5["ema21"]) + (r5["ema21"] < r5["ema50"]) + \
        (r15["ema9"] < r15["ema21"]) + (r5["rsi"] < 50) + (r15["rsi"] < 50) + (r5["hist"] < 0)
    rng = ((r5["ema9"] - r5["ema21"]).abs() / r5["close"] < 0.001) & (r5["rsi"] > 40) & (r5["rsi"] < 60)
    reg = pd.DataFrame("RANGE", index=r5["close"].index, columns=r5["close"].columns)
    reg[bear >= 4] = "BEAR"; reg[bull >= 4] = "BULL"; reg[bear >= 6] = "BEAR_FORTE"; reg[bull >= 6] = "BULL_FORTE"
    reg[rng] = "RANGE"; reg[caos] = "CAOS"
    return reg

def original(I, CAP_PRECO=60, FLUXO=8, H1=6):
    r5, r15, r1 = I["5m"], I["15m"], I["1h"]
    reg = regime(I)
    ses = sessao_bonus(r5["close"].index)
    out = {}
    for lado in ("L", "S"):
        lg = lado == "L"
        c = (lambda a, b: a > b) if lg else (lambda a, b: a < b)
        t = np.where(c(r5["ema9"], r5["ema21"]) & c(r5["ema21"], r5["ema50"]), 15, np.where(c(r5["ema9"], r5["ema21"]), 8, 0)) \
            + 10 * c(r15["ema9"], r15["ema21"]) + 5 * c(r5["close"], r5["ema200"])
        rsi = r5["rsi"]; h0 = r5["hist"]; h1 = r5["hist"].shift(1)
        if lg:
            m = np.where((rsi >= 45) & (rsi <= 65), 10, np.where(((rsi >= 40) & (rsi < 45)) | ((rsi > 65) & (rsi <= 70)), 5, 0)) \
                + np.where((h0 > 0) & (h1 > 0), 10, np.where(h0 > 0, 5, 0)) + 5 * (r5["stoch"] < 70)
            f = np.where(r5["buy_ratio"] > 0.55, FLUXO, np.where(r5["buy_ratio"] < 0.45, -FLUXO, 0))
        else:
            m = np.where((rsi >= 35) & (rsi <= 55), 10, np.where(((rsi >= 30) & (rsi < 35)) | ((rsi > 55) & (rsi <= 60)), 5, 0)) \
                + np.where((h0 < 0) & (h1 < 0), 10, np.where(h0 < 0, 5, 0)) + 5 * (r5["stoch"] > 30)
            f = np.where(r5["buy_ratio"] < 0.45, FLUXO, np.where(r5["buy_ratio"] > 0.55, -FLUXO, 0))
        v = np.where(r5["vol_rat"] >= 1.5, 10, np.where(r5["vol_rat"] >= 1.2, 6, np.where(r5["vol_rat"] >= 1.0, 3, 0))) \
            + np.where(r15["vol_rat"] >= 1.2, 10, np.where(r15["vol_rat"] >= 1.0, 5, 0))
        up = (r1["ema9"] > r1["ema21"]) & (r1["close"] > r1["ema200"])
        dn = (r1["ema9"] < r1["ema21"]) & (r1["close"] < r1["ema200"])
        hh = np.where(up, H1, np.where(dn, -H1, 0)) * (1 if lg else -1)
        a = 8 * (r5["atr"] > r5["atr_ma"] * 0.8) + 7 * ((r5["bb_wid"] > r5["bb_wid_ma"] * 0.5) | r5["bb_wid_ma"].isna())
        preco = t + m + a
        exc = np.maximum(0, preco - CAP_PRECO)
        pen = -10 * (reg == "RANGE") - 20 * (reg.isin(["BEAR", "BEAR_FORTE"]) if lg else reg.isin(["BULL", "BULL_FORTE"]))
        s = preco - exc + v + f + hh + pen
        s = s.add(ses, axis=0)
        out[lado] = s.clip(0, 100).where(r5["close"].notna(), 0).fillna(0)
    return out["L"], out["S"]

def momento(I, horas=336, k=5, univ=None):
    c = I["5m"]["close"]
    ch = c[c.index.minute == 0]                                   # decide de hora em hora
    ret = ch / ch.shift(horas) - 1
    vol = ch.pct_change(fill_method=None).rolling(168, min_periods=84).std()
    s = ret / vol
    if univ is not None:
        s = s.where(univ.reindex(s.index).fillna(False))
    rk = s.rank(axis=1); n = s.notna().sum(axis=1).values[:, None]
    L = (rk > n - k).astype(float) * 100; S = (rk <= k).astype(float) * 100
    L = L * (n >= 2 * k); S = S * (n >= 2 * k)
    return L.reindex(c.index, method="ffill").fillna(0), S.reindex(c.index, method="ffill").fillna(0)

def choque(I, z=3.5, h=12):
    c = I["5m"]["close"]
    ch = c[c.index.minute == 0]
    r = ch.pct_change(fill_method=None)
    zz = r / r.rolling(168, min_periods=84).std()
    up = (zz > z).astype(float).rolling(h, min_periods=1).max()
    dn = (zz < -z).astype(float).rolling(h, min_periods=1).max()
    L = (up * (1 - dn)) * 100; S = (dn * (1 - up)) * 100
    return L.reindex(c.index, method="ffill").fillna(0), S.reindex(c.index, method="ffill").fillna(0)

def mom_gatilho(I, univ=None):
    L, S = momento(I, univ=univ)
    r5, r15 = I["5m"], I["15m"]
    up = (r5["ema9"] > r5["ema21"]) & (r15["ema9"] > r15["ema21"])
    dn = (r5["ema9"] < r5["ema21"]) & (r15["ema9"] < r15["ema21"])
    return L.where(up, 0), S.where(dn, 0)

def choque_v(C, z=3.5, h=12, modo="base", QV=None):
    """Variantes do choque (C: closes de 5m; QV: volume em USDT de 5m).
    base   : choque de 1h acima de z desvios, segue por h horas
    residuo: idem, mas no movimento próprio da moeda (descontado o BTC x beta de 7 dias)
    volume : só choques cuja hora teve volume >= 2x a média das últimas 24 horas
    btc    : só choques no sentido da tendência do BTC (preço vs média de 50 horas)"""
    ch = C[C.index.minute == 0]
    r = ch.pct_change(fill_method=None)
    if modo == "residuo":
        b = r["BTCUSDT"]
        beta = r.rolling(168, min_periods=84).cov(b).div(b.rolling(168, min_periods=84).var(), axis=0)
        r = r.sub(beta.mul(b, axis=0)); r["BTCUSDT"] = np.nan
    zz = r / r.rolling(168, min_periods=84).std()
    up, dn = zz > z, zz < -z
    if modo == "volume":
        qh = QV.rolling(12, min_periods=12).sum()
        qh = qh[qh.index.minute == 0]
        forte = qh > 2 * qh.rolling(24, min_periods=12).mean().shift(1)
        up &= forte; dn &= forte
    if modo == "btc":
        btc = ch["BTCUSDT"]; alta = btc > btc.rolling(50).mean()
        up = up.mul(alta, axis=0).astype(bool); dn = dn.mul(~alta, axis=0).astype(bool)
    up = up.astype(float).rolling(h, min_periods=1).max(); dn = dn.astype(float).rolling(h, min_periods=1).max()
    L = (up * (1 - dn)) * 100; S = (dn * (1 - up)) * 100
    return L.reindex(C.index, method="ffill").fillna(0), S.reindex(C.index, method="ffill").fillna(0)
