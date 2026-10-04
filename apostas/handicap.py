"""Handicap asiático: valor contra o preço justo (Pinnacle ou Betfair), aposta na máxima do mercado.
Liquidação correta de linhas inteiras, meias e quartos (quarto = metade em cada linha vizinha)."""
import numpy as np
import pandas as pd
import estrategias as S

def liquida(dif, linha, odd):
    """dif = gols mandante - visitante (do ponto de vista do lado apostado); linha do lado apostado."""
    def meia(l):
        x = dif + l
        return np.where(x > 0, odd - 1, np.where(x == 0, 0.0, -1.0))
    q = np.round(linha * 4) % 2 == 1          # linha de quarto (.25 / .75)
    return np.where(q, 0.5 * (meia(linha - 0.25) + meia(linha + 0.25)), meia(linha))

def apostas(ref, odd, linha_col, lim, om=3.0):
    J = S.J
    d = J.dropna(subset=[f"{ref}_H", f"{ref}_A", f"{odd}_H", f"{odd}_A", linha_col]).reset_index(drop=True)
    inv = 1 / d[[f"{ref}_H", f"{ref}_A"]].values; pj = inv / inv.sum(1, keepdims=True)
    O = d[[f"{odd}_H", f"{odd}_A"]].values
    L = []
    for i, lado in enumerate(("H", "A")):
        ev = O[:, i] * pj[:, i] - 1; ok = (ev > lim) & (O[:, i] <= om); s = d[ok]
        dif = (s.gc - s.gf).values if lado == "H" else (s.gf - s.gc).values
        linha = s[linha_col].values if lado == "H" else -s[linha_col].values
        L.append(pd.DataFrame({"data": s.data.values, "odd": O[ok, i], "ev": ev[ok], "lucro": liquida(dif, linha, O[ok, i])}))
    return pd.concat(L, ignore_index=True).sort_values("data")

if __name__ == "__main__":
    for nome, ref, odd, lc in [("abertura, ref. Pinnacle", "pah", "mah", "ahl"), ("fechamento, ref. Pinnacle", "pcah", "mcah", "ahcl"),
                               ("fechamento, ref. Betfair", "ecah", "mcah", "ahcl")]:
        for lim in (0.0, 0.02, 0.05):
            A = apostas(ref, odd, lc, lim)
            if len(A) < 50: continue
            t = A.lucro.mean() / (A.lucro.std() / np.sqrt(len(A)))
            pa = A.groupby(A.data.dt.year).lucro.mean()
            print(f"handicap {nome}, valor>{lim:.0%}: n={len(A)} ROI {A.lucro.mean():+.1%} t={t:.1f} anos+ {(pa > 0).sum()}/{len(pa)}")
