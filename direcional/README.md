# Perfil CH — balança de choque + saída por tempo

`hydra_direcional_teste.py` (carteira fictícia) com dois perfis novos:

| Perfil | O que faz |
|---|---|
| `CH`   | balança de choque 1h, uma entrada por choque, sai depois de 12h, trava só de catástrofe, **5x**, taxa MEXC simulada |
| `CH10` | igual, com **10x** |

## Regras
- **Entrada:** moeda do top 30 (volume >= 50M) cuja última hora fechada andou mais de **4 desvios**
  (desvio das últimas 168 horas) com volume da hora >= 2x a média das 24 anteriores.
  Entra no MESMO sentido. O sinal vale 12 horas; só uma entrada por choque.
- **Saída:** depois de **12 horas**; ou trava de catástrofe (10x ATR de 5m, máx. 8% de preço);
  ou choque no sentido contrário (fecha; se ROI >= 10% inverte).
- Margem 2% da banca por posição, até 20 posições, colheita global e pausas do script original.

## Como rodar (no lugar do teste atual, em outro terminal se quiser comparar)
```
python3 hydra_direcional_teste.py --perfil CH --reset
python3 hydra_direcional_teste.py --perfil CH10 --reset
```
Ou aplicar numa cópia do seu arquivo: `cp hydra_direcional_teste.py hydra_ch.py && python3 patch_ch.py hydra_ch.py`.

## Resultado no simulador (fev/2025–set/2026, 100 USDT, top 30)
| | 5x | 10x |
|---|---|---|
| taxa MEXC + slippage 0,02% | 266 (queda −23%) | 546 (queda −43%) |
| taxa Binance + slippage 0,05% | 202 | 251 |
| alavancagem real do par (20–150x) | liquidada em abr/2025 | |

A balança dentro do script foi conferida contra a do simulador: 1.500 comparações, 0 diferenças.
