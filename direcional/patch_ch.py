"""Aplica os perfis CH e CH10 (balança de choque 1h + saída por tempo) a uma cópia do hydra_direcional_teste.py.
Uso: python3 patch_ch.py ARQUIVO   (grava backup ARQUIVO.bak_ch)"""
import re, shutil, sys

f = sys.argv[1] if len(sys.argv) > 1 else "hydra_ch.py"
s = open(f, encoding="utf-8").read()
if "BALANCA_CHOQUE" in s:
    sys.exit("O perfil CH já está aplicado neste arquivo.")

def troca(a, b, opcional=False):
    global s
    n = s.count(a)
    if n != 1:
        if opcional:
            return
        sys.exit(f"ERRO: trecho não encontrado (achou {n}x). Nada foi alterado.\n{a[:150]}")
    s = s.replace(a, b)

def insere_apos(regex, texto):
    global s
    m = re.search(regex, s, flags=re.M)
    if not m:
        sys.exit(f"ERRO: ponto de inserção não encontrado: {regex}. Nada foi alterado.")
    s = s[:m.end()] + texto + s[m.end():]

PERFIS_CH = '''
    # ── CH / CH10: balança de choque 1h + saída por tempo (validada no simulador fev/2025–set/2026) ──
    "CH": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": False,
           "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True, "TRAVA_ROI": None, "TRAVA_ATR_K": 10.0, "TRAVA_MAX_PCT": 0.08,
           "BALANCA_CHOQUE": True, "CHOQUE_Z": 4.0, "CHOQUE_HORAS": 12, "CHOQUE_VOLUME": True,
           "SAIDA_TEMPO_H": 12, "SEM_TP": True, "REENTRA_CHOQUE": False, "LEV_TETO": 5, "TOP_PARES": 30,
           "FEES_PCT": 0.0001, "TAXA_TAKER": 0.0001, "SLIPPAGE_PCT": 0.0002, "COOLDOWN_TP_MIN": 5,
           "MOM_HORAS": None, "LIVRO_FILTRO": False,
           "NOME": "CH — CHOQUE 1h + SAÍDA 12h (5x, taxa MEXC)"},
    "CH10": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": False,
             "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True, "TRAVA_ROI": None, "TRAVA_ATR_K": 10.0, "TRAVA_MAX_PCT": 0.08,
             "BALANCA_CHOQUE": True, "CHOQUE_Z": 4.0, "CHOQUE_HORAS": 12, "CHOQUE_VOLUME": True,
             "SAIDA_TEMPO_H": 12, "SEM_TP": True, "REENTRA_CHOQUE": False, "LEV_TETO": 10, "TOP_PARES": 30,
             "FEES_PCT": 0.0001, "TAXA_TAKER": 0.0001, "SLIPPAGE_PCT": 0.0002, "COOLDOWN_TP_MIN": 5,
             "MOM_HORAS": None, "LIVRO_FILTRO": False,
             "NOME": "CH10 — CHOQUE 1h + SAÍDA 12h (10x, taxa MEXC)"},'''
insere_apos(r"^PERFIS\s*=\s*\{[^\n]*\n", PERFIS_CH.lstrip("\n") + "\n")

GLOBAIS = '''
# ── balança de CHOQUE (perfis CH/CH10; desligada nos outros) ──
BALANCA_CHOQUE  = False   # True = troca o score antigo pela balança de choque de 1h
CHOQUE_Z        = 4.0     # choque = retorno da última hora fechada > CHOQUE_Z x desvio das últimas 168 horas
CHOQUE_HORAS    = 12      # o choque vale (LONG ou SHORT = 100 pts) durante estas horas
CHOQUE_VOLUME   = True    # exige volume (USDT) da hora do choque >= 2x a média das 24 horas anteriores
SAIDA_TEMPO_H   = None    # fecha a perna depois de N horas (None = desligado)
SEM_TP          = False   # True = sem TP por ATR (sai pelo tempo, pela trava ou pela balança)
REENTRA_CHOQUE  = True    # False = uma entrada por choque: só reentra depois que o sinal apagar
LEV_TETO        = None    # teto de alavancagem (None = máxima do par)
'''
insere_apos(r"^TRAVA_ROI\s*=.*\n", GLOBAIS)
troca("Use --perfil A, B, C, D ou E", "Use --perfil A, B, C, D, E, CH ou CH10", opcional=True)

# teto de alavancagem
troca('''def get_alavancagem_max(client, symbol):
    try:''', '''def get_alavancagem_max(client, symbol):
    alv = _get_alavancagem_max(client, symbol)
    return min(alv, LEV_TETO) if LEV_TETO else alv

def _get_alavancagem_max(client, symbol):
    try:''')
troca('''        for L in sorted({int(b["initialLeverage"]) for b in brs}, reverse=True):
            if permitida(margem * L) >= L:''', '''        for L in sorted({int(b["initialLeverage"]) for b in brs}, reverse=True):
            if LEV_TETO and L > LEV_TETO:
                continue
            if permitida(margem * L) >= L:''')

# balança de choque: entra no início do calcular_score
SCORE_CHOQUE = '''def score_choque(client, symbol):
    """Balança de CHOQUE: (100, 0) se houve choque de alta nas últimas CHOQUE_HORAS horas fechadas,
    (0, 100) se de baixa, (0, 0) se nenhum ou os dois. Choque = retorno da hora > CHOQUE_Z desvios
    (desvio das últimas 168 horas) e, com CHOQUE_VOLUME, volume da hora >= 2x a média das 24 anteriores."""
    kl = _buscar_klines(client, symbol, "1h", 260)
    if not kl or len(kl) < 120:
        return 0, 0
    if USAR_VELA_FECHADA:
        kl = kl[:-1]
    df = pd.DataFrame([k[:12] for k in kl], columns=["time", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tq", "ig"])
    c = df["close"].astype(float); qv = df["qvol"].astype(float)
    r = c.pct_change()
    zz = r / r.rolling(168, min_periods=84).std()
    up, dn = zz > CHOQUE_Z, zz < -CHOQUE_Z
    if CHOQUE_VOLUME:
        forte = qv > 2 * qv.rolling(24, min_periods=12).mean().shift(1)
        up, dn = up & forte, dn & forte
    up, dn = bool(up.iloc[-CHOQUE_HORAS:].any()), bool(dn.iloc[-CHOQUE_HORAS:].any())
    if up and not dn:
        return 100, 0
    if dn and not up:
        return 0, 100
    return 0, 0

'''
m = re.search(r"^def calcular_score\(symbol, dfs, regime, lado, sessao, losses_seguidos\):\n", s, flags=re.M)
if not m:
    sys.exit("ERRO: calcular_score não encontrado. Nada foi alterado.")
s = s[:m.start()] + SCORE_CHOQUE + s[m.start():m.end()] + '''    if BALANCA_CHOQUE:
        _l, _s = score_choque(HYDRA_REF.client, symbol)
        return (_l if lado == "LONG" else _s), {"choque": (_l, _s)}
''' + s[m.end():]

# uma entrada por choque
troca('''    if not fechar_ordem(client, symbol, lado, leg.qty):
        return None
''', '''    if not fechar_ordem(client, symbol, lado, leg.qty):
        return None
    if not REENTRA_CHOQUE:
        h.bloq_choque = True
''')
troca('''    h = hydra.hedges[symbol]
    h.ciclos_reentrada += 1
    h.ultimo_score, h.ultimo_regime, h.ultimo_preco = (sl, ss), regime, preco
    if getattr(h, "conf_estado", None) != h.estado:''', '''    h = hydra.hedges[symbol]
    h.ciclos_reentrada += 1
    h.ultimo_score, h.ultimo_regime, h.ultimo_preco = (sl, ss), regime, preco
    if max(sl, ss) < SCORE_ENTRADA:
        h.bloq_choque = False          # sinal apagou: pode entrar no próximo choque
    if not REENTRA_CHOQUE and getattr(h, "bloq_choque", False) and h.estado in (AGUARDA, CONGELADO):
        return                         # já operou este choque: espera o sinal apagar
    if getattr(h, "conf_estado", None) != h.estado:''')

# sem TP + saída por tempo
troca('''        if roi >= alvo_atr:
            log.info(f"🏆 {symbol} TP ATR''', '''        if not SEM_TP and roi >= alvo_atr:
            log.info(f"🏆 {symbol} TP ATR''')
troca('''        if TRAVA_ATR:
            mov = _mov_contra(lado, leg.preco_entrada, preco)''', '''        if SAIDA_TEMPO_H and time.time() * 1000 - leg.timestamp_ms >= SAIDA_TEMPO_H * 3600 * 1000:
            log.info(f"⏱️ {symbol} SAÍDA POR TEMPO {lado} | {SAIDA_TEMPO_H}h | ROI={roi*100:+.1f}% → fecha a perna")
            _cortar_perna(hydra, h, symbol, lado, f"Tempo {SAIDA_TEMPO_H}h roi={roi*100:.0f}%",
                          regime, (sl if lado == "LONG" else ss), sessao, preco)
            return
        if TRAVA_ATR:
            mov = _mov_contra(lado, leg.preco_entrada, preco)''')

troca('''    print(f"║  Balança virou c/ perna negativa: {'FECHA' if CORTE_SEM_HEDGE else 'HEDGE'}".ljust(53)+"║")''', '''    print(f"║  Balança virou c/ perna negativa: {'FECHA' if CORTE_SEM_HEDGE else 'HEDGE'}".ljust(53)+"║")
    if BALANCA_CHOQUE:
        print(f"║  Balança: CHOQUE 1h >= {CHOQUE_Z} desvios por {CHOQUE_HORAS}h{' + volume 2x' if CHOQUE_VOLUME else ''}".ljust(53)+"║")
        print(f"║  Saída: {SAIDA_TEMPO_H}h | TP: {'NÃO' if SEM_TP else 'SIM'} | alav. máx {LEV_TETO or 'par'}x | taxa {FEES_PCT*100:.2f}%".ljust(53)+"║")''', opcional=True)

compile(s, f, "exec")
shutil.copy(f, f + ".bak_ch")
open(f, "w", encoding="utf-8").write(s)
print(f"OK: perfis CH e CH10 aplicados em {f} (backup em {f}.bak_ch)")
