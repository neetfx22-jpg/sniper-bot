"""Lê as odds atuais (1X2) das ligas configuradas, grava um resumo por jogo/resultado
e marca sinais de valor nas casas portuguesas.

Grava em dados/:
  odds.csv    uma linha por leitura x jogo x resultado (referência, casas PT, máxima)
  sinais.csv  uma linha por sinal novo (casa PT acima do preço justo)
"""
import csv, os, sys
from datetime import datetime, timezone
import requests
import config as C

CAMPOS_ODDS = ["leitura", "liga", "jogo_id", "inicio", "casa_time", "fora_time", "resultado",
               "ref_casa", "ref_odd", "prob_justa", "max_odd", "max_casa", "n_casas"] + \
              [f"odd_{k}" for k in C.CASAS_PT]
CAMPOS_SINAIS = ["leitura", "liga", "jogo_id", "inicio", "casa_time", "fora_time", "resultado",
                 "casa", "odd", "prob_justa", "valor", "ref_casa", "ref_odd"]

def _anexa(nome, campos, linhas):
    caminho = os.path.join(C.PASTA, nome)
    novo = not os.path.exists(caminho)
    with open(caminho, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        w.writerows(linhas)

def _precos(bookmaker):
    for m in bookmaker.get("markets", []):
        if m["key"] == "h2h":
            return {o["name"]: float(o["price"]) for o in m["outcomes"]}
    return {}

def ler_liga(liga, k):
    r = requests.get(f"{C.API}/sports/{liga}/odds/", timeout=30, params={
        "apiKey": k, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"})
    r.raise_for_status()
    return r.json(), r.headers.get("x-requests-remaining")

def processar(liga, eventos, leitura, sinais_existentes):
    odds, sinais = [], []
    for e in eventos:
        if datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) <= leitura:
            continue                                   # já começou
        casas = {b["key"]: _precos(b) for b in e["bookmakers"]}
        ref = next((r for r in C.REFERENCIAS if len(casas.get(r, {})) == 3), None)
        if not ref:
            continue
        inv = {n: 1 / p for n, p in casas[ref].items()}
        tot = sum(inv.values())
        for nome in casas[ref]:
            pj = inv[nome] / tot
            todas = [(p[nome], c) for c, p in casas.items() if nome in p and c not in C.REFERENCIAS]
            mx = max(todas) if todas else (None, None)
            lin = {"leitura": leitura.isoformat(timespec="seconds"), "liga": liga, "jogo_id": e["id"],
                   "inicio": e["commence_time"], "casa_time": e["home_team"], "fora_time": e["away_team"],
                   "resultado": "Draw" if nome == "Draw" else ("H" if nome == e["home_team"] else "A"),
                   "ref_casa": ref, "ref_odd": casas[ref][nome], "prob_justa": round(pj, 5),
                   "max_odd": mx[0], "max_casa": mx[1], "n_casas": len(todas)}
            for c in C.CASAS_PT:
                lin[f"odd_{c}"] = casas.get(c, {}).get(nome)
            odds.append(lin)
            for c, rotulo in C.CASAS_PT.items():
                o = casas.get(c, {}).get(nome)
                if o and o <= C.ODD_MAX and o * pj - 1 > C.LIMIAR_VALOR:
                    chave = (e["id"], lin["resultado"], c)
                    if chave in sinais_existentes:
                        continue                       # já sinalizado antes
                    sinais_existentes.add(chave)
                    sinais.append({k: lin[k] for k in ("leitura", "liga", "jogo_id", "inicio", "casa_time",
                                                        "fora_time", "resultado", "ref_casa", "ref_odd", "prob_justa")}
                                  | {"casa": rotulo, "odd": o, "valor": round(o * pj - 1, 4)})
    return odds, sinais

def main():
    os.makedirs(C.PASTA, exist_ok=True)
    k = C.chave()
    leitura = datetime.now(timezone.utc)
    existentes = set()
    cam = os.path.join(C.PASTA, "sinais.csv")
    if os.path.exists(cam):
        rot = {v: kk for kk, v in C.CASAS_PT.items()}
        with open(cam) as f:
            for s in csv.DictReader(f):
                existentes.add((s["jogo_id"], s["resultado"], rot.get(s["casa"], s["casa"])))
    tot_odds, tot_sinais, resta = 0, [], None
    for liga in C.LIGAS:
        try:
            ev, resta = ler_liga(liga, k)
        except Exception as ex:
            print("erro", liga, ex, file=sys.stderr); continue
        o, s = processar(liga, ev, leitura, existentes)
        _anexa("odds.csv", CAMPOS_ODDS, o); _anexa("sinais.csv", CAMPOS_SINAIS, s)
        tot_odds += len(o); tot_sinais += s
    print(f"{leitura:%Y-%m-%d %H:%M} UTC | {tot_odds} linhas de odds | {len(tot_sinais)} sinais novos | consultas restantes: {resta}")
    for s in tot_sinais:
        print(f"  SINAL {s['casa']}: {s['casa_time']} x {s['fora_time']} ({s['inicio'][:16]}) "
              f"resultado {s['resultado']} odd {s['odd']} | justo {1 / s['prob_justa']:.2f} | valor {s['valor']:+.1%}")

if __name__ == "__main__":
    main()
