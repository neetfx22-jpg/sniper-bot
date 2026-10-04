"""Jogos FIXOS: os mesmos N jogos em todos os sorteios. Custo por sorteio/mês e lucro mês a mês, com prémios reais.
A) N jogos aleatórios fixos (1.000 conjuntos diferentes, para ver a faixa de resultados)
B) os N jogos que mais lucraram no passado (treino), fixados e jogados DEPOIS (teste)"""
import itertools, sys
import numpy as np
import pandas as pd
from backtest import H, D, PR, PRECO

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
datas = pd.to_datetime([h["data"] for h in H], dayfirst=True)
LUT = np.array([bin(i).count("1") for i in range(1 << 13)], dtype=np.int8)
pc = lambda x: LUT[x & 0x1FFF] + LUT[(x >> 13) & 0x1FFF]

def joga(jogos, idx):
    """Devolve DataFrame por sorteio: custo, prémio, nº de 11..15 pontos."""
    linhas = []
    for i in idx:
        ac = pc(jogos & D[i])
        linhas.append({"data": datas[i], "custo": len(jogos) * PRECO[i], "premio": PR[i, ac].sum(),
                       **{f"p{k}": int((ac == k).sum()) for k in (11, 12, 13, 14, 15)}})
    return pd.DataFrame(linhas).set_index("data")

def mensal(df):
    m = df.resample("ME").sum(); m["lucro"] = m.premio - m.custo
    return m

atual = [i for i in range(len(H)) if PRECO[i] == 3.5]
print(f"== {N} jogos fixos | preço atual R$ 3,50 | {len(atual)} sorteios ({datas[atual[0]]:%d/%m/%Y} a {datas[atual[-1]]:%d/%m/%Y}) ==")
print(f"custo por sorteio: R$ {N * 3.5:,.2f} | sorteios por semana: 6 (seg-sáb) | custo por mês: ~R$ {N * 3.5 * 26:,.0f}".replace(",", "."))

# A) aleatórios fixos
rng = np.random.default_rng(7)
res = []
for s in range(1000):
    jg = np.array([sum(1 << d for d in rng.choice(25, 15, replace=False)) for _ in range(N)], dtype=np.int64)
    df = joga(jg, atual)
    res.append((df.premio.sum() - df.custo.sum(), df.p14.sum(), df.p15.sum(), df.premio.sum() / df.custo.sum()))
    if s == 0:
        m = mensal(df)
        print(f"\nA) um conjunto de {N} jogos aleatórios fixos, mês a mês:")
        print((m[["custo", "premio", "lucro", "p11", "p12", "p13", "p14", "p15"]]).round(0).astype(int).to_string())
R = np.array(res)
print(f"\nA) 1.000 conjuntos diferentes de {N} jogos aleatórios fixos, no período todo ({len(atual)} sorteios, custo R$ {N * 3.5 * len(atual):,.0f}):".replace(",", "."))
print(f"   lucro: mediana R$ {np.median(R[:, 0]):,.0f} | melhor R$ {R[:, 0].max():,.0f} | pior R$ {R[:, 0].min():,.0f} | "
      f"conjuntos com lucro: {(R[:, 0] > 0).mean():.1%} | fizeram 15 pontos: {(R[:, 2] > 0).mean():.1%} | retorno médio {R[:, 3].mean():.3f}".replace(",", "."))

# B) os N melhores do passado
treino = [i for i in range(len(H)) if pd.Timestamp("2023-01-01") <= datas[i] < pd.Timestamp("2025-07-01")]
teste = [i for i in range(len(H)) if datas[i] >= pd.Timestamp("2025-07-01")]
todas = np.fromiter((sum(1 << d for d in c) for c in itertools.combinations(range(25), 15)), dtype=np.int64, count=3268760)
lucro_tr = np.zeros(len(todas))
for i in treino:
    lucro_tr += PR[i, pc(todas & D[i])] - PRECO[i]
top = todas[np.argsort(-lucro_tr)[:N]]
tr, te = joga(top, treino), joga(top, teste)
print(f"\nB) os {N} jogos que MAIS lucraram de 01/2023 a 06/2025 ({len(treino)} sorteios):")
print(f"   no TREINO: custo R$ {tr.custo.sum():,.0f} | prémios R$ {tr.premio.sum():,.0f} | lucro R$ {tr.premio.sum() - tr.custo.sum():,.0f} | 15 pts: {tr.p15.sum()} | 14 pts: {tr.p14.sum()}".replace(",", "."))
print(f"   no TESTE (07/2025 a 10/2026, {len(teste)} sorteios, os mesmos {N} jogos fixos):")
m = mensal(te)
print((m[["custo", "premio", "lucro", "p11", "p12", "p13", "p14", "p15"]]).round(0).astype(int).to_string())
print(f"   TOTAL no teste: custo R$ {te.custo.sum():,.0f} | prémios R$ {te.premio.sum():,.0f} | lucro R$ {te.premio.sum() - te.custo.sum():,.0f} | "
      f"retorno {te.premio.sum() / te.custo.sum():.3f} | meses com lucro: {(m.lucro > 0).sum()}/{len(m)}".replace(",", "."))
