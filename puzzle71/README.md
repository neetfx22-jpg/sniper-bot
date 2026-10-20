# Puzzle 71: teste da estratégia "onda" (dupla fenda) no engine_salto

## O que foi feito

- `engine_salto_onda.c` é o seu `engine_salto_final.c` com duas mudanças, e nada mais:
  1. **`--modo onda`**: a faixa é dividida em até 4096 faixas. Cada faixa recebe a intensidade do padrão da dupla fenda,
     `I(u) = cos²(π·F·u) · sinc²(π·L·u)`, com `u` = posição na faixa − 0,5.
     As faixas são visitadas da mais clara (onde as ondas se encontram em fase) para a mais escura e, dentro de cada faixa,
     com o mesmo salto áureo do engine. Continua cobrindo 100% dos chunks, sem repetir nenhum.
     Parâmetros: `--franjas F` (padrão 10) e `--envelope L` (padrão 1,5).
  2. **SHA-256 portátil** quando o processador não é ARM com extensão crypto (para rodar o teste em x86).
     No celular continua sendo usado o caminho NEON original.
- Sem `--modo onda`, o comportamento é idêntico ao `engine_salto_final` (mesmo passo: 2780662151054439).
- O selftest passa (55/55).

Compilar no Termux: `./build_onda.sh`. Rodar: `./engine_salto_onda --threads 8 --modo onda --franjas 10 --ckpt ckpt_onda.txt`.

> Use um arquivo de checkpoint **separado** para o modo onda. O checkpoint guarda só o índice lógico, e esse índice
> aponta para chunks diferentes em cada modo.

## Como foi testado

1. **Engine real** (`rodar_teste_real.sh`): o binário compilado busca de verdade as chaves dos puzzles 22 a 32
   (já resolvidos), em 4 ordens: sequencial (`--stride 1`), salto (padrão), onda F=10 e onda F=20.
   O teste confere se a chave achada é a certa e anota quantas chaves foram testadas até achar.
2. **Simulador exato da ordem** (`simular_ordem.py`): a mesma permutação do C, invertida (chunk → posição na fila).
   Ele dá a fração da faixa percorrida até a chave para:
   - todas as 82 chaves resolvidas (puzzles 2 a 135), na faixa real de cada uma;
   - 200 mil chaves aleatórias na faixa real do Puzzle 71 (2^70 chaves, 4,5 quatrilhões de chunks).

   O simulador bate com o engine real: por exemplo, puzzle 25 onda F=10 dá 0,7747 nos dois.
3. **As chaves resolvidas se concentram em alguma região?** Histograma das posições relativas mais o teste de Kolmogorov-Smirnov
   contra a distribuição uniforme.

Arquivos de resultado: `resultado_teste_real.csv`, `resultado_simulacao.txt`, `resultado_chaves_resolvidas.csv`.

## Resultados

Métrica: **fração da faixa percorrida até achar a chave**. Menor é melhor. Uma ordem sem vantagem dá 0,50 em média.

### 200 mil chaves aleatórias, faixa real do Puzzle 71

| Estratégia | Média | IC 95% |
|---|---|---|
| sequencial | 0,5001 | ±0,0013 |
| salto (atual) | 0,5011 | ±0,0013 |
| onda F=5 | 0,5003 | ±0,0013 |
| onda F=10 | 0,4996 | ±0,0013 |
| onda F=20 | 0,4997 | ±0,0013 |
| onda F=50 | 0,5006 | ±0,0013 |

### 82 chaves reais resolvidas (puzzles 2 a 135)

| Estratégia | Média | IC 95% |
|---|---|---|
| sequencial | 0,522 | ±0,059 |
| salto (atual) | 0,515 | ±0,062 |
| onda F=5 | 0,462 | ±0,062 |
| onda F=10 | 0,484 | ±0,060 |
| onda F=20 | 0,488 | ±0,067 |
| onda F=50 | 0,476 | ±0,068 |

Todas as diferenças ficam dentro da margem de erro. O F=5 parecer um pouco melhor é ruído: com 6 variantes testadas
em 82 chaves, é esperado que uma delas fique uns 0,04 abaixo de 0,5 por sorte.

### Posição das chaves resolvidas dentro da faixa

74 chaves (puzzles ≥ 10). KS contra uniforme: D = 0,079, **p-valor = 0,73**. Não há concentração detectável:
as chaves estão espalhadas como se fossem sorteadas uniformemente.

### Engine real, puzzles 22 a 32

Ver a seção "Rodadas reais" no fim deste arquivo.

## Conclusão

- **A ordem "onda" não acha a chave mais rápido.** A conta é a seguinte: se a chave pode estar em qualquer lugar com a mesma
  chance, **toda** ordem que cobre a faixa sem repetir percorre, em média, metade dela. Sequencial, salto áureo ou franjas
  de interferência, tanto faz. Só ajudaria se as chaves se concentrassem em algum lugar, e o teste 3 mostra que não se concentram.
- O que muda o tempo esperado é **a velocidade** (chaves/s), não a ordem. O seu engine já faz 6,7 M chaves/s no celular.
  Mesmo assim, percorrer metade de 2^70 leva cerca de 2,8 milhões de anos.
- O modo onda fica disponível. Ele não piora nada (mesma velocidade, mesma cobertura), só não melhora.
