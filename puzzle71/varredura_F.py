"""Varredura do numero de franjas F em varios tamanhos de puzzle (simulacao exata da ordem do engine)."""
import math
import random
import statistics
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from simular_ordem import Ordem

FS = [1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 100, 200, 500, 1000]
PUZZLES = [40, 71, 80, 100, 135]
N = 50_000
print(f"fracao media da faixa ate achar a chave ({N} chaves sorteadas por celula, IC 95% ~ +-0,0025)\n")
print("F      " + "".join(f"p{p:<8}" for p in PUZZLES))
rnd = random.Random(135)
pior = 0
for F in FS:
    linha = f"{F:<6} "
    for p in PUZZLES:
        faixa = 1 << (p - 1)
        o = Ordem(faixa, "onda", franjas=F)
        m = statistics.fmean(o.fracao(rnd.randrange(faixa), faixa) for _ in range(N))
        pior = max(pior, abs(m - 0.5))
        linha += f"{m:.4f}   "
    print(linha, flush=True)
print(f"\nmaior distancia de 0,5 em {len(FS) * len(PUZZLES)} combinacoes: {pior:.4f}")
