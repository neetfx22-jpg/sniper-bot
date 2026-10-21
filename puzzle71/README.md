# Puzzle 71: teste da estratégia "onda" (dupla fenda) no engine_salto

## O que foi feito

- `engine_salto_onda.c` é o seu `engine_salto_final.c` com duas mudanças, e nada mais:
  1. **`--modo onda`**: a faixa é dividida em até 4096 faixas. Cada faixa recebe a intensidade do padrão da dupla fenda,
     `I(u) = cos²(π·F·u) · sinc²(π·L·u)`, com `u` = posição na faixa − 0,5.
     As faixas são visitadas da mais clara (onde as ondas se encontram em fase) para a mais escura e, dentro de cada faixa,
     com o mesmo salto áureo do engine. Continua cobrindo 100% dos chunks, sem repetir nenhum.
     Parâmetros: `--franjas F` (padrão 10) e `--envelope L` (padrão 1,5).
     - `--dentro sequencial`: **onda pura**, sem salto áureo nenhum. A ordem vem só da intensidade das franjas e,
       dentro de cada faixa, vai em sequência.
     - `--ordem escuras`: começa pelas faixas escuras, onde as ondas se encontram e **se anulam**.
  2. **SHA-256 portátil** quando o processador não é ARM com extensão crypto (para rodar o teste em x86).
     No celular continua sendo usado o caminho NEON original.
- Sem `--modo onda`, o comportamento é idêntico ao `engine_salto_final` (mesmo passo: 2780662151054439).
- O selftest passa (55/55).

Compilar no Termux: `./build_onda.sh`. Rodar, por exemplo:

```
./engine_salto_onda --threads 8 --modo onda --dentro sequencial --franjas 10 --ckpt ckpt_onda.txt
./engine_salto_onda --threads 8 --modo onda --dentro sequencial --ordem escuras --franjas 10 --ckpt ckpt_escura.txt
```

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

   O simulador bate com o engine real: puzzle 25 onda F=10 dá 0,7747 nos dois; puzzle 27 onda pura F=10 dá 0,5235 nos dois e escuras F=10 dá 0,4844 nos dois.
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
| onda pura F=10 (sem áureo) | 0,4996 | ±0,0013 |
| onda pura F=20 (sem áureo) | 0,4997 | ±0,0013 |
| escuras primeiro F=10 (sem áureo) | 0,5004 | ±0,0013 |
| escuras primeiro F=20 (sem áureo) | 0,5003 | ±0,0013 |

### 82 chaves reais resolvidas (puzzles 2 a 135)

| Estratégia | Média | IC 95% |
|---|---|---|
| sequencial | 0,522 | ±0,059 |
| salto (atual) | 0,515 | ±0,062 |
| onda F=5 | 0,462 | ±0,062 |
| onda F=10 | 0,484 | ±0,060 |
| onda F=20 | 0,488 | ±0,067 |
| onda F=50 | 0,476 | ±0,068 |
| onda pura F=10 (sem áureo) | 0,484 | ±0,060 |
| onda pura F=20 (sem áureo) | 0,488 | ±0,067 |
| escuras primeiro F=10 (sem áureo) | 0,509 | ±0,061 |
| escuras primeiro F=20 (sem áureo) | 0,505 | ±0,065 |

Todas as diferenças ficam dentro da margem de erro. O F=5 parecer um pouco melhor é ruído: com 10 variantes testadas
em 82 chaves, é esperado que uma delas fique uns 0,04 abaixo de 0,5 por sorte.

### Posição das chaves resolvidas dentro da faixa

74 chaves (puzzles ≥ 10). KS contra uniforme: D = 0,079, **p-valor = 0,73**. Não há concentração detectável:
as chaves estão espalhadas como se fossem sorteadas uniformemente.

### Engine real, puzzles 22 a 32 (`resultado_teste_real.csv`)

Médias: sequencial 0,64 · salto 0,43 · onda F=10 0,54 · onda F=20 0,45 (11 puzzles; a margem com 11 chaves é de ~±0,17).
Detalhes e explicação na seção 5.5 do `RELATORIO_PARA_AGENTE.md`.

## Modo partículas (versão 2, inspirado nos elétrons do vídeo)

No modo onda, cada faixa do Puzzle 71 tem ~2,9×10¹⁷ chaves: o engine ficaria ~1.370 anos na primeira, sem sair do centro.
O `--modo particulas` faz **rodadas**. Em cada rodada, dispara janelas de 4 chunks (~1,05 milhão de chaves) em todas as
4096 faixas, mais nas claras (até 100 por faixa, mínimo 1), sem repetir chave. Uma rodada leva ~5,3 h no celular.
`simular_particulas.py`, resultado em `resultado_particulas.txt`:

- versão B (rodadas sem repetição, a implementada): puzzle 71 F=10 = 0,497 ± 0,011, F=20 = 0,503 ± 0,010; puzzles 40 e 50 também ~0,50;
- versão A (partículas aleatórias que podem repetir lugar, literal do vídeo): 1.302× a faixa sem piso, 1,8× com piso de 10%. Muito pior.

Validação: cobertura exata (cada chunk uma vez) e ordem do engine igual à do simulador.

## Aceleração (versão 3)

Perfil por chave no x86: o RIPEMD-160 era 36 a 45% do tempo. Agora ele calcula 4 chaves de uma vez com vetores do
compilador (NEON no celular), totalmente desenrolado: de 306 a 351 ns para 50 ns por chave. O engine junta as chaves
em grupos de 4 antes dos hashes, sem pular nenhuma.

- x86: de 5,0 para 8,1 M chaves/s (+60%). ARM emulado (qemu): +60%.
- **No celular (8 threads, média de 3 rodadas de 60 s):** v2 = 6.396.614 chaves/s · v3 normal = 12.602.809 (+97%) ·
  v3 x2 = 12.714.958 (**+98,8%**). Em produção, a x2 roda a 12,74 M chaves/s e retomou do checkpoint (1578937) sem perder nada.
  Com isso, uma rodada do modo partículas cai de ~5 h para ~2,8 h.
- Opção `-DSHA_INTERCALADO` (binário `engine_salto_onda_x2`): SHA-256 por hardware em 2 mensagens intercaladas, para
  testar no celular.
- Verificado no ARM64 emulado, com gcc e clang: selftest 55/55, RIPEMD 4 vias = 1 via (4000/4000),
  SHA intercalado = normal (1000/1000), e chave certa em todas as rodadas da corrida.
- A ordem de busca não mudou: os checkpoints continuam valendo.

## Conclusão

- **A ordem "onda" não acha a chave mais rápido.** A conta é a seguinte: se a chave pode estar em qualquer lugar com a mesma
  chance, **toda** ordem que cobre a faixa sem repetir percorre, em média, metade dela. Sequencial, salto áureo ou franjas
  de interferência, tanto faz. Só ajudaria se as chaves se concentrassem em algum lugar, e o teste 3 mostra que não se concentram.
- O que muda o tempo esperado é **a velocidade** (chaves/s), não a ordem. O seu engine já faz 6,7 M chaves/s no celular.
  Mesmo assim, percorrer metade de 2^70 leva cerca de 2,8 milhões de anos.
- O modo onda fica disponível. Ele não piora nada (mesma velocidade, mesma cobertura), só não melhora.
