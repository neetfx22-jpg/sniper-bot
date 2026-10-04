"""Backtest dos scripts do usuário nos concursos reais, com os prémios pagos e o preço de cada época."""
import ast, re, random, itertools
import numpy as np
from backtest import H, D, PR, PRECO, ok, mask, popc, escolhe

anos = np.array([int(h["data"][-4:]) for h in H])

def avalia(nome, gerador, idx):
    gasto = ganho = 0.0; c = np.zeros(16, int); univ15 = 0
    for i in idx:
        jogos, univ = gerador(i)
        ap = np.array([mask(j) for j in jogos], dtype=np.int64)
        ac = popc(np.bitwise_and(ap, D[i])); gasto += len(ap) * PRECO[i]; ganho += PR[i, ac].sum()
        for a in ac: c[a] += 1
        if univ is not None: univ15 += bin(mask(univ) & int(D[i])).count("1") == 15
    print(f"   {nome:<52} {len(idx):>5} concursos | gasto R$ {gasto:>11,.0f} | ganho R$ {ganho:>11,.0f} | retorno {ganho / gasto:.3f} | "
          f"14 pts: {c[14]:>3} | 15 pts: {c[15]} | 15 dentro das 18: {univ15}".replace(",", "."))
    return ganho / gasto

# 1) matriz do correçãoloto.py
src = open("scripts_usuario/correçãoloto.py", encoding="utf-8").read()
MAT = [sorted(set(r)) for r in ast.literal_eval(re.search(r"MATRIZ_FECHAMENTO = (\[.*?\n\])", src, re.S).group(1))]
# 2) gerador aleatório do lotofacil18numeros18jogos.py
def gera_aleatorio(dez, rnd):
    from collections import Counter
    cont, fin = Counter(), set()
    while len(fin) < 18:
        j = tuple(sorted(rnd.sample(sorted(dez, key=lambda x: cont[x]), 15)))
        if j not in fin: fin.add(j); cont.update(j)
    return [list(j) for j in fin]
# 3) 24 apostas fixas do loto1.py
src1 = open("scripts_usuario/loto1.py", encoding="utf-8").read()
FIXAS = [sorted(s) for s in ast.literal_eval(re.search(r"apostas = (\[.*?\n\])", src1, re.S).group(1).replace("{", "[").replace("}", "]"))]

rng = np.random.default_rng(1); rnd = random.Random(1)
todos = [i for i in range(10, len(H)) if ok[i]]
atual = [i for i in todos if PRECO[i] == 3.5]
print(f"concursos: todos {len(todos)} | época atual (aposta R$ 3,50) {len(atual)}")
for metodo in ("mais sorteadas (últimos 10)", "aleatório"):
    print(f"\n== fechamentos de 18 dezenas, dezenas escolhidas por: {metodo} ==")
    for per, idx in (("toda a história", todos), ("época atual R$3,50", atual)):
        avalia(f"correçãoloto (matriz 18 jogos) | {per}", lambda i: (lambda dz: ([[dz[k] for k in r] for r in MAT], dz))(escolhe(metodo, i, 18, rng)), idx)
        avalia(f"lotofacil18numeros18jogos (aleat.) | {per}", lambda i: (lambda dz: (gera_aleatorio(dz, rnd), dz))(escolhe(metodo, i, 18, rng)), idx)

print("\n== loto1.py: as 24 apostas fixas ==")
for ano in sorted(set(anos[todos]))[-6:]:
    idx = [i for i in todos if anos[i] == ano]
    avalia(f"24 apostas fixas | ano {ano}", lambda i: (FIXAS, None), idx)
avalia("24 apostas fixas | toda a história", lambda i: (FIXAS, None), todos)
