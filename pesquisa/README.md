# Pesquisa independente — estratégias de futuros (Binance USDT-M)

Construída do zero; **não usa a balança K/3.0 nem os sinais dela**.
Meta pedida: 2.000 USD/mês (ou 50 USD/dia) com 500 USD iniciais = 400% ao mês.

## Como rodar
```
pip install pandas numpy
bash dados/baixar2.sh && python3 carregar.py          # 45 pares, 1h + funding, jan/2023–set/2026
python3 grade2.py                                      # 330 combinações, 10 famílias, 2 taxas
python3 walkforward.py mexc                            # escolha trimestral só com o passado
python3 estresse.py                                    # atraso, slippage, teto por par, metades do universo
python3 combinada.py                                   # carteira combinada (escolhida olhando tudo = otimista)
python3 wf_combo.py                                    # carteira combinada escolhida às cegas (honesto)
python3 overlay.py                                     # alvo de volatilidade / freio por queda
bash dados5m/baixar5m.sh && python3 carregar5m.py && python3 grade5m.py   # curto prazo (5m)
```

## Regras do teste
- Decisão no fechamento da vela; executa na seguinte. Taxa + slippage sobre o giro; funding real (1h).
- Validação por janelas: em cada trimestre, os parâmetros são escolhidos **só com os 12 meses anteriores**.
- Liquidação pelos pavios: se a perda alavancada dentro da hora passar de 90% do patrimônio, a conta zera.

## Resultados principais (fora da amostra, jan/2024–set/2026, 500 USD, custo 0,04%/lado)
| O quê | 500 USD viram | Pior queda |
|---|---|---|
| BTC comprado e segurado 1x | 814 | −54% |
| Carteira combinada às cegas, 1x | 1.155 | −37% |
| Carteira combinada às cegas, 2x | 1.810 | −62% |
| Carteira combinada, alvo de vol. 50% | ~2.000 | −50% |
| Carteira combinada, 5x | 689 | −97% |

Carteira combinada = 4 peças com igual peso: seguir choques de 1h, momento entre pares,
momento do resíduo contra o BTC e momento só comprado com filtro do BTC.

- Escolhendo os parâmetros olhando o período todo, a mesma carteira "fazia" 12.736 com 2x:
  a diferença para 1.810 é o viés de escolher depois de ver.
- Reversão (1h e 5m), carry de funding, sazonalidade por hora e tudo em 5m perderam fora da amostra.
  Em 5m a vantagem bruta existe em alguns casos, mas o custo de giro (~300%/ano) é muito maior.

## Conclusão
Nenhuma combinação chega a 2.000 USD/mês com 500 USD. O melhor resultado honesto fica perto
de 40–50 USD/mês em média, com quedas de 50–60% no caminho. Com ~3–4%/mês (já otimista),
2.000 USD/mês exigiria um capital da ordem de 50.000 USD.
