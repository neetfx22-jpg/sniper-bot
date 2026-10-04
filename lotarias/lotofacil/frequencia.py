"""Tabela de frequência de cada dezena (1 a 25) na Lotofácil: total de vezes que saiu,
percentagem, atraso (sorteios desde a última vez) e frequência nos últimos 50 e 100 sorteios."""
import numpy as np
import base as B

n = len(B.D)
print(f"Lotofácil: {n} concursos (1 a {B.concursos[-1]}), de {B.datas[0]:%d/%m/%Y} a {B.datas[-1]:%d/%m/%Y}")
print(f"Cada sorteio tem 15 dezenas, logo a média esperada por dezena é {n*15/25/n:.0%} dos sorteios ({n*15//25} vezes).\n")

saiu = np.array([[(int(B.D[i]) >> (d-1)) & 1 for d in range(1, 26)] for i in range(n)])  # n x 25
total = saiu.sum(axis=0)
ult50 = saiu[-50:].sum(axis=0)
ult100 = saiu[-100:].sum(axis=0)
atraso = np.array([int(np.argmax(saiu[::-1, d])) for d in range(25)])  # 0 = saiu no último

print(f"{'Dez':>3} | {'Total':>6} | {'%':>5} | {'Atraso':>6} | {'Últ.50':>6} | {'Últ.100':>7}")
print("-" * 46)
for d in range(25):
    print(f"{d+1:>3} | {total[d]:>6} | {total[d]/n:>5.1%} | {atraso[d]:>6} | {ult50[d]:>6} | {ult100[d]:>7}")

ordem = np.argsort(-total)
print("\nMais sorteadas (histórico):", ", ".join(f"{d+1}({total[d]})" for d in ordem[:6]))
print("Menos sorteadas (histórico):", ", ".join(f"{d+1}({total[d]})" for d in ordem[-6:]))
print(f"\nDiferença entre a mais e a menos sorteada: {total.max()-total.min()} sorteios "
      f"({(total.max()-total.min())/n:.1%} do total) — pequena e dentro do esperado para {n} sorteios independentes.")
print("Mais atrasadas agora:", ", ".join(f"{d+1}({atraso[d]})" for d in np.argsort(-atraso)[:6]))

# teste: a dezena mais frequente no passado sai mais no futuro?
meio = n // 2
t1 = saiu[:meio].sum(axis=0); t2 = saiu[meio:].sum(axis=0)
r = np.corrcoef(t1, t2)[0, 1]
print(f"\ncorrelação entre frequência na 1ª metade e na 2ª metade da história: {r:+.3f}")
print("(perto de 0 = uma dezena 'quente' no passado não é mais provável no futuro)")
