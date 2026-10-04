"""Simula a banca de 500 com as apostas de valor (Kelly fracionado, teto por aposta),
e testa vieses simples do mercado na Pinnacle (fechamento)."""
import numpy as np
import pandas as pd
import estrategias as S

def simular(A, frac=0.25, teto=0.03, cap=500.0, ini="2019-07-01"):
    A = A[A.data >= ini].copy()
    A["f"] = (frac * A.ev / (A.odd - 1)).clip(upper=teto)
    eq, serie = cap, []
    for dia, g in A.groupby("data"):               # apostas do dia com a banca do início do dia
        stake = g.f.values * eq
        eq += float((stake * g.lucro.values).sum())
        serie.append((dia, eq))
    s = pd.Series(dict(serie))
    m = s.resample("ME").last().ffill()
    return s, m

CEN = [
    ("máx. do mercado (fechamento), odd<=4, valor>2%", S.apostas_valor("pc", "mc", 0.02, 4.0)),
    ("Bet365 sozinha (abertura), odd<=4, valor>0%",    S.apostas_valor("p", "b", 0.0, 4.0)),
    ("Betfair 2% (fechamento), odd<=4, valor>5%",      S.apostas_valor("pc", "ec", 0.05, 4.0)),
    ("gols 2.5 máx. (fechamento), valor>2%",           S.apostas_gols("pc", "mc", 0.02)),
]
print("== banca 500, 1/4 de Kelly, máx. 3% por aposta, jul/2019 em diante ==")
for nome, A in CEN:
    s, m = simular(A)
    meses = len(m); dd = (s / s.cummax() - 1).min()
    ganho = m.diff().fillna(m.iloc[0] - 500)
    print(f"{nome}\n   apostas/mês {len(A[A.data >= '2019-07-01']) / meses:.0f} | final {s.iloc[-1]:,.0f} | pior queda {dd:.0%} | "
          f"lucro médio/mês {ganho.mean():,.0f} | últimos 12 meses/mês {ganho.iloc[-12:].mean():,.0f}")

print("\n== vieses simples (apostar sempre, odd de fechamento da Pinnacle) ==")
J = S.J.dropna(subset=["pc_H", "pc_D", "pc_A"])
for x, nome in (("H", "mandante"), ("D", "empate"), ("A", "visitante")):
    for lo, hi in ((1.0, 1.5), (1.5, 2.5), (2.5, 4.0), (4.0, 8.0), (8.0, 100.0)):
        o = J[f"pc_{x}"]; sel = (o >= lo) & (o < hi)
        luc = np.where(J.res[sel] == x, o[sel] - 1, -1.0)
        if len(luc) > 300:
            print(f"   {nome:<10} odd {lo:>4}-{hi:<5} n={len(luc):>6}  ROI {luc.mean():+.1%}")
