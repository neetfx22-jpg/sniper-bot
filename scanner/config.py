"""Configuração do scanner de apostas de valor (Portugal)."""
import os

# Ligas observadas (6 ligas x 2 leituras/dia ~ 360 consultas/mês; o plano grátis tem 500)
LIGAS = [
    "soccer_portugal_primeira_liga",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
]
# Casas onde se pode apostar em Portugal e que a API cobre (Betclic aparece na versão FR)
CASAS_PT = {"betclic_fr": "Betclic", "sport888": "888"}
# Referência do preço justo, por ordem de preferência
REFERENCIAS = ["pinnacle", "betfair_ex_eu"]
COMISSAO_BETFAIR = 0.0   # só para referência; não se aposta na Betfair
LIMIAR_VALOR = 0.02      # sinal quando odd x prob. justa - 1 > 2%
ODD_MAX = 4.0            # no backtest a vantagem estava nas odds até 4

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
API = "https://api.the-odds-api.com/v4"

def chave():
    k = os.environ.get("ODDS_API_KEY")
    if not k:
        f = os.environ.get("ODDS_API_KEY_FILE")
        if f and os.path.exists(f):
            k = open(f).read().strip()
    if not k:
        raise SystemExit("Defina ODDS_API_KEY (ou ODDS_API_KEY_FILE).")
    return k
