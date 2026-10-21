"""Modo "particulas": em vez de esgotar uma faixa inteira por vez, dispara muitas janelas pequenas
(alguns milhoes de chaves) espalhadas pela faixa toda, mais nas franjas claras -- como os eletrons do video.

Duas versoes:
  A) aleatoria (literal do video): cada particula cai numa faixa sorteada com probabilidade ~ intensidade,
     numa janela aleatoria dentro dela. Pode repetir janelas.
  B) rodadas sem repeticao: a cada rodada, cada faixa recebe k_b janelas novas, k_b ~ intensidade
     (minimo 1). Passa pela faixa inteira a cada rodada e nunca repete chave.
"""
import bisect
import math
import random
import statistics
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from simular_ordem import CHUNK, golden_stride

NB = 4096


def intensidades(F, L=1.5, nb=NB):
    out = []
    for b in range(nb):
        u = (b + 0.5) / nb - 0.5
        a, c = math.pi * F * u, math.pi * L * u
        sn = 1.0 if c == 0 else math.sin(c) / c
        out.append(math.cos(a) ** 2 * sn * sn)
    return out


def esperado_A(F, piso=0.0):
    """fracao media da faixa ate achar, versao aleatoria com reposicao (formula exata, faixa grande)."""
    I = [max(x, piso) for x in intensidades(F)]
    s = sum(I)
    p = [x / s for x in I]
    return sum(1 / pb for pb in p) / NB ** 2


class OrdemB:
    """versao B, com mapeamento inverso exato (chunk -> quantos chunks foram varridos antes)."""

    def __init__(self, n_chunks, F, janela=4, kmax=100):
        self.n, self.jan = n_chunks, janela
        nb = min(NB, n_chunks)
        I = intensidades(F, nb=nb)
        imax = max(I)
        self.lo = [n_chunks * b // nb for b in range(nb + 1)]
        self.ordem = sorted(range(nb), key=lambda b: (-I[b], b))      # claras primeiro em cada rodada
        self.k = [max(1, round(I[b] / imax * kmax)) for b in range(nb)]
        self.W = [-(-(self.lo[b + 1] - self.lo[b]) // janela) for b in range(nb)]
        self.pos = {b: i for i, b in enumerate(self.ordem)}
        self.inv = [pow(golden_stride(w), -1, w) if w > 1 else 0 for w in self.W]
        # a ultima janela de cada faixa pode ser parcial: guarda o tamanho dela e a posicao dela na fila da faixa
        self.ult = [(self.lo[b + 1] - self.lo[b]) - (self.W[b] - 1) * janela for b in range(nb)]
        self.pos_ult = [(self.W[b] - 1) * self.inv[b] % self.W[b] if self.W[b] > 1 else 0 for b in range(nb)]

    def chunks_primeiras(self, c, m):
        """chunks varridos pelas m primeiras janelas da faixa c"""
        m = min(m, self.W[c])
        return m * self.jan - ((self.jan - self.ult[c]) if self.pos_ult[c] < m else 0)

    def fracao(self, chunk):
        b = bisect.bisect_right(self.lo, chunk) - 1
        off = chunk - self.lo[b]
        jw, dentro = divmod(off, self.jan)
        wi = jw * self.inv[b] % self.W[b] if self.W[b] > 1 else 0      # posicao da janela na fila da faixa
        R, j = divmod(wi, self.k[b])
        antes = sum(self.chunks_primeiras(c, R * self.k[c]) for c in range(len(self.W)))   # rodadas completas
        for c in self.ordem[:self.pos[b]]:                                                  # faixas antes, na rodada R
            antes += self.chunks_primeiras(c, (R + 1) * self.k[c]) - self.chunks_primeiras(c, R * self.k[c])
        antes += self.chunks_primeiras(b, wi) - self.chunks_primeiras(b, R * self.k[b])     # janelas da faixa b antes dela
        return (antes + dentro + 1) / self.n


if __name__ == "__main__":
    print("A) aleatoria com reposicao (literal do video), faixa grande -- fracao media ate achar:")
    for F in (10, 20):
        print(f"   F={F}: sem piso = {esperado_A(F):.1f}   | piso 1% = {esperado_A(F, 0.01):.3f}   | piso 10% = {esperado_A(F, 0.1):.3f}")
    print("   (1,0 = a faixa inteira; uniforme sem repeticao = 0,5)\n")

    print("B) rodadas sem repeticao (janela = 4 chunks ~ 1,05 milhao de chaves, kmax = 100):")
    rnd = random.Random(99)
    for bits in (40, 50, 71):
        n = -(-(1 << (bits - 1)) // CHUNK)
        for F in (10, 20):
            o = OrdemB(n, F)
            T = sum(o.k)
            amostra = 3000 if bits == 71 else 5000
            xs = [o.fracao(rnd.randrange(n)) for _ in range(amostra)]
            ic = 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))
            extra = ""
            if bits == 71:
                horas = T * o.jan * CHUNK / 6.67e6 / 3600
                extra = f"  | 1 rodada = {T} janelas, passa pelas 4096 faixas em ~{horas:.1f} h no celular"
            print(f"   puzzle {bits} F={F}: media={statistics.fmean(xs):.4f} (+-{ic:.4f}){extra}")
