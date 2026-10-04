"""Verifica se um fechamento de 18 dezenas GARANTE 13 acertos quando as 15 sorteadas estão nas 18:
testa os 816 sorteios possíveis dentro das 18 e mede o melhor bilhete em cada um."""
import itertools, random, re, ast
from collections import Counter

def melhor_por_sorteio(jogos):
    res = Counter()
    for s in itertools.combinations(range(18), 15):
        s = set(s); res[max(len(s & set(j)) for j in jogos)] += 1
    return res

# matriz do correçãoloto.py (índices 0-17)
src = open("scripts_usuario/correçãoloto.py", encoding="utf-8").read()
M = ast.literal_eval(re.search(r"MATRIZ_FECHAMENTO = (\[.*?\n\])", src, re.S).group(1))
jogos = [sorted(set(r)) for r in M]
print(f"correçãoloto.py: {len(M)} linhas na matriz | jogos válidos (15 dezenas distintas): {sum(len(j) == 15 for j in jogos)}")
r = melhor_por_sorteio([j for j in jogos if len(j) == 15])
print("   melhor bilhete nos 816 sorteios possíveis:", dict(sorted(r.items())), "| garante 13?", "SIM" if min(r) >= 13 else f"NÃO (pior caso: {min(r)} acertos)")

# gerador aleatório do lotofacil18numeros18jogos.py: repete a lógica 1.000 vezes
falhas, piores = 0, Counter()
for semente in range(1000):
    random.seed(semente); cont = Counter(); fin = set(); dez = list(range(18))
    while len(fin) < 18:
        ordd = sorted(dez, key=lambda x: cont[x]); j = tuple(sorted(random.sample(ordd, 15)))
        if j not in fin: fin.add(j); cont.update(j)
    r = melhor_por_sorteio(list(fin)); piores[min(r)] += 1; falhas += min(r) < 13
print(f"\nlotofacil18numeros18jogos.py (1.000 gerações): a 'garantia de 13' FALHA em {falhas / 10:.1f}% das gerações | pior caso por geração: {dict(sorted(piores.items()))}")

# quantos jogos são precisos de verdade para garantir 13 (ganancioso) e 14
todos = [frozenset(c) for c in itertools.combinations(range(18), 15)]
for alvo in (13, 14):
    falta, esc = set(range(len(todos))), 0
    viz = [{i for i, t in enumerate(todos) if len(w & t) >= alvo} for w in todos]
    while falta:
        k = max(range(len(todos)), key=lambda a: len(viz[a] & falta)); falta -= viz[k]; esc += 1
    print(f"para GARANTIR {alvo} acertos com 18 dezenas são precisos ~{esc} jogos (construção gananciosa)")
