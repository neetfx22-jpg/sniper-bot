"""Teste grande da selecao de particulas: 200 mil chaves sorteadas na faixa real do puzzle 71,
todas as estrategias medidas nas MESMAS chaves (comparacao pareada)."""
import math
import random
import statistics
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from simular_ordem import CHUNK, Ordem
from simular_particulas import OrdemB

M = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
FAIXA = 1 << 70
N = -(-FAIXA // CHUNK)
ests = {
    "sequencial": Ordem(FAIXA, "sequencial"),
    "salto": Ordem(FAIXA, "salto"),
    "onda10": Ordem(FAIXA, "onda", franjas=10),
    "part10": OrdemB(N, 10),
    "part20": OrdemB(N, 20),
}


def fr(nome, o, d):
    return o.fracao(d // CHUNK) if nome.startswith("part") else o.fracao(d, FAIXA)


rnd = random.Random(71071)
res = {k: [] for k in ests}
for i in range(M):
    d = rnd.randrange(FAIXA)
    for k, o in ests.items():
        res[k].append(fr(k, o, d))
    if (i + 1) % 50_000 == 0:
        print(f"... {i + 1} chaves", flush=True)
print(f"\n{M} chaves sorteadas, faixa real do puzzle 71")
for k, xs in res.items():
    print(f"  {k:<11} media={statistics.fmean(xs):.4f} (+-{1.96 * statistics.stdev(xs) / math.sqrt(M):.4f})")
print("\nconfronto direto contra part10 (mesmas chaves):")
for k in ests:
    if k == "part10":
        continue
    d = [a - b for a, b in zip(res["part10"], res[k])]
    ic = 1.96 * statistics.stdev(d) / math.sqrt(M)
    print(f"  part10 - {k:<11} = {statistics.fmean(d):+.4f} (+-{ic:.4f});  part10 ganha em {sum(x < 0 for x in d) / M:.1%}")
