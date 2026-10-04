"""Busca de parâmetros no TREINO (2025) e prova no TESTE (jan–set/2026), que a busca nunca vê."""
import itertools, json, os
import pandas as pd
import estrategias as E
import motor as M

base = pd.read_pickle(os.path.join(os.path.dirname(__file__), "dados", "base.pkl"))
C, H, Lo, R, FR = M.montar(base)
TREINO = slice("2025-01-01", "2025-12-31")
TESTE  = slice("2026-01-01", "2026-09-30")

grades = {
    "tendencia":        [dict(L=L, reb=rb) for L in (24, 72, 168, 336, 720) for rb in (8, 24, 168)],
    "momento_cruzado":  [dict(L=L, reb=rb, k=k) for L in (24, 72, 168, 336, 720) for rb in (24, 168) for k in (3, 5)],
    "reversao_cruzada": [dict(L=L, reb=rb, k=k, inverso=True) for L in (4, 12, 24, 72) for rb in (4, 12, 24) for k in (3, 5)],
    "carry_funding":    [dict(L=L, reb=rb, k=k) for L in (24, 72, 168, 336) for rb in (8, 24, 168) for k in (3, 5)],
    "rompimento":       [dict(N=N) for N in (24, 72, 168, 336, 720)],
}

def pesos(nome, p):
    if nome == "tendencia":        return E.tendencia(C, R, **p)
    if nome in ("momento_cruzado", "reversao_cruzada"): return E.momento_cruzado(C, R, **p)
    if nome == "carry_funding":    return E.carry_funding(FR, **p)
    if nome == "rompimento":       return E.rompimento(C, H, Lo, R, **p)

linhas, melhores = [], {}
for nome, grade in grades.items():
    for p in grade:
        W = pesos(nome, p)
        for taxa_nome, taxa in (("binance", M.TAXA_BINANCE), ("mexc", M.TAXA_MEXC)):
            r = M.rodar(W, R, FR, taxa=taxa)
            mt, ms = M.metricas(r[TREINO]), M.metricas(r[TESTE])
            linhas.append({"estrategia": nome, "param": json.dumps(p), "taxa": taxa_nome,
                           **{f"treino_{k}": v for k, v in mt.items()},
                           **{f"teste_{k}": v for k, v in ms.items()}})
T = pd.DataFrame(linhas)
os.makedirs("saida", exist_ok=True)
T.to_csv("saida/grade.csv", index=False)

# escolha SÓ pelo treino (sharpe), por estratégia e taxa
esc = T.loc[T.groupby(["estrategia", "taxa"])["treino_sharpe"].idxmax()]
cols = ["estrategia", "taxa", "param", "treino_sharpe", "treino_mes_medio", "teste_sharpe",
        "teste_mes_medio", "teste_mes_pior", "teste_max_dd", "teste_meses_pos", "teste_ret_total"]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(esc[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
esc.to_csv("saida/escolhidas.csv", index=False)
