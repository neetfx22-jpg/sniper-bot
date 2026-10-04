"""Hipótese dos NÚMEROS CARREGADOS: combinações que pontuaram alto no passado pontuam melhor depois?
Como os sorteios são independentes, a correlação deve ser ~0. Medimos isso com dados reais."""
import numpy as np, pandas as pd
import base as B

T = B.todas_combinacoes()
treino = B.indices("2023-01-01", "2025-06-30")
teste = B.indices("2025-07-01")
print(f"treino {B.datas[treino[0]]:%d/%m/%Y}–{B.datas[treino[-1]]:%d/%m/%Y} ({len(treino)} sorteios) | "
      f"teste {B.datas[teste[0]]:%d/%m/%Y}–{B.datas[teste[-1]]:%d/%m/%Y} ({len(teste)} sorteios)")

# pontos de cada combinação em cada período
def perfil(idx):
    p13 = np.zeros(len(T)); p14 = np.zeros(len(T)); p15 = np.zeros(len(T)); premio = np.zeros(len(T))
    for i in idx:
        ac = B.popcount(T & B.D[i])
        p13 += ac == 13; p14 += ac == 14; p15 += ac == 15; premio += B.PR[i, ac]
    return p13, p14, p15, premio
tr13, tr14, tr15, _ = perfil(treino)
te13, te14, te15, te_prem = perfil(teste)

print("\n-- 'carregadas' = as que MAIS fizeram 14+ pontos no treino. Como se saíram no teste? --")
score_tr = tr14 * 10 + tr15 * 100 + tr13
for rotulo, sel in (("top 100 mais carregadas", np.argsort(-score_tr)[:100]),
                    ("top 1.000", np.argsort(-score_tr)[:1000]),
                    ("as 'frias' (menos 14+ no treino), 100", np.argsort(score_tr)[:100]),
                    ("todas (referência)", np.arange(len(T)))):
    n = len(sel); nsort = len(teste)
    print(f"   {rotulo:<40} no teste: 15pts {te15[sel].sum():.0f} | 14pts {te14[sel].sum():.0f} | 13pts {te13[sel].sum():.0f} | "
          f"retorno {te_prem[sel].sum() / (n * nsort * B.PRECO[teste].mean()):.3f}")

r = np.corrcoef(score_tr, te14 * 10 + te15 * 100 + te13)[0, 1]
print(f"\ncorrelação entre 'carga' no treino e pontuação no teste: {r:+.4f}  (0 = passado não prevê futuro)")
print("conclusão: uma combinação que fez muito 14/15 no passado NÃO tem vantagem no futuro.")
