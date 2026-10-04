"""Modelo (gradient boosting) para prever se o lado cobre o handicap, treinado época a época
só com o passado; aposta quando a probabilidade prevista x odd - 1 > limiar."""
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

momento = sys.argv[1] if len(sys.argv) > 1 else "abertura"
L = pd.read_pickle(f"dados/ah_{momento}.pkl")
L = L[L.lucro != 0].copy()                                   # devoluções totais não informam nada
L["ganha"] = (L.lucro > 0).astype(int)
X_COLS = ["odd", "prob", "linha", "favorito", "f_pts5", "f_sg5", "f_sg10", "f_cob10", "meu_cob10",
          "desc_dif", "meu_desc", "fase", "mes"] + (["mov_linha", "mov_prob"] if momento == "fecho" else [])
L["lado_n"] = (L.lado == "H").astype(int); X_COLS.append("lado_n")
L["liga_n"] = L.liga.astype("category").cat.codes; X_COLS.append("liga_n")
temps = sorted(L.temporada.unique())
inicio = temps.index("1920") if momento == "abertura" else temps.index("2223")
P = pd.Series(np.nan, index=L.index)
for t in temps[inicio:]:
    tr, te = L.temporada < t, L.temporada == t
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                       categorical_features=[X_COLS.index("liga_n")], random_state=0)
    m.fit(L.loc[tr, X_COLS], L.loc[tr, "ganha"])
    P[te] = m.predict_proba(L.loc[te, X_COLS])[:, 1]
T = L[P.notna()].assign(p=P[P.notna()])
# prob. de ganhar entre os que não devolvem; valor esperado aproximado para linhas inteiras/meias
T["ev"] = T.p * T.odd - 1
print(f"{momento}: teste {T.temporada.min()}–{T.temporada.max()}, {len(T)} apostas possíveis, ROI de tudo {T.lucro.mean():+.2%}")
for lim in (0.0, 0.02, 0.05, 0.08, 0.12):
    s = T[T.ev > lim]
    if len(s) < 30: continue
    t = s.lucro.mean() / (s.lucro.std() / np.sqrt(len(s)))
    pa = s.groupby("temporada").lucro.mean()
    print(f"  aposta se valor previsto > {lim:.0%}: {len(s):>6} apostas | ROI {s.lucro.mean():+.2%} (t={t:.1f}) | "
          f"Bet365 {s.lucro_b365.mean():+.2%} | épocas positivas {(pa > 0).sum()}/{len(pa)}")
