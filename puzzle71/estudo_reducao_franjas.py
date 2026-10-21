"""Reducao das franjas por etapas (zoom) ate um alvo pequeno.

Em cada etapa, a area atual e dividida em F franjas (padrao de dupla fenda dentro da area) e ficam as M
franjas mais claras. Repete ate a area restante ter poucos milhoes de chaves. Pergunta: a area final
contem a chave mais vezes do que o tamanho dela explica?

Teste nas chaves resolvidas (puzzles 30 a 135) e em 100 mil chaves sorteadas.
"""
import bisect
import math
import random

L_ENV = 1.5


def intensidade(u, F):
    a, c = math.pi * F * u, math.pi * L_ENV * u
    sn = 1.0 if c == 0 else math.sin(c) / c
    return math.cos(a) ** 2 * sn * sn


def reduzir(F, M, etapas):
    """lista de intervalos [a, b) em fracao da faixa que sobram apos as etapas"""
    areas = [(0.0, 1.0)]
    for _ in range(etapas):
        novas = []
        for a, b in areas:
            w = (b - a) / F
            # intensidade MEDIA de cada faixa (amostrar so o centro cai numa franja escura quando F e par)
            franjas = [(sum(intensidade((i + (j + 0.5) / 32) / F - 0.5, F) for j in range(32)) / 32,
                        a + i * w, a + (i + 1) * w) for i in range(F)]
            franjas.sort(key=lambda t: -t[0])
            novas += [(x, y) for _, x, y in franjas[:M]]
        areas = novas
    return areas


def contem(areas, u):
    """areas ordenadas e sem sobreposicao: busca binaria"""
    i = bisect.bisect_right(areas, (u, 2.0)) - 1
    return i >= 0 and areas[i][0] <= u < areas[i][1]


def main():
    pos = []
    for linha in open("chaves_resolvidas.txt"):
        n, k = linha.split()[:2]
        n, k = int(n), int(k, 16)
        if n >= 30:
            pos.append((n, (k - (1 << (n - 1))) / (1 << (n - 1))))
    rnd = random.Random(5)
    sorteadas = [rnd.random() for _ in range(100_000)]
    print(f"{len(pos)} chaves resolvidas (puzzles >= 30) e 100 mil sorteadas\n")
    print("F    M  etapas  fracao da faixa no alvo  chaves do 71 no alvo   resolvidas dentro   sorteadas dentro   esperado")
    for F, M, et in [(10, 1, 6), (10, 1, 15), (10, 2, 6), (10, 3, 6), (20, 1, 5), (20, 4, 6), (5, 2, 10), (10, 5, 6)]:
        areas = sorted(reduzir(F, M, et))
        frac = sum(b - a for a, b in areas)
        dentro = sum(contem(areas, u) for _, u in pos)
        sort_d = sum(contem(areas, u) for u in sorteadas)
        print(f"{F:<4} {M:<2} {et:<7} {frac:<24.3e} {frac * 2**70:<20.3e} {dentro:>3}/{len(pos):<14} "
              f"{sort_d / len(sorteadas):<18.3e} {frac:.3e}")
    centro = reduzir(10, 1, 15)[0]
    dist = sorted(abs(u - 0.5) for _, u in pos)
    print(f"\ncom M=1 o zoom cai SEMPRE NO MESMO PONTO, em qualquer puzzle (com F par as 2 faixas do meio empatam): {centro[0]:.10f} a {centro[1]:.10f}")
    print(f"distancia das chaves resolvidas ate o centro: media {sum(dist) / len(dist):.3f} (sorteio uniforme: 0,250);"
          f" a mais perto esta a {dist[0]:.4f} da faixa")


if __name__ == "__main__":
    main()
