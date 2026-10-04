"""Base de código Lotofácil: carrega o histórico e dá utilitários para testar hipóteses.
Fonte: historico.json (API oficial da Caixa). Prémios e preço reais de cada concurso."""
import json
import numpy as np
import pandas as pd

_H = sorted(json.load(open("historico.json")), key=lambda x: x["concurso"])
datas = pd.to_datetime([h["data"] for h in _H], dayfirst=True)
concursos = np.array([h["concurso"] for h in _H])

def _mask(ds):
    m = 0
    for d in ds:
        m |= 1 << (int(d) - 1)
    return m

D = np.array([_mask(h["dezenas"]) for h in _H], dtype=np.int64)       # cada sorteio como bitmask de 25 bits
PR = np.zeros((len(_H), 16))
for i, h in enumerate(_H):
    for p in h["premiacoes"]:
        k = int(p["descricao"].split()[0])
        PR[i, k] = float(p["valorPremio"] or 0)
PRECO = PR[:, 11] / 2                                                  # relação fixa: prémio de 11 = metade do preço
_LUT = np.array([bin(i).count("1") for i in range(1 << 13)], dtype=np.int8)
def popcount(x):
    x = np.asarray(x, dtype=np.int64)
    return _LUT[x & 0x1FFF] + _LUT[(x >> 13) & 0x1FFF]

TODAS = None
def todas_combinacoes():
    """As 3.268.760 combinações de 15 em 25, como bitmasks (memoizado)."""
    global TODAS
    if TODAS is None:
        import itertools
        TODAS = np.fromiter((sum(1 << d for d in c) for c in itertools.combinations(range(25), 15)),
                            dtype=np.int64, count=3268760)
    return TODAS

def indices(ini=None, fim=None, preco=None):
    sel = np.ones(len(_H), bool)
    if ini: sel &= datas >= pd.Timestamp(ini)
    if fim: sel &= datas <= pd.Timestamp(fim)
    if preco: sel &= np.isclose(PRECO, preco)
    return np.where(sel)[0]

def paridade(mask):
    impares = sum(((mask >> d) & 1) for d in range(0, 25, 2))          # dezenas 1,3,5,... (bits pares)
    return impares, 15 - impares
