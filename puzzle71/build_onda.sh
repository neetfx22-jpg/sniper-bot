#!/data/data/com.termux/files/usr/bin/bash
# Compila as duas variantes do engine no Termux e roda o selftest de cada uma.
#   engine_salto_onda     : RIPEMD-160 em 4 vias (NEON), SHA-256 por hardware 1 mensagem por vez
#   engine_salto_onda_x2  : igual, mas com SHA-256 por hardware em 2 mensagens intercaladas
# Use o benchmark das instrucoes para escolher a mais rapida no seu celular.
cd "$(dirname "$0")" || exit 1
FLAGS="-O3 -march=armv8-a+crypto -flto -funroll-loops -pthread"
clang $FLAGS engine_salto_onda.c -o engine_salto_onda -lm || exit 1
clang $FLAGS -DSHA_INTERCALADO engine_salto_onda.c -o engine_salto_onda_x2 -lm || exit 1
for b in engine_salto_onda engine_salto_onda_x2; do
    echo "--- selftest $b ---"
    ./$b --selftest | grep -E "sha256|ripemd|selftest"
done
