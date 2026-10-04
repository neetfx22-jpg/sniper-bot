#!/bin/bash
PARES=$(ls ../dados/*-1h-2025-01.zip | xargs -n1 basename | cut -d- -f1)
MESES=""; for y in 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do [ "$y-$m" \> "2026-09" ] && continue; MESES="$MESES $y-$m"; done; done
baixa() { f=$1-5m-$2.zip; [ -f $f ] || curl -s -f -m 90 -o $f "https://data.binance.vision/data/futures/um/monthly/klines/$1/5m/$f" 2>/dev/null; true; }
export -f baixa
for p in $PARES; do for ym in $MESES; do echo "$p $ym"; done; done | xargs -P 16 -n 2 bash -c 'baixa "$0" "$1"'
