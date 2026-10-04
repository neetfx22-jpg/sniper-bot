"""Jogar POUCOS jogos e esperar o prémio grande: compensa? Números exatos + simulação."""
import numpy as np

PRECO = 3.50
SORTEIOS_ANO = 6 * 52            # ~6 por semana
P15 = 1 / 3268760                # prob. de 15 pontos por jogo
P14 = 1 / 21792
JACK = 1_500_000                 # jackpot médio real
PR14 = 1789                      # prémio médio de 14 pontos

print("== Quanto tempo até um JACKPOT, conforme quantos jogos por sorteio ==")
print(f"{'jogos/sort.':>11} | {'custo/mês':>11} | {'tempo médio p/ 1 jackpot':>26} | {'gasto até lá':>14}")
for n in (1, 5, 10, 50, 100):
    sorteios_ate = 1 / (n * P15)
    anos = sorteios_ate / SORTEIOS_ANO
    gasto = sorteios_ate * n * PRECO
    custo_mes = n * PRECO * SORTEIOS_ANO / 12
    print(f"{n:>11} | R$ {custo_mes:>8,.0f} | {anos:>18,.0f} anos | R$ {gasto:>11,.0f}".replace(",", "."))

print("\n'um acerto paga anos de jogo' — sim, mas veja o equilíbrio:")
n = 10
custo_ano = n * PRECO * SORTEIOS_ANO
anos_que_jack_paga = JACK / custo_ano
anos_ate_jack = 1 / (n * P15) / SORTEIOS_ANO
print(f"   jogando {n} jogos/sorteio: custo R$ {custo_ano:,.0f}/ano".replace(",", "."))
print(f"   um jackpot de R$ {JACK:,.0f} paga {anos_que_jack_paga:,.0f} anos de jogo".replace(",", "."))
print(f"   MAS em média leva {anos_ate_jack:,.0f} anos para sair um jackpot".replace(",", "."))
print(f"   ou seja: gasta {anos_ate_jack/anos_que_jack_paga:.0f}x mais tempo a pagar do que o prémio devolve.")

print("\n== Simulação: 50 jogos/sorteio (R$ 175/sorteio) durante 5 anos, 20.000 vidas possíveis ==")
rng = np.random.default_rng(1)
n, anos = 50, 5
sorteios = anos * SORTEIOS_ANO
custo_total = n * PRECO * sorteios
finais = []
jackpots = 0
for _ in range(20000):
    # prémios por sorteio: nº de 15 e 14 (Poisson), e os menores devolvem ~0,40 em média
    q15 = rng.poisson(n * P15 * sorteios)
    q14 = rng.poisson(n * P14 * sorteios)
    menores = 0.40 * custo_total    # 11/12/13 recuperam ~40% de forma estável
    ganho = q15 * JACK + q14 * PR14 + menores
    finais.append(ganho - custo_total)
    jackpots += q15 > 0
finais = np.array(finais)
print(f"custo em 5 anos: R$ {custo_total:,.0f}".replace(",", "."))
print(f"   acabaram no LUCRO: {(finais>0).mean():.1%} das vidas  (quase sempre os que tiveram a sorte de um jackpot)")
print(f"   tiveram pelo menos 1 jackpot em 5 anos: {jackpots/20000:.1%}")
print(f"   resultado MEDIANO: R$ {np.median(finais):,.0f}  (o que acontece na vida típica)".replace(",", "."))
print(f"   resultado MÉDIO:   R$ {finais.mean():,.0f}".replace(",", "."))
print(f"   pior / melhor: R$ {finais.min():,.0f} / R$ {finais.max():,.0f}".replace(",", "."))
