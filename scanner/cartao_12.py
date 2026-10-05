"""Primeiro caso de teste REAL em papel: o booking code A8QS78UE (Betano),
uma Múltipla de 12 favoritos. Grava as seleções/odds exatas da app e, quando
os resultados estiverem preenchidos, settla em papel TODOS os sistemas
(Múltiplas 2..12 seleções, como o Betano mostra) e a aposta simples.

Como usar:
  1) quando os jogos terminarem, preenche RESULTADOS (True = o favorito acertou).
  2) python cartao_12.py
Não aposta nada. Não gasta API. É só a matemática do bilhete.
"""
from itertools import combinations
from math import comb

# (favorito apostado, jogo, odd) — exatamente como no booking code
CARTAO = [
    ("França",              "França x Bélgica",            1.52),
    ("Itália",              "Itália x Turquia",            1.44),
    ("Suécia",              "Roménia x Suécia",            1.72),
    ("Polónia",             "Bósnia-Herzegovina x Polónia", 2.30),
    ("Ucrânia",             "Ucrânia x Hungria",           2.45),
    ("Irlanda do Norte",    "Irlanda do Norte x Geórgia",  2.40),
    ("RD Congo",            "Uganda x RD Congo",           1.72),
    ("Montenegro",          "Montenegro x Arménia",        1.53),
    ("Chipre",              "Chipre x Letónia",            1.62),
    ("Curaçao",             "Trinidad & Tobago x Curaçao", 1.37),
    ("Velez Sarsfield",     "Velez Sarsfield x CA Platense", 1.88),
    ("República Dominicana", "Nicarágua x República Dominicana", 1.52),
]

# Preenche com True (favorito ganhou) / False (não ganhou) após os jogos.
# Deixa None no que ainda não terminou — esses ficam de fora do cálculo.
RESULTADOS = {
    "França": None, "Itália": None, "Suécia": None, "Polónia": None,
    "Ucrânia": None, "Irlanda do Norte": None, "RD Congo": None,
    "Montenegro": None, "Chipre": None, "Curaçao": None,
    "Velez Sarsfield": None, "República Dominicana": None,
}

APOSTA_LINHA = 1.0   # unidade por linha


def settla(selec, stake=APOSTA_LINHA):
    """Para um conjunto de seleções com resultado conhecido, devolve por
    tamanho de sistema k: (nº de linhas, apostado, retorno)."""
    n = len(selec)
    ganhou = [r for _, _, _, r in selec]
    por_k = {}
    for k in range(1, n + 1):
        linhas = apostado = retorno = 0
        for idx in combinations(range(n), k):
            linhas += 1
            apostado += stake
            if all(ganhou[i] for i in idx):
                prod = 1.0
                for i in idx:
                    prod *= selec[i][2]
                retorno += stake * prod
        por_k[k] = (linhas, apostado, retorno)
    return por_k


def main():
    print("Booking code A8QS78UE — Múltipla de 12 favoritos (Betano)\n")
    prontos, pendentes = [], []
    for fav, jogo, odd in CARTAO:
        r = RESULTADOS.get(fav)
        if r is None:
            pendentes.append((fav, jogo, odd))
        else:
            prontos.append((fav, jogo, odd, bool(r)))

    for fav, jogo, odd, r in prontos:
        print(f"  {'OK ' if r else 'ERRO'} {jogo:<36} {fav} @ {odd:.2f}")
    for fav, jogo, odd in pendentes:
        print(f"  ...  {jogo:<36} {fav} @ {odd:.2f}  (sem resultado)")

    if len(prontos) < 2:
        print(f"\n{len(prontos)} de 12 com resultado. Preenche RESULTADOS e corre outra vez.")
        return

    acertos = sum(1 for *_, r in prontos if r)
    n = len(prontos)
    print(f"\n{n} de 12 com resultado | acertos: {acertos}/{n}\n")

    por_k = settla(prontos)
    # aposta simples (k=1) como referência
    l1, ap1, ret1 = por_k[1]
    print(f"{'Sistema':<26}{'linhas':>7}{'apostado':>10}{'retorno':>11}{'lucro':>10}")
    print(f"{'Simples (1 seleção)':<26}{l1:>7}{ap1:>9.0f}u{ret1:>10.2f}u{ret1-ap1:>+9.2f}u")
    for k in range(2, n + 1):
        linhas, ap, ret = por_k[k]
        tag = f"Múltiplas {k} seleções"
        print(f"{tag:<26}{linhas:>7}{ap:>9.0f}u{ret:>10.2f}u{ret-ap:>+9.2f}u")

    # sistema completo "tudo" (todas as combinações 2..n, como um sistema Betano total)
    linhas_t = sum(comb(n, k) for k in range(2, n + 1))
    ap_t = sum(por_k[k][1] for k in range(2, n + 1))
    ret_t = sum(por_k[k][2] for k in range(2, n + 1))
    print(f"\n{'SISTEMA TOTAL (2..'+str(n)+')':<26}{linhas_t:>7}{ap_t:>9.0f}u{ret_t:>10.2f}u{ret_t-ap_t:>+9.2f}u")
    print(f"ROI do sistema total: {(ret_t-ap_t)/ap_t:+.1%}  |  ROI da aposta simples: {(ret1-ap1)/ap1:+.1%}")
    print("\n(1 u = o que puseres por linha. Compara sistema vs simples: se o sistema"
          "\nganha mais por unidade, amplificou; se ganha menos, amplificou o prejuízo.)")


if __name__ == "__main__":
    main()
