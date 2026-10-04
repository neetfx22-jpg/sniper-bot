"""Fluxo de caixa REAL: gera o conjunto 4.0.0 treinado só até 31/12/2023 (sem ver o futuro)
e joga esses MESMOS jogos fixos em todos os sorteios de 2024 a out/2026, contando TODOS os prémios.
Mostra se, somando prémios pequenos e jackpots, a estratégia se pagava."""
import numpy as np
import pandas as pd
import base as B

T = B.todas_combinacoes(); pc = B.popcount
for N_SEL in (10000, 1000, 100):
    # seleção treinada só com dados ATÉ 2023 (honesto: não viu 2024-2026)
    tre = B.indices("2023-01-01", "2023-12-31")
    c11 = np.zeros(len(T), np.int16); c12 = np.zeros(len(T), np.int16); mau = np.zeros(len(T), bool)
    for i in tre:
        ac = pc(T & B.D[i]); c11 += ac == 11; c12 += ac == 12; mau |= ac >= 13
    cand = np.where((c12 >= 4) & (~mau))[0]
    sel = T[cand[np.argsort(-c11[cand])[:N_SEL]]]

    idx = B.indices("2024-01-01")
    reg = []
    for i in idx:
        ac = pc(sel & B.D[i])
        reg.append({"data": B.datas[i], "custo": N_SEL * B.PRECO[i], "premio": B.PR[i, ac].sum(),
                    "p15": int((ac == 15).sum()), "p14": int((ac == 14).sum())})
    df = pd.DataFrame(reg).set_index("data")
    custo = df.custo.sum(); premio = df.premio.sum()
    print(f"\n===== {N_SEL} jogos fixos (gerados com dados até 2023), jogados de 01/2024 a 10/2026 =====")
    print(f"sorteios: {len(df)} | custo por sorteio: R$ {N_SEL*B.PRECO[idx[-1]]:,.0f} | jackpots (15 pts) acertados: {df.p15.sum()} | 14 pts: {df.p14.sum()}".replace(",", "."))
    print(f"GASTO TOTAL:   R$ {custo:,.0f}".replace(",", "."))
    print(f"GANHO TOTAL:   R$ {premio:,.0f}  (todos os prémios, 11 a 15)".replace(",", "."))
    print(f"RESULTADO:     R$ {premio-custo:,.0f}  ->  recuperou {premio/custo:.1%} do que gastou".replace(",", "."))
    if df.p15.sum() == 0:
        print("   (sem nenhum jackpot neste conjunto honesto — os jackpots do teste anterior eram de outra seleção, feita olhando o futuro)")
