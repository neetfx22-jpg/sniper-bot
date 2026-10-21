"""As chaves vizinhas do alvo "se parecem" com ele?

Para alvos conhecidos (puzzles resolvidos), testa chaves a distancia d do alvo e mede a semelhanca
com o alvo em duas etapas do calculo:
  - hash160 (o que o engine compara): bits iguais (de 160) e tamanho do prefixo igual (em bits)
  - coordenada x do ponto na curva (antes do hash): bits iguais (de 256)
Se houvesse "quente e frio", a semelhanca subiria quando d diminui. Sem padrao: ~80 de 160 e ~128 de 256
em qualquer distancia, igual a chaves sorteadas longe.
"""
import random
import statistics

from hash160 import hash160, mul

ALVOS = [30, 40, 50, 60, 70]
DIST = [1, 2, 3, 10, 100, 1000, 10**4, 10**6, 10**9]
AMOSTRAS = 60


def bits_iguais(a, b, nbits):
    return nbits - bin(a ^ b).count("1")


def prefixo(a, b, nbits):
    x = a ^ b
    return nbits if x == 0 else nbits - x.bit_length()


def main():
    chaves = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    rnd = random.Random(7)
    linhas = {d: [[], [], []] for d in DIST + ["longe"]}
    for p in ALVOS:
        k = chaves[p]
        h0 = int(hash160(k), 16)
        x0 = mul(k)[0]
        for d in DIST + ["longe"]:
            for _ in range(AMOSTRAS):
                if d == "longe":
                    v = rnd.randrange(1 << (p - 1), 1 << p)
                else:
                    v = k + d * rnd.choice((-1, 1)) + (rnd.randrange(-d // 10, d // 10 + 1) if d >= 10 else 0)
                if v == k:
                    continue
                h = int(hash160(v), 16)
                linhas[d][0].append(bits_iguais(h, h0, 160))
                linhas[d][1].append(prefixo(h, h0, 160))
                linhas[d][2].append(bits_iguais(mul(v)[0], x0, 256))
    print(f"alvos: puzzles {ALVOS}; {AMOSTRAS} vizinhas por distancia por alvo\n")
    print("distancia do alvo   hash160 bits iguais (/160)   prefixo igual (bits)   ponto x bits iguais (/256)")
    for d, (b, pr, xb) in linhas.items():
        nome = f"{d:,}".replace(",", ".") if d != "longe" else "longe (sorteada)"
        print(f"{nome:<19} {statistics.fmean(b):6.2f} (dp {statistics.stdev(b):4.1f})          "
              f"{statistics.fmean(pr):5.2f}                  {statistics.fmean(xb):6.2f}")
    print("\nesperado sem nenhum padrao: 80,00 de 160 | prefixo ~1,0 bit | 128,00 de 256")


if __name__ == "__main__":
    main()
