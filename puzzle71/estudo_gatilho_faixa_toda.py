"""O "gatilho" (enderecos parecidos com o do alvo) aponta para a chave quando NAO sabemos onde ela esta?

No estudo_ordem_enderecos.py as chaves foram geradas so numa janela de 60 mil em volta do alvo, entao
qualquer chave dali fica a ~15 mil do alvo. Aqui as chaves cobrem a faixa inteira do puzzle (como no 71):
40 blocos de 4 mil chaves consecutivas espalhados pela faixa, um deles contendo o alvo.
Pergunta: as chaves com endereco mais parecido com o do alvo caem perto da chave do alvo?
"""
import hashlib
import random
import statistics

from hash160 import G, add, mul, ripemd160

BLOCOS, POR_BLOCO = 40, 4000


def h160_ponto(pt):
    x, y = pt
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return int.from_bytes(ripemd160(hashlib.sha256(pub).digest()), "big")


def estudar(p, kalvo, rnd):
    ini, faixa = 1 << (p - 1), 1 << (p - 1)
    inicios = [rnd.randrange(ini, ini + faixa - POR_BLOCO) for _ in range(BLOCOS - 1)] + [kalvo - POR_BLOCO // 2]
    dados = []
    for k0 in inicios:
        pt = mul(k0)
        for i in range(POR_BLOCO):
            dados.append((k0 + i, h160_ponto(pt)))
            pt = add(pt, G)
    h_alvo = dict(dados)[kalvo]

    def iguais(h):
        x = h ^ h_alvo
        return 160 if x == 0 else 160 - x.bit_length()

    outros = [t for t in dados if t[0] != kalvo]
    gat = sorted(outros, key=lambda t: -iguais(t[1]))[:50]
    dist = [abs(k - kalvo) for k, _ in gat]
    no_bloco_do_alvo = sum(abs(k - kalvo) <= POR_BLOCO for k, _ in gat)
    print(f"puzzle {p}: {len(dados):,} chaves em {BLOCOS} blocos pela faixa inteira ({faixa:,} chaves)".replace(",", "."))
    print(f"   as 50 com endereco mais parecido com o do alvo ({iguais(gat[-1][1])}+ bits iniciais iguais):")
    print(f"   distancia media ate a chave do alvo = {statistics.fmean(dist):,.0f}   (faixa inteira ao acaso: ~{faixa / 3:,.0f})".replace(",", "."))
    print(f"   quantas cairam no bloco do alvo: {no_bloco_do_alvo} de 50   (ao acaso: ~{50 / BLOCOS:.1f})\n")


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    rnd = random.Random(40)
    for p in (40, 50, 60):
        estudar(p, ch[p], rnd)


if __name__ == "__main__":
    main()
