#!/bin/bash
# universo amplo: 45 pares USDT-M, velas 1h + funding, jan/2023–set/2026
PARES="BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT BNBUSDT ADAUSDT AVAXUSDT LINKUSDT SUIUSDT LTCUSDT DOTUSDT TRXUSDT NEARUSDT APTUSDT ARBUSDT OPUSDT WLDUSDT ENAUSDT AAVEUSDT BCHUSDT ETCUSDT FILUSDT ATOMUSDT UNIUSDT INJUSDT TIAUSDT SEIUSDT 1000PEPEUSDT 1000SHIBUSDT 1000BONKUSDT WIFUSDT XLMUSDT HBARUSDT ICPUSDT RUNEUSDT STXUSDT IMXUSDT LDOUSDT CRVUSDT MKRUSDT GALAUSDT SANDUSDT ORDIUSDT TONUSDT"
MESES=""
for y in 2023 2024 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  [ "$y-$m" \> "2026-09" ] && continue; MESES="$MESES $y-$m"; done; done
baixa() { p=$1; ym=$2
  f=$p-1h-$ym.zip; [ -f $f ] || curl -s -f -m 60 -o $f "https://data.binance.vision/data/futures/um/monthly/klines/$p/1h/$f" 2>/dev/null
  f=$p-fundingRate-$ym.zip; [ -f $f ] || curl -s -f -m 60 -o $f "https://data.binance.vision/data/futures/um/monthly/fundingRate/$p/$f" 2>/dev/null
  true; }
export -f baixa
for p in $PARES; do for ym in $MESES; do echo "$p $ym"; done; done | xargs -P 16 -n 2 bash -c 'baixa "$0" "$1"'
