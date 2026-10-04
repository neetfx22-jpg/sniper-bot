"""Paridade dos sorteios: distribuição de ímpares/pares e baixos/altos. Útil para montar jogos
'equilibrados', mas NÃO cria vantagem (todas as combinações com a mesma paridade são iguais entre si)."""
import numpy as np, pandas as pd
import base as B
from collections import Counter

idx = B.indices("2023-01-01")
imp = Counter(); baixo = Counter()
for i in idx:
    m = int(B.D[i])
    imp[sum((m >> d) & 1 for d in range(0, 25, 2))] += 1          # bits 0,2,4... = dezenas 1,3,5,.. (ímpares)
    baixo[sum((m >> d) & 1 for d in range(13))] += 1              # dezenas 1..13
n = len(idx)
print(f"paridade dos {n} sorteios desde 2023:")
print("  ímpares (de 15):", {k: f"{v/n:.0%}" for k, v in sorted(imp.items()) if v})
print("  dezenas 1-13 :  ", {k: f"{v/n:.0%}" for k, v in sorted(baixo.items()) if v})
print("\nos splits mais comuns (7 ou 8 ímpares; 7 ou 8 baixos) aparecem na maioria dos sorteios,")
print("mas há milhões de combinações com cada split — escolher por paridade não aumenta o retorno por aposta.")
