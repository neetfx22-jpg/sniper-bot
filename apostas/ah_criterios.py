"""Busca de critérios de entrada no handicap asiático, com prova fora da amostra.

1) Cada característica vira 5 faixas (cortes calculados só no treino); categóricas ficam como estão.
2) Testa todas as condições simples e todos os pares de condições no TREINO.
3) Aprovadas no treino: >= 300 apostas, ROI > 0 e t > 2.
4) Mede as aprovadas no TESTE (épocas que a busca nunca viu).
"""
import sys, itertools
import numpy as np
import pandas as pd

momento = sys.argv[1] if len(sys.argv) > 1 else "abertura"
L = pd.read_pickle(f"dados/ah_{momento}.pkl")
TREINO = ["1213", "1314", "1415", "1516", "1617", "1718", "1819"] if momento == "abertura" else ["1920", "2021", "2122", "2223"]
tr = L.temporada.isin(TREINO)
te = ~tr & (L.temporada >= ("1920" if momento == "abertura" else "2324"))

NUM = ["odd", "prob", "f_pts5", "f_sg5", "f_sg10", "f_cob10", "meu_cob10", "desc_dif", "meu_desc", "fase"]
if momento == "fecho":
    NUM += ["mov_linha", "mov_prob"]
CAT = ["lado", "favorito", "linha", "liga", "mes"]
cond = {}
for c in NUM:
    q = L.loc[tr, c].quantile([0.2, 0.4, 0.6, 0.8]).values
    b = np.digitize(L[c].values, np.unique(q))
    b = np.where(L[c].isna(), -1, b)
    for k in np.unique(b[b >= 0]):
        lo = -np.inf if k == 0 else np.unique(q)[k - 1]; hi = np.inf if k == len(np.unique(q)) else np.unique(q)[k]
        cond[f"{c} em [{lo:.2f},{hi:.2f})"] = b == k
for c in CAT:
    vc = L.loc[tr, c].value_counts()
    for v in vc[vc >= 300].index:
        cond[f"{c} = {v}"] = (L[c] == v).values
nomes = list(cond)
M = np.column_stack([cond[n] for n in nomes])
lucro = L.lucro.values
trv, tev = tr.values, te.values

def stats(mask, part):
    x = lucro[mask & part]
    if len(x) < 2: return len(x), np.nan, np.nan
    return len(x), x.mean(), x.mean() / (x.std() / np.sqrt(len(x)))

res = []
for i in range(len(nomes)):
    res.append((nomes[i], "", M[:, i]))
for i, j in itertools.combinations(range(len(nomes)), 2):
    if nomes[i].split(" ")[0] == nomes[j].split(" ")[0]:
        continue
    res.append((nomes[i], nomes[j], M[:, i] & M[:, j]))
print(f"{momento}: {len(nomes)} condições, {len(res)} regras testadas no treino")

aprov = []
for a, b, m in res:
    n, roi, t = stats(m, trv)
    if n >= 300 and roi > 0 and t > 2:
        n2, roi2, t2 = stats(m, tev)
        aprov.append({"regra": a + (" E " + b if b else ""), "n_treino": n, "roi_treino": roi, "t_treino": t,
                      "n_teste": n2, "roi_teste": roi2, "t_teste": t2, "_m": m})
A = pd.DataFrame(aprov)
print(f"aprovadas no treino: {len(A)}")
if len(A):
    print(f"no teste: {(A.roi_teste > 0).mean():.0%} continuam positivas | ROI médio no teste {A.roi_teste.mean():+.2%} "
          f"| significativas no teste (t>2): {(A.t_teste > 2).sum()}")
    uniao = np.any(np.column_stack(A._m.values), axis=1)
    n, roi, t = stats(uniao, tev)
    print(f"apostar em TODAS as aprovadas no teste: {n} apostas, ROI {roi:+.2%} (t={t:.1f})")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
    print("\nmelhores 15 no treino e como foram no teste:")
    print(A.sort_values("t_treino", ascending=False).head(15).drop(columns="_m").to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    A.drop(columns="_m").to_csv(f"ah_regras_{momento}.csv", index=False)
    import pickle; pickle.dump({"regras": A.regra.tolist(), "mascara": np.column_stack(A._m.values)}, open(f"dados/ah_regras_{momento}.pkl", "wb"))
