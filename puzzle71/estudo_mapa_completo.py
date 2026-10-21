"""Mapa completo de puzzles pequenos: todas as chaves da faixa, ordenadas pelo endereco.

Para os puzzles 16 a 20 (faixa inteira), calcula o hash160 de TODAS as chaves, ordena pelo endereco e segue a
cadeia a partir do alvo: chave do alvo -> vizinha no endereco -> vizinha da vizinha... medindo os espacamentos
(distancia entre as chaves). Compara cada medida com a mesma lista de chaves EMBARALHADA AO ACASO (referencia).

1) cadeia em volta do alvo (as 10 vizinhas de cada lado no endereco)
2) espacamentos ao longo da cadeia: media, mediana, quantos pequenos, autocorrelacao (real x embaralhado)
3) o espacamento tem "assinatura"? histograma do puzzle N comparado com o do puzzle N+1 e com o embaralhado
"""
import hashlib
import math
import random
import statistics

from hash160 import G, add, mul, ripemd160


def h160_ponto(pt):
    x, y = pt
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return ripemd160(hashlib.sha256(pub).digest())


def mapa(p):
    ini, n = 1 << (p - 1), 1 << (p - 1)
    pt, out = mul(ini), []
    for i in range(n):
        out.append((h160_ponto(pt), ini + i))
        pt = add(pt, G)
    out.sort()
    return [k for _, k in out]


def stats(seq, n):
    d = [b - a for a, b in zip(seq, seq[1:])]
    ad = [abs(x) for x in d]
    lag = statistics.correlation(d[:-1], d[1:])
    alag = statistics.correlation(ad[:-1], ad[1:])
    peq = sum(x <= 16 for x in ad)
    return {"media": statistics.fmean(ad) / n, "mediana": statistics.median(ad) / n,
            "pequenos": peq, "autocorr": lag, "autocorr_abs": alag, "hist": hist(ad, n)}


def hist(ad, n, bins=10):
    h = [0] * bins
    for x in ad:
        h[min(int(x / n * bins), bins - 1)] += 1
    t = len(ad)
    return [v / t for v in h]


def dist_hist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / 2   # distancia de variacao total (0 = iguais)


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    rnd = random.Random(16)
    hs = {}
    print("puzzle  chaves   | espacamento medio/N  mediana/N | <=16 de distancia | autocorr(d)  autocorr(|d|)")
    for p in range(16, 21):
        n = 1 << (p - 1)
        seq = mapa(p)
        emb = seq[:]
        rnd.shuffle(emb)
        r, e = stats(seq, n), stats(emb, n)
        hs[p] = (r["hist"], e["hist"])
        print(f"{p:<7} {n:<8} | real {r['media']:.4f}  {r['mediana']:.4f}   | {r['pequenos']:>5}            |"
              f" {r['autocorr']:+.4f}     {r['autocorr_abs']:+.4f}")
        print(f"{'':16} | emb. {e['media']:.4f}  {e['mediana']:.4f}   | {e['pequenos']:>5}            |"
              f" {e['autocorr']:+.4f}     {e['autocorr_abs']:+.4f}")
        if p == 20:
            i = seq.index(ch[20])
            print(f"\n1) cadeia em volta do alvo do puzzle 20 (chave {ch[20]:#x}, posicao {i} de {n} na ordem dos enderecos):")
            viz = seq[max(0, i - 10):i + 11]
            print("   chaves:      " + " ".join(f"{k - (1 << 19):>6}" for k in viz) + "   (posicao dentro da faixa)")
            print("   espacamentos: " + " ".join(f"{b - a:+7}" for a, b in zip(viz, viz[1:])))
            sp = [abs(b - a) for a, b in zip(viz, viz[1:])]
            print(f"   espacamento medio em volta do alvo: {statistics.fmean(sp) / n:.3f} da faixa (geral: ~0,333)\n")
    print("3) assinatura do espacamento (histograma de |d| em 10 faixas); 0 = histogramas identicos:")
    for p in range(16, 20):
        print(f"   puzzle {p} x {p + 1}: real {dist_hist(hs[p][0], hs[p + 1][0]):.4f}   |  real x embaralhado (puzzle {p}): "
              f"{dist_hist(hs[p][0], hs[p][1]):.4f}")
    print("\nreferencia: para chaves em ordem aleatoria, espacamento medio = 1/3 da faixa, mediana ~0,29,"
          " autocorr(d) = -0,5 e autocorr(|d|) ~ +0,10 (ver as linhas 'emb.')")


if __name__ == "__main__":
    main()
