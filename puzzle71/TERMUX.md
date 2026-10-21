# Como testar no Termux

```
tar xzf engine_onda_termux.tar.gz
cd engine_onda
./build_onda.sh                      # compila e roda o selftest (tem que dar 55/55)
```

## 1. Corrida com chaves sorteadas (o teste justo)

Sorteia chaves novas, roda o engine de verdade em todas as estratégias e mostra o placar a cada 10 chaves:

```
python3 corrida_aleatoria.py ./engine_salto_onda --chaves 100 --bits 28 --threads 8
```

- `--bits 28` = faixa de 2^27 chaves (~20 s por estratégia por chave no seu celular). Use 26 para ir mais rápido.
- `--estrategias salto,onda10,onda20` para comparar só algumas.
- O resultado vai para `corrida_aleatoria.csv`.

## 2. Usar no Puzzle 71

Use **um checkpoint separado por modo**:

```
nohup ./engine_salto_onda --threads 8 --modo onda --franjas 10 --ckpt ckpt_onda10.txt --status status.txt > log_onda.txt 2>&1 &
```

Sem `--modo onda`, ele se comporta igual ao `engine_salto_final` (mesmo passo, e usa o seu `ckpt_salto.txt` normalmente).
