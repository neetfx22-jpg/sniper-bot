#!/data/data/com.termux/files/usr/bin/bash
# Inicia o projeto engine_onda10 (Puzzle 71, modo onda F=10) em segundo plano.
cd "$(dirname "$0")" || exit 1
if pgrep -f "engine_salto" > /dev/null; then
    echo "ja existe um engine_salto* rodando; pare antes (rodar dois ao mesmo tempo divide os 8 nucleos):"
    pgrep -af engine_salto
    exit 1
fi
nohup ./engine_salto_onda --threads 8 --modo onda --franjas 10 \
    --ckpt ckpt_onda10.txt --status status.txt --found FOUND.txt > log_onda10.txt 2>&1 &
disown
sleep 2
echo "iniciado, PID:"
pgrep -af engine_salto_onda
head -3 log_onda10.txt
