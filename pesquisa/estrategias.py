"""Estratégias independentes (não usam a balança K nem os sinais dela).

Cada função devolve uma matriz de pesos (horas x pares) já com a decisão tomada
só com informação até o fechamento da vela anterior. Exposição bruta = 1x (soma |w| = 1).
"""
import numpy as np
import pandas as pd

def _vol(R, n=168):
    return R.rolling(n, min_periods=n // 2).std()

def _rebalanceia(W, reb):
    """Só muda os pesos a cada 'reb' horas; no meio mantém os anteriores."""
    marca = (np.arange(len(W)) % reb == 0)
    return W[marca].reindex(W.index).ffill()

def _normaliza(W):
    s = W.abs().sum(axis=1).replace(0, np.nan)
    return W.div(s, axis=0).fillna(0.0)

def tendencia(C, R, L=168, reb=24):
    """Tendência por par: lado = sinal do retorno de L horas; peso inverso à volatilidade."""
    sinal = np.sign(C / C.shift(L) - 1)
    W = sinal / _vol(R)
    W = _rebalanceia(W, reb)
    return _normaliza(W.fillna(0))

def momento_cruzado(C, R, L=168, reb=24, k=4, inverso=False):
    """Momento entre pares: compra os k que mais subiram em L horas, vende os k que mais caíram."""
    ret = (C / C.shift(L) - 1) / _vol(R)
    rk = ret.rank(axis=1)
    n = ret.notna().sum(axis=1)
    W = (rk > n.values[:, None] - k).astype(float) - (rk <= k).astype(float)
    W = W.where(ret.notna(), 0.0)
    if inverso:
        W = -W
    W = _rebalanceia(W, reb)
    return _normaliza(W.fillna(0))

def carry_funding(FR, L=72, reb=8, k=4):
    """Carry de funding: vende os k com funding médio mais alto, compra os k mais baixos."""
    med = FR.rolling(L, min_periods=L // 2).mean()
    rk = med.rank(axis=1)
    n = med.notna().sum(axis=1)
    W = (rk <= k).astype(float) - (rk > n.values[:, None] - k).astype(float)
    W = W.where(med.notna(), 0.0)
    W = _rebalanceia(W, reb)
    return _normaliza(W.fillna(0))

def rompimento(C, H, Lo, R, N=72, reb=1):
    """Rompimento de canal (Donchian): compra no topo de N horas, vende no fundo; mantém até romper o lado oposto."""
    topo = H.rolling(N).max().shift(1)
    fundo = Lo.rolling(N).min().shift(1)
    s = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    s[C > topo] = 1.0
    s[C < fundo] = -1.0
    s = s.ffill().fillna(0.0)
    W = s / _vol(R)
    return _normaliza(W.fillna(0))
