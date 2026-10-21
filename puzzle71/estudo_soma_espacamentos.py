"""Os espacamentos da cadeia (ordem dos enderecos) vao e voltam e a soma tem limite: isso e padrao?

Mapa completo do puzzle 20. Compara as chaves reais (na ordem dos enderecos) com as mesmas chaves embaralhadas.
- troca de sinal: com que frequencia o espacamento muda de + para - (ou o contrario)
- soma acumulada dos espacamentos: a soma ate o passo i e sempre (chave_i - chave_0), entao nunca sai da faixa
- quantas vezes a soma "volta a zero" (cruza o ponto de partida)
"""
import random

from estudo_mapa_completo import mapa


def medir(seq, n):
    d = [b - a for a, b in zip(seq, seq[1:])]
    trocas = sum((x > 0) != (y > 0) for x, y in zip(d, d[1:])) / (len(d) - 1)
    soma, smax, smin, cruza = 0, 0, 0, 0
    for x in d:
        antes = soma
        soma += x
        smax, smin = max(smax, soma), min(smin, soma)
        cruza += (antes > 0) != (soma > 0)
    return trocas, smin / n, smax / n, cruza


def main():
    p = 20
    n = 1 << (p - 1)
    real = mapa(p)
    emb = real[:]
    random.Random(20).shuffle(emb)
    print(f"puzzle {p}, {n} chaves (faixa inteira)\n")
    print("               troca de sinal   soma minima/N   soma maxima/N   cruzou o zero")
    for nome, s in (("real", real), ("embaralhado", emb)):
        t, mn, mx, c = medir(s, n)
        print(f"{nome:<14} {t:>8.1%}         {mn:+.3f}          {mx:+.3f}          {c:>7}")
    print("\nporque: a soma dos espacamentos ate o passo i e chave_i - chave_0, que fica sempre entre -N e +N;"
          " e numa lista em ordem aleatoria o sinal troca em ~2/3 dos passos.")


if __name__ == "__main__":
    main()
