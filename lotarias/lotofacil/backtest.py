"""Backtest de fechamentos/desdobramentos da Lotofácil com TODOS os concursos e os prémios realmente pagos.

Preço da aposta de 15 dezenas em cada época = prémio de 11 acertos / 2 (relação fixa da Caixa:
R$7 com aposta a R$3,50; R$6 a R$3,00; R$5 a R$2,50...). Retorno medido em R$ ganho por R$ apostado.
"""
import json, itertools
import numpy as np

H = sorted(json.load(open("historico.json")), key=lambda x: x["concurso"])
def mask(ds): 
    m = 0
    for d in ds: m |= 1 << (int(d) - 1)
    return m
D = np.array([mask(h["dezenas"]) for h in H], dtype=np.int64)
PR = np.zeros((len(H), 16))
for i, h in enumerate(H):
    for p in h["premiacoes"]:
        k = int(p["descricao"].split()[0]); PR[i, k] = float(p["valorPremio"] or 0)
PRECO = PR[:, 11] / 2
ok = PRECO > 0
popc = np.vectorize(lambda x: bin(int(x)).count("1"))

def premio(apostas, i):
    """Prémio total de um conjunto de apostas (máscaras) no concurso i."""
    acertos = popc(np.bitwise_and(apostas, D[i]))
    return PR[i, acertos].sum()

def fechamento_completo(dez):
    return np.array([mask(c) for c in itertools.combinations(dez, 15)], dtype=np.int64)

def fechamento_reduzido_18():
    """Greedy: conjunto de apostas (15 de 18) que garante 14 acertos se as 15 sorteadas estiverem nas 18."""
    tods = [frozenset(c) for c in itertools.combinations(range(18), 15)]
    falta = set(range(len(tods))); esc = []
    viz = [{j for j, t in enumerate(tods) if len(w & t) >= 14} for w in tods]
    while falta:
        k = max(range(len(tods)), key=lambda a: len(viz[a] & falta))
        esc.append(sorted(tods[k])); falta -= viz[k]
    return esc

def escolhe(metodo, i, n, rng):
    if metodo == "aleatório":
        return sorted(rng.choice(np.arange(1, 26), n, replace=False))
    if metodo == "último concurso":   # as 15 do último + as mais frequentes até completar n
        base = [d for d in range(1, 26) if D[i - 1] >> (d - 1) & 1]
    else:
        base = []
    freq = np.array([sum((D[j] >> (d - 1)) & 1 for j in range(i - 10, i)) for d in range(1, 26)])
    ordem = list(np.argsort(-freq, kind="stable") + 1) if not metodo.startswith("menos") else list(np.argsort(freq, kind="stable") + 1)
    for d in ordem:
        if len(base) >= n: break
        if d not in base: base.append(int(d))
    return sorted(base[:n])

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    RED = fechamento_reduzido_18()
    idx = [i for i in range(10, len(H)) if ok[i]]
    print(f"concursos testados: {len(idx)} ({H[idx[0]]['concurso']} a {H[idx[-1]]['concurso']}) | fechamento reduzido de 18: {len(RED)} apostas")
    estr = [("1 aposta simples", 15, None), ("fechamento completo 16", 16, "c"), ("fechamento completo 17", 17, "c"),
            ("fechamento completo 18", 18, "c"), (f"fechamento reduzido 18 ({len(RED)} apostas, garante 14 se 15 nas 18)", 18, "r")]
    for metodo in ("mais sorteadas (últimos 10)", "menos sorteadas (últimos 10)", "último concurso", "aleatório"):
        print(f"\n== dezenas escolhidas por: {metodo} ==")
        for nome, n, tipo in estr:
            gasto = ganho = 0.0; p15 = p14 = 0
            for i in idx:
                dez = escolhe(metodo, i, n, rng)
                ap = np.array([mask([dez[k] for k in w]) for w in RED], dtype=np.int64) if tipo == "r" else \
                     (fechamento_completo(dez) if tipo == "c" else np.array([mask(dez)], dtype=np.int64))
                gasto += len(ap) * PRECO[i]
                ac = popc(np.bitwise_and(ap, D[i])); ganho += PR[i, ac].sum()
                p15 += (ac == 15).any(); p14 += (ac >= 14).any()
            print(f"   {nome:<58} gasto R$ {gasto:>14,.0f} | ganho R$ {ganho:>14,.0f} | retorno {ganho / gasto:.3f} por real | "
                  f"15 pts em {p15} concursos, 14+ em {p14}".replace(",", "."))
