"""Testa a combinacao de salto aureo + onda F=10 (+ onda F=20) numa estrategia so.

Faixa abstrata de N chunks, chaves sorteadas. Tres formas de combinar:
  intercalada : alterna um chunk de cada estrategia, pulando os ja visitados (cobre tudo sem repetir)
  paralela    : metade da velocidade para cada estrategia, sem coordenacao (pode repetir chunks)
  melhor_de_2 : 'adivinha' depois qual das duas teria achado primeiro (impossivel na pratica; teto otimista)
"""
import random
import statistics
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from simular_ordem import CHUNK, Ordem

N_CHUNKS = 200_003
faixa = N_CHUNKS * CHUNK
ords = {"salto": Ordem(faixa, "salto"), "onda10": Ordem(faixa, "onda", franjas=10),
        "onda20": Ordem(faixa, "onda", franjas=20)}


def fila(o):
    """ordem de visita completa (lista de chunks) de uma estrategia"""
    pos = [0] * N_CHUNKS
    for c in range(N_CHUNKS):
        pos[o.indice(c)] = c
    return pos


filas = {k: fila(o) for k, o in ords.items()}


def intercalada(nomes):
    vis, out, its = bytearray(N_CHUNKS), [], [iter(filas[n]) for n in nomes]
    while len(out) < N_CHUNKS:
        for it in its:
            for c in it:
                if not vis[c]:
                    vis[c] = 1
                    out.append(c)
                    break
    rank = [0] * N_CHUNKS
    for i, c in enumerate(out):
        rank[c] = i
    return rank


rank_inter2 = intercalada(["salto", "onda10"])
rank_inter3 = intercalada(["salto", "onda10", "onda20"])
idx = {k: [0] * N_CHUNKS for k in filas}
for k, f in filas.items():
    for i, c in enumerate(f):
        idx[k][c] = i

rnd = random.Random(42)
R = {k: [] for k in ["salto", "onda10", "onda20", "intercalada salto+onda10", "intercalada salto+onda10+onda20",
                     "paralela salto+onda10", "melhor_de_2 (impossivel)"]}
for _ in range(200_000):
    c = rnd.randrange(N_CHUNKS)
    a, b = idx["salto"][c], idx["onda10"][c]
    R["salto"].append(a / N_CHUNKS)
    R["onda10"].append(b / N_CHUNKS)
    R["onda20"].append(idx["onda20"][c] / N_CHUNKS)
    R["intercalada salto+onda10"].append(rank_inter2[c] / N_CHUNKS)
    R["intercalada salto+onda10+onda20"].append(rank_inter3[c] / N_CHUNKS)
    R["paralela salto+onda10"].append(2 * min(a, b) / N_CHUNKS)   # cada uma anda a meia velocidade
    R["melhor_de_2 (impossivel)"].append(min(a, b) / N_CHUNKS)
print("fracao do TRABALHO TOTAL ate achar a chave (200 mil chaves sorteadas):")
for k, xs in R.items():
    print(f"  {k:<34} media={statistics.fmean(xs):.4f}")
