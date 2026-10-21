"""Ordenar as chaves pelo endereco (hash160) e ver se o embaralhamento tem padrao.

60 mil chaves consecutivas em volta da chave do puzzle 40 (o alvo esta no meio).
1) Ordena pelo hash160 (ordem binaria = ordem alfabetica do hex). Para cada par de vizinhos na lista
   ordenada, mede a distancia entre as CHAVES. Se o embaralhamento tivesse padrao, vizinhos de endereco
   seriam chaves proximas (ou a distancias fixas). Num embaralhamento sem padrao, a distancia media e ~N/3.
2) "Gatilho": as 50 chaves cujo endereco e mais parecido com o do alvo (mais bits iniciais iguais).
   Elas ficam perto da chave do alvo? Sem padrao, ficam espalhadas por todo o intervalo (media ~N/4).
3) Desembaralhar: a posicao na lista ordenada permite prever a posicao da chave? (correlacao de postos)
4) Os mesmos testes com o alvo do puzzle 50, para ver se algo encontrado em um vale no outro.
"""
import hashlib
import math
import random
import statistics

from hash160 import G, add, mul, ripemd160

N = 60000


def h160_ponto(pt):
    x, y = pt
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return int.from_bytes(ripemd160(hashlib.sha256(pub).digest()), "big")


def gerar(k0):
    pt, out = mul(k0), []
    for i in range(N):
        out.append((k0 + i, h160_ponto(pt)))
        pt = add(pt, G)
    return out


def spearman(a, b):
    n = len(a)
    ra = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: a[i]))}
    rb = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: b[i]))}
    x = [ra[i] for i in range(n)]
    y = [rb[i] for i in range(n)]
    return statistics.correlation(x, y)


def estudar(nome, kalvo):
    dados = gerar(kalvo - N // 2)
    h_alvo = dict(dados)[kalvo]
    ordenado = sorted(dados, key=lambda t: t[1])
    print(f"== {nome}: {N} chaves em volta da chave do alvo ==")

    dist = [abs(a[0] - b[0]) for a, b in zip(ordenado, ordenado[1:])]
    perto = sum(d <= 10 for d in dist)
    esperado_perto = (len(dist)) * (2 * 10 / N)
    print(f"1) vizinhos na ordem dos enderecos: distancia media entre as chaves = {statistics.fmean(dist):,.0f}"
          f" (sem padrao: ~{N / 3:,.0f})")
    print(f"   pares de vizinhos de endereco que sao chaves a ate 10 de distancia: {perto} (sem padrao: ~{esperado_perto:.0f})")
    rnd = random.Random(1)
    difs = [b[0] - a[0] for a, b in zip(ordenado, ordenado[1:])]
    comuns = {}
    for d in difs:
        comuns[d] = comuns.get(d, 0) + 1
    rep = max(comuns.values())
    print(f"   distancia mais repetida entre vizinhos de endereco aparece {rep}x (embaralhamento aleatorio: 6 a 8x)")

    def bits_iniciais_iguais(h):
        x = h ^ h_alvo
        return 160 if x == 0 else 160 - x.bit_length()

    outros = [t for t in dados if t[0] != kalvo]
    gatilho = sorted(outros, key=lambda t: -bits_iniciais_iguais(t[1]))[:50]
    dg = [abs(k - kalvo) for k, _ in gatilho]
    print(f"2) as 50 chaves com endereco mais parecido com o do alvo ({bits_iniciais_iguais(gatilho[-1][1])}+ bits iniciais iguais):")
    print(f"   distancia media ate a chave do alvo = {statistics.fmean(dg):,.0f} (sem padrao: ~{N / 4:,.0f});"
          f" a mais perto esta a {min(dg):,}")

    rho = spearman([k for k, _ in dados], [h for _, h in dados])
    print(f"3) correlacao entre a ordem das chaves e a ordem dos enderecos: {rho:+.4f}"
          f" (sem padrao: 0 +- {2 / math.sqrt(N):.4f})\n")


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    estudar("puzzle 40", ch[40])
    estudar("puzzle 50", ch[50])


if __name__ == "__main__":
    main()
