"""Relatório dos sinais: valor contra o FECHO (última leitura antes do jogo) e resultado.

Valor contra o fecho (CLV) é a melhor medida rápida: se as odds apanhadas ficam, em média,
acima do preço justo de fecho da Pinnacle, a vantagem é real, mesmo antes de haver muitos resultados.
"""
import os
import numpy as np
import pandas as pd
import config as C

def main():
    S = pd.read_csv(os.path.join(C.PASTA, "sinais.csv"))
    O = pd.read_csv(os.path.join(C.PASTA, "odds.csv"))
    O = O[pd.to_datetime(O.leitura) < pd.to_datetime(O.inicio)]
    fecho = O.sort_values("leitura").groupby(["jogo_id", "resultado"]).last()[["prob_justa", "leitura"]]
    S = S.join(fecho.rename(columns={"prob_justa": "pj_fecho", "leitura": "leitura_fecho"}), on=["jogo_id", "resultado"])
    S["clv"] = S.odd * S.pj_fecho - 1
    cam_r = os.path.join(C.PASTA, "resultados.csv")
    if os.path.exists(cam_r):
        R = pd.read_csv(cam_r).set_index("jogo_id")[["gols_casa", "gols_fora"]]
        S = S.join(R, on="jogo_id")
        res = np.select([S.gols_casa > S.gols_fora, S.gols_casa == S.gols_fora], ["H", "Draw"], "A")
        S["lucro"] = np.where(S.gols_casa.isna(), np.nan, np.where(res == S.resultado, S.odd - 1, -1.0))
    else:
        S["lucro"] = np.nan
    agora = pd.Timestamp.now(tz="UTC")
    jogados = S[pd.to_datetime(S.inicio) < agora]
    print(f"Sinais: {len(S)} ({len(S) / max(1, (agora - pd.to_datetime(S.leitura).min()).days / 7):.1f} por semana)")
    for casa, g in S.groupby("casa"):
        j = g[pd.to_datetime(g.inicio) < agora]
        liq = j.lucro.dropna()
        print(f"  {casa}: {len(g)} sinais | valor médio no aviso {g.valor.mean():+.1%} | "
              f"valor contra o fecho {j.clv.mean():+.1%} ({j.clv.notna().sum()} jogos) | "
              f"resultados {len(liq)}: lucro {liq.sum():+.2f} u, ROI {liq.mean() if len(liq) else float('nan'):+.1%}")
    print("\nÚltimos sinais:")
    cols = ["inicio", "casa_time", "fora_time", "resultado", "casa", "odd", "valor", "clv", "lucro"]
    print(S.sort_values("leitura").tail(15)[cols].to_string(index=False))

if __name__ == "__main__":
    main()
