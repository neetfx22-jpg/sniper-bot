"""De 100 € a 1 milhão? Junta os 3 mercados de valor (1X2, gols 2.5, handicap asiático),
simula a banca com juros compostos (1/4 de Kelly, máx. 3% da banca por aposta) e mede mês a mês.

Período A (ref. Pinnacle): jul/2019–jun/2025.  Período B (ref. Betfair, a única que ainda existe): 2024–2026.
Teto por aposta = quanto as casas aceitam de um apostador que ganha (cenários).
"""
import numpy as np
import pandas as pd
import estrategias as S
import handicap as AH
import ref_betfair as RB

def gols_ref(ref_o, ref_u, odd_o, odd_u, lim):
    J = S.J; d = J.dropna(subset=[ref_o, ref_u, odd_o, odd_u]).reset_index(drop=True)
    inv = 1 / d[[ref_o, ref_u]].values; pj = inv / inv.sum(1, keepdims=True); O = d[[odd_o, odd_u]].values
    L = []
    for i, lado in enumerate(("over", "under")):
        ev = O[:, i] * pj[:, i] - 1; ok = ev > lim; s = d[ok]
        g = s.over.values if lado == "over" else ~s.over.values
        L.append(pd.DataFrame({"data": s.data.values, "odd": O[ok, i], "ev": ev[ok], "lucro": np.where(g, O[ok, i] - 1, -1.0)}))
    return pd.concat(L, ignore_index=True)

def junta(*partes):
    return pd.concat([p[["data", "odd", "ev", "lucro"]] for p in partes], ignore_index=True).sort_values("data")

PER = {
    "A: ref. Pinnacle (jul/2019–jun/2025)": (junta(S.apostas_valor("pc", "mc", 0.02, 4.0), gols_ref("pco", "pcu", "mco", "mcu", 0.02),
                                                   AH.apostas("pcah", "mcah", "ahcl", 0.02)), "2019-07-01", "2025-06-30"),
    "B: ref. Betfair (2024–set/2026)": (junta(RB.apostas(0.02), gols_ref("eco", "ecu", "mco", "mcu", 0.02),
                                              AH.apostas("ecah", "mcah", "ahcl", 0.02)), "2024-01-01", "2026-09-30"),
}

def banca(A, teto, cap=100.0, frac=0.25):
    eq, s = cap, []
    for dia, g in A.groupby("data"):
        st = (frac * g.ev / (g.odd - 1)).clip(upper=0.03).values * eq
        if teto: st = np.minimum(st, teto)
        eq += float((st * g.lucro.values).sum()); s.append((dia, eq))
        if eq <= 1: break
    return pd.Series(dict(s))

for nome, (A, ini, fim) in PER.items():
    A = A[(A.data >= ini) & (A.data <= fim)]
    print(f"\n=== {nome}: {len(A)} apostas, ROI médio {A.lucro.mean():+.1%} ===")
    print(f"{'teto/aposta':>12}{'final':>14}{'meses +':>9}{'mês médio %':>12}{'pior mês %':>11}{'pior queda':>11}{'chega a 1 milhão?':>40}")
    for teto in (None, 1000, 200, 50, 20):
        s = banca(A, teto)
        m = s.resample("ME").last().ffill(); rm = m.pct_change().fillna(m.iloc[0] / 100 - 1)
        anos = (s.index[-1] - s.index[0]).days / 365
        cagr = (s.iloc[-1] / 100) ** (1 / anos) - 1 if s.iloc[-1] > 0 else -1
        if s.max() >= 1e6:
            chega = f"SIM, em {(s[s >= 1e6].index[0] - s.index[0]).days / 365:.1f} anos"
        elif teto:
            chega = f"NÃO: lucro trava em ~{(m.diff().iloc[-12:].mean()):,.0f} €/mês"
        else:
            chega = f"no ritmo: {np.log(1e4) / np.log(1 + cagr):.0f} anos" if cagr > 0 else "nunca"
        print(f"{str(teto or 'sem limite'):>12}{s.iloc[-1]:>14,.0f}{(rm > 0).mean():>9.0%}{rm.median() * 100:>12.1f}{rm.min() * 100:>11.1f}"
              f"{(s / s.cummax() - 1).min():>11.0%}{chega:>40}")
