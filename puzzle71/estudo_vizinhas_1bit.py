"""Vizinhas de 1 bit: chaves que diferem do alvo em UM unico bit ("mesmo bairro").

Para os alvos dos puzzles 30, 40, 50, 60 e 70, inverte cada bit da chave (um por vez) e mede o quanto o
endereco (hash160) e o ponto da curva (x) da vizinha se parecem com os do alvo.
Compara com chaves sorteadas na mesma faixa (outros "paises").
Se o bairro se mantivesse no endereco, vizinhas de 1 bit teriam bem mais que 80/160 bits iguais.
Tambem separa por posicao do bit invertido (bits baixos = vizinha muito perto; bits altos = longe).
"""
import random
import statistics

from hash160 import hash160, mul

ALVOS = [30, 40, 50, 60, 70]


def iguais(a, b, n):
    return n - bin(a ^ b).count("1")


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    rnd = random.Random(1)
    viz_h, viz_x, sor_h, sor_x = [], [], [], []
    por_faixa = {"bits 0-9 (ate ~1 mil de distancia)": [], "bits 10-29 (mil a 500 milhoes)": [],
                 "bits 30+ (bilhoes ou mais)": []}
    for p in ALVOS:
        k = ch[p]
        h0, x0 = int(hash160(k), 16), mul(k)[0]
        for b in range(p - 1):                       # o bit mais alto define a faixa; os outros podem mudar
            v = k ^ (1 << b)
            h, x = int(hash160(v), 16), mul(v)[0]
            viz_h.append(iguais(h, h0, 160))
            viz_x.append(iguais(x, x0, 256))
            chave = ("bits 0-9 (ate ~1 mil de distancia)" if b < 10 else
                     "bits 10-29 (mil a 500 milhoes)" if b < 30 else "bits 30+ (bilhoes ou mais)")
            por_faixa[chave].append(viz_h[-1])
            s = rnd.randrange(1 << (p - 1), 1 << p)
            sor_h.append(iguais(int(hash160(s), 16), h0, 160))
            sor_x.append(iguais(mul(s)[0], x0, 256))
    n = len(viz_h)
    print(f"{n} vizinhas de 1 bit (puzzles {ALVOS}) e {n} chaves sorteadas\n")
    print("                     endereco: bits iguais (/160)    ponto x: bits iguais (/256)")
    print(f"vizinhas de 1 bit    {statistics.fmean(viz_h):6.2f} (min {min(viz_h)}, max {max(viz_h)})"
          f"          {statistics.fmean(viz_x):6.2f}")
    print(f"sorteadas            {statistics.fmean(sor_h):6.2f} (min {min(sor_h)}, max {max(sor_h)})"
          f"          {statistics.fmean(sor_x):6.2f}")
    print("\nvizinhas de 1 bit, por posicao do bit invertido:")
    for nome, xs in por_faixa.items():
        print(f"   {nome:<36} {statistics.fmean(xs):6.2f} /160  ({len(xs)} vizinhas)")
    print("\nsem nenhuma ligacao: 80/160 e 128/256 (margem tipica com essas amostras: +-1,5)")


if __name__ == "__main__":
    main()
