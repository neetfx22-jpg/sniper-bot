"""Validação por janelas (walk-forward).

Para cada trimestre de 2024T1 a 2026T3: escolhe, por família, a combinação com melhor
Sharpe nos 12 meses ANTERIORES e aplica no trimestre seguinte. O resultado concatenado
é 100% fora da amostra (inclui o risco de escolher mal).
"""
import sys
import numpy as np
import pandas as pd
import motor as M

tx = sys.argv[1] if len(sys.argv) > 1 else "mexc"
RET = pd.read_pickle(f"saida/ret_{tx}.pkl").astype("float64")
RET = RET.loc["2023-01-01":"2026-09-30"]
fam = pd.Series({c: c.split(" ")[0] for c in RET.columns})

def sharpe(r):
    s = r.std()
    return r.mean() / s * np.sqrt(8760) if s > 0 else -9

trimestres = pd.period_range("2024Q1", "2026Q3", freq="Q")
oos, escolhas = {}, []
for f in sorted(fam.unique()) + ["_todas"]:
    cols = RET.columns if f == "_todas" else fam.index[fam == f]
    partes = []
    for q in trimestres:
        ini, fim = q.start_time.tz_localize("UTC"), q.end_time.tz_localize("UTC")
        tr = RET.loc[ini - pd.DateOffset(months=12): ini - pd.Timedelta(hours=1), cols]
        sh = tr.apply(sharpe)
        best = sh.idxmax()
        escolhas.append({"familia": f, "tri": str(q), "escolha": best, "sharpe_treino": sh.max()})
        partes.append(RET.loc[ini:fim, best])
    oos[f] = pd.concat(partes)
OOS = pd.DataFrame(oos)
# carteira mista: média das famílias que tiveram Sharpe de treino > 0 no trimestre
E = pd.DataFrame(escolhas)
mix = []
for q in trimestres:
    ini, fim = q.start_time.tz_localize("UTC"), q.end_time.tz_localize("UTC")
    ok = E[(E.tri == str(q)) & (E.sharpe_treino > 0) & (E.familia != "_todas")].familia.tolist()
    mix.append(OOS.loc[ini:fim, ok].mean(axis=1) if ok else OOS.loc[ini:fim].iloc[:, 0] * 0)
OOS["_mistura"] = pd.concat(mix)
OOS.to_pickle(f"saida/oos_{tx}.pkl"); E.to_csv(f"saida/escolhas_{tx}.csv", index=False)

linhas = []
for f in OOS.columns:
    r = OOS[f]
    m = M.metricas(r)
    anos = {str(a): (1 + r[str(a)]).prod() - 1 for a in (2024, 2025, 2026)}
    linhas.append({"familia": f, "sharpe": m["sharpe"], "mes_medio": m["mes_medio"], "mes_pior": m["mes_pior"],
                   "max_dd": m["max_dd"], "meses_pos": m["meses_pos"], **anos})
T = pd.DataFrame(linhas).sort_values("sharpe", ascending=False)
pd.set_option("display.width", 250)
print(f"== fora da amostra 2024T1–2026T3, taxa {tx}, exposição 1x ==")
print(T.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

# robustez: fração das combinações de cada família com Sharpe > 0 no período todo (2023–2026)
rob = RET.apply(sharpe).groupby(fam).agg(["median", lambda s: (s > 0).mean(), "count"])
rob.columns = ["sharpe_mediano", "fracao_positiva", "n"]
print("\n== robustez das famílias (todas as combinações, 2023–set/2026) ==")
print(rob.sort_values("sharpe_mediano", ascending=False).to_string(float_format=lambda x: f"{x:.2f}"))
