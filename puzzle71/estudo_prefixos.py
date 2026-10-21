"""Sistema de prefixos: chaves cujo endereco comeca igual ao do alvo indicam onde esta a chave?

Para alvos conhecidos (puzzles 40, 50, 60, 70): 100 blocos de 4 mil chaves consecutivas espalhados pela
faixa inteira (um bloco contem o alvo). Para cada chave, mede quantos bits iniciais do hash160 sao iguais
aos do alvo (prefixo) e quantos caracteres iniciais do endereco Base58 sao iguais.

1) mapa de calor: acertos de prefixo (>= 8 bits) por bloco; o bloco do alvo se destaca?
2) prefixo mais longo => mais perto? (prefixo medio por faixa de distancia ate o alvo)
3) previsao: o bloco com mais acertos de prefixo e o bloco do alvo? (acaso: 1 em 100)
4) Base58: chaves com 2+ caracteres iniciais iguais no endereco ficam perto da chave?
"""
import hashlib
import math
import random
import statistics

from hash160 import G, add, mul, ripemd160

BLOCOS, POR_BLOCO, MIN_BITS = 100, 4000, 8
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def endereco(h160):
    v = b"\x00" + h160.to_bytes(20, "big")
    v += hashlib.sha256(hashlib.sha256(v).digest()).digest()[:4]
    n = int.from_bytes(v, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" + s


def h160_ponto(pt):
    x, y = pt
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return int.from_bytes(ripemd160(hashlib.sha256(pub).digest()), "big")


def comum(a, b):
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def estudar(p, kalvo, rnd):
    ini = faixa = 1 << (p - 1)
    inicios = sorted([rnd.randrange(ini, ini + faixa - POR_BLOCO) for _ in range(BLOCOS - 1)] + [kalvo - POR_BLOCO // 2])
    b_alvo = inicios.index(kalvo - POR_BLOCO // 2)
    h_alvo = int(__import__("hash160").hash160(kalvo), 16)
    a_alvo = endereco(h_alvo)
    acertos = [0] * BLOCOS
    prefs, b58 = [], []
    for b, k0 in enumerate(inicios):
        pt = mul(k0)
        for i in range(POR_BLOCO):
            k = k0 + i
            h = h160_ponto(pt)
            pt = add(pt, G)
            if k == kalvo:
                continue
            x = h ^ h_alvo
            pb = 160 - x.bit_length()
            d = abs(k - kalvo)
            prefs.append((pb, d))
            if pb >= MIN_BITS:
                acertos[b] += 1
            if pb >= 6:   # Base58 so vale a pena calcular quando o comeco ja e parecido
                c = comum(endereco(h), a_alvo)
                if c >= 3:   # '1' + 2 caracteres
                    b58.append(d)
    print(f"== puzzle {p} (endereco do alvo {a_alvo}) ==")
    media = statistics.fmean(acertos)
    print(f"1) acertos de prefixo (>= {MIN_BITS} bits iguais) por bloco: media {media:.1f}, "
          f"min {min(acertos)}, max {max(acertos)}; no bloco do alvo: {acertos[b_alvo]}")
    rank = sorted(range(BLOCOS), key=lambda b: -acertos[b]).index(b_alvo) + 1
    print(f"   posicao do bloco do alvo no ranking de acertos: {rank} de {BLOCOS}")
    faixas = [(0, POR_BLOCO), (POR_BLOCO, faixa // 100), (faixa // 100, faixa // 10), (faixa // 10, faixa)]
    print("2) prefixo medio (bits iguais) por distancia ate o alvo:")
    for lo, hi in faixas:
        xs = [pb for pb, d in prefs if lo <= d < hi]
        if xs:
            print(f"   distancia {lo:>22,} a {hi:<24,}: {statistics.fmean(xs):.3f} bits ({len(xs):,} chaves)".replace(",", "."))
    if b58:
        perto = sum(d <= POR_BLOCO for d in b58)
        print(f"4) {len(b58)} chaves com 2+ caracteres iguais no endereco Base58; no bloco do alvo: {perto} "
              f"(acaso: ~{len(b58) / BLOCOS:.1f})")
    return rank == 1, rank


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    rnd = random.Random(2071)
    res = [estudar(p, ch[p], rnd) for p in (40, 50, 60, 70)]
    print("\n3) previsao 'o bloco com mais prefixos iguais e o do alvo':")
    print(f"   acertou em {sum(a for a, _ in res)} de {len(res)} puzzles (acaso: 1 em {BLOCOS});"
          f" posicao media do bloco do alvo no ranking: {statistics.fmean(r for _, r in res):.0f} de {BLOCOS} (acaso: ~50)")
    print(f"   esperado sem padrao: prefixo medio ~1,0 bit em qualquer distancia")


if __name__ == "__main__":
    main()
