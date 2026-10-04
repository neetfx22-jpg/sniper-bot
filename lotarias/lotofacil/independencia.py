"""Cobrir TODAS as 3.268.760 combinações na Lotofácil da Independência: dá lucro?
Quem tem todas as combinações ganha, em cada sorteio de 15 dezenas:
  1 x (15 pts) + 150 x (14) + 4725 x (13) + 54600 x (12) + 286650 x (11)
Os prémios 13/12/11 são fixos; 14 e 15 são divididos entre os acertadores (rateio)."""
import json
from math import comb
H = {h["concurso"]: h for h in json.load(open("historico.json"))}

# nº de combinações (de 15 em 25) que fazem exatamente k pontos, tendo TODAS as combinações
qtd = {k: comb(15, k) * comb(10, 15 - k) for k in (11, 12, 13, 14, 15)}
CUSTO = 3268760 * 3.50
print(f"cobrir tudo = 3.268.760 jogos x R$ 3,50 = R$ {CUSTO:,.0f}".replace(",", "."))
print(f"bilhetes premiados que você teria em cada sorteio: {qtd}\n")

indep = [3780, 3480, 3190, 2900, 2610, 2320, 2030, 1861, 1708, 1557, 1408, 1255, 1102, 952, 800]
print(f"{'conc':>5} | {'ano':>4} | {'ganho 15pts':>14} | {'ganho 14pts':>13} | {'13/12/11':>13} | {'GANHO TOTAL':>14} | {'resultado':>14}")
for c in indep:
    h = H.get(c)
    if not h: continue
    pr = {int(p["descricao"].split()[0]): (p["ganhadores"] or 0, p["valorPremio"] or 0) for p in h["premiacoes"]}
    # 15 pts: entro com +1 ganhador no rateio -> pool / (ganhadores+1)
    g15, v15 = pr[15]; pool15 = g15 * v15
    ganho15 = pool15 / (g15 + 1) if g15 else v15
    # 14 pts: tenho 150 bilhetes; eles entram no rateio e reduzem o valor por bilhete
    g14, v14 = pr[14]; pool14 = g14 * v14
    meus14 = qtd[14]
    ganho14 = pool14 * meus14 / (g14 + meus14) if (g14 + meus14) else 0
    # 13/12/11 fixos
    ganho_fixo = sum(qtd[k] * pr.get(k, (0, 0))[1] for k in (13, 12, 11))
    total = ganho15 + ganho14 + ganho_fixo
    print(f"{c:>5} | {h['data'][-4:]:>4} | R$ {ganho15:>11,.0f} | R$ {ganho14:>10,.0f} | R$ {ganho_fixo:>10,.0f} | R$ {total:>11,.0f} | R$ {total-CUSTO:>11,.0f}".replace(",", "."))
