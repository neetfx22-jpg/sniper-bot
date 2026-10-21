#!/data/data/com.termux/files/usr/bin/bash
# Dashboard do projeto engine_onda10 (puzzle 71, modo particulas F=10)
# Obs.: em modo particulas o "chunk logico" conta posicoes da fila (inclui janelas puladas no fim);
# o progresso real e "Chaves nesta execucao" somado entre execucoes.
cd "$(dirname "$0")" || exit 1

STATUS="status.txt"
LOG="log_onda10.txt"
FOUND="FOUND.txt"
CKPT="ckpt_onda10.txt"

if [ -f "$FOUND" ] && [ -s "$FOUND" ]; then
    echo "!!! CHAVE ENCONTRADA !!!"
    cat "$FOUND"
    exit 0
fi

if pgrep -f "engine_salto_onda" > /dev/null; then
    STATUS_PROC="RODANDO"
else
    STATUS_PROC="PARADO"
fi

python3 - "$STATUS" "$STATUS_PROC" "$CKPT" <<'EOF'
import sys

status_file, status_proc, ckpt_file = sys.argv[1], sys.argv[2], sys.argv[3]

dados = {}
try:
    with open(status_file) as f:
        for linha in f:
            if "=" in linha:
                k, v = linha.strip().split("=", 1)
                dados[k] = v
except FileNotFoundError:
    pass

chunk_idx = 0
CHUNK_KEYS = 4198400  # fallback, sobrescrito pelo checkpoint se existir
try:
    with open(ckpt_file) as f:
        partes = f.read().split()
        if len(partes) >= 3:
            CHUNK_KEYS = int(partes[1])
            chunk_idx = int(partes[2])
except (FileNotFoundError, ValueError, IndexError):
    pass

TOTAL_CHUNKS = -(-(2**70) // CHUNK_KEYS)  # ceil div, le o tamanho real do chunk do checkpoint

print("=" * 60)
print(" DASHBOARD - PUZZLE 71 (engine_onda10, particulas F=10)")
print("=" * 60)
print(f"Processo              : {status_proc}")
print(f"Chaves nesta execucao  : {int(dados.get('chaves_nesta_execucao', 0)):,}")
print(f"Velocidade             : {float(dados.get('velocidade_chaves_por_s', 0)):,.0f} chaves/s")
print(f"Chunk logico atual     : {int(dados.get('chunk_atual', chunk_idx)):,} / {TOTAL_CHUNKS:,}")
print(f"Progresso do ciclo     : {int(dados.get('chunk_atual', chunk_idx)) / TOTAL_CHUNKS * 100:.10f}%")
print(f"Tempo rodando (sessao) : {float(dados.get('tempo_s', 0))/60:.1f} min")
print("=" * 60)
EOF

echo
echo "--- ultimas linhas do log ---"
tail -n 5 "$LOG" 2>/dev/null
