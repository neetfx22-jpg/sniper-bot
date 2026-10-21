"""Segunda rodada de busca de padrao nas chaves resolvidas, com o mesmo metodo:
varredura de parametros -> p-valor contra posicoes sorteadas (mesma varredura) -> treino/teste.

A) N fendas (grade de difracao), N = 2..6: I(u) = [sin(N pi F u) / (N sin(pi F u))]^2, picos finos nas franjas claras
B) duas fendas de larguras diferentes (amplitudes a e 1): I = a^2 + 1 + 2a cos(2 pi F u)
   -> e a mesma oscilacao cos(2 pi F u) do estudo anterior, so com outra altura; testada em conjunto com A (N=2)
C) puzzle anterior como fonte: onda centrada na posicao da chave n-1, medida na chave n:
   I = cos^2(pi F (u_n - u_{n-1}))
"""
import math
import random
import statistics

FS = range(1, 301)
NS = range(2, 7)
RAND = 1000


def carregar():
    pos = {}
    for linha in open("chaves_resolvidas.txt"):
        n, k = linha.split()[:2]
        n, k = int(n), int(k, 16)
        if n >= 10:
            pos[n] = (k - (1 << (n - 1))) / (1 << (n - 1))
    return pos


def grade(u, N, F):
    x = math.pi * F * (u - 0.5)
    s = math.sin(x)
    if abs(s) < 1e-12:
        return 1.0
    return (math.sin(N * x) / (N * s)) ** 2


def stat_grade(us, N, F):
    # intensidade media nas chaves relativa a media sob acaso (1/N); >0 = caem nos picos
    return statistics.fmean(grade(u, N, F) for u in us) * N - 1


def melhor_grade(us):
    return max((stat_grade(us, N, F), N, F) for N in NS for F in FS)


def stat_ant(dif, F):
    return statistics.fmean(math.cos(2 * math.pi * F * d) for d in dif)


def melhor_ant(dif):
    return max((stat_ant(dif, F), F) for F in FS)


def pval(obs, melhor_fn, n, rnd, gerar):
    maiores = [melhor_fn(gerar(n, rnd))[0] for _ in range(RAND)]
    return sum(m >= obs for m in maiores) / RAND, statistics.fmean(maiores)


def main():
    pos = carregar()
    us = list(pos.values())
    rnd = random.Random(2026)

    print(f"A/B) N fendas (N=2..6, F=1..300), {len(us)} chaves")
    s, N, F = melhor_grade(us)
    p, media_acaso = pval(s, melhor_grade, len(us), rnd, lambda n, r: [r.random() for _ in range(n)])
    print(f"   melhor: N={N} fendas, F={F}: {s:+.3f}   | no acaso o melhor fica em {media_acaso:+.3f}   | p-valor = {p:.2f}")
    for nome, tr, te in [("pares -> impares", 0, 1), ("impares -> pares", 1, 0)]:
        ut = [u for k, u in pos.items() if k % 2 == tr]
        uv = [u for k, u in pos.items() if k % 2 == te]
        s, N, F = melhor_grade(ut)
        print(f"   treino {nome}: N={N} F={F} ({s:+.3f}) -> teste {stat_grade(uv, N, F):+.3f}")

    print("\nC) puzzle anterior como fonte da onda (F=1..300)")
    ks = sorted(pos)
    pares = [(a + 1, pos[a + 1] - pos[a]) for a in ks if a + 1 in pos]
    dif = [d for _, d in pares]
    s, F = melhor_ant(dif)
    p, media_acaso = pval(s, melhor_ant, len(dif), rnd, lambda n, r: [r.random() - r.random() for _ in range(n)])
    print(f"   melhor: F={F}: {s:+.3f}   | no acaso o melhor fica em {media_acaso:+.3f}   | p-valor = {p:.2f}  ({len(dif)} pares)")
    for nome, tr, te in [("pares -> impares", 0, 1), ("impares -> pares", 1, 0)]:
        dt = [d for k, d in pares if k % 2 == tr]
        dv = [d for k, d in pares if k % 2 == te]
        s, F = melhor_ant(dt)
        print(f"   treino {nome}: F={F} ({s:+.3f}) -> teste {stat_ant(dv, F):+.3f}")


if __name__ == "__main__":
    main()
