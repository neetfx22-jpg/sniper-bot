"""Testa estratégias de apostas com stake fixo de 1 unidade.

Valor: aposta quando a odd disponível paga mais que a probabilidade 'justa' da Pinnacle
(margem removida). Fonte da odd: máxima do mercado, Bet365, média, Betfair (comissão 2%).
Vieses: aposta tudo de um tipo (mandante, empate, favorito, zebra, over...) para ver se
o mercado erra de forma sistemática.
"""
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

J = pd.read_pickle("dados/jogos.pkl")
J["ano"] = J.data.dt.year
COMISSAO = 0.02

def justo(df, pre):
    inv = 1 / df[[f"{pre}_H", f"{pre}_D", f"{pre}_A"]].values
    return inv / inv.sum(axis=1, keepdims=True)

def apostas_valor(fonte_fair, fonte_odd, limiar, odd_max=None):
    """Uma linha por aposta: odd, prob justa, ganhou?, data, liga."""
    cols_f = [f"{fonte_fair}_{x}" for x in "HDA"]; cols_o = [f"{fonte_odd}_{x}" for x in "HDA"]
    d = J.dropna(subset=cols_f + cols_o)
    pj = justo(d, fonte_fair)
    O = d[cols_o].values.astype(float)
    if fonte_odd in ("e", "ec"):
        O = 1 + (O - 1) * (1 - COMISSAO)
    linhas = []
    for i, x in enumerate("HDA"):
        ev = O[:, i] * pj[:, i] - 1
        ok = ev > limiar
        if odd_max:
            ok &= O[:, i] <= odd_max
        sub = d[ok]
        linhas.append(pd.DataFrame({"data": sub.data.values, "liga": sub.liga.values, "odd": O[ok, i],
                                    "pj": pj[ok, i], "ev": ev[ok], "ganhou": (sub.res == x).values, "lado": x}))
    A = pd.concat(linhas)
    A["lucro"] = np.where(A.ganhou, A.odd - 1, -1.0)
    return A.sort_values("data")

def apostas_gols(fonte_fair, fonte_odd, limiar):
    fo, fu = {"p": ("po", "pu"), "pc": ("pco", "pcu")}[fonte_fair]
    oo, ou = {"m": ("mo", "mu"), "mc": ("mco", "mcu"), "e": ("eo", "eu"), "ec": ("eco", "ecu")}[fonte_odd]
    d = J.dropna(subset=[fo, fu, oo, ou])
    inv = 1 / d[[fo, fu]].values; pj = inv / inv.sum(1, keepdims=True)
    O = d[[oo, ou]].values.astype(float)
    if fonte_odd in ("e", "ec"):
        O = 1 + (O - 1) * (1 - COMISSAO)
    linhas = []
    for i, lado in enumerate(("over", "under")):
        ev = O[:, i] * pj[:, i] - 1; ok = ev > limiar; sub = d[ok]
        g = sub.over.values if lado == "over" else ~sub.over.values
        linhas.append(pd.DataFrame({"data": sub.data.values, "liga": sub.liga.values, "odd": O[ok, i], "pj": pj[ok, i],
                                    "ev": ev[ok], "ganhou": g, "lado": lado}))
    A = pd.concat(linhas); A["lucro"] = np.where(A.ganhou, A.odd - 1, -1.0)
    return A.sort_values("data")

def resumo(A):
    if len(A) == 0:
        return dict(n=0)
    roi = A.lucro.mean(); t = roi / (A.lucro.std() / np.sqrt(len(A)))
    por_ano = A.groupby(A.data.dt.year).lucro.mean()
    return dict(n=len(A), roi=roi, t=t, anos_pos=f"{(por_ano > 0).sum()}/{len(por_ano)}", odd_media=A.odd.mean())

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    L = []
    for nome, ff, fo in [("abertura: máx. do mercado", "p", "m"), ("abertura: Bet365", "p", "b"),
                         ("abertura: média", "p", "a"), ("abertura: Betfair (2%)", "p", "e"),
                         ("fechamento: máx. do mercado", "pc", "mc"), ("fechamento: Bet365", "pc", "bc"),
                         ("fechamento: Betfair (2%)", "pc", "ec")]:
        for lim in (0.0, 0.02, 0.05, 0.10):
            for om in (None, 4.0):
                L.append({"estrategia": "valor 1X2 " + nome, "limiar": lim, "odd_max": om or "-",
                          **resumo(apostas_valor(ff, fo, lim, om))})
    for nome, ff, fo in [("abertura: máx.", "p", "m"), ("abertura: Betfair", "p", "e"),
                         ("fechamento: máx.", "pc", "mc"), ("fechamento: Betfair", "pc", "ec")]:
        for lim in (0.0, 0.02, 0.05):
            L.append({"estrategia": "valor gols 2.5 " + nome, "limiar": lim, "odd_max": "-", **resumo(apostas_gols(ff, fo, lim))})
    T = pd.DataFrame(L)
    print(T.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    T.to_csv("saida_valor.csv", index=False)
