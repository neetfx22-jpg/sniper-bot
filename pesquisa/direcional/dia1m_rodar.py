import sys, itertools
import numpy as np
import pandas as pd
import dia1m, motor as MT

D, U, SL, SS = pd.read_pickle("../dados1m/prep1m.pkl")

def um_dia(perfil, saldo, risco, maxpos, lev_padrao, dia="2026-10-03"):
    p = {**dia1m.perfil(perfil, lev_padrao), "SALDO": saldo, "RISCO_PCT": risco, "MAX_POS": maxpos}
    return MT.simular(D, SL, SS, U, p, ini=f"{dia} 00:00", fim=f"{dia} 23:59")

def mostra(perfil, saldo=100.0, risco=0.04, maxpos=15, lev_padrao=20, dia="2026-10-03"):
    ops, curva, info = um_dia(perfil, saldo, risco, maxpos, lev_padrao, dia)
    print(f"\n=== {perfil} | {dia} | banca {saldo:g} | {risco:.0%} por posição | até {maxpos} posições | taxa Binance | pares sem tabela: {lev_padrao}x ===")
    if len(ops):
        o = ops.copy(); o["roi"] = (o.pnl / o.margem * 100).round(0)
        o["ent"] = o.entrada_t.dt.strftime("%H:%M"); o["sai"] = o.saida_t.dt.strftime("%H:%M")
        o["lado"] = o.lado.map({"L": "LONG", "S": "SHORT"})
        print(o[["ent", "sai", "par", "lado", "alav", "margem", "pnl", "taxas", "roi", "motivo"]].round(2).to_string(index=False))
    for a in info["abertas"]:
        print(f"  ABERTA às 23:59: {a['par']} {'LONG' if a['lado']=='L' else 'SHORT'} {a['alav']:.0f}x desde {a['entrada_t']:%H:%M} | PnL aberto {a['pnl_aberto']:+.2f}")
    fim = curva.iloc[-1] if len(curva) else saldo
    print(f"  operações fechadas {len(ops)} | ganhas {(ops.pnl>0).sum()} | perdidas {(ops.pnl<=0).sum()} | taxas {ops.taxas.sum():.2f} | "
          f"banca {saldo:g} -> {fim:.2f} ({(fim/saldo-1):+.1%}) | pior momento {curva.min():.2f} | liquidou: {'SIM' if info['liquidou'] else 'não'}")
    return fim

if __name__ == "__main__":
    for pf in ("CHXM 3:1", "CHXM 2:1", "CHX 10x 3:1"):
        mostra(pf)
