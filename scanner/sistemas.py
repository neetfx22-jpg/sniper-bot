"""Múltiplas-sistema em PAPEL a partir dos sinais de valor já gravados.

Ideia (validação ao vivo, sem apostar e sem gastar créditos da API):
  - "Âncora" = um favorito com valor (sinal com odd em [ANCORA_ODD_MIN, ANCORA_ODD_MAX],
    e que não seja empate). É a seleção que o teu plano combina.
  - Em cada dia de jogos juntam-se as âncoras desse dia e monta-se um sistema
    (Trixie/Yankee/Heinz...). O sistema cobre TODAS as combinações de 2+ âncoras,
    por isso não precisa de acertar tudo: com 1 ou 2 erros ainda pode dar lucro.
  - Compara-se sempre com a aposta simples (1 unidade em cada âncora) nos MESMOS
    jogos, para ver se o sistema amplifica (ou não) o mesmo edge.

Não consome API: só lê dados/sinais.csv + dados/resultados.csv.
Corre depois de scan.py / resultados.py:  python sistemas.py
"""
import csv, os
from datetime import datetime, timezone
from itertools import combinations
import config as C


def _carrega():
    cam_s = os.path.join(C.PASTA, "sinais.csv")
    if not os.path.exists(cam_s):
        return [], {}
    with open(cam_s) as f:
        sinais = list(csv.DictReader(f))
    resultados = {}
    cam_r = os.path.join(C.PASTA, "resultados.csv")
    if os.path.exists(cam_r):
        with open(cam_r) as f:
            for r in csv.DictReader(f):
                gc, gf = r.get("gols_casa"), r.get("gols_fora")
                if gc in (None, "") or gf in (None, ""):
                    continue
                gc, gf = int(gc), int(gf)
                resultados[r["jogo_id"]] = "H" if gc > gf else ("A" if gf > gc else "Draw")
    return sinais, resultados


def ancoras(sinais):
    """Favoritos-com-valor, um por jogo (o de maior valor), ordenados por dia de jogo."""
    melhor = {}
    for s in sinais:
        odd = float(s["odd"])
        if s["resultado"] == "Draw":
            continue                                   # âncora é favorito, não empate
        if not (C.ANCORA_ODD_MIN <= odd <= C.ANCORA_ODD_MAX):
            continue
        chave = s["jogo_id"]
        val = float(s["valor"])
        if chave not in melhor or val > float(melhor[chave]["valor"]):
            melhor[chave] = s
    out = []
    for s in melhor.values():
        dia = s["inicio"][:10]                         # AAAA-MM-DD do início do jogo
        out.append({"jogo_id": s["jogo_id"], "dia": dia, "odd": float(s["odd"]),
                    "resultado": s["resultado"], "valor": float(s["valor"]),
                    "jogo": f"{s['casa_time']} x {s['fora_time']}", "casa": s["casa"]})
    out.sort(key=lambda a: (a["dia"], a["jogo_id"]))
    return out


def retorno_sistema(selec, resultados):
    """Dado um conjunto de âncoras (todas com resultado conhecido), devolve
    (nº de linhas, apostado, retorno, nº de acertos) para um sistema que cobre
    todas as combinações de tamanho 2..N. Linha ganha se TODAS as suas âncoras
    acertarem; paga produto das odds x aposta."""
    n = len(selec)
    ganhou = [resultados[a["jogo_id"]] == a["resultado"] for a in selec]
    linhas = apostado = retorno = 0
    for tam in range(2, n + 1):
        for idx in combinations(range(n), tam):
            linhas += 1
            apostado += C.APOSTA_LINHA
            if all(ganhou[i] for i in idx):
                prod = 1.0
                for i in idx:
                    prod *= selec[i]["odd"]
                retorno += C.APOSTA_LINHA * prod
    return linhas, apostado, retorno, sum(ganhou)


def retorno_simples(selec, resultados):
    """Aposta simples de 1 unidade em cada âncora, nos mesmos jogos."""
    apostado = retorno = 0.0
    for a in selec:
        apostado += C.APOSTA_LINHA
        if resultados[a["jogo_id"]] == a["resultado"]:
            retorno += C.APOSTA_LINHA * a["odd"]
    return apostado, retorno


def main():
    sinais, resultados = _carrega()
    anc = ancoras(sinais)
    if not anc:
        return print("Ainda sem âncoras (favoritos com valor). O scanner precisa de gravar mais sinais.")

    # Agrupa por dia de jogo
    dias = {}
    for a in anc:
        dias.setdefault(a["dia"], []).append(a)

    print(f"Âncoras (favoritos com valor): {len(anc)} em {len(dias)} dias de jogos.\n")

    tot = {nome: {"ap": 0.0, "ret": 0.0, "bilhetes": 0} for nome in C.SISTEMAS}
    tot["Simples"] = {"ap": 0.0, "ret": 0.0, "bilhetes": 0}
    pendentes = 0

    for dia in sorted(dias):
        grupo = dias[dia]
        prontos = [a for a in grupo if a["jogo_id"] in resultados]
        if len(prontos) < min(C.SISTEMAS.values()):
            pendentes += len(grupo)
            continue
        print(f"=== {dia} === {len(prontos)} âncoras com resultado")
        for a in prontos:
            ok = "OK " if resultados[a["jogo_id"]] == a["resultado"] else "ERRO"
            print(f"   {ok} {a['jogo']:<34} {a['resultado']} @ {a['odd']:.2f} "
                  f"(valor {a['valor']:+.1%}, {a['casa']})")
        # aposta simples de referência
        ap_s, ret_s = retorno_simples(prontos, resultados)
        tot["Simples"]["ap"] += ap_s; tot["Simples"]["ret"] += ret_s; tot["Simples"]["bilhetes"] += 1
        print(f"   Simples: apostado {ap_s:.0f} u | retorno {ret_s:.2f} u | "
              f"lucro {ret_s - ap_s:+.2f} u")
        # cada sistema aplicável (precisa de pelo menos N âncoras nesse dia)
        for nome, n in C.SISTEMAS.items():
            if len(prontos) < n:
                continue
            # usa as n âncoras de maior valor desse dia
            selec = sorted(prontos, key=lambda x: -x["valor"])[:n]
            linhas, ap, ret, acertos = retorno_sistema(selec, resultados)
            tot[nome]["ap"] += ap; tot[nome]["ret"] += ret; tot[nome]["bilhetes"] += 1
            print(f"   {nome} ({n} âncoras, {linhas} linhas): apostado {ap:.0f} u | "
                  f"retorno {ret:.2f} u | lucro {ret - ap:+.2f} u | acertos {acertos}/{n}")
        print()

    print("================ RESUMO (papel) ================")
    for nome, d in tot.items():
        if d["bilhetes"] == 0:
            continue
        roi = (d["ret"] - d["ap"]) / d["ap"] if d["ap"] else 0.0
        print(f"  {nome:<9}: {d['bilhetes']} bilhetes | apostado {d['ap']:.0f} u | "
              f"retorno {d['ret']:.2f} u | lucro {d['ret'] - d['ap']:+.2f} u | ROI {roi:+.1%}")
    if pendentes:
        print(f"\n  ({pendentes} âncoras ainda sem resultado / dias com poucas âncoras — ficam pendentes.)")
    print("\nNota: tudo em papel. Simples = referência; se um sistema tiver ROI acima da"
          "\nsimples de forma consistente ao longo de semanas, a múltipla está a amplificar o edge.")


if __name__ == "__main__":
    main()
