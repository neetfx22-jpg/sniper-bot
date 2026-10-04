"""Euromilhões: escolher as 'melhores' N combinações pelo passado e testar no futuro.
Replica o método do usuário: pontua candidatas por quanto teriam ganho no TREINO, pega as top N,
e mede o retorno delas no TESTE (sorteios que nunca viram). Compara com candidatas aleatórias."""
import json
import numpy as np
from math import comb

D = json.load(open("draws.json"))
# formato atual: 5 nºs de 1-50 + 2 estrelas de 1-12. Usa sorteios com estrelas <= 12.
draws = []
for d in D:
    nums = [int(x) for x in d["numbers"]]; st = [int(x) for x in d["stars"]]
    if len(nums) == 5 and len(st) == 2 and max(st) <= 12:
        mn = 0
        for n in nums: mn |= 1 << (n - 1)
        ms = 0
        for s in st: ms |= 1 << (s - 1)
        draws.append((d["date"], mn, ms))
print(f"sorteios usáveis (formato 5/50 + 2/12): {len(draws)}")
dm = np.array([x[1] for x in draws], dtype=np.int64)
ds = np.array([x[2] for x in draws], dtype=np.int64)
corte = int(len(draws) * 0.7)
print(f"treino: {corte} sorteios | teste: {len(draws)-corte} sorteios\n")

def popc(a):
    a = a - ((a >> 1) & 0x5555555555555555)
    a = (a & 0x3333333333333333) + ((a >> 2) & 0x3333333333333333)
    a = (a + (a >> 4)) & 0x0f0f0f0f0f0f0f0f
    return (a * 0x0101010101010101) >> 56

# prémio médio (€) por categoria (nº acertos, estrelas acertadas)
PREM = {(5,2):50_000_000,(5,1):300_000,(5,0):25_000,(4,2):2_500,(4,1):150,(4,0):60,
        (3,2):80,(3,1):12,(3,0):10,(2,2):20,(2,1):7,(1,2):8}
def valor(nn, ss):
    return np.array([[PREM.get((int(n),int(s)),0) for s in range(3)] for n in range(6)])[nn, ss]

# gera candidatas aleatórias
rng = np.random.default_rng(0)
NC = 400000
cm = np.empty(NC, dtype=np.int64); cs = np.empty(NC, dtype=np.int64)
for i in range(NC):
    m=0
    for n in rng.choice(50,5,replace=False): m|=1<<int(n)
    s=0
    for e in rng.choice(12,2,replace=False): s|=1<<int(e)
    cm[i]=m; cs[i]=s
print(f"candidatas geradas: {NC:,}".replace(",","."))

def ganho(idx_draws):
    """ganho total de cada candidata nos sorteios dados (€)."""
    g = np.zeros(NC)
    for k in idx_draws:
        nn = popc(cm & dm[k]).astype(int); ss = popc(cs & ds[k]).astype(int)
        g += valor(nn, ss)
    return g
tr = np.arange(corte); te = np.arange(corte, len(draws))
g_tr = ganho(tr); g_te = ganho(te)
custo_te = len(te) * 2.50   # por candidata

print(f"\n{'seleção':>22} | {'retorno no TESTE (€ por €)':>26}")
ordem = np.argsort(-g_tr)
for N in (10000, 20000, 50000):
    sel = ordem[:N]
    ret = g_te[sel].sum() / (N * custo_te)
    print(f"   melhores {N:>6,} do treino | {ret:.3f}".replace(",","."))
print(f"   {'todas (aleatórias)':>19} | {g_te.sum()/(NC*custo_te):.3f}")
r = np.corrcoef(g_tr, g_te)[0,1]
print(f"\ncorrelação ganho-treino x ganho-teste: {r:+.4f} (0 = o passado não prevê o futuro)")
