"""Junta todos os CSVs do football-data.co.uk num formato único (dados/jogos.pkl).

Colunas por resultado X em {H, D, A}:
  p_X  Pinnacle abertura   pc_X Pinnacle fechamento
  m_X  máxima do mercado (abertura)   mc_X máxima no fechamento
  a_X  média do mercado (abertura)    ac_X média no fechamento
  b_X  Bet365 abertura     bc_X Bet365 fechamento
  e_X  Betfair Exchange abertura      ec_X Betfair Exchange fechamento
Gols 2.5: po/pu (Pinnacle), mo/mu (máx), pco/pcu, mco/mcu (fechamento), eo/eu, eco/ecu (Betfair).
"""
import glob, os
import numpy as np
import pandas as pd

D = os.path.join(os.path.dirname(__file__), "dados")
MAPA = {  # destino: lista de nomes possíveis (o primeiro que existir)
    "p_H": ["PSH"], "p_D": ["PSD"], "p_A": ["PSA"],
    "pc_H": ["PSCH"], "pc_D": ["PSCD"], "pc_A": ["PSCA"],
    "m_H": ["MaxH", "BbMxH"], "m_D": ["MaxD", "BbMxD"], "m_A": ["MaxA", "BbMxA"],
    "mc_H": ["MaxCH"], "mc_D": ["MaxCD"], "mc_A": ["MaxCA"],
    "a_H": ["AvgH", "BbAvH"], "a_D": ["AvgD", "BbAvD"], "a_A": ["AvgA", "BbAvA"],
    "ac_H": ["AvgCH"], "ac_D": ["AvgCD"], "ac_A": ["AvgCA"],
    "b_H": ["B365H"], "b_D": ["B365D"], "b_A": ["B365A"],
    "bc_H": ["B365CH"], "bc_D": ["B365CD"], "bc_A": ["B365CA"],
    "e_H": ["BFEH"], "e_D": ["BFED"], "e_A": ["BFEA"],
    "ec_H": ["BFECH"], "ec_D": ["BFECD"], "ec_A": ["BFECA"],
    "po": ["P>2.5"], "pu": ["P<2.5"], "pco": ["PC>2.5"], "pcu": ["PC<2.5"],
    "mo": ["Max>2.5", "BbMx>2.5"], "mu": ["Max<2.5", "BbMx<2.5"],
    "mco": ["MaxC>2.5"], "mcu": ["MaxC<2.5"],
    "eo": ["BFE>2.5"], "eu": ["BFE<2.5"], "eco": ["BFEC>2.5"], "ecu": ["BFEC<2.5"],
}

def padroniza(df, liga, temporada):
    out = pd.DataFrame({"liga": liga, "temporada": temporada}, index=df.index)
    out["data"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    out["casa"] = df.get("HomeTeam", df.get("Home"))
    out["fora"] = df.get("AwayTeam", df.get("Away"))
    out["gc"] = pd.to_numeric(df.get("FTHG", df.get("HG")), errors="coerce")
    out["gf"] = pd.to_numeric(df.get("FTAG", df.get("AG")), errors="coerce")
    for dst, srcs in MAPA.items():
        col = next((s for s in srcs if s in df.columns), None)
        out[dst] = pd.to_numeric(df[col], errors="coerce") if col else np.nan
    return out

partes = []
for f in sorted(glob.glob(f"{D}/*_*.csv")):
    nome = os.path.basename(f)[:-4]
    try:
        df = pd.read_csv(f, encoding="latin-1", on_bad_lines="skip")
    except Exception as e:
        print("erro", nome, e); continue
    df.columns = [c.replace("﻿", "").replace("ï»¿", "") for c in df.columns]
    if nome.startswith("extra_"):
        for (lg, temp), g in df.groupby(["League", "Season"]):
            partes.append(padroniza(g.reset_index(drop=True), nome[6:] + ":" + lg, str(temp)))
    else:
        liga, temp = nome.split("_")
        partes.append(padroniza(df, liga, temp))
J = pd.concat(partes, ignore_index=True).dropna(subset=["data", "gc", "gf"])
J["res"] = np.select([J.gc > J.gf, J.gc == J.gf], ["H", "D"], "A")
J["over"] = (J.gc + J.gf) > 2.5
J = J.sort_values("data").reset_index(drop=True)
J.to_pickle(f"{D}/jogos.pkl")
print(len(J), "jogos", J.data.min().date(), "->", J.data.max().date(), "| ligas:", J.liga.nunique())
print("com Pinnacle abertura:", J.p_H.notna().sum(), "| fechamento:", J.pc_H.notna().sum(),
      "| Betfair:", J.ec_H.notna().sum(), "| Bet365:", J.b_H.notna().sum())
