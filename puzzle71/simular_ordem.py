"""Simulador exato da ORDEM de busca do engine_salto_onda.c.

Para cada chave alvo, calcula qual fracao da faixa o engine percorre antes de
chegar nela, em cada estrategia (sequencial, salto aureo, onda com F franjas).
A ordem e a mesma do C (map_chunk), so que invertida: chunk fisico -> indice logico.
Nao precisa calcular curva eliptica: a posicao em que a chave e achada so depende
da ordem dos chunks e de onde a chave esta.
"""
import bisect
import math
import random
import statistics
import sys
from fractions import Fraction
from math import gcd

HALF = 512
BATCH = 2 * HALF + 1
CHUNK = BATCH * 256          # 262400 chaves, igual ao engine
NBINS_MAX = 4096
PHI = Fraction("0.6180339887498949")


def golden_stride(n):
    st = int(n * PHI)
    st = max(st, 1) | 1
    while gcd(st, n) != 1:
        st += 2
    return st


class Ordem:
    def __init__(self, faixa, modo, franjas=10.0, envelope=1.5, dentro_seq=False, escuras=False):
        self.n = -(-faixa // CHUNK)
        self.modo = modo
        self.dentro_seq = dentro_seq
        if modo == "salto":
            self.st = golden_stride(self.n)
            self.inv = pow(self.st, -1, self.n) if self.n > 1 else 0
        elif modo == "onda":
            nb = min(self.n, NBINS_MAX)
            self.lo = [self.n * b // nb for b in range(nb + 1)]
            inten = []
            for b in range(nb):
                u = (b + 0.5) / nb - 0.5
                a, c = math.pi * franjas * u, math.pi * envelope * u
                sn = 1.0 if c == 0 else math.sin(c) / c
                inten.append(math.cos(a) ** 2 * sn * sn)
            sgn = 1 if escuras else -1
            ordem = sorted(range(nb), key=lambda b: (sgn * inten[b], b))
            self.rank = [0] * nb
            self.cum = [0] * (nb + 1)
            for r, b in enumerate(ordem):
                self.rank[b] = r
                self.cum[r + 1] = self.cum[r] + self.lo[b + 1] - self.lo[b]
            self.binv = []
            for b in range(nb):
                sz = self.lo[b + 1] - self.lo[b]
                st = golden_stride(sz) if sz > 1 else 1
                self.binv.append((1 if dentro_seq else (pow(st, -1, sz) if sz > 1 else 0), sz))

    def indice(self, chunk):
        """chunk fisico -> posicao na ordem de visita"""
        if self.modo == "sequencial":
            return chunk
        if self.modo == "salto":
            return chunk * self.inv % self.n
        b = bisect.bisect_right(self.lo, chunk) - 1
        inv, sz = self.binv[b]
        return self.cum[self.rank[b]] + (chunk - self.lo[b]) * inv % sz

    def fracao(self, desloc, faixa):
        """fracao da faixa percorrida ate achar a chave em `desloc` (0 = inicio da faixa)"""
        c, dentro = divmod(desloc, CHUNK)
        return (self.indice(c) * CHUNK + dentro + 1) / faixa


ESTRATEGIAS = [("sequencial", {}), ("salto", {}),
               ("onda F=5", {"franjas": 5}), ("onda F=10", {"franjas": 10}),
               ("onda F=20", {"franjas": 20}), ("onda F=50", {"franjas": 50}),
               ("pura F=10", {"franjas": 10, "dentro_seq": True}),
               ("pura F=20", {"franjas": 20, "dentro_seq": True}),
               ("escura F=10", {"franjas": 10, "dentro_seq": True, "escuras": True}),
               ("escura F=20", {"franjas": 20, "dentro_seq": True, "escuras": True})]


def ordens_para(faixa):
    modo = {"pura": "onda", "escura": "onda"}
    return {nome: Ordem(faixa, modo.get(nome.split()[0], nome.split()[0]), **kw) for nome, kw in ESTRATEGIAS}


def resumo(nome, xs):
    m = statistics.fmean(xs)
    ep = statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0
    return f"{nome:<12} media={m:.4f}  (+-{1.96*ep:.4f})  mediana={statistics.median(xs):.4f}"


def main():
    alvos = [l.split() for l in open("chaves_resolvidas.txt")]
    alvos = [(int(n), int(k, 16)) for n, k in alvos if int(n) >= 2]

    print("== 1) chaves resolvidas (puzzles 2..135), fracao da faixa ate achar ==")
    res = {nome: [] for nome, _ in ESTRATEGIAS}
    linhas = []
    for n, k in alvos:
        faixa = 1 << (n - 1)
        ords = ordens_para(faixa)
        fr = {nome: o.fracao(k - faixa, faixa) for nome, o in ords.items()}
        for nome in fr:
            res[nome].append(fr[nome])
        linhas.append((n, (k - faixa) / faixa, fr))
    for nome, _ in ESTRATEGIAS:
        print(resumo(nome, res[nome]))
    with open("resultado_chaves_resolvidas.csv", "w") as f:
        f.write("puzzle,posicao_relativa," + ",".join(n for n, _ in ESTRATEGIAS) + "\n")
        for n, pos, fr in linhas:
            f.write(f"{n},{pos:.6f}," + ",".join(f"{fr[e]:.6f}" for e, _ in ESTRATEGIAS) + "\n")

    amostras = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    print(f"\n== 2) {amostras} chaves aleatorias na faixa REAL do puzzle 71 (2^70 chaves) ==")
    faixa = 1 << 70
    ords = ordens_para(faixa)
    print(f"   passo do salto = {ords['salto'].st} (engine no celular: 2780662151054439)")
    rnd = random.Random(71)
    res = {nome: [] for nome, _ in ESTRATEGIAS}
    for _ in range(amostras):
        d = rnd.randrange(faixa)
        for nome, o in ords.items():
            res[nome].append(o.fracao(d, faixa))
    for nome, _ in ESTRATEGIAS:
        print(resumo(nome, res[nome]))

    print("\n== 3) as chaves resolvidas se concentram em alguma regiao? ==")
    pos = sorted((k - (1 << (n - 1))) / (1 << (n - 1)) for n, k in alvos if n >= 10)
    m = len(pos)
    d = max(max((i + 1) / m - p, p - i / m) for i, p in enumerate(pos))
    # p-valor assintotico do teste de Kolmogorov-Smirnov contra distribuicao uniforme
    lam = (math.sqrt(m) + 0.12 + 0.11 / math.sqrt(m)) * d
    pval = 2 * sum((-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam) for j in range(1, 100))
    print(f"   {m} chaves (puzzles >=10), KS contra uniforme: D={d:.4f}, p-valor={min(max(pval,0),1):.3f}")
    hist = [0] * 10
    for p in pos:
        hist[min(int(p * 10), 9)] += 1
    for i, h in enumerate(hist):
        print(f"   {i*10:>3}-{i*10+10:<3}% da faixa: {'#' * h} {h}")


if __name__ == "__main__":
    main()
