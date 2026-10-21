"""Procura um padrao de "particulas" nas chaves ja resolvidas.

Pergunta: as chaves resolvidas caem mais nas franjas claras de algum padrao de onda do que o acaso explica?
Para F franjas, a intensidade em u = posicao - 0,5 e cos^2(pi F u) = (1 + cos(2 pi F u)) / 2.
Estatistica por F: media de cos(2 pi F u) nas chaves (0 = sem preferencia; >0 = caem nas claras; <0 = nas escuras).

1) varre F = 1..500 e mostra os melhores
2) p-valor honesto: repete a varredura inteira em 2000 conjuntos de posicoes sorteadas (corrige o fato de testarmos 500 F)
3) treino/teste: escolhe o melhor F nos puzzles pares e mede nos impares (e vice-versa)
4) outros padroes: posicao de um puzzle x posicao do seguinte; bits logo abaixo do bit mais alto
"""
import math
import random
import statistics

FS = range(1, 501)


def carregar():
    pos = {}
    for linha in open("chaves_resolvidas.txt"):
        n, k = linha.split()[:2]
        n, k = int(n), int(k, 16)
        if n >= 10:
            pos[n] = (k - (1 << (n - 1))) / (1 << (n - 1))
    return pos


def estat(us, F):
    return statistics.fmean(math.cos(2 * math.pi * F * (u - 0.5)) for u in us)


def melhor(us):
    return max((estat(us, F), F) for F in FS)


def main():
    pos = carregar()
    us = list(pos.values())
    n = len(us)
    print(f"{n} chaves resolvidas (puzzles >= 10)\n")

    print("1) os 8 F em que as chaves mais caem nas franjas CLARAS:")
    todos = sorted(((estat(us, F), F) for F in FS), reverse=True)
    for s, F in todos[:8]:
        print(f"   F={F:<4} media cos = {s:+.3f}   (z = {s / math.sqrt(1 / (2 * n)):+.2f})")
    print(f"   F=10: {estat(us, 10):+.3f}   F=20: {estat(us, 20):+.3f}")

    print("\n2) isso e mais do que o acaso daria? (2000 conjuntos de posicoes sorteadas, mesma varredura de 500 F)")
    rnd = random.Random(500)
    obs = todos[0][0]
    maiores = []
    for _ in range(2000):
        fake = [rnd.random() for _ in range(n)]
        maiores.append(melhor(fake)[0])
    p = sum(m >= obs for m in maiores) / len(maiores)
    print(f"   melhor F real = {todos[0][1]} com {obs:+.3f}; no acaso, o melhor F fica em media {statistics.fmean(maiores):+.3f}")
    print(f"   p-valor = {p:.2f}  (abaixo de 0,05 seria sinal de padrao)")

    print("\n3) treino/teste (escolhe o F numa metade, mede na outra):")
    for nome, treino, teste in [("pares -> impares", 0, 1), ("impares -> pares", 1, 0)]:
        ut = [u for k, u in pos.items() if k % 2 == treino]
        uv = [u for k, u in pos.items() if k % 2 == teste]
        s, F = melhor(ut)
        sv = estat(uv, F)
        print(f"   {nome}: melhor F no treino = {F} ({s:+.3f}); no teste = {sv:+.3f}  (z = {sv / math.sqrt(1 / (2 * len(uv))):+.2f})")

    print("\n4) outros padroes:")
    ks = sorted(pos)
    pares = [(pos[a], pos[a + 1]) for a in ks if a + 1 in pos]
    r = statistics.correlation([a for a, _ in pares], [b for _, b in pares])
    print(f"   correlacao posicao(n) x posicao(n+1): r = {r:+.3f} ({len(pares)} pares; |r| > {2 / math.sqrt(len(pares)):.2f} seria notavel)")
    bits = [int(u * 2) for u in us]
    bits2 = [int(u * 4) % 2 for u in us]
    print(f"   2o bit mais alto = 1 em {sum(bits)}/{n} chaves; 3o bit = 1 em {sum(bits2)}/{n}  (acaso: ~{n // 2} +- {math.sqrt(n) :.0f})")
    print(f"   chaves na metade de cima da faixa: {sum(u >= 0.5 for u in us)}/{n}")


if __name__ == "__main__":
    main()
