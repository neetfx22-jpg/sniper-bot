"""Compara as estrategias chave a chave (mesmas chaves para todas) em 1 milhao de chaves na faixa do puzzle 71."""
import sys, random, statistics as st, math
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from simular_ordem import Ordem
faixa = 1 << 70
o = {"salto": Ordem(faixa, "salto"), "onda10": Ordem(faixa, "onda", franjas=10), "onda20": Ordem(faixa, "onda", franjas=20), "sequencial": Ordem(faixa, "sequencial")}
rnd = random.Random(20261021)
N = 1_000_000
res = {k: [] for k in o}
for _ in range(N):
    d = rnd.randrange(faixa)
    for k, v in o.items():
        res[k].append(v.fracao(d, faixa))
for k, xs in res.items():
    print(f"{k:<11} media={st.fmean(xs):.4f} +-{1.96*st.stdev(xs)/math.sqrt(N):.4f}")
for a, b in [("onda10", "onda20"), ("onda10", "salto"), ("salto", "sequencial")]:
    dif = [x - y for x, y in zip(res[a], res[b])]
    m = st.fmean(dif); ic = 1.96 * st.stdev(dif) / math.sqrt(N)
    vit = sum(1 for x in dif if x < 0) / N
    print(f"{a} - {b}: diferenca media={m:+.4f} (+-{ic:.4f}), {a} ganha em {vit:.1%} das chaves")
# F10 ganha quando F20 demora?
lent = [i for i in range(N) if res["onda20"][i] > 0.8]
print(f"quando onda20 > 0.8: onda10 media={st.fmean(res['onda10'][i] for i in lent):.3f}; quando onda20 < 0.2: onda10 media={st.fmean(res['onda10'][i] for i in range(N) if res['onda20'][i] < 0.2):.3f}")
print("correlacao onda10 x onda20:", round(st.correlation(res['onda10'], res['onda20']), 3))
