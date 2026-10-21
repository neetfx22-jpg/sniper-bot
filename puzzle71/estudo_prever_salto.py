"""Da para prever o tamanho do proximo salto na cadeia (ordem dos enderecos)? E a chave do alvo pelas vizinhas?

Mapa completo do puzzle 20 (524.288 chaves). Real (ordem dos enderecos) x embaralhado ao acaso.
1) prever o proximo salto a partir do anterior (melhor regra linear, ajustada em metade e testada na outra)
2) prever a CHAVE de uma posicao da cadeia pelas chaves das 10 vizinhas (5 de cada lado):
   media das vizinhas, mediana, e "a vizinha mais proxima + salto tipico"; comparado com chutar o meio da faixa
"""
import random
import statistics

from estudo_mapa_completo import mapa


def ajusta_linear(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return b, my - b * mx


def prever_saltos(seq, n):
    d = [b - a for a, b in zip(seq, seq[1:])]
    meio = len(d) // 2
    b, a = ajusta_linear(d[:meio - 1], d[1:meio])                 # treino: 1a metade
    teste = list(zip(d[meio:-1], d[meio + 1:]))                    # teste: 2a metade
    erro_regra = statistics.fmean(abs(y - (a + b * x)) for x, y in teste) / n
    erro_zero = statistics.fmean(abs(y) for _, y in teste) / n     # chutar salto 0
    return b, erro_regra, erro_zero


def prever_chave(seq, n, ini, rnd, amostras=20000):
    erros = {"media das 10 vizinhas": [], "mediana das vizinhas": [], "chute: meio da faixa": [], "chute aleatorio": []}
    for _ in range(amostras):
        i = rnd.randrange(5, len(seq) - 5)
        viz = seq[i - 5:i] + seq[i + 1:i + 6]
        alvo = seq[i]
        erros["media das 10 vizinhas"].append(abs(statistics.fmean(viz) - alvo))
        erros["mediana das vizinhas"].append(abs(statistics.median(viz) - alvo))
        erros["chute: meio da faixa"].append(abs(ini + n / 2 - alvo))
        erros["chute aleatorio"].append(abs(ini + rnd.random() * n - alvo))
    return {k: statistics.fmean(v) / n for k, v in erros.items()}


def main():
    p = 20
    n, ini = 1 << (p - 1), 1 << (p - 1)
    real = mapa(p)
    emb = real[:]
    rnd = random.Random(7)
    rnd.shuffle(emb)
    print(f"puzzle {p}, {n} chaves (faixa inteira)\n")
    print("1) prever o proximo salto pelo anterior (erro medio em fracao da faixa; menor = melhor)")
    for nome, s in (("real", real), ("embaralhado", emb)):
        b, er, ez = prever_saltos(s, n)
        print(f"   {nome:<12} regra: proximo = {b:+.3f} x anterior   erro {er:.4f}   (chutar 0: {ez:.4f})")
    print("\n2) prever a CHAVE de um ponto da cadeia pelas 10 vizinhas (erro medio em fracao da faixa)")
    for nome, s in (("real", real), ("embaralhado", emb)):
        r = prever_chave(s, n, ini, random.Random(3))
        print(f"   {nome}:")
        for k, v in r.items():
            print(f"      {k:<24} {v:.4f}")
    print("\nreferencia: chutar o meio da faixa erra em media 0,25; chute aleatorio, 0,333")


if __name__ == "__main__":
    main()
