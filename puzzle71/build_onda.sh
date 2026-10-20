#!/data/data/com.termux/files/usr/bin/bash
# Compila o engine com o modo onda no Termux (mesmas flags do build_final.sh) e roda o selftest.
cd "$(dirname "$0")" || exit 1
clang -O3 -march=armv8-a+crypto -flto -funroll-loops -pthread engine_salto_onda.c -o engine_salto_onda -lm
echo "--- selftest ---"
./engine_salto_onda --selftest
