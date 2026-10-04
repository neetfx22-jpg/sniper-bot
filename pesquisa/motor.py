"""Motor de backtest de carteira em velas de 1h.

- pesos decididos no fechamento da hora t-1 são aplicados ao retorno da hora t;
- taxa cobrada sobre o giro |Δw| (taker por padrão);
- funding cobrado nas horas em que ele ocorre (comprado paga taxa positiva).
"""
import numpy as np
import pandas as pd

TAXA_BINANCE = 0.0005   # taker
TAXA_MEXC    = 0.0001

def montar(base):
    V, F = base["velas"], base["funding"]
    idx = pd.date_range(min(v.index.min() for v in V.values()), max(v.index.max() for v in V.values()), freq="h")
    V = {p: v.reindex(idx) for p, v in V.items()}
    C  = pd.DataFrame({p: v["close"] for p, v in V.items()})
    H  = pd.DataFrame({p: v["high"] for p, v in V.items()})
    Lo = pd.DataFrame({p: v["low"] for p, v in V.items()})
    R  = C.pct_change(fill_method=None).fillna(0.0)
    FR = pd.DataFrame({p: f.groupby(f.index.floor("h")).last() for p, f in F.items()}).reindex(C.index).fillna(0.0)
    return C, H, Lo, R, FR

def rodar(W, R, FR, taxa=TAXA_BINANCE, alav=1.0):
    """Retorno horário da carteira com alavancagem 'alav' (exposição bruta = alav x patrimônio)."""
    Wp = W.shift(1).fillna(0.0) * alav          # posição em vigor durante a hora t
    bruto = (Wp * R).sum(axis=1)
    giro = (Wp - Wp.shift(1).fillna(0.0)).abs().sum(axis=1)
    custo = giro * taxa
    fund = (Wp * FR).sum(axis=1)                 # comprado paga funding positivo
    return bruto - custo - fund

def metricas(r):
    if len(r) == 0:
        return {}
    eq = (1 + r).cumprod()
    mens = (1 + r).groupby(r.index.tz_localize(None).to_period("M")).prod() - 1
    anos = len(r) / (24 * 365)
    dd = (eq / eq.cummax() - 1).min()
    sharpe = r.mean() / r.std() * np.sqrt(24 * 365) if r.std() > 0 else 0
    return {"ret_total": eq.iloc[-1] - 1, "cagr": eq.iloc[-1] ** (1 / anos) - 1 if eq.iloc[-1] > 0 else -1,
            "sharpe": sharpe, "max_dd": dd, "mes_medio": mens.mean(), "mes_pior": mens.min(),
            "mes_melhor": mens.max(), "meses_pos": (mens > 0).mean()}
