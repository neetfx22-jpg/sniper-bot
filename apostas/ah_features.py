"""Características pré-jogo para apostas de handicap asiático (uma linha por lado apostado).

Só usa informação conhecida ANTES do jogo: forma recente (pontos, saldo de gols, cobertura do
handicap nos últimos jogos), descanso, fase da época, liga, linha e odd, e o movimento
abertura -> fecho (este só para apostas feitas no fecho).
"""
import numpy as np
import pandas as pd
from handicap import liquida

J = pd.read_pickle("dados/jogos.pkl")
J = J[~J.liga.str.contains(":")].dropna(subset=["ahl", "aah_H", "aah_A"]).sort_values("data").reset_index(drop=True)
J["dif"] = J.gc - J.gf
# cobertura do handicap de abertura pelo mandante (+1 cobre, 0 devolve/meio, -1 não cobre), média de quartos
lin_c = J.ahcl.fillna(J.ahl)
J["cobre_casa"] = np.sign(liquida(J.dif.values, lin_c.values, np.full(len(J), 2.0)))

# histórico por equipa (casa e fora juntos), em ordem temporal, sem olhar o jogo atual
h = pd.concat([
    pd.DataFrame({"idx": J.index, "liga": J.liga, "time": J.casa, "data": J.data, "pts": np.select([J.dif > 0, J.dif == 0], [3, 1], 0),
                  "sg": J.dif, "cob": J.cobre_casa, "casa": 1}),
    pd.DataFrame({"idx": J.index, "liga": J.liga, "time": J.fora, "data": J.data, "pts": np.select([J.dif < 0, J.dif == 0], [3, 1], 0),
                  "sg": -J.dif, "cob": -J.cobre_casa, "casa": 0}),
]).sort_values(["data", "idx"])
g = h.groupby(["liga", "time"])
for n in (5, 10):
    h[f"pts{n}"] = g.pts.transform(lambda s: s.shift(1).rolling(n, min_periods=3).mean())
    h[f"sg{n}"] = g.sg.transform(lambda s: s.shift(1).rolling(n, min_periods=3).mean())
    h[f"cob{n}"] = g.cob.transform(lambda s: s.shift(1).rolling(n, min_periods=3).mean())
h["descanso"] = g.data.transform(lambda s: s.diff().dt.days)
h["njogos"] = g.cumcount()
F = ["pts5", "pts10", "sg5", "sg10", "cob5", "cob10", "descanso", "njogos"]
hc = h[h.casa == 1].set_index("idx")[F].add_prefix("c_")
hf = h[h.casa == 0].set_index("idx")[F].add_prefix("f_")
J = J.join(hc).join(hf)

def lados(momento):
    """momento='abertura': linha AHh, odd média de abertura; 'fecho': linha AHCh, odd média de fecho."""
    if momento == "abertura":
        d = J.dropna(subset=["ahl", "aah_H", "aah_A"]).copy(); lin, oh, oa = d.ahl, d.aah_H, d.aah_A
        bh, ba = d.bah_H, d.bah_A
    else:
        d = J.dropna(subset=["ahcl", "acah_H", "acah_A", "ahl", "aah_H"]).copy(); lin, oh, oa = d.ahcl, d.acah_H, d.acah_A
        bh, ba = d.bcah_H, d.bcah_A
    linhas = []
    for lado in ("H", "A"):
        s = 1 if lado == "H" else -1
        me, op = ("c_", "f_") if lado == "H" else ("f_", "c_")
        x = pd.DataFrame({
            "data": d.data, "liga": d.liga, "temporada": d.temporada, "lado": lado,
            "linha": lin * s, "odd": (oh if lado == "H" else oa), "odd_b365": (bh if lado == "H" else ba),
            "favorito": (lin * s < 0).astype(int),
            "f_pts5": d[me + "pts5"] - d[op + "pts5"], "f_sg5": d[me + "sg5"] - d[op + "sg5"],
            "f_sg10": d[me + "sg10"] - d[op + "sg10"], "f_cob10": d[me + "cob10"] - d[op + "cob10"],
            "meu_cob10": d[me + "cob10"], "desc_dif": d[me + "descanso"] - d[op + "descanso"],
            "meu_desc": d[me + "descanso"], "fase": d[[me + "njogos", op + "njogos"]].min(axis=1) % 46,
            "mes": d.data.dt.month,
        })
        # probabilidade implícita do lado (média, sem margem)
        inv = 1 / pd.concat([oh, oa], axis=1)
        x["prob"] = (inv.iloc[:, 0 if lado == "H" else 1] / inv.sum(axis=1)).values
        if momento == "fecho":
            x["mov_linha"] = (d.ahcl - d.ahl) * s            # >0: linha andou a favor (mercado gosta menos de mim)
            x["mov_prob"] = x["prob"] - ((1 / (d.aah_H if lado == "H" else d.aah_A)) /
                                         (1 / d.aah_H + 1 / d.aah_A)).values * (d.ahcl == d.ahl)
            x.loc[d.ahcl != d.ahl, "mov_prob"] = np.nan
        dif = (d.gc - d.gf).values * s
        x["lucro"] = liquida(dif, x.linha.values, x.odd.values)
        x["lucro_b365"] = liquida(dif, x.linha.values, x.odd_b365.fillna(0).values)
        x.loc[x.odd_b365.isna(), "lucro_b365"] = np.nan
        linhas.append(x)
    return pd.concat(linhas).sort_values("data").reset_index(drop=True)

if __name__ == "__main__":
    for m in ("abertura", "fecho"):
        L = lados(m)
        print(m, len(L), "apostas possíveis | ROI apostando tudo (odd média):", f"{L.lucro.mean():+.2%}",
              "| Bet365:", f"{L.lucro_b365.mean():+.2%}")
    L.to_pickle("dados/ah_fecho.pkl"); lados("abertura").to_pickle("dados/ah_abertura.pkl")
