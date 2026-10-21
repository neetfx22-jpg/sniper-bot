"""Estudo da selecao de particulas (modo particulas, puzzle 71).

Varia um parametro por vez a partir do padrao (F=10, L=1,5, janela=4, kmax=100) e mede:
  - fracao media da faixa ate achar a chave (menor = melhor; 0,5 = sem vantagem)
  - chance de achar dentro de 50 anos no celular (6,67 M chaves/s)
Janela e kmax so mudam a ordem em faixas grandes, entao tudo roda na faixa real do puzzle 71.
"""
import math
import random
import statistics
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import simular_particulas as sp
from simular_ordem import CHUNK

FAIXA = 1 << 70
N = -(-FAIXA // CHUNK)
CHAVES = 3000
LIMITE = 6.67e6 * 3600 * 24 * 365.25 * 50 / FAIXA   # fracao da faixa varrida em 50 anos


def medir(F=10, L=1.5, janela=4, kmax=100, semente=1):
    orig = sp.intensidades
    sp.intensidades = lambda F_, L_=L, nb=sp.NB: orig(F_, L, nb)
    try:
        o = sp.OrdemB(N, F, janela=janela, kmax=kmax)
    finally:
        sp.intensidades = orig
    rnd = random.Random(semente)
    xs = [o.fracao(rnd.randrange(N)) for _ in range(CHAVES)]
    achou = sum(x <= LIMITE for x in xs)
    return statistics.fmean(xs), 1.96 * statistics.stdev(xs) / math.sqrt(CHAVES), achou


def main():
    print(f"puzzle 71, {CHAVES} chaves sorteadas por configuracao (IC 95% ~ +-0,010)")
    print(f"em 50 anos o celular varre {LIMITE:.2e} da faixa; a chance esperada de achar e essa mesma fracao\n")
    testes = [("F (franjas)", "F", [2, 5, 10, 20, 50, 200]),
              ("L (envelope)", "L", [0.0, 0.5, 1.5, 3.0]),
              ("janela (chunks)", "janela", [1, 4, 16, 256]),
              ("kmax (janelas na faixa mais clara)", "kmax", [1, 10, 100, 1000])]
    pior = 0
    for titulo, nome, valores in testes:
        print(titulo)
        for v in valores:
            m, ic, achou = medir(**{nome: v})
            pior = max(pior, abs(m - 0.5))
            print(f"   {nome}={v:<6} media={m:.4f} (+-{ic:.4f})   achou em 50 anos: {achou}/{CHAVES}")
    print(f"\nmaior distancia de 0,5: {pior:.4f}")


if __name__ == "__main__":
    main()
