"""Um padrao aprendido em um alvo funciona em outro?

Gera chaves consecutivas (vizinhas umas das outras) a partir de dois pontos de partida diferentes:
  - TREINO: 15 mil chaves vizinhas de um alvo (puzzle 60)
  - TESTE : 15 mil chaves vizinhas de outro alvo (puzzle 70)
Para cada par (bit i do hash160, bit j da chave), mede a correlacao no TREINO, guarda os 20 pares
mais fortes ("padroes") e confere se eles se repetem no TESTE.
Se existir padrao, os 20 pares voltam fortes no teste. Se for acaso, voltam a ~0.
Tambem testa se o hash160 de chaves consecutivas tem relacao entre si (k e k+1).
"""
import hashlib
import math
import statistics

from hash160 import G, add, mul, ripemd160

N = 15000
BITS_CHAVE = 16       # bits baixos da chave (os que mudam entre vizinhas)


def h160_ponto(pt):
    x, y = pt
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return int.from_bytes(ripemd160(hashlib.sha256(pub).digest()), "big")


def gerar(k0):
    pt = mul(k0)
    out = []
    for i in range(N):
        out.append((k0 + i, h160_ponto(pt)))
        pt = add(pt, G)
    return out


def correlacoes(dados):
    n = len(dados)
    hb = [[(h >> i) & 1 for _, h in dados] for i in range(160)]
    kb = [[(k >> j) & 1 for k, _ in dados] for j in range(BITS_CHAVE)]
    corr = {}
    for i in range(160):
        mi = sum(hb[i]) / n
        for j in range(BITS_CHAVE):
            mj = sum(kb[j]) / n
            cov = sum(a * b for a, b in zip(hb[i], kb[j])) / n - mi * mj
            den = math.sqrt(mi * (1 - mi) * mj * (1 - mj)) or 1
            corr[(i, j)] = cov / den
    return corr


def main():
    ch = {int(n): int(k, 16) for n, k in (l.split()[:2] for l in open("chaves_resolvidas.txt"))}
    treino = gerar(ch[60] - N // 2)
    teste = gerar(ch[70] - N // 2)
    ct, cv = correlacoes(treino), correlacoes(teste)
    lim = 1 / math.sqrt(N)
    top = sorted(ct, key=lambda p: -abs(ct[p]))[:20]
    print(f"{N} chaves vizinhas por grupo; acaso tipico: |r| ~ {lim:.4f}\n")
    print("os 20 'padroes' mais fortes no TREINO e o que viram no TESTE:")
    for i, j in top:
        print(f"   bit {i:>3} do hash160 x bit {j:>2} da chave: treino r={ct[(i, j)]:+.4f}  ->  teste r={cv[(i, j)]:+.4f}")
    mesmo = sum(1 for p in top if ct[p] * cv[p] > 0)
    print(f"\nmantiveram o sinal no teste: {mesmo}/20 (acaso: ~10)")
    print(f"media de |r| no teste dos 20 escolhidos: {statistics.fmean(abs(cv[p]) for p in top):.4f} (acaso ~{0.8 * lim:.4f})")
    print(f"maior |r| entre os {160 * BITS_CHAVE} pares no treino: {abs(ct[top[0]]):.4f} "
          f"(esperado so por acaso com tantos pares: ~{lim * math.sqrt(2 * math.log(160 * BITS_CHAVE * 2)):.4f})")

    # vizinhas consecutivas: hash de k e de k+1 se parecem?
    iguais = [160 - bin(a[1] ^ b[1]).count("1") for a, b in zip(treino, treino[1:])]
    print(f"\nhash160(k) x hash160(k+1): bits iguais em media {statistics.fmean(iguais):.2f} de 160 (acaso: 80)")


if __name__ == "__main__":
    main()
