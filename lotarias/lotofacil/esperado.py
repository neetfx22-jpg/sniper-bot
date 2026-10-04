"""Retorno esperado EXATO de uma aposta de 15 dezenas na Lotofácil (prémios e preço atuais).
Pela linearidade da esperança, qualquer fechamento com N apostas tem retorno esperado = N x isto."""
import json
from math import comb
import numpy as np
H = sorted(json.load(open("historico.json")), key=lambda x: x["concurso"])
rec = [h for h in H if any(p["descricao"].startswith("11") and float(p["valorPremio"] or 0) == 7.0 for p in h["premiacoes"])]
def media(k):
    v = [float(p["valorPremio"]) for h in rec for p in h["premiacoes"] if p["descricao"].startswith(str(k)) and (p["ganhadores"] or 0) > 0]
    return np.mean(v), len(v)
tot = comb(25, 15)
prob = {k: comb(15, k) * comb(10, 15 - k) / tot for k in (11, 12, 13, 14, 15)}
pr15, n15 = media(15); pr14, _ = media(14)
premio = {11: 7.0, 12: 14.0, 13: 35.0, 14: pr14, 15: pr15}
print(f"período com aposta a R$ 3,50: {len(rec)} concursos (média do prémio de 15: R$ {pr15:,.0f}; de 14: R$ {pr14:,.0f})")
ev = 0
for k in (15, 14, 13, 12, 11):
    ev += prob[k] * premio[k]
    print(f"   {k} acertos: 1 em {1 / prob[k]:>10,.0f} | prémio R$ {premio[k]:>12,.2f} | vale R$ {prob[k] * premio[k]:.3f} por aposta")
print(f"\nretorno esperado por aposta de R$ 3,50: R$ {ev:.2f}  ->  {ev / 3.5:.1%} do valor apostado (perde {1 - ev / 3.5:.1%} em média)")
for n, ap in (("16 dezenas", 16), ("17 dezenas", 136), ("18 dezenas", 816), ("reduzido 18 (24 apostas)", 24)):
    print(f"   fechamento {n:<26} {ap:>4} apostas = R$ {ap * 3.5:>8,.2f} | retorno esperado R$ {ap * ev:>8,.2f} | perda esperada R$ {ap * (3.5 - ev):>8,.2f} por concurso")
