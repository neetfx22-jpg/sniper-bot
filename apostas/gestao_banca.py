"""A gestão de banca muda o resultado? Mesmas apostas, regras de banca diferentes.

Sequências reais (handicap asiático, 2019/20–2025/26, em ordem cronológica):
  A) apostador típico: aposta no mandante no fecho, odd da Bet365 (sem vantagem)
  B) apostas de valor: odd máxima > preço justo da Pinnacle + 2% (com vantagem)
Regras: fixa 2 €, 2% da banca, 1/4 Kelly, 3 para 1 (por dia: para com +3 unidades ou -1 unidade),
martingale (dobra após perda, até 6 vezes), Soros (reinveste o lucro até 3 vitórias seguidas).
Também 1.000 ordens embaralhadas das mesmas apostas para medir a chance de quebrar.
"""
import numpy as np
import pandas as pd
import handicap as AH

L = pd.read_pickle("dados/ah_fecho.pkl")
A = L[(L.lado == "H") & L.lucro_b365.notna()].assign(lucro=lambda d: d.lucro_b365, odd=lambda d: d.odd_b365)
A = A[["data", "odd", "lucro"]].assign(ev=0.0).sort_values("data").reset_index(drop=True)
B = AH.apostas("pcah", "mcah", "ahcl", 0.02)
B = B[B.data >= "2019-07-01"][["data", "odd", "lucro", "ev"]].reset_index(drop=True)

def joga(seq, regra, cap=100.0):
    banca, pico, dd = cap, cap, 0.0
    unidade_dia, dia, res_dia, parado = 0, None, 0.0, False
    mart, soros, giro = 0, 0.0, 0.0
    for d, o, l, ev in zip(seq.data.values, seq.odd.values, seq.lucro.values, seq.ev.values):
        if banca < 2: return banca, -1.0, giro, True
        if regra == "fixa 2 €":       st = 2.0
        elif regra == "2% da banca":  st = 0.02 * banca
        elif regra == "1/4 Kelly":
            st = max(0.0, min(0.03, 0.25 * ev / (o - 1))) * banca
        elif regra == "3 para 1":
            if d != dia: dia, res_dia, parado, unidade_dia = d, 0.0, False, 0.02 * banca
            if parado: continue
            st = unidade_dia
        elif regra == "martingale":   st = 2.0 * 2 ** mart
        elif regra == "Soros":        st = 2.0 + soros
        st = min(st, banca)
        if st <= 0: continue
        r = st * l; banca += r; giro += st
        if regra == "3 para 1":
            res_dia += r
            if res_dia >= 3 * unidade_dia or res_dia <= -unidade_dia: parado = True
        if regra == "martingale": mart = 0 if l > 0 else min(mart + 1, 6)
        if regra == "Soros":      soros = soros + r if (l > 0 and soros < 2.0 * 7) else 0.0
        pico = max(pico, banca); dd = min(dd, banca / pico - 1)
    return banca, dd, giro, False

REGRAS = ["fixa 2 €", "2% da banca", "1/4 Kelly", "3 para 1", "martingale", "Soros"]
rng = np.random.default_rng(1)
for nome, seq in (("A) apostador típico (sem vantagem)", A), ("B) apostas de valor (com vantagem)", B)):
    print(f"\n=== {nome}: {len(seq)} apostas, lucro médio por aposta {seq.lucro.mean():+.2%} ===")
    print(f"{'regra':<14}{'100 € viram':>13}{'pior queda':>12}{'lucro/apostado':>16}{'P(quebrar)':>12}{'mediana final':>15}")
    for r in REGRAS:
        if r == "1/4 Kelly" and seq.ev.max() <= 0:
            print(f"{r:<14}{'não aposta (sem vantagem, Kelly = 0)':>68}"); continue
        f, dd, giro, q = joga(seq, r)
        sims = [joga(seq.sample(frac=1, random_state=int(s)).sort_values("data", kind="stable") if False else
                     seq.iloc[rng.permutation(len(seq))].assign(data=seq.data.values), r) for s in range(200)]
        finais = np.array([s[0] for s in sims]); quebras = np.mean([s[3] for s in sims])
        print(f"{r:<14}{f:>13,.0f}{dd:>12.0%}{(f - 100) / giro if giro else 0:>+16.2%}{quebras:>12.0%}{np.median(finais):>15,.0f}")
