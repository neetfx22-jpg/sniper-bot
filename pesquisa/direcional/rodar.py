"""Roda várias simulações em paralelo e grava o resumo em saida/resumo.csv (e as operações de cada uma)."""
import os, sys, json, time
import numpy as np
import pandas as pd
from multiprocessing import Pool
import motor as MT

PREP = None
def _carrega():
    global PREP
    if PREP is None:
        PREP = pd.read_pickle("../dados5m/prep.pkl")
    return PREP

def uma(cfg):
    t0 = time.time()
    P = _carrega()
    bal, uni = cfg["balanca"], cfg["universo"]
    chave = bal if bal in ("original", "choque") else f"{bal}|{uni}"
    SL, SS = P["S"][chave]
    D = dict(P["D"]); D["close"] = P["D"]["close_dec"]
    # O/H/L da vela seguinte já estão deslocados; o motor usa C (=preço da decisão) como fecho para entradas
    Dm = {"open": P["D"]["open"], "high": P["D"]["high"], "low": P["D"]["low"], "close": P["D"]["close_dec"], "atrp": P["D"]["atrp"]}
    ops, curva, info = MT.simular(Dm, SL, SS, P["U"][uni], cfg.get("p"), ini=cfg.get("ini", "2025-02-01"), fim=cfg.get("fim"))
    nome = cfg["nome"]
    os.makedirs("saida", exist_ok=True)
    ops.to_csv(f"saida/ops_{nome}.csv", index=False); curva.to_csv(f"saida/curva_{nome}.csv")
    m = curva.resample("ME").last()
    rm = m.pct_change().fillna(m.iloc[0] / 100 - 1) if len(m) else pd.Series(dtype=float)
    return {"nome": nome, "final": round(float(curva.iloc[-1]), 2) if len(curva) else None,
            "liquidou": str(info["liquidou"])[:10] if info["liquidou"] else "-",
            "pior_queda": round(float((curva / curva.cummax() - 1).min()), 3) if len(curva) else None,
            "maximo": round(float(curva.max()), 1) if len(curva) else None,
            "operacoes": len(ops), "acerto": round(float((ops.pnl > 0).mean()), 3) if len(ops) else None,
            "pnl_bruto_total": round(float(ops.pnl.sum() + ops.taxas.sum()), 2), "taxas_total": round(float(ops.taxas.sum()), 2),
            "meses_pos": f"{int((rm > 0).sum())}/{len(rm)}", "por_motivo": json.dumps(ops.groupby("motivo").pnl.sum().round(2).to_dict()),
            "segundos": round(time.time() - t0)}

if __name__ == "__main__":
    cfgs = json.load(open(sys.argv[1]))
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 4) as pool:
        res = pool.map(uma, cfgs, chunksize=1)
    R = pd.DataFrame(res)
    arq = "saida/resumo.csv"
    R.to_csv(arq, mode="a", header=not os.path.exists(arq), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70)
    print(R.drop(columns=["por_motivo"]).to_string(index=False))
