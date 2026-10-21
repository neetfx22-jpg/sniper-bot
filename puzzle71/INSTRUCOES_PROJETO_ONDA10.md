# Instruções: construir o projeto `engine_onda10` (Puzzle 71, modo partículas F=10)

> **Atualização (versão 2): o projeto passa a usar `--modo particulas`, não `--modo onda`.** Motivo: no modo onda,
> cada uma das 4096 faixas do Puzzle 71 tem ~2,9×10¹⁷ chaves. A 6,7 M chaves/s, o engine ficaria **~1.370 anos** na
> primeira faixa, sem nunca sair do centro. O modo partículas, inspirado nos elétrons disparados um a um do vídeo,
> faz **rodadas**: em cada rodada dispara janelas de 4 chunks (~1,05 milhão de chaves) em **todas** as 4096 faixas,
> com mais janelas nas franjas claras (k ∝ intensidade, até 100, mínimo 1). Uma rodada leva ~5,3 h no celular, e
> nenhuma chave é repetida. **Se você já iniciou o Puzzle 71 em `--modo onda` com `ckpt_onda10.txt`, pare,
> renomeie esse checkpoint (ex.: `ckpt_onda10_modo_onda.txt`) e comece do zero em partículas:** o índice salvo de um
> modo não vale no outro.

Para: o agente que mantém o projeto Engine no Termux.
Pedido do dono do projeto: criar um projeto novo que **replica o `engine_salto_final.c`** e acrescenta o modo onda F=10,
**sem perder a velocidade atual (~6,7 M chaves/s com 8 threads)**. Contexto e resultados da pesquisa estão em
`RELATORIO_PARA_AGENTE.md`.

Regra geral: **não mexer no projeto atual `~/engine_salto/`** (binários, `ckpt_salto.txt`, logs). O projeto novo fica
numa pasta separada, `~/engine_onda10/`.

---

## 0. Arquivos que você recebe

No pacote `engine_onda_termux.tar.gz` (ou no repositório `neetfx22-jpg/sniper-bot`, branch `ccr-fed56ee1-ov03gr`,
pasta `puzzle71/`):

| Arquivo | O que é |
|---|---|
| `engine_salto_onda.c` | o engine novo = `engine_salto_final.c` + modo onda + travas de NEON |
| `engine_salto_onda.patch` | as mesmas mudanças em formato diff, contra o `engine_salto_final.c` |
| `build_onda.sh` | compila com as mesmas flags do `build_final.sh` e roda o selftest |
| `start_onda10.sh` | inicia o Puzzle 71 em modo onda F=10, com checkpoint próprio |
| `status_onda10.sh` | dashboard (cópia do `status_salto.sh`, apontando para os arquivos do onda10) |
| `corrida_aleatoria.py`, `hash160.py` | corrida com chaves sorteadas (verificação opcional) |

SHA-256 dos fontes, para conferir:

```
6665b221737f50b1fd7b45e123a250fe680b946c66f75755cd90283f6e5f3f56  engine_salto_final.c  (o original, em ~/engine_salto/)
e45d564fb3b1436350206898bcef8d8887881dc925e35dc1d66b663a561ea212  engine_salto_onda.c
```

## 1. Criar o projeto a partir do engine atual

```
mkdir -p ~/engine_onda10 && cd ~/engine_onda10
sha256sum ~/engine_salto/engine_salto_final.c     # tem que dar 6665b221...
cp ~/engine_salto/engine_salto_final.c .
patch -o engine_salto_onda.c engine_salto_final.c < engine_salto_onda.patch   # (patch: pkg install patch)
sha256sum engine_salto_onda.c                     # tem que dar e45d564f...
cp <pacote>/build_onda.sh <pacote>/start_onda10.sh <pacote>/status_onda10.sh <pacote>/corrida_aleatoria.py <pacote>/hash160.py .
chmod +x *.sh
```

- Se o hash do `engine_salto_final.c` local for diferente, ele foi alterado depois do backup de 17/10.
  Nesse caso, aplique o patch mesmo assim e revise os trechos que não aplicarem. Não copie o `engine_salto_onda.c`
  do pacote por cima sem olhar o que muda.
- O `build_onda.sh` faz `cd "$(dirname "$0")"`, então funciona em qualquer pasta.

### O que o patch muda (e nada além disso)

1. `--modo onda`, com `--franjas F` (padrão 10), `--envelope L` (padrão 1,5), `--dentro sequencial|aureo` e
   `--ordem claras|escuras`. A faixa é dividida em até 4096 faixas, ordenadas pela intensidade
   `cos²(π·F·u)·sinc²(π·L·u)`. A troca é só em `map_chunk(idx)`, que substitui `(idx*STRIDE) % TOTAL_CHUNKS`
   no `worker`. É chamado **uma vez por chunk de 262.400 chaves**: custo desprezível.
2. `golden_stride()` foi extraído de `init_salto()`, sem mudar o resultado (o passo continua 2780662151054439).
3. SHA-256: o código NEON original foi mantido **byte a byte**, agora dentro de
   `#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)`. O `#else` traz um SHA-256 portátil, só para rodar fora do ARM.
4. **Trava de velocidade:** `#error` se for compilado em aarch64 **sem** a extensão crypto. Assim é impossível gerar no
   celular, sem perceber, um binário com o SHA-256 lento.
5. O engine imprime `sha256: NEON (hardware)` (ou `portatil`) no início e no selftest.
6. `#include <math.h>` e `-lm`.
7. **`--modo particulas`** (`--franjas F`, `--janela J` chunks, padrão 4, `--kmax K`, padrão 100): usa as mesmas 4096
   faixas e intensidades do modo onda, mas em rodadas. Na rodada R, a faixa b recebe as janelas `R·k_b … R·k_b+k_b−1`
   da sua fila própria (salto áureo sobre as janelas da faixa). Faixas mais claras vêm primeiro em cada rodada.
   A fila lógica tem `rodadas_max × Σk × J` posições (`LOGICAL_TOTAL`). Posições de faixas já esgotadas viram
   `SKIP_CHUNK` e são puladas sem custo (no Puzzle 71 isso só aconteceria depois de bilhões de anos).
   O `worker` e o laço principal agora usam `LOGICAL_TOTAL`, que é igual a `TOTAL_CHUNKS` nos outros modos.
   Validação: cada chunk visitado exatamente uma vez (n = 37, 4096, 50003 e 12305), e a ordem do engine é igual à do
   simulador (puzzles 26 a 30, diferença menor que um chunk).

Nada mudou em: aritmética de campo, inversão em lote, HALF/BATCH/CHUNK, RIPEMD-160, threads, checkpoint, status e FOUND.

## 2. Compilar

```
./build_onda.sh
```

Ele executa:
`clang -O3 -march=armv8-a+crypto -flto -funroll-loops -pthread engine_salto_onda.c -o engine_salto_onda -lm`,
que são as flags exatas do `build_final.sh` mais `-lm`.

## 3. Verificações de ARM/NEON (obrigatórias, todas têm que passar)

### 3.1 O compilador ativa o crypto
```
echo | clang -march=armv8-a+crypto -dM -E - | grep -E "__ARM_FEATURE_(CRYPTO|SHA2)"
```
Esperado: `#define __ARM_FEATURE_CRYPTO 1` e `#define __ARM_FEATURE_SHA2 1`.

### 3.2 O binário usa o SHA-256 por hardware
```
./engine_salto_onda --selftest | head -1
```
Esperado: `sha256: NEON (hardware)`. Se aparecer `portatil`, **pare**: o binário está errado.

### 3.3 As instruções SHA estão mesmo no binário
```
llvm-objdump -d engine_salto_onda | grep -c -E "sha256h|sha256su0"     # (pkg install llvm, se faltar)
llvm-objdump -d ~/engine_salto/engine_salto_final | grep -c -E "sha256h|sha256su0"
```
Os dois números têm que ser **maiores que zero e iguais** (ou muito próximos).

### 3.4 O processador suporta (sanidade)
```
grep -m1 -o -w -E "sha2|sha256" /proc/cpuinfo
```
Esperado: `sha2`. O engine atual já roda com NEON, então isso deve passar.

### 3.5 Selftest
```
./engine_salto_onda --selftest
```
Esperado: `selftest: 55/55 casos ok`. **Se der qualquer falha, não usar o binário.**

### 3.6 O modo salto continua idêntico ao original
```
./engine_salto_onda --threads 8 --seconds 5 --ckpt /tmp/x1.txt --status /dev/null | grep passo
```
Esperado: `passo=2780662151054439`, o mesmo do `log_salto.txt`.

## 4. Benchmark de velocidade (não pode perder os ~6,7 M chaves/s)

**Com o engine do Puzzle 71 parado**, porque dois engines dividem os 8 núcleos. Celular na tomada, tela ligada, sem
outro app pesado. Alterne as rodadas para o aquecimento do aparelho não favorecer nenhum binário:

```
cd ~/engine_onda10
for r in 1 2 3; do
  ~/engine_salto/engine_salto_final --threads 8 --seconds 60 --ckpt /tmp/b_a.txt --status /dev/null | tail -1
  ./engine_salto_onda --threads 8 --seconds 60 --ckpt /tmp/b_b.txt --status /dev/null | tail -1
  ./engine_salto_onda --threads 8 --seconds 60 --modo particulas --franjas 10 --ckpt /tmp/b_c.txt --status /dev/null | tail -1
  sleep 60
done
```

Critério de aceite: a média do `engine_salto_onda --modo particulas` fica **a até 3% do `engine_salto_final`**.
No x86 de teste a diferença foi zero (5,09 contra 5,09 M chaves/s).

Se ficar mais de 3% abaixo:
1. Repita a verificação 3.2/3.3. Quase sempre a causa é o SHA-256 portátil ter entrado.
2. Confira se as flags de compilação são idênticas às do `build_final.sh` (`-flto`, `-funroll-loops`, `-march=armv8-a+crypto`).
3. Compare `--modo onda` com o modo padrão do mesmo binário. Se só o modo onda estiver lento, o problema está em
   `map_chunk` (não deveria acontecer, porque é uma busca binária em 4096 posições por chunk).
4. Teste também `--threads 7`. Em alguns celulares, deixar um núcleo livre evita disputa com o sistema.

## 5. Teste funcional antes do Puzzle 71

Primeiro em modo partículas, que é o que vai rodar:

```
./engine_salto_onda --threads 8 --modo particulas --franjas 10 \
  --start 20000000 --end 3fffffff --target d39c4704664e1deb76c9331e637564c257d68a08 \
  --ckpt /tmp/t30p.txt --found /tmp/t30p_found.txt --status /dev/null
```

Esperado: `CHAVE ENCONTRADA: 0x...3d94cd64` e, no início, a linha
`modo PARTICULAS | janela=4 chunks (1049600 chaves) | kmax=100 | janelas por rodada=...`.
(Em faixas pequenas como a do puzzle 30, cada faixa tem poucos chunks e a ordem fica quase igual à do modo onda.
A diferença aparece em faixas grandes como a do 71; ela foi verificada no simulador, que é idêntico ao engine.)

Depois, o mesmo teste em modo onda:

O engine tem que achar uma chave conhecida em modo onda, de verdade:

```
./engine_salto_onda --threads 8 --modo onda --franjas 10 \
  --start 20000000 --end 3fffffff --target d39c4704664e1deb76c9331e637564c257d68a08 \
  --ckpt /tmp/t30.txt --found /tmp/t30_found.txt --status /dev/null
```

Esperado: `CHAVE ENCONTRADA: 0x...3d94cd64` (puzzle 30). No modo onda F=10 essa chave fica a ~63% da fila: cerca de 1 minuto a 6,7 M chaves/s. Apague `/tmp/t30*` depois.

Opcional, se o dono quiser ver o placar no aparelho:
```
python3 corrida_aleatoria.py ./engine_salto_onda --chaves 100 --bits 26 --threads 8 --estrategias sequencial,salto,onda10,onda20
```

## 6. Rodar o Puzzle 71

```
./start_onda10.sh       # recusa iniciar se outro engine_salto* estiver rodando
./status_onda10.sh      # dashboard
```

- O `start_onda10.sh` roda `--modo particulas --franjas 10 --janela 4 --kmax 100`.
- Checkpoint: **`ckpt_onda10.txt`**, só dele. **Nunca** apontar para o `ckpt_salto.txt`: o índice salvo é lógico,
  e o mesmo número aponta para chunks diferentes em cada modo. Reaproveitar pularia faixas sem testar.
- Para retomar depois de parar, basta rodar o `start_onda10.sh` de novo. Ele lê o `ckpt_onda10.txt` (a faixa e o
  tamanho do chunk são conferidos na carga).
- **Um engine de cada vez.** Salto e onda rodando juntos dividem os núcleos e repetem chunks entre si.
- **Não trocar de modo nem de F no meio.** O progresso de um modo não vale para outro. Para mudar, comece outro
  checkpoint do zero.
- No `status_onda10.sh`, o "chunk lógico" em modo partículas é a posição na fila (que é maior que o número de chunks).
  O progresso real são as chaves testadas, somadas entre as execuções.
- O FOUND vai para `~/engine_onda10/FOUND.txt`. O `status_onda10.sh` mostra a chave em destaque se ele existir.

## 7. Melhoria recomendada (opcional): gravar o modo no checkpoint

Hoje o `load_ckpt` confere só o início da faixa e o tamanho do chunk. Para impedir que um checkpoint de um modo seja
carregado em outro por engano:

- No `write_ckpt`, acrescentar um 4º campo com o modo, por exemplo `onda:F=10:L=1.5:dentro=aureo:ordem=claras`
  ou `salto:<passo>`.
- No `load_ckpt`, ler o 4º campo se existir. Se for diferente do modo atual, imprimir
  `checkpoint de outro modo; ignorado` e recusar (melhor ainda: sair com erro, para não recomeçar do zero sem querer).
- Se o campo não existir (checkpoint antigo), aceitar só no modo salto.

Depois da mudança: selftest 55/55, teste do item 5 e um ciclo de parar e retomar para confirmar que o checkpoint carrega.

## 8. O que esperar (para alinhar com o dono do projeto)

- Velocidade igual à do `engine_salto_final`.
- Cobertura de 100% da faixa, sem repetir chunks.
- Em partículas: a busca passa pela faixa inteira a cada ~5,3 h, em vez de ficar presa no centro.
- **O tempo esperado até achar a chave é o mesmo de qualquer outra ordem:** em média, metade da faixa
  (partículas F=10 no Puzzle 71: 0,497 ± 0,011; `resultado_particulas.txt`).
  A versão literal do vídeo, com partículas aleatórias que podem repetir lugar, foi testada e é muito pior
  (1,8× a faixa inteira, mesmo com piso de 10%), por isso não foi implementada.
  Isso foi verificado com 1 milhão de chaves simuladas, 82 chaves reais e o engine real (seções 5 e 6 do relatório).
  O modo onda é uma escolha do dono, não um atalho.

## 9. Checklist final (marcar tudo antes de iniciar o Puzzle 71)

- [ ] hash do `engine_salto_onda.c` = `e45d564f…` (ou diff revisado, se o original local for diferente)
- [ ] 3.1 macros crypto ativas
- [ ] 3.2 `sha256: NEON (hardware)`
- [ ] 3.3 instruções sha256h no binário, mesma contagem do original
- [ ] 3.5 selftest 55/55
- [ ] 3.6 passo = 2780662151054439 no modo salto
- [ ] 4 velocidade em modo partículas a até 3% do `engine_salto_final`
- [ ] 5 puzzle 30 encontrado em modo partículas (e em modo onda)
- [ ] se havia `ckpt_onda10.txt` de modo onda, foi renomeado antes de iniciar
- [ ] engine antigo parado; `start_onda10.sh` usando `ckpt_onda10.txt`
- [ ] `ckpt_salto.txt` antigo intacto em `~/engine_salto/`
