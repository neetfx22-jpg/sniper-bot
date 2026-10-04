# Pesquisa — apostas esportivas (futebol)

Base: football-data.co.uk — 171 mil jogos, 46 ligas (22 europeias + 16 países extras), 2012–2026,
com odds da Pinnacle, Bet365, Betfair Exchange, média e máxima do mercado (abertura e fechamento).

## Como rodar
```
pip install pandas numpy
bash dados/baixar.sh && python3 carregar.py
python3 estrategias.py     # valor contra o preço justo (Pinnacle), 1X2 e gols 2.5, várias casas
python3 banca.py           # banca de 500 com 1/4 de Kelly + vieses simples (favorito, empate, zebra)
python3 ref_betfair.py     # sem Pinnacle (desde meados de 2025): referência = Betfair Exchange
```

## Resultados
- **Vieses simples** (apostar sempre no mandante, empate, favorito ou zebra): todos perdem (−0,1% a −21%).
- **Valor na melhor odd do mercado** (odd máxima > preço justo, odd ≤ 4): +3% a +7% por aposta,
  positivo em 13–14 de 15 anos. Com a Betfair como referência (2024–2026): +7,4% (valor > 2%).
- **Uma casa só** (Bet365) ou **só a Betfair**: perto de zero; não compensa.
- Banca de 500, 1/4 de Kelly, aposta máxima de 20–200 USD: ~80–220 USD/mês, quedas de ~26%.
  Nenhum mês chegou a 2.000 USD.

## Limites reais
- A "máxima do mercado" exige contas em dezenas de casas e apostar no instante certo.
- Casas comuns **limitam ou fecham** contas que ganham com essa estratégia, em semanas ou meses.
- A Pinnacle deixou de publicar odds em meados de 2025; a referência passou a ser a Betfair.
- 2025 foi o ano mais fraco na referência Pinnacle (−0,5%).
