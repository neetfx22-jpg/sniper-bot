"""Verificacao em grande escala: vizinhas de 1 bit nos bits baixos (0 a 9).

No estudo_vizinhas_1bit.py, 50 vizinhas (bits 0-9 de 5 alvos) deram 77,2/160 bits iguais no endereco, abaixo de 80.
Aqui: 3000 chaves base sorteadas (faixas de 30 a 70 bits) x 10 bits baixos = 30 mil pares.
Se for um efeito real, a media fica abaixo de 80 de novo; se foi acaso, volta para ~80.
"""
import math
import random
import statistics

from hash160 import hash160

BASES = 3000


def main():
    rnd = random.Random(2026)
    por_bit = {b: [] for b in range(10)}
    for _ in range(BASES):
        p = rnd.randrange(30, 71)
        k = rnd.randrange(1 << (p - 1), 1 << p)
        h0 = int(hash160(k), 16)
        for b in range(10):
            h = int(hash160(k ^ (1 << b)), 16)
            por_bit[b].append(160 - bin(h ^ h0).count("1"))
    todos = [x for xs in por_bit.values() for x in xs]
    ep = statistics.stdev(todos) / math.sqrt(len(todos))
    print(f"{len(todos)} pares (chave, chave com 1 bit baixo invertido)\n")
    print(f"media de bits iguais no endereco: {statistics.fmean(todos):.3f} /160   (sem ligacao: 80; margem 95%: +-{1.96 * ep:.3f})\n")
    for b, xs in por_bit.items():
        print(f"   bit {b} invertido (distancia {1 << b:>3}): {statistics.fmean(xs):.2f}")


if __name__ == "__main__":
    main()
