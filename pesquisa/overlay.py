"""Controles de risco sobre a carteira combinada escolhida às cegas (fora da amostra):
alvo de volatilidade e freio por queda. Liquidação pelos pavios (perda intrabar > 90%)."""
import numpy as np
import pandas as pd
import motor as M
import wf_combo as WC   # reaproveita W (pesos fora da amostra) e os pavios

W, R, FR, CAP = WC.W, WC.R, WC.FR, 500.0
base = M.rodar(W, R, FR, taxa=WC.CUSTO)

def escala_vol(alvo_anual, teto, janela_d=30):
    vol = base.rolling(24 * janela_d, min_periods=24 * 10).std() * np.sqrt(8760)
    e = (alvo_anual / vol).clip(upper=teto).shift(1)
    return e.where(np.arange(len(e)) % 24 == 0).ffill().fillna(1.0)   # ajusta 1x por dia

def rodar_com_escala(esc, freio=None, ini="2024-01-01"):
    Ws = W.mul(esc, axis=0)
    r = M.rodar(Ws, R, FR, taxa=WC.CUSTO).loc[ini:]
    Wp = Ws.shift(1).fillna(0).loc[ini:]
    pior = (Wp.clip(lower=0) * WC.adv_l.loc[Wp.index] + Wp.clip(upper=0) * WC.adv_s.loc[Wp.index]).sum(axis=1)
    eq, pico, out, liq = CAP, CAP, [], None
    for t, ri, pi in zip(r.index, r.values, pior.values):
        if eq > 0 and pi <= -0.9:
            eq, liq = 0.0, t
        elif eq > 0:
            f = 1.0
            if freio and eq < pico * (1 - freio):   # abaixo do freio: metade da exposição
                f = 0.5
            eq *= 1 + ri * f
            pico = max(pico, eq)
        out.append(eq)
    return pd.Series(out, index=r.index), liq

if __name__ == "__main__":
    print(f"{'config':<34}{'set/2026':>10}{'pior queda':>11}{'lucro/mês médio':>16}{'liquidou':>11}")
    for alvo in (0.5, 1.0, 1.5, 2.0):
        for teto in (3, 5):
            for freio in (None, 0.25):
                s, liq = rodar_com_escala(escala_vol(alvo, teto), freio)
                nome = f"alvo vol {alvo:.0%} teto {teto}x freio {freio or '-'}"
                print(f"{nome:<34}{s.iloc[-1]:>10.0f}{(s / s.cummax() - 1).min():>11.0%}{(s.iloc[-1] - CAP) / 33:>16.0f}{str(liq.date()) if liq is not None else '-':>11}")
