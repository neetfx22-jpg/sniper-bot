#!/bin/bash
# baixa velas 1h (futuros USDT-M) da data.binance.vision
PARES="BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT BNBUSDT ADAUSDT AVAXUSDT LINKUSDT SUIUSDT LTCUSDT DOTUSDT TRXUSDT NEARUSDT APTUSDT ARBUSDT OPUSDT WLDUSDT ENAUSDT AAVEUSDT"
for p in $PARES; do
  for ym in 2025-01 2025-02 2025-03 2025-04 2025-05 2025-06 2025-07 2025-08 2025-09 2025-10 2025-11 2025-12 2026-01 2026-02 2026-03 2026-04 2026-05 2026-06 2026-07 2026-08 2026-09; do
    for tipo in klines/$p/1h fundingRate/$p; do
      nome=$(basename $tipo)
      [ "$nome" = "1h" ] && f=$p-1h-$ym.zip || f=$p-fundingRate-$ym.zip
      [ -f $f ] || curl -s -f -m 60 -o $f "https://data.binance.vision/data/futures/um/monthly/$tipo/$f" || echo "falta $f"
    done
  done
done
