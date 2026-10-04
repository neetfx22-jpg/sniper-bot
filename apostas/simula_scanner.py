"""Simula a regra do scanner no histórico das 6 ligas dele, com casas parecidas às portuguesas.

Regra: sinal quando odd da casa x prob. justa - 1 > 2% e odd <= 4.
Prob. justa = Pinnacle sem margem (ou Betfair, onde a Pinnacle falta).
Mede: sinais por semana, taxa de acerto real vs esperada, lucro (1 u por aposta) e valor contra o fecho.
"""
import numpy as np
import pandas as pd
import estrategias as S

LIGAS = ["P1", "E0", "SP1", "I1", "D1", "F1"]
J = S.J[S.J.liga.isin(LIGAS)].copy()

def justa(d, pre):
    inv = 1 / d[[f"{pre}_{x}" for x in "HDA"]].values
    return inv / inv.sum(1, keepdims=True)

def simula(casa, ref, ref_fecho, lim=0.02, om=4.0):
    cols = [f"{casa}_{x}" for x in "HDA"] + [f"{ref}_{x}" for x in "HDA"]
    d = J.dropna(subset=cols).reset_index(drop=True)
    pj = justa(d, ref)
    pf = justa(d, ref_fecho) if ref_fecho else None
    tem_f = d[[f"{ref_fecho}_{x}" for x in "HDA"]].notna().all(1).values if ref_fecho else None
    O = d[[f"{casa}_{x}" for x in "HDA"]].values
    L = []
    for i, x in enumerate("HDA"):
        ev = O[:, i] * pj[:, i] - 1
        ok = (ev > lim) & (O[:, i] <= om)
        L.append(pd.DataFrame({"data": d.data[ok].values, "odd": O[ok, i], "pj": pj[ok, i], "ev": ev[ok],
                               "ganhou": (d.res[ok] == x).values,
                               "clv": np.where(tem_f[ok], O[ok, i] * pf[ok, i] - 1, np.nan) if ref_fecho else np.nan}))
    A = pd.concat(L, ignore_index=True)
    A["lucro"] = np.where(A.ganhou, A.odd - 1, -1.0)
    return A, d.data.min(), d.data.max()

def linha(nome, A, ini, fim):
    sem = max(1, (fim - ini).days / 7)
    if len(A) == 0:
        return print(f"{nome:<44} sem sinais")
    t = A.lucro.mean() / (A.lucro.std() / np.sqrt(len(A)))
    print(f"{nome:<44} {len(A):>5} sinais ({len(A) / sem:.1f}/sem) | acerto {A.ganhou.mean():.1%} (esperado {A.pj.mean():.1%}) | "
          f"odd média {A.odd.mean():.2f} | ROI {A.lucro.mean():+.1%} (t={t:.1f}) | valor contra o fecho {A.clv.mean():+.1%}")

print("== 6 ligas do scanner, regra do scanner (valor > 2%, odd <= 4) ==\n")
for nome, casa, ref, rf in [
    ("Bwin abertura vs Pinnacle abertura", "w", "p", "pc"),
    ("Bwin fecho vs Pinnacle fecho", "wc", "pc", "pc"),
    ("William Hill abertura vs Pinnacle abertura", "h", "p", "pc"),
    ("William Hill fecho vs Pinnacle fecho", "hc", "pc", "pc"),
    ("Bet365 abertura vs Pinnacle abertura", "b", "p", "pc"),
    ("Bwin fecho vs Betfair fecho (2024-26)", "wc", "ec", "ec"),
    ("Bet365 fecho vs Betfair fecho (2024-26)", "bc", "ec", "ec"),
]:
    A, ini, fim = simula(casa, ref, rf)
    linha(nome, A, ini, fim)

print("\n== por ano (Bwin abertura vs Pinnacle abertura) ==")
A, _, _ = simula("w", "p", "pc")
print(A.groupby(A.data.dt.year).agg(sinais=("lucro", "size"), acerto=("ganhou", "mean"), esperado=("pj", "mean"),
                                    roi=("lucro", "mean"), clv=("clv", "mean")).round(3).to_string())

print("\n== limiar de valor (Bwin abertura vs Pinnacle abertura) ==")
for lim in (0.0, 0.02, 0.04, 0.06, 0.10):
    A, ini, fim = simula("w", "p", "pc", lim=lim)
    linha(f"valor > {lim:.0%}", A, ini, fim)

print("\n== simulação de banca: 100 €, 2 € por sinal (Bwin abertura vs Pinnacle abertura) ==")
A, ini, fim = simula("w", "p", "pc")
A = A.sort_values("data"); banca = 100 + (A.lucro * 2).cumsum()
m = (A.lucro * 2).groupby(A.data.dt.to_period("M")).sum()
print(f"final {banca.iloc[-1]:.0f} € em {(fim - ini).days / 365:.1f} anos | lucro médio/mês {m.mean():+.2f} € | "
      f"meses positivos {(m > 0).mean():.0%} | pior momento {banca.min():.0f} €")
