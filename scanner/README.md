# Scanner de apostas de valor (Portugal)

Lê as odds 1X2 de 6 ligas (The Odds API, região EU) duas vezes por dia e marca um **sinal**
quando uma casa disponível em Portugal (Betclic, 888) paga mais do que o preço justo
(Pinnacle sem margem; Betfair se faltar a Pinnacle). Fase atual: **só observar, sem apostar**.

## Medidas
- **Valor contra o fecho (CLV):** a odd do sinal comparada com o preço justo na última leitura
  antes do jogo. Positivo em média = vantagem real (é a medida que importa no primeiro mês).
- **Resultado:** lucro por aposta de 1 unidade, quando houver resultados.

## Configuração (uma vez)
1. Repositório no GitHub → Settings → Secrets and variables → Actions → New repository secret:
   nome `ODDS_API_KEY`, valor = a chave da The Odds API.
2. O workflow `.github/workflows/scanner.yml` precisa de estar no ramo principal (`main`)
   para o agendamento funcionar. Os dados vão para o ramo `scanner-dados`.

## Correr à mão
```
pip install requests pandas numpy
export ODDS_API_KEY=...        # nunca pôr a chave no código
python scan.py                 # 1 crédito por liga
python resultados.py           # 2 créditos por liga com sinais por fechar
python relatorio.py
```

## Limites conhecidos
- A Betclic na API é a versão francesa; as odds da Betclic PT podem ser diferentes.
- Betano, Bwin e Placard não estão na API.
- Plano grátis: 500 créditos/mês (6 ligas x 2 leituras/dia ~ 360 + resultados).
