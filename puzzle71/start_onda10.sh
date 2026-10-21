#!/data/data/com.termux/files/usr/bin/bash
# Inicia o projeto engine_onda10 (Puzzle 71, modo particulas F=10) em segundo plano.
# Particulas: a cada rodada (~5,3 h) dispara janelas de ~1 milhao de chaves em todas as 4096 faixas.
cd "$(dirname "$0")" || exit 1
if pgrep -f "engine_salto" > /dev/null; then
    echo "ja existe um engine_salto* rodando; pare antes (rodar dois ao mesmo tempo divide os 8 nucleos):"
    pgrep -af engine_salto
    exit 1
fi
nohup ./engine_salto_onda --threads 8 --modo particulas --franjas 10 --janela 4 --kmax 100 \
    --ckpt ckpt_onda10.txt --status status.txt --found FOUND.txt > log_onda10.txt 2>&1 &
disown
sleep 2
echo "iniciado, PID:"
pgrep -af engine_salto_onda
head -3 log_onda10.txt
