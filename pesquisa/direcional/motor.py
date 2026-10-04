"""Carteira fictícia que reproduz o ciclo_direcional() (perfil D: filtro B + trava ATR + corte sem hedge).

Por vela de 5m (decisões no fecho da vela, como o script com USAR_VELA_FECHADA):
  1. posições abertas: percorre o caminho do preço da vela seguinte (abertura -> mínima -> máxima -> fecho
     em vela de alta; abertura -> máxima -> mínima -> fecho em vela de baixa) e verifica, nessa ordem de
     chegada, TRAVA e TP; se os dois cabem na mesma vela, assume o pior (trava primeiro).
  2. liquidação da conta (margem cruzada): se o patrimônio no pior ponto da vela cair abaixo da margem
     de manutenção (MMR_FATOR x margem inicial), fecha tudo nesse ponto.
  3. no fecho: colheita global, virada da balança, entradas novas.
Custos: taxa sobre o valor da posição na abertura e no fecho + slippage nas ordens a mercado.
"""
import numpy as np
import pandas as pd

LEV_POR_PAR = {"BNBUSDT": 75, "BZUSDT": 100, "DOGEUSDT": 75, "ENAUSDT": 75, "ETHUSDT": 150, "HYPEUSDT": 75,
               "KORUUSDT": 25, "LITUSDT": 75, "MOVRUSDT": 25, "MUUSDT": 50, "NEARUSDT": 75, "PUMPUSDT": 75,
               "QNTUSDT": 75, "SKHYNIXUSDT": 50, "SOLUSDT": 100, "SOONUSDT": 50, "SOXLUSDT": 50, "SUIUSDT": 75,
               "WLDUSDT": 75, "XRPUSDT": 100, "BTCUSDT": 125}
PADRAO = dict(SALDO=100.0, RISCO_PCT=0.02, LEV_PAPER=20, LEV_TETO=None, TAXA=0.0005, SLIP=0.0002,
              SCORE_ENTRADA=75, DIF_ENTRADA=10.0, DIF_VIRAR=10.0, ROI_MIN_DIR=0.10,
              TP_ATR_K=2.0, TP_MIN=0.15, TP_MAX=0.60, TRAVA_K=3.0, TRAVA_MIN=0.004, TRAVA_MAX=0.03,
              COOLDOWN_BARRAS=1, MAX_POS=20, MAX_USO_MARGEM=0.80, MMR_FATOR=0.5, COLHEITA_PCT=0.035,
              LOSSES_STOP=4, PAUSA_BARRAS=6, SEM_TP=False)

def simular(D, SL, SS, univ, p=None, ini=None, fim=None):
    """D: dict com DataFrames 5m open/high/low/close e atrp (ATR%/preço 5m). SL, SS: pontuações.
    univ: máscara booleana (tempo x par) de pares operáveis. Devolve (operações, patrimônio por hora, info)."""
    P = dict(PADRAO, **(p or {}))
    idx = D["close"].index
    sel = np.ones(len(idx), bool)
    if ini: sel &= idx >= pd.Timestamp(ini, tz="UTC")
    if fim: sel &= idx <= pd.Timestamp(fim, tz="UTC")
    rows = np.where(sel)[0]
    pares = list(D["close"].columns)
    O, H, L, C = (D[k].values for k in ("open", "high", "low", "close"))
    ATR = D["atrp"].values; sl, ss = SL.values, SS.values; U = univ.values
    lev = np.array([LEV_POR_PAR.get(x, P["LEV_PAPER"]) for x in pares], float)
    if P["LEV_TETO"]:
        lev = np.minimum(lev, P["LEV_TETO"])
    taxa, slip = P["TAXA"], P["SLIP"]

    caixa = P["SALDO"]                      # saldo realizado
    pos = {}                                # j -> dict(lado, entrada, qty, margem, atr, barra)
    cooldown = np.zeros(len(pares), int)    # barra até a qual não reentra
    perdas_seg, pausa_ate = 0, -1
    ops, curva = [], []
    liquidou = None

    def fechar(j, preco_exec, t, motivo):
        nonlocal caixa, perdas_seg, pausa_ate
        q = pos.pop(j)
        sgn = 1 if q["lado"] == "L" else -1
        pnl = sgn * (preco_exec - q["entrada"]) * q["qty"] - preco_exec * q["qty"] * taxa
        caixa += pnl
        bruto_total = pnl - q["taxa_ent"]                     # resultado da operação inteira
        ops.append((idx[q["barra"]], idx[t], pares[j], q["lado"], q["entrada"], preco_exec, q["qty"],
                    q["margem"], q["lev"], bruto_total, q["taxa_ent"] + preco_exec * q["qty"] * taxa, motivo))
        if bruto_total < 0:
            perdas_seg += 1
            if perdas_seg >= P["LOSSES_STOP"]:
                pausa_ate, perdas_seg = t + P["PAUSA_BARRAS"], 0
        else:
            perdas_seg = 0
        cooldown[j] = t + P["COOLDOWN_BARRAS"]

    def pnl_aberto(precos):
        return sum((1 if q["lado"] == "L" else -1) * (precos[j] - q["entrada"]) * q["qty"] for j, q in pos.items())

    for t in rows:
        # 1) caminho do preço dentro da vela t para as posições abertas (abertas no fecho de t-1 ou antes)
        if pos:
            for j in list(pos):
                q = pos[j]; o, h, l, c = O[t, j], H[t, j], L[t, j], C[t, j]
                if np.isnan(c):
                    continue
                e, lv = q["entrada"], q["lev"]
                trv = min(P["TRAVA_MAX"], max(P["TRAVA_MIN"], P["TRAVA_K"] * q["atr"]))
                alvo_roi = min(P["TP_MAX"], max(P["TP_MIN"], P["TP_ATR_K"] * q["atr"] * lv + 2 * taxa * lv))
                if q["lado"] == "L":
                    p_trv, p_tp = e * (1 - trv), e * (1 + alvo_roi / lv)
                    hit_trv, hit_tp = l <= p_trv, (h >= p_tp) and not P["SEM_TP"]
                    alta = c >= o
                    if hit_trv and (not hit_tp or alta or o <= p_trv):     # vela de alta passa pela mínima antes
                        fechar(j, min(o, p_trv) * (1 - slip), t, "trava")
                    elif hit_tp:
                        fechar(j, max(o, p_tp) * (1 - slip), t, "TP")
                else:
                    p_trv, p_tp = e * (1 + trv), e * (1 - alvo_roi / lv)
                    hit_trv, hit_tp = h >= p_trv, (l <= p_tp) and not P["SEM_TP"]
                    baixa = c < o
                    if hit_trv and (not hit_tp or baixa or o >= p_trv):
                        fechar(j, max(o, p_trv) * (1 + slip), t, "trava")
                    elif hit_tp:
                        fechar(j, min(o, p_tp) * (1 + slip), t, "TP")
            # 2) liquidação da conta no pior ponto da vela
            if pos:
                pior = sum(((L[t, j] if q["lado"] == "L" else H[t, j]) - q["entrada"]) * (1 if q["lado"] == "L" else -1) * q["qty"]
                           for j, q in pos.items() if not np.isnan(L[t, j]))
                manut = sum(q["margem"] for q in pos.values()) * P["MMR_FATOR"]
                if caixa + pior <= manut:
                    for j in list(pos):
                        q = pos[j]; fechar(j, L[t, j] if q["lado"] == "L" else H[t, j], t, "LIQUIDAÇÃO")
                    caixa = max(caixa, 0.0); liquidou = idx[t]
                    curva.append((idx[t], caixa)); break
        precos = C[t]
        eq = caixa + pnl_aberto(precos)
        # 3a) colheita global
        if pos and pnl_aberto(precos) >= P["COLHEITA_PCT"] * eq:
            for j in list(pos):
                q = pos[j]; sgn = 1 if q["lado"] == "L" else -1
                if sgn * (precos[j] - q["entrada"]) * q["qty"] > q["qty"] * precos[j] * (2 * taxa + slip):
                    fechar(j, precos[j] * (1 - sgn * slip), t, "colheita")
        # 3b) balança virou
        for j in list(pos):
            q = pos[j]
            if t <= q["barra"]:
                continue
            contra = (ss[t, j] - sl[t, j]) if q["lado"] == "L" else (sl[t, j] - ss[t, j])
            if contra >= P["DIF_VIRAR"]:
                sgn = 1 if q["lado"] == "L" else -1
                roi = sgn * (precos[j] - q["entrada"]) / q["entrada"] * q["lev"]
                novo = "S" if q["lado"] == "L" else "L"
                fechar(j, precos[j] * (1 - sgn * slip), t, "virada" if roi >= P["ROI_MIN_DIR"] else "corte")
                if roi >= P["ROI_MIN_DIR"]:
                    cooldown[j] = t                            # virada reabre já do outro lado
                    _abre = (j, novo)
                    eq = caixa + pnl_aberto(precos)
                    m = max(0.10, eq * P["RISCO_PCT"])
                    if len(pos) < P["MAX_POS"] and (sum(x["margem"] for x in pos.values()) + m) / eq <= P["MAX_USO_MARGEM"]:
                        px = precos[j] * (1 + (slip if novo == "L" else -slip))
                        qty = m * lev[j] / px
                        caixa -= px * qty * taxa
                        pos[j] = dict(lado=novo, entrada=px, qty=qty, margem=m, lev=lev[j], atr=ATR[t, j], barra=t, taxa_ent=px * qty * taxa)
        # 3c) entradas novas
        eq = caixa + pnl_aberto(precos)
        if eq <= 1.0:
            liquidou = liquidou or idx[t]; curva.append((idx[t], eq)); break
        if t >= pausa_ate and len(pos) < P["MAX_POS"]:
            cand = np.where(U[t] & ((np.maximum(sl[t], ss[t]) >= P["SCORE_ENTRADA"]) & (np.abs(sl[t] - ss[t]) >= P["DIF_ENTRADA"])))[0]
            for j in cand:
                if j in pos or cooldown[j] > t or np.isnan(precos[j]) or np.isnan(ATR[t, j]):
                    continue
                if len(pos) >= P["MAX_POS"]:
                    break
                m = max(0.10, eq * P["RISCO_PCT"])
                if (sum(x["margem"] for x in pos.values()) + m) / eq > P["MAX_USO_MARGEM"]:
                    break
                lado = "L" if sl[t, j] > ss[t, j] else "S"
                px = precos[j] * (1 + (slip if lado == "L" else -slip))
                qty = m * lev[j] / px
                caixa -= px * qty * taxa
                pos[j] = dict(lado=lado, entrada=px, qty=qty, margem=m, lev=lev[j], atr=ATR[t, j], barra=t, taxa_ent=px * qty * taxa)
        if idx[t].minute == 0:
            curva.append((idx[t], caixa + pnl_aberto(precos)))
    ops = pd.DataFrame(ops, columns=["entrada_t", "saida_t", "par", "lado", "preco_ent", "preco_sai", "qty", "margem",
                                     "alav", "pnl", "taxas", "motivo"])
    curva = pd.Series(dict(curva), dtype=float)
    return ops, curva, {"liquidou": liquidou}
