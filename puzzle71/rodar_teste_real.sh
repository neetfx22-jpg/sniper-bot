#!/usr/bin/env bash
# Roda o engine de verdade contra puzzles ja resolvidos, em 4 estrategias de ordem,
# e grava quantas chaves cada uma testou ate achar. Uso: ./rodar_teste_real.sh BINARIO [PMIN] [PMAX] [THREADS]
set -u
E=${1:?binario do engine}; PMIN=${2:-22}; PMAX=${3:-32}; T=${4:-4}
TMP=$(mktemp -d)
echo "puzzle,estrategia,chaves_testadas,tamanho_faixa,fracao,segundos"
while read -r n k h; do
  [ "$n" -ge "$PMIN" ] && [ "$n" -le "$PMAX" ] || continue
  start=$(python3 -c "print(format(1<<($n-1),'x'))"); end=$(python3 -c "print(format((1<<$n)-1,'x'))")
  for est in sequencial salto onda10 onda20; do
    case $est in
      sequencial) extra="--stride 1";;
      salto) extra="";;
      onda10) extra="--modo onda --franjas 10";;
      onda20) extra="--modo onda --franjas 20";;
    esac
    rm -f "$TMP"/*
    out=$("$E" --threads "$T" --start "$start" --end "$end" --target "$h" $extra \
          --ckpt "$TMP/c" --found "$TMP/f" --status "$TMP/s")
    linha=$(echo "$out" | grep "CHAVE ENCONTRADA")
    achou=$(echo "$linha" | sed -E 's/.*0x([0-9a-f]+).*/\1/')
    [ "$(python3 -c "print(int('$achou',16)==int('$k',16))")" = True ] || { echo "ERRO puzzle $n $est: $linha" >&2; continue; }
    ch=$(echo "$linha" | sed -E 's/.*chaves=([0-9]+).*/\1/'); sec=$(echo "$linha" | sed -E 's/.*tempo_s=([0-9.]+).*/\1/')
    python3 -c "print(f'$n,$est,$ch,{1<<($n-1)},{$ch/(1<<($n-1)):.4f},$sec')"
  done
done < alvos.txt
rm -rf "$TMP"
