"""Traduz (família, parâmetros) do grade2.py em pesos."""
import estrategias2 as E

def pesos(C, H, Lo, R, FR, nome, p):
    if nome in ("xs_mom", "xs_rev"):   return E.xs_mom(C, R, **p)
    if nome in ("res_mom", "res_rev"): return E.xs_resid(C, R, **p)
    if nome == "ts_trend":     return E.ts_trend(C, R, **p)
    if nome == "ema_cross":    return E.ema_cross(C, R, **p)
    if nome == "breakout":     return E.breakout(C, H, Lo, R, **p)
    if nome == "choque":       return E.choque(C, R, **p)
    if nome == "carry":        return E.carry(FR, **p)
    if nome == "mom_long_btc": return E.mom_long_filtro(C, R, **p)
    raise ValueError(nome)
