"""Corrida entre estrategias do engine com chaves NOVAS sorteadas.

Sorteia chaves aleatorias numa faixa pequena, calcula o hash160 de cada uma e roda
o engine de verdade em cada estrategia, anotando a fracao da faixa percorrida ate
achar. Mostra o placar acumulado: media, intervalo de 95% e vitorias.

Uso (Termux ou PC):
    python3 corrida_aleatoria.py ./engine_salto_onda --chaves 100 --bits 26 --threads 8
"""
import argparse
import csv
import math
import os
import random
import re
import statistics
import subprocess
import tempfile

from hash160 import hash160

ESTRATEGIAS = {
    "sequencial": ["--stride", "1"],
    "salto": [],
    "onda10": ["--modo", "onda", "--franjas", "10"],
    "onda20": ["--modo", "onda", "--franjas", "20"],
    "pura10": ["--modo", "onda", "--franjas", "10", "--dentro", "sequencial"],
    "escura10": ["--modo", "onda", "--franjas", "10", "--dentro", "sequencial", "--ordem", "escuras"],
}


def rodar(engine, args, ini, fim, alvo, threads, pasta):
    for nome in ("c", "f", "s"):
        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            os.remove(caminho)
    saida = subprocess.run(
        [engine, "--threads", str(threads), "--start", format(ini, "x"), "--end", format(fim, "x"),
         "--target", alvo, "--ckpt", os.path.join(pasta, "c"), "--found", os.path.join(pasta, "f"),
         "--status", os.path.join(pasta, "s")] + args,
        capture_output=True, text=True, check=True).stdout
    m = re.search(r"CHAVE ENCONTRADA: 0x([0-9a-f]+).*chaves=(\d+)", saida)
    if not m:
        raise RuntimeError("engine nao achou a chave:\n" + saida)
    return int(m.group(1), 16), int(m.group(2))


def placar(res):
    n = len(next(iter(res.values())))
    vit = {e: 0 for e in res}
    for i in range(n):
        vit[min(res, key=lambda e: res[e][i])] += 1
    print(f"\n--- placar apos {n} chaves ---")
    for e, xs in sorted(res.items(), key=lambda kv: statistics.fmean(kv[1])):
        ic = 1.96 * statistics.stdev(xs) / math.sqrt(n) if n > 1 else float("nan")
        print(f"{e:<11} media={statistics.fmean(xs):.3f} (+-{ic:.3f})  vitorias={vit[e]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("engine")
    ap.add_argument("--chaves", type=int, default=100)
    ap.add_argument("--bits", type=int, default=26, help="tamanho da faixa: puzzle de N bits (2^(N-1) chaves)")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--semente", type=int, default=None, help="fixe para repetir exatamente o mesmo sorteio")
    ap.add_argument("--estrategias", default=",".join(ESTRATEGIAS))
    ap.add_argument("--csv", default="corrida_aleatoria.csv")
    a = ap.parse_args()

    rnd = random.Random(a.semente)
    ini, fim = 1 << (a.bits - 1), (1 << a.bits) - 1
    faixa = fim - ini + 1
    ests = a.estrategias.split(",")
    res = {e: [] for e in ests}
    with tempfile.TemporaryDirectory() as pasta, open(a.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chave", "posicao_relativa"] + ests)
        for i in range(a.chaves):
            k = rnd.randint(ini, fim)
            alvo = hash160(k)
            linha = []
            for e in ests:
                achou, testadas = rodar(a.engine, ESTRATEGIAS[e], ini, fim, alvo, a.threads, pasta)
                if achou != k:
                    raise RuntimeError(f"chave errada: {achou:x} != {k:x}")
                res[e].append(testadas / faixa)
                linha.append(f"{testadas / faixa:.4f}")
            w.writerow([format(k, "x"), f"{(k - ini) / faixa:.4f}"] + linha)
            f.flush()
            print(f"chave {i + 1}/{a.chaves} ({(k - ini) / faixa:.0%} da faixa): " +
                  "  ".join(f"{e}={x}" for e, x in zip(ests, linha)), flush=True)
            if (i + 1) % 10 == 0 or i + 1 == a.chaves:
                placar(res)


if __name__ == "__main__":
    main()
