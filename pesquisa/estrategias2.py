"""Famílias de estratégias para a pesquisa ampla (independentes da balança K).

Todas devolvem pesos (horas x pares) decididos com dados até o fechamento da hora t;
o motor aplica o peso ao retorno da hora t+1. Exposição bruta normalizada a 1x.
"""
import numpy as np
import pandas as pd

def vol(R, n=168):
    return R.rolling(n, min_periods=n // 2).std()

def rebalanceia(W, reb):
    if reb <= 1:
        return W
    marca = np.arange(len(W)) % reb == 0
    return W[marca].reindex(W.index).ffill()

def normaliza(W):
    W = W.fillna(0.0)
    s = W.abs().sum(axis=1).replace(0, np.nan)
    return W.div(s, axis=0).fillna(0.0)

def _top_bottom(score, k):
    rk = score.rank(axis=1)
    n = score.notna().sum(axis=1).values[:, None]
    W = (rk > n - k).astype(float) - (rk <= k).astype(float)
    W = W.where(score.notna(), 0.0)
    return W * (n >= 2 * k)   # precisa de pares suficientes

def beta_btc(R, n=168):
    b = R["BTCUSDT"]
    cov = R.rolling(n, min_periods=n // 2).cov(b)
    return cov.div(b.rolling(n, min_periods=n // 2).var(), axis=0)

# 1) momento entre pares (com opção de pular as últimas 'skip' horas)
def xs_mom(C, R, L, reb, k, skip=0, inverso=False):
    s = (C.shift(skip) / C.shift(L + skip) - 1) / vol(R)
    W = _top_bottom(s, k)
    return normaliza(rebalanceia(-W if inverso else W, reb))

# 2) momento/reversão do resíduo contra o BTC
def xs_resid(C, R, L, reb, k, inverso=False):
    beta = beta_btc(R)
    res = R.sub(beta.mul(R["BTCUSDT"], axis=0))
    s = res.rolling(L, min_periods=L).sum() / vol(R)
    s["BTCUSDT"] = np.nan
    W = _top_bottom(s, k)
    return normaliza(rebalanceia(-W if inverso else W, reb))

# 3) tendência por par: sinal do retorno de L horas
def ts_trend(C, R, L, reb):
    W = np.sign(C / C.shift(L) - 1) / vol(R)
    return normaliza(rebalanceia(W, reb))

# 4) cruzamento de médias exponenciais
def ema_cross(C, R, fast, slow, reb):
    W = np.sign(C.ewm(span=fast).mean() - C.ewm(span=slow).mean()) / vol(R)
    W = W.where(C.notna())
    return normaliza(rebalanceia(W, reb))

# 5) rompimento de canal com saída no canal oposto de N/2
def breakout(C, H, Lo, R, N):
    top = H.rolling(N).max().shift(1).values
    bot = Lo.rolling(N).min().shift(1).values
    xt = H.rolling(max(N // 2, 2)).max().shift(1).values
    xb = Lo.rolling(max(N // 2, 2)).min().shift(1).values
    c = C.values
    pos = np.zeros_like(c)
    cur = np.zeros(c.shape[1])
    for t in range(c.shape[0]):
        ct = c[t]
        cur = np.where(ct > top[t], 1.0, np.where(ct < bot[t], -1.0, cur))
        cur = np.where((cur > 0) & (ct < xb[t]), 0.0, cur)
        cur = np.where((cur < 0) & (ct > xt[t]), 0.0, cur)
        cur = np.where(np.isnan(ct), 0.0, cur)
        pos[t] = cur
    W = pd.DataFrame(pos, index=C.index, columns=C.columns) / vol(R)
    return normaliza(W)

# 6) choque de 1h: segue (ou desfaz) movimentos acima de z desvios, por h horas
def choque(C, R, z, h, seguir):
    zz = R / vol(R)
    s = np.sign(zz) * (zz.abs() > z)
    s = s if seguir else -s
    W = s.rolling(h, min_periods=1).sum()
    return normaliza(W)

# 7) carry de funding
def carry(FR, L, reb, k):
    med = FR.replace(0, np.nan).ffill().rolling(L, min_periods=L // 2).mean()
    W = -_top_bottom(med, k)
    return normaliza(rebalanceia(W, reb))

# 8) momento só comprado, ligado apenas com o BTC acima da média de M horas
def mom_long_filtro(C, R, L, reb, k, M):
    s = (C / C.shift(L) - 1) / vol(R)
    W = _top_bottom(s, k).clip(lower=0)
    btc = C["BTCUSDT"]
    liga = (btc > btc.rolling(M).mean()).astype(float)
    W = W.mul(liga, axis=0)
    return normaliza(rebalanceia(W, reb))
