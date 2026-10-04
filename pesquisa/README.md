# Pesquisa independente — estratégias de futuros (Binance USDT-M)

Construída do zero; **não usa a balança K/3.0 nem os sinais dela**.

## Como rodar
```
pip install pandas numpy
bash dados/baixar.sh        # velas 1h + funding de 20 pares, jan/2025–set/2026 (data.binance.vision)
python3 carregar.py         # junta tudo em dados/base.pkl
python3 pesquisa.py         # escolhe parâmetros em 2025 (treino) e prova em jan–set/2026 (teste)
python3 alavancagem.py      # efeito da alavancagem e simulação de 2.000 anos com 500 USDT
```

## Método
- Carteira com exposição bruta 1x; decisão no fechamento da hora anterior.
- Taxa sobre o giro (Binance 0,05% ou MEXC 0,01%) e funding real cobrado.
- Parâmetros escolhidos só pelo treino (2025); o teste (2026) nunca entra na escolha.

## Resultado (teste jan–set/2026, taxa MEXC, 1x)
| Estratégia | Lucro/mês médio | Pior queda |
|---|---|---|
| Momento entre pares (14 dias, rebalanceio diário, 5+5) | +2,9% | −8,5% |
| Rompimento de canal 30 dias | +2,7% | −20% |
| Tendência por par 30 dias | +2,1% | −20% |
| Carry de funding | −0,4% | −27% |
| Reversão entre pares | −4,1% | −39% |

Cuidado: quase todas as variantes de momento **perderam em 2025** e ganharam em 2026.
A vantagem depende do tipo de mercado.

## Meta de 2.000 USD/mês com 500 USD
Ver `alavancagem.py`. Nenhuma alavancagem chega à meta com segurança:
o melhor caso histórico (8x) rendeu ~131 USD/mês com queda de −88%; 15x ou mais zerou a conta.
