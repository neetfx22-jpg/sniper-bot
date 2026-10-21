# Relatório: estratégia "onda" (dupla fenda) no engine_salto — pesquisa completa e pedido de alteração

Destinatário: o agente que mantém o projeto Engine (Puzzle 71) no Termux.
Origem: sessão de pesquisa no repositório `neetfx22-jpg/sniper-bot`, branch `ccr-fed56ee1-ov03gr`, pasta `puzzle71/`.

---

## 1. Resumo para decisão

- **Pedido:** incluir no engine um modo de ordem de busca opcional, `--modo onda`, inspirado no padrão de interferência
  da dupla fenda. **Não muda o comportamento padrão**: sem a flag, o engine é idêntico ao `engine_salto_final`.
- **Resultado da pesquisa:** nenhuma ordem de busca (sequencial, salto áureo, onda clara, onda pura, franjas escuras)
  acha a chave mais rápido em média. Todas percorrem ~50% da faixa até a chave, com diferenças dentro da margem de erro
  em 1 milhão de chaves simuladas, em 82 chaves reais resolvidas e no engine real.
- **Por que incluir mesmo assim:** o dono do projeto quer testar no próprio celular. O modo não custa velocidade
  (o mapeamento acontece uma vez por chunk de 262.400 chaves) e cobre 100% da faixa sem repetir.
  Junto vai um script de corrida com chaves sorteadas que permite verificar a hipótese no aparelho.
- **Expectativa correta:** o modo onda **não** reduz o tempo esperado para achar a chave do Puzzle 71.
  O que reduz é a velocidade em chaves/s.

## 2. Ponto de partida

- Engine analisado: `engine_salto_final.c` (backup `engine_salto_backup_20261017_123532.tar.gz`).
  - secp256k1 com soma de pontos e inversão em lote (Montgomery, HALF=512, BATCH=1025, chunk = 262.400 chaves).
  - SHA-256 por hardware (ARMv8 crypto, NEON) e RIPEMD-160 próprio.
  - Ordem dos chunks: `phys = (idx * STRIDE) mod N`, com `STRIDE ≈ N·0,618` (razão áurea), coprimo com N.
  - Faixa do Puzzle 71: 2^70 chaves = 4.499.205.871.636.477 chunks. Passo = 2780662151054439.
- Velocidade no celular (status.txt): **6,67 M chaves/s** com 8 threads.
- Inspiração: vídeo "Dr. Quantum" sobre a dupla fenda. Onde as ondas chegam em fase surgem franjas claras;
  onde chegam fora de fase, se anulam e surgem franjas escuras.

## 3. O que foi implementado (`puzzle71/engine_salto_onda.c`)

É o `engine_salto_final.c` com estas mudanças, e só estas:

1. **`--modo onda`**
   - A faixa é dividida em `NBINS = min(4096, N)` faixas contíguas (`bin_lo[b] = N·b/NBINS`).
   - Intensidade de cada faixa no centro `u = (b+0,5)/NBINS − 0,5`:
     `I(u) = cos²(π·F·u) · sinc²(π·L·u)`, com `F = --franjas` (padrão 10) e `L = --envelope` (padrão 1,5).
   - As faixas são ordenadas por intensidade decrescente (empate: menor índice) e visitadas nessa ordem.
   - Dentro de cada faixa: salto áureo próprio da faixa (padrão) ou sequencial (`--dentro sequencial`, "onda pura").
   - `--ordem escuras`: inverte a ordem, começando pelas franjas escuras (onde as ondas se anulam).
   - Função nova `map_chunk(idx)`: busca binária na soma acumulada por rank e depois o offset dentro da faixa.
     Substitui `(idx*STRIDE) % TOTAL_CHUNKS` no `worker`.
   - `golden_stride(n)` foi extraído de `init_salto` sem mudar o resultado (o passo continua 2780662151054439).
2. **SHA-256 portátil** com `#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)` … `#else` … `#endif`.
   No celular, com `-march=armv8-a+crypto`, o caminho NEON original continua sendo usado (macros conferidas no clang).
   O fallback serve só para rodar os testes em x86.
3. `#include <math.h>` e linkagem com `-lm`.

Arquivos de apoio na mesma pasta:

| Arquivo | Função |
|---|---|
| `build_onda.sh` | compila no Termux com as mesmas flags do `build_final.sh` e roda o selftest |
| `corrida_aleatoria.py` | sorteia chaves novas, roda o engine real em todas as estratégias, mostra o placar |
| `hash160.py` | hash160 comprimido de uma chave (Python puro, para gerar alvos) |
| `simular_ordem.py` | réplica exata da ordem do engine, invertida (chunk → posição na fila) |
| `comparacao_pareada.py` | compara as estratégias chave a chave em 1 milhão de chaves na faixa do Puzzle 71 |
| `rodar_teste_real.sh` | roda o engine contra os puzzles resolvidos 22–32 |
| `chaves_resolvidas.txt`, `alvos.txt` | 83 chaves de puzzles resolvidos e o hash160 de cada uma |

## 4. Validação

- **Selftest:** 55/55 em x86 (com o SHA-256 portátil). **No celular ainda falta rodar `./build_onda.sh`**,
  que deve dar 55/55 com o caminho NEON.
- **Os hash160 dos alvos** batem com os do selftest original (puzzles 20, 30 e 70).
- **Engine real contra puzzles resolvidos:** a chave achada é conferida em toda rodada. Até agora: 0 erros.
- **Simulador = engine:** puzzle 25 onda F=10 dá 0,7747 nos dois; puzzle 27 onda pura dá 0,5235 nos dois
  e escuras dá 0,4844 nos dois. O passo do salto no simulador é igual ao do log do celular.
- **Velocidade:** idêntica com e sem `--modo onda` (5,09 M chaves/s nos dois casos, em 4 núcleos x86).

## 5. Resultados

Métrica em todos os testes: **fração da faixa percorrida até achar a chave** (menor é melhor; uma ordem sem vantagem dá 0,50).

### 5.1 Simulação exata: 1 milhão de chaves sorteadas, faixa real do Puzzle 71 (pareada)

| Estratégia | Média | IC 95% |
|---|---|---|
| sequencial | 0,4995 | ±0,0006 |
| salto áureo | 0,4998 | ±0,0006 |
| onda F=10 | 0,5000 | ±0,0006 |
| onda F=20 | 0,5004 | ±0,0006 |

Confrontos diretos, nas mesmas chaves:

- salto × sequencial: diferença +0,0002 (±0,0008); o salto ganha em 50,0% das chaves.
- onda F=10 × salto: diferença +0,0002 (±0,0008); a onda ganha em 50,0% das chaves.
- onda F=10 × onda F=20: diferença −0,0004 (±0,0008). **A F=10 ganha em 66% das chaves**, por 0,23 da faixa em média;
  quando perde, perde por 0,46. O saldo é zero.

### 5.2 Simulação: 200 mil chaves sorteadas, faixa real do Puzzle 71, todas as variantes

| Estratégia | Média (±0,0013) |
|---|---|
| sequencial | 0,5001 |
| salto áureo | 0,5011 |
| onda F=5 / 10 / 20 / 50 | 0,5003 / 0,4996 / 0,4997 / 0,5006 |
| onda pura F=10 / 20 | 0,4996 / 0,4997 |
| escuras primeiro F=10 / 20 | 0,5004 / 0,5003 |

### 5.3 Simulação: 82 chaves reais resolvidas (puzzles 2 a 135)

| Estratégia | Média | IC 95% |
|---|---|---|
| sequencial | 0,522 | ±0,059 |
| salto áureo | 0,515 | ±0,062 |
| onda F=5 / 10 / 20 / 50 | 0,462 / 0,484 / 0,488 / 0,476 | ±0,06–0,07 |
| onda pura F=10 / 20 | 0,484 / 0,488 | ±0,06–0,07 |
| escuras F=10 / 20 | 0,509 / 0,505 | ±0,06–0,07 |

Tudo dentro da margem de erro. Com 10 variantes em 82 chaves, é esperado que alguma fique ~0,04 abaixo de 0,5 por acaso.

### 5.4 As chaves resolvidas se concentram em alguma região?

74 chaves (puzzles ≥ 10). Kolmogorov-Smirnov contra uniforme: D = 0,079, **p = 0,73**. Sem concentração: elas se
distribuem como chaves sorteadas uniformemente, então não há "região quente" para priorizar.

### 5.5 Engine real, puzzles resolvidos 22 a 32 (4 threads) — concluído

| Puzzle | Sequencial | Salto | Onda F=10 | Onda F=20 |
|---|---|---|---|---|
| 22 | 0,24 | 0,75 | 0,72 | 0,22 |
| 23 | 0,34 | 0,83 | 0,82 | 0,09 |
| 24 | 0,65 | 0,37 | 0,50 | 0,41 |
| 25 | 0,98 | 0,29 | 0,77 | 0,99 |
| 26 | 0,64 | 0,03 | 0,23 | 0,77 |
| 27 | 0,67 | 0,09 | 0,53 | 0,48 |
| 28 | 0,69 | 0,60 | 0,11 | 0,12 |
| 29 | 0,49 | 0,93 | 0,01 | 0,08 |
| 30 | 0,92 | 0,40 | 0,63 | 0,97 |
| 31 | 0,96 | 0,20 | 0,91 | 0,63 |
| 32 | 0,44 | 0,24 | 0,70 | 0,14 |
| **Média** | **0,64** | **0,43** | **0,54** | **0,45** |

44 rodadas, 44 chaves certas. Mais rápida por puzzle: salto 6, onda F=20 3, onda F=10 2, sequencial 0.

Nestes puzzles o sequencial ficou pior (média 0,64), porque por acaso as chaves caíram tarde nas suas faixas
(puzzle 25 em 98%, puzzle 31 em 96%). Isso é uma propriedade dessas chaves, não da estratégia: nas 82 chaves o sequencial
dá 0,52 e em 1 milhão de chaves dá 0,4995. Atenção: estes 9–10 puzzles foram o ponto de partida da hipótese.
Por isso a confirmação precisa de chaves novas (seções 5.1, 5.2 e 5.6).

### 5.6 Engine real, chaves novas sorteadas (em andamento)

`corrida_aleatoria.py`, 300 chaves, faixa de 2^24 chaves, 6 estratégias, semente 2026.
Resultado parcial em `resultado_corrida_aleatoria.csv`/`.txt`. Com poucas chaves a margem ainda é de ±0,2, então
não dá para concluir nada dele ainda; a seção 5.1 já tem o poder estatístico.

## 6. Por que o resultado é esse (a matemática)

Se a chave pode estar em qualquer posição da faixa com a mesma probabilidade, então para **qualquer** ordem que visita
cada chunk exatamente uma vez, a posição da chave na fila também é uniforme. O valor esperado da fração percorrida é
1/2, seja a ordem sequencial, áurea, por franjas claras ou escuras. Uma ordem só ganharia se a distribuição das chaves
não fosse uniforme. A seção 5.4 mostra que não há sinal disso nas chaves resolvidas, e os puzzles foram criados
com chaves aleatórias.

A interferência das ondas é física de sistemas quânticos. Um programa clássico que imita o padrão como regra de
ordenação não ganha superposição nem interferência. Um algoritmo quântico real para busca (Grover) exigiria um
computador quântico com milhões de qubits corrigidos, que não existe. O algoritmo de Shor não se aplica ao Puzzle 71,
porque a chave pública dele não é conhecida.

O que muda o tempo esperado é a **velocidade**: com 6,67 M chaves/s, metade de 2^70 leva ~2,8 milhões de anos.

## 7. Pedido de alteração (para o agente aplicar)

1. Copiar `puzzle71/engine_salto_onda.c` e `puzzle71/build_onda.sh` para `~/engine_salto/`
   (ou fazer o diff contra `engine_salto_final.c`: as mudanças estão listadas na seção 3).
2. Rodar `./build_onda.sh`. **Precisa dar `selftest: 55/55`**. Se não der, não usar o binário.
3. Benchmark curto, para confirmar que a velocidade não mudou:
   ```
   ./engine_salto_onda --threads 8 --seconds 30 --ckpt /tmp/b.txt --status /dev/null
   ./engine_salto_onda --threads 8 --seconds 30 --modo onda --franjas 10 --ckpt /tmp/b2.txt --status /dev/null
   ```
4. Corrida de verificação no aparelho (opcional, mas é o teste que o dono do projeto quer ver):
   ```
   python3 corrida_aleatoria.py ./engine_salto_onda --chaves 100 --bits 26 --threads 8 --estrategias sequencial,salto,onda10,onda20
   ```
5. Se for rodar o Puzzle 71 em modo onda: **usar um checkpoint separado** (`--ckpt ckpt_onda10.txt`).
   O checkpoint guarda o índice lógico, e o mesmo índice aponta para chunks diferentes em cada modo.
   **Não reaproveitar o `ckpt_salto.txt`.** Opcional: gravar o modo no checkpoint e recusar a carga quando
   o modo for diferente (hoje o `load_ckpt` só confere o início da faixa e o tamanho do chunk).
6. **Manter o `engine_salto_final` como padrão.** O modo onda é opt-in, para experimento.

## 8. Limitações

- O binário ARM não foi executado nesta pesquisa: só o caminho x86 rodou. O selftest no celular é obrigatório.
- No modo onda, o `TOTAL_CHUNKS * b` dentro de `init_onda` é calculado em u128. Na faixa do Puzzle 71 cabe com folga
  (4,5e15 × 4096 ≈ 1,8e19). Para faixas acima de ~2^150 chaves seria preciso outra conta, mas isso está fora do escopo.
- Nos testes reais com 4 threads, várias threads processam chunks em paralelo, então o número de chaves testadas tem uma
  folga de alguns chunks. Em faixas pequenas (poucos chunks) isso mexe na fração. A métrica do simulador é exata.
