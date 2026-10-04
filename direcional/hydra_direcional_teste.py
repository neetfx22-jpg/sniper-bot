"""
🐉🧠 HYDRA CÉREBRO DIRECIONAL — TESTE A/B (CARTEIRA FICTÍCIA)
Mesma lógica do hydra_direcional_real.py (incl. regra 2b e subsídio fora da sequência),
rodando em CARTEIRA FICTÍCIA. Só muda o FILTRO DA BALANÇA conforme o perfil:

    Perfil A = filtros atuais do direcional  (score>=50, dif>=3,  confirma 2, sem memória)
    Perfil B = filtros do Hydra Real          (score>=75, dif>=10, confirma 3, com memória)
    Perfil C = B + TRAVA ATR: fecha a perna quando o preço anda 3x ATR(5m) contra (0,4%–3%), sem hedge
    Perfil D = C + quando a balança vira com a perna negativa, FECHA a perna em vez de abrir hedge
    Perfil E = D, mas a trava é fixa em -50% de ROI (preço = 0,50 / alavancagem) em vez de 3x ATR
    Perfil CH   = balança de CHOQUE de 1h (segue moedas que se moveram >= 4 desvios numa hora, com volume
                  forte), uma entrada por choque, sai depois de 12h; trava só de catástrofe; 5x; taxa MEXC
    Perfil CH10 = CH com 10x

Cada perfil tem carteira, estado, log, ciclos e medição próprios (sufixo _A / _B),
então os dois podem rodar AO MESMO TEMPO em dois terminais.

Dados de mercado: Binance Futures (endpoints públicos).
Chave API (opcional, SÓ LEITURA) em ~/cerebro_teste/config.json: usada apenas para ler a
alavancagem máxima real de cada par (igual ao real). Sem chave: usa LEV_POR_PAR / 20x.
Ordens, posições, TP/STOP, taxas, notional mínimo e liquidação: simulados localmente.

Medição da balança: cada entrada direcional é gravada em hydra_teste_medicao_<P>.jsonl com o
movimento a favor aos 5/15/60 min e o máximo a favor/contra (MFE/MAE) na 1ª hora.

Uso:
    python hydra_direcional_teste.py --perfil A            (continua a carteira do perfil A)
    python hydra_direcional_teste.py --perfil B --reset    (zera o perfil B: 100 USDT)
"""
import os, sys, json, time, logging, threading, requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ─── PERFIL DO TESTE ───────────────────────────────────────
PERFIS = {
    #      score entrada | dif entrada | dif virar | confirmação | memória no score
    "A": {"SCORE_ENTRADA": 50, "DIF_ENTRADA": 3.0,  "DIF_VIRAR": 3.0,  "CONFIRMA_CICLOS": 2, "MEMORIA_NO_SCORE": False,
          "NOME": "A — filtros do DIRECIONAL"},
    "B": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": True,
          "NOME": "B — filtros do HYDRA REAL"},
    # ── FASE 3: filtro B + trava por ATR ──
    "C": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": True,
          "TRAVA_ATR": True, "CORTE_SEM_HEDGE": False,
          "NOME": "C — B + TRAVA ATR"},
    "D": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": True,
          "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True,
          "NOME": "D — B + TRAVA ATR + SEM HEDGE"},
    "E": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": True,
          "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True, "TRAVA_ROI": 0.50,
          "NOME": "E — B + TRAVA -50% ROI + SEM HEDGE"},
    # ── balança de choque 1h + saída por tempo (validada no simulador fev/2025–set/2026) ──
    "CH": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": False,
           "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True, "TRAVA_ATR_K": 10.0, "TRAVA_MAX_PCT": 0.08,
           "BALANCA_CHOQUE": True, "CHOQUE_Z": 4.0, "CHOQUE_HORAS": 12, "CHOQUE_VOLUME": True,
           "SAIDA_TEMPO_H": 12, "SEM_TP": True, "REENTRA_CHOQUE": False, "LEV_TETO": 5, "TOP_PARES": 30,
           "FEES_PCT": 0.0001, "TAXA_TAKER": 0.0001,
           "NOME": "CH — CHOQUE 1h + SAÍDA 12h (5x, taxa MEXC)"},
    "CH10": {"SCORE_ENTRADA": 75, "DIF_ENTRADA": 10.0, "DIF_VIRAR": 10.0, "CONFIRMA_CICLOS": 3, "MEMORIA_NO_SCORE": False,
             "TRAVA_ATR": True, "CORTE_SEM_HEDGE": True, "TRAVA_ATR_K": 10.0, "TRAVA_MAX_PCT": 0.08,
             "BALANCA_CHOQUE": True, "CHOQUE_Z": 4.0, "CHOQUE_HORAS": 12, "CHOQUE_VOLUME": True,
             "SAIDA_TEMPO_H": 12, "SEM_TP": True, "REENTRA_CHOQUE": False, "LEV_TETO": 10, "TOP_PARES": 30,
             "FEES_PCT": 0.0001, "TAXA_TAKER": 0.0001,
             "NOME": "CH10 — CHOQUE 1h + SAÍDA 12h (10x, taxa MEXC)"},
}

# ── FASE 3: trava da perna solta (valores padrão; perfis A/B mantêm desligado) ──
TRAVA_ATR       = False   # True = fecha a perna quando o preço anda TRAVA_ATR_K x ATR(5m) contra
TRAVA_ATR_K     = 3.0     # distância da trava em múltiplos do ATR(5m) da entrada
TRAVA_MIN_PCT   = 0.004   # piso da trava: 0,4% de preço (moedas muito calmas)
TRAVA_MAX_PCT   = 0.030   # teto da trava: 3% de preço (moedas muito voláteis)
CORTE_SEM_HEDGE = False   # True = balança virou com perna negativa -> FECHA a perna (não abre hedge)
TRAVA_ROI       = None    # ex.: 0.50 = trava fixa em -50% de ROI (preço = 0.50 / alavancagem); None = usa o ATR

# ── balança de CHOQUE (perfis CH/CH10; desligada nos outros) ──
BALANCA_CHOQUE  = False   # True = troca o score antigo pela balança de choque de 1h
CHOQUE_Z        = 4.0     # choque = retorno da última hora fechada > CHOQUE_Z x desvio das últimas 168 horas
CHOQUE_HORAS    = 12      # o choque vale (LONG ou SHORT = 100 pts) durante estas horas
CHOQUE_VOLUME   = True    # exige volume (USDT) da hora do choque >= 2x a média das 24 horas anteriores
SAIDA_TEMPO_H   = None    # fecha a perna depois de N horas (None = desligado)
SEM_TP          = False   # True = sem TP por ATR (sai pelo tempo, pela trava ou pela balança)
REENTRA_CHOQUE  = True    # False = uma entrada por choque: só reentra depois que o sinal apagar
LEV_TETO        = None    # teto de alavancagem (None = máxima do par)

def _ler_perfil():
    for i, a in enumerate(sys.argv):
        if a == "--perfil" and i + 1 < len(sys.argv):
            return sys.argv[i + 1].upper()
        if a.startswith("--perfil="):
            return a.split("=", 1)[1].upper()
    return "A"

PERFIL = _ler_perfil()
if PERFIL not in PERFIS:
    print(f"Perfil inválido: {PERFIL}. Use --perfil A, B, C, D, E, CH ou CH10"); sys.exit(1)

# ─── CONFIG ────────────────────────────────────────────────
PASTA       = os.path.expanduser("~/cerebro_teste")
os.makedirs(PASTA, exist_ok=True)
CFG_FILE    = os.path.join(PASTA, "config.json")   # opcional: chave SÓ LEITURA
_SUF        = "_" + PERFIL
LOG_FILE    = os.path.join(PASTA, f"hydra_teste{_SUF}.log")
RES_FILE    = os.path.join(PASTA, f"hydra_teste_resultados{_SUF}.json")
ESTADO_FILE = os.path.join(PASTA, f"hydra_teste_estado{_SUF}.json")
MEM_FILE    = os.path.join(PASTA, f"memoria_teste{_SUF}.json")
SIM_FILE    = os.path.join(PASTA, f"hydra_teste_carteira{_SUF}.json")
MEDICAO_FILE = os.path.join(PASTA, f"hydra_teste_medicao{_SUF}.jsonl")       # medições concluídas (1h)
MEDICAO_PEND = os.path.join(PASTA, f"hydra_teste_medicao_pendente{_SUF}.json")  # medições em andamento

# ─── CARTEIRA FICTÍCIA / SIMULAÇÃO ─────────────────────────
SALDO_INICIAL = 100.0     # saldo da carteira fictícia (USDT)
LEV_PAPER     = 20        # alavancagem máxima simulada por par
LEV_POR_PAR = {   # alavancagem maxima por par (igual ao Real); par fora da lista usa LEV_PAPER
    "BNBUSDT": 75, "BZUSDT": 100, "DOGEUSDT": 75, "ENAUSDT": 75, "ETHUSDT": 150,
    "HYPEUSDT": 75, "KORUUSDT": 25, "LITUSDT": 75, "MOVRUSDT": 25, "MUUSDT": 50,
    "NEARUSDT": 75, "PUMPUSDT": 75, "QNTUSDT": 75, "SKHYNIXUSDT": 50, "SOLUSDT": 100,
    "SOONUSDT": 50, "SOXLUSDT": 50, "SUIUSDT": 75, "WLDUSDT": 75, "XRPUSDT": 100,
}
MMR_FATOR = 0.5   # margem de manutencao ~ 0.5 x margem inicial (1/alavancagem), como na faixa 1 da Binance
SLIPPAGE_PCT  = 0.0002    # derrapagem adversa em ordens a mercado (0.02%)
MMR_PAPER     = 0.005     # taxa de margem de manutenção simulada (liquidação)
WATCH_S       = 2         # segundos entre verificações de TP/STOP/liquidação

# ─── PARÂMETROS ────────────────────────────────────────────
RISCO_PCT          = 0.02
SCORE_ENTRADA      = 50
SCORE_DECISAO      = 50
MIN_ROI            = 0.10   # Exigência mínima de ROI pra soltar uma perna (FILTRO de liberação, piso do alvo adaptativo min_roi_par — NÃO é o TP)
MARGEM_BALANCA     = 3.0    # Diferença de pontos no score para reabrir o hedge (evita ruído)
REDE_SEGURANCA_ROI = 0.30   # Queda de 30% além do ROI âncora para forçar o hedge de segurança
INTERVALO          = 15
COOLDOWN_REENTRADA = 4
FEES_PCT           = 0.0005
TAXA_TAKER         = FEES_PCT
TOP_PARES          = 20
MIN_VOLUME         = 50_000_000
DRAWDOWN_STOP      = 0.15
LOSSES_STOP        = 4
PAUSA_MINUTOS      = 30
SALDO_MINIMO       = 0.20
MAX_HEDGES         = 20      # máx. posições simultâneas (qualquer modo)

# --- MODO DIRECIONAL (confia só na balança; sem TP e sem STOP) ---
DIF_ENTRADA   = 3.0    # diferença mínima L-S para entrar (além do score >= SCORE_ENTRADA)
DIF_VIRAR     = 3.0    # diferença L-S para a balança 'virar' de lado
ROI_MIN_DIR   = 0.10   # ROI minimo da perna p/ fechar e virar (10% cobre as taxas); abaixo disso abre o hedge
MEMORIA_NO_SCORE = False   # False = score sem bônus de memória (balança pura)
TP_ATR_K       = 2.0    # alvo da perna solo = TP_ATR_K x ATR(5m) x alavancagem + taxas
TP_ATR_MIN_ROI = 0.15   # piso do alvo (ROI)
TP_ATR_MAX_ROI = 0.60   # teto do alvo (ROI)
COOLDOWN_TP_MIN = 5     # minutos sem reentrar no par depois do TP por ATR
DESARME_MIN_LUCRO = 0.05   # regra 1: fecha hedge se PnL somado liquido > isso (USDT)
SUBSIDIO_MIN_LUCRO = 0.50  # regra 2: so usa lucro de TP maior que isso (USDT)
SUBSIDIO_FRACAO = 0.70     # regra 2: usa no maximo 70% do lucro para pagar hedges
SUBSIDIO_FRACAO_TOTAL = 0.30   # regra 2b: se o lucro do TP nao cobre o hedge, completa com ate 30% do lucro total realizado
SUBSIDIO_FORA_DA_SEQUENCIA = True   # True = hedge pago/desarmado nao conta na sequencia de losses (evita PAUSA)
RECON_CADA_S       = 60     # reconciliação Binance x estado (segundos)

# --- AJUSTES v1.3 (contabilidade) ---
CICLOS_FILE   = os.path.join(PASTA, f"hydra_teste_ciclos{_SUF}.jsonl")
UNIDADE_CICLO = True    # True = resultado oficial = CICLO completo (W/L, memória, sequência de losses); False = legado por perna
HYDRA_REF     = None

# --- AJUSTES v1.3 (execução/exchange) ---
EXIGIR_ISOLADA  = False   # simulacao em margem CRUZADA (nao exige isolada)
MAX_USO_MARGEM  = 0.80    # (margem inicial total + nova) / patrimônio de margem
MAX_MANUT_RATIO = 0.50    # margem de manutenção / patrimônio de margem
TP_ROI          = 0.15    # TP da perna solta (ROI)
TP_ADAPTATIVO   = False   # True = TP = max(TP_ROI, alvo por ATR); False = TP fixo

# --- AJUSTES v1.3 (dados/sinal) ---
USAR_VELA_FECHADA = True   # True = indicadores só com vela FECHADA
TIMEOUT_TF        = 25      # segundos de espera por cada timeframe
CAP_PRECO         = 60     # teto do grupo correlacionado (tendência+momentum+volatilidade); máx. teórico = 70
MEM_AMOSTRA_MIN   = 10     # trades p/ a memória ter efeito pleno no score

BLACKLIST = {
    "SNDKUSDT","XAUUSDT","XAGUSDT","SPCXUSDT",
    "ZECUSDT","CLUSDT","UNIUSDT",
    "BTCUSDT","DEFIUSDT"
}

# ─── LOGGING ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("HYDRA_CEREBRO")

# ─── ESTADOS ───────────────────────────────────────────────
AGUARDA        = "AGUARDA"
HEDGE_COMPLETO = "HEDGE_COMPLETO"
MEIA_SHORT     = "MEIA_SHORT"
MEIA_LONG      = "MEIA_LONG"
CONGELADO      = "CONGELADO"

# ═════════════════════════════════════════════════════════════
#  CORRETORA FICTÍCIA (substitui a conta real)
# ═════════════════════════════════════════════════════════════

class SimExchange:
    """Hedge mode, margem isolada, taxas, slippage, ordens condicionais (TP/STOP) e liquidação."""

    def __init__(self, mark_fn, saldo_inicial, reset=False):
        self.lk            = threading.RLock()
        self.mark_fn       = mark_fn
        self.marks         = {}     # symbol -> (preco, timestamp)
        self.wallet        = float(saldo_inicial)
        self.saldo_inicial = float(saldo_inicial)
        self.pos           = {}     # (symbol, lado) -> {"amt","entry","lev","ts"}
        self.algo          = {}     # algoId -> ordem condicional
        self.trades        = []
        self.lev           = {}     # symbol -> alavancagem
        self.orders        = {}     # clientOrderId -> ordem
        self.next_id       = 1000
        self.dirty         = False
        if not reset:
            self._carregar()

    # ── persistência ──
    def _carregar(self):
        try:
            if not os.path.exists(SIM_FILE):
                return
            with open(SIM_FILE) as f:
                d = json.load(f)
            self.wallet        = float(d.get("wallet", self.wallet))
            self.saldo_inicial = float(d.get("saldo_inicial", self.saldo_inicial))
            for p in d.get("pos", []):
                self.pos[(p["symbol"], p["lado"])] = {
                    "amt": float(p["amt"]), "entry": float(p["entry"]),
                    "lev": int(p["lev"]), "ts": int(p["ts"])}
            for o in d.get("algo", []):
                self.algo[int(o["algoId"])] = o
            self.trades  = d.get("trades", [])
            self.lev     = {k: int(v) for k, v in d.get("lev", {}).items()}
            self.next_id = int(d.get("next_id", 1000))
            log.info(f"🧪 Carteira fictícia carregada: {self.wallet:.4f} USDT | {len(self.pos)} posição(ões)")
        except Exception as e:
            log.error(f"SimExchange._carregar: {e}")

    def salvar(self):
        with self.lk:
            try:
                d = {
                    "wallet":        round(self.wallet, 8),
                    "saldo_inicial": self.saldo_inicial,
                    "pos": [{"symbol": k[0], "lado": k[1], **v} for k, v in self.pos.items()],
                    "algo":          list(self.algo.values()),
                    "trades":        self.trades[-3000:],
                    "lev":           self.lev,
                    "next_id":       self.next_id,
                    "atualizado":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                tmp = SIM_FILE + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(d, f)
                os.replace(tmp, SIM_FILE)
                self.dirty = False
            except Exception as e:
                log.error(f"SimExchange.salvar: {e}")

    # ── utilidades ──
    def _unreal_cache(self):
        """PnL aberto de todas as posicoes (precos em cache; sem rede)."""
        un = 0.0
        for (s_, l_), p_ in self.pos.items():
            m_ = self.marks.get(s_, (p_["entry"], 0))[0]
            un += (m_ - p_["entry"]) * p_["amt"] if l_ == "LONG" else (p_["entry"] - m_) * p_["amt"]
        return un

    def _novo_id(self):
        self.next_id += 1
        return self.next_id

    def preco(self, sym):
        with self.lk:
            m = self.marks.get(sym)
            if m and time.time() - m[1] < 15:
                return m[0]
        p = None
        try:
            p = self.mark_fn(sym)
        except Exception as e:
            log.warning(f"⚠️ [SIM] preço {sym} indisponível: {e}")
        with self.lk:
            if p:
                self.marks[sym] = (p, time.time())
                return p
            m = self.marks.get(sym)
            if m:
                return m[0]
        raise Exception(f"sem preço de mercado para {sym}")

    def disponivel(self):
        with self.lk:
            return self.wallet + self._unreal_cache() - sum(p["amt"] * p["entry"] / p["lev"] for p in self.pos.values())

    def _cancelar_close(self, sym, lado):
        for aid in list(self.algo.keys()):
            o = self.algo[aid]
            if o["symbol"] == sym and o["positionSide"] == lado and o.get("closePosition"):
                del self.algo[aid]

    # ── execução ──
    def _fill(self, sym, side, lado, qty, mk):
        abre  = (side == "BUY" and lado == "LONG") or (side == "SELL" and lado == "SHORT")
        px    = mk * (1 + SLIPPAGE_PCT) if side == "BUY" else mk * (1 - SLIPPAGE_PCT)
        agora = int(time.time() * 1000)
        oid   = self._novo_id()
        if abre:
            lev      = self.lev.get(sym, LEV_PAPER)
            notional = qty * px
            fee      = notional * TAXA_TAKER
            if self.disponivel() < notional / lev + fee:
                raise Exception("APIError(code=-2019): Margin is insufficient.")
            p = self.pos.get((sym, lado))
            if p:
                novo = p["amt"] + qty
                p["entry"] = (p["entry"] * p["amt"] + px * qty) / novo
                p["amt"]   = round(novo, 12)
                p["ts"]    = agora
            else:
                self.pos[(sym, lado)] = {"amt": round(qty, 12), "entry": px, "lev": lev, "ts": agora}
            self.wallet -= fee
            rpnl = 0.0
        else:
            p = self.pos.get((sym, lado))
            if not p:
                raise Exception("APIError(code=-2022): ReduceOnly Order is rejected.")
            qty  = min(qty, p["amt"])
            fee  = qty * px * TAXA_TAKER
            rpnl = (px - p["entry"]) * qty if lado == "LONG" else (p["entry"] - px) * qty
            self.wallet += rpnl - fee
            restante = round(p["amt"] - qty, 12)
            if restante <= 1e-12:
                del self.pos[(sym, lado)]
                self._cancelar_close(sym, lado)
            else:
                p["amt"] = restante
        trade = {
            "symbol": sym, "id": self._novo_id(), "orderId": oid, "side": side,
            "positionSide": lado, "price": str(px), "qty": str(qty),
            "quoteQty": str(qty * px), "realizedPnl": str(rpnl),
            "commission": str(fee), "commissionAsset": "USDT", "time": agora,
        }
        self.trades.append(trade)
        if len(self.trades) > 6000:
            self.trades = self.trades[-3000:]
        self.dirty = True
        return trade, oid, px

    def check_liq(self, sym, mk):
        """Margem CRUZADA: se patrimonio (saldo + PnL aberto) <= manutencao total, liquida TUDO."""
        if not self.pos:
            return
        manut = 0.0
        for (s_, l_), p_ in self.pos.items():
            m_ = self.marks.get(s_, (p_["entry"], 0))[0]
            manut += p_["amt"] * m_ * (MMR_FATOR / p_["lev"])
        patrimonio = self.wallet + self._unreal_cache()
        if patrimonio > manut:
            return
        log.warning("💥 [SIM] LIQUIDACAO CRUZADA | patrimonio %.4f <= manutencao %.4f — fecha TODAS as posicoes" % (patrimonio, manut))
        for (s_, l_), p_ in list(self.pos.items()):
            m_ = self.marks.get(s_, (p_["entry"], 0))[0]
            rpnl = (m_ - p_["entry"]) * p_["amt"] if l_ == "LONG" else (p_["entry"] - m_) * p_["amt"]
            self.wallet += rpnl
            self.trades.append({
                "symbol": s_, "id": self._novo_id(), "orderId": self._novo_id(),
                "side": "SELL" if l_ == "LONG" else "BUY", "positionSide": l_,
                "price": str(m_), "qty": str(p_["amt"]), "quoteQty": str(p_["amt"] * m_),
                "realizedPnl": str(rpnl), "commission": "0",
                "commissionAsset": "USDT", "time": int(time.time() * 1000),
            })
            del self.pos[(s_, l_)]
        self.wallet = max(0.0, self.wallet - manut)
        self.algo.clear()
        self.dirty = True

    def _check_liq_isolada(self, sym, mk):
        for lado in ("LONG", "SHORT"):
            p = self.pos.get((sym, lado))
            if not p:
                continue
            margem = p["amt"] * p["entry"] / p["lev"]
            un = (mk - p["entry"]) * p["amt"] if lado == "LONG" else (p["entry"] - mk) * p["amt"]
            if margem + un <= p["amt"] * mk * (MMR_FATOR / p["lev"]):
                log.warning(f"💥 [SIM] {sym} {lado} LIQUIDADA @ {mk} (margem perdida {margem:.4f})")
                self.wallet -= margem
                self.trades.append({
                    "symbol": sym, "id": self._novo_id(), "orderId": self._novo_id(),
                    "side": "SELL" if lado == "LONG" else "BUY", "positionSide": lado,
                    "price": str(mk), "qty": str(p["amt"]), "quoteQty": str(p["amt"] * mk),
                    "realizedPnl": str(-margem), "commission": "0",
                    "commissionAsset": "USDT", "time": int(time.time() * 1000),
                })
                del self.pos[(sym, lado)]
                self._cancelar_close(sym, lado)
                self.dirty = True

    def check_triggers(self, sym, mk):
        for aid in list(self.algo.keys()):
            o = self.algo.get(aid)
            if not o or o["symbol"] != sym:
                continue
            stop = o["stopPrice"]
            buy  = o["side"] == "BUY"
            if o["type"] == "STOP_MARKET":
                trig = (mk >= stop) if buy else (mk <= stop)
            else:
                trig = (mk <= stop) if buy else (mk >= stop)
            if not trig:
                continue
            del self.algo[aid]
            self.dirty = True
            try:
                if o.get("closePosition"):
                    p = self.pos.get((sym, o["positionSide"]))
                    if not p:
                        continue
                    self._fill(sym, o["side"], o["positionSide"], p["amt"], mk)
                else:
                    self._fill(sym, o["side"], o["positionSide"], o["qty"], mk)
                log.info(f"🧪 [SIM] {sym} {o['type']} {o['positionSide']} disparada @ {mk}")
            except Exception as e:
                log.warning(f"⚠️ [SIM] {sym} {o['type']} disparou mas falhou: {e}")

    # ── API de ordens ──
    def create_order(self, p):
        sym  = p["symbol"]
        side = p["side"]
        lado = p.get("positionSide", "BOTH")
        tipo = p["type"]
        cid  = p.get("newClientOrderId") or ("sim" + str(int(time.time() * 1000)))
        mk   = self.preco(sym)
        with self.lk:
            if tipo == "MARKET":
                qty = float(p["quantity"])
                if qty <= 0:
                    raise Exception("APIError(code=-1102): quantity invalida")
                trade, oid, px = self._fill(sym, side, lado, qty, mk)
                ordem = {"orderId": oid, "symbol": sym, "status": "FILLED",
                         "clientOrderId": cid, "avgPrice": str(px),
                         "executedQty": trade["qty"], "origQty": trade["qty"],
                         "side": side, "positionSide": lado, "type": "MARKET"}
                self.orders[cid] = ordem
                if len(self.orders) > 300:
                    self.orders.pop(next(iter(self.orders)))
                return dict(ordem)

            if tipo in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
                stop = float(p["stopPrice"])
                cp   = str(p.get("closePosition", "false")).lower() == "true"
                qty  = float(p.get("quantity", 0) or 0)
                if not cp and qty <= 0:
                    raise Exception("APIError(code=-1102): quantity invalida")
                if tipo == "STOP_MARKET":
                    imediato = (mk >= stop) if side == "BUY" else (mk <= stop)
                else:
                    imediato = (mk <= stop) if side == "BUY" else (mk >= stop)
                if imediato:
                    raise Exception("APIError(code=-2021): Order would immediately trigger.")
                if cp:
                    for o in self.algo.values():
                        if (o["symbol"] == sym and o["positionSide"] == lado
                                and o["type"] == tipo and o.get("closePosition")):
                            raise Exception("APIError(code=-4130): An open stop or take profit order with GTE and closePosition in the direction is existing.")
                aid = self._novo_id()
                self.algo[aid] = {
                    "algoId": aid, "orderId": aid, "symbol": sym, "side": side,
                    "positionSide": lado, "type": tipo, "orderType": tipo,
                    "algoType": "CONDITIONAL", "stopPrice": stop, "triggerPrice": stop,
                    "qty": qty, "closePosition": cp, "status": "NEW",
                    "criado": int(time.time() * 1000),
                }
                self.dirty = True
                return dict(self.algo[aid])

            raise Exception(f"APIError(code=-1116): tipo de ordem nao suportado na simulacao: {tipo}")

    def algo_api(self, metodo, caminho, dados):
        with self.lk:
            sym = dados.get("symbol")
            if caminho == "openAlgoOrders" and metodo == "get":
                return [dict(o) for o in self.algo.values() if (not sym or o["symbol"] == sym)]
            if caminho == "algoOpenOrders" and metodo == "delete":
                for aid in list(self.algo.keys()):
                    if not sym or self.algo[aid]["symbol"] == sym:
                        del self.algo[aid]
                self.dirty = True
                return {"code": 200, "msg": "success"}
            if caminho == "algoOrder" and metodo == "delete":
                aid = dados.get("algoId")
                if aid is not None and int(aid) in self.algo:
                    del self.algo[int(aid)]
                    self.dirty = True
                    return {"code": 200, "msg": "success"}
                raise Exception("APIError(code=-2013): Order does not exist.")
            raise Exception(f"APIError(code=-1116): endpoint Algo nao suportado: {metodo} {caminho}")

    # ── consultas de conta ──
    def resumo(self):
        with self.lk:
            syms = {k[0] for k in self.pos}
        px = {}
        for s in syms:
            px[s] = self.preco(s)
        with self.lk:
            margem = un = manut = 0.0
            for (s, lado), p in self.pos.items():
                m = px.get(s, p["entry"])
                margem += p["amt"] * p["entry"] / p["lev"]
                un     += (m - p["entry"]) * p["amt"] if lado == "LONG" else (p["entry"] - m) * p["amt"]
                manut  += p["amt"] * m * (MMR_FATOR / p["lev"])
            return {"wallet": self.wallet, "unreal": un, "margem": margem,
                    "manut": manut, "disp": self.wallet + un - margem}

    def posicoes(self, symbol=None):
        with self.lk:
            syms = [symbol] if symbol else sorted({k[0] for k in self.pos})
        out = []
        for s in syms:
            with self.lk:
                tem = any((s, l) in self.pos for l in ("LONG", "SHORT"))
            pxs = self.preco(s) if tem else None
            with self.lk:
                for lado in ("LONG", "SHORT"):
                    p = self.pos.get((s, lado))
                    if p:
                        un  = (pxs - p["entry"]) * p["amt"] if lado == "LONG" else (p["entry"] - pxs) * p["amt"]
                        amt = p["amt"] if lado == "LONG" else -p["amt"]
                        out.append({"symbol": s, "positionAmt": str(amt), "entryPrice": str(p["entry"]),
                                    "unRealizedProfit": str(un), "positionSide": lado,
                                    "marginType": "cross", "updateTime": p["ts"],
                                    "leverage": str(p["lev"]), "markPrice": str(pxs)})
                    else:
                        out.append({"symbol": s, "positionAmt": "0.0", "entryPrice": "0.0",
                                    "unRealizedProfit": "0.0", "positionSide": lado,
                                    "marginType": "cross", "updateTime": 0,
                                    "leverage": str(self.lev.get(s, LEV_PAPER)), "markPrice": "0.0"})
        return out


class MedidorBalanca:
    """Mede se a balança acertou a direção: movimento do preço a favor da entrada
    aos 5/15/60 min e o máximo a favor (MFE) / contra (MAE) na 1ª hora."""
    MARCOS = (5, 15, 60)

    def __init__(self):
        self.lk = threading.Lock()
        self.pend = []
        self.ult_save = 0.0
        try:
            if os.path.exists(MEDICAO_PEND):
                self.pend = json.load(open(MEDICAO_PEND))
        except Exception as e:
            log.error(f"MedidorBalanca carregar: {e}")

    def registrar(self, symbol, lado, preco, alv, sl, ss, regime, tipo):
        with self.lk:
            self.pend.append({
                "perfil": PERFIL, "symbol": symbol, "lado": lado, "tipo": tipo,
                "preco": float(preco), "alv": int(alv), "sl": sl, "ss": ss,
                "dif": round(abs(sl - ss), 1), "regime": regime,
                "atr_pct": round((ATR_PCT.get(symbol) or 0) * 100, 4),
                "trava_pct": round(((TRAVA_ROI / max(1, int(alv))) if TRAVA_ROI else
                                    min(TRAVA_MAX_PCT, max(TRAVA_MIN_PCT, TRAVA_ATR_K * (ATR_PCT.get(symbol) or 0))))*100, 4),
                "ts": time.time(), "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mfe_pct": 0.0, "mae_pct": 0.0,
            })
            self._salvar(forcar=True)

    def atualizar(self, marks):
        agora = time.time()
        feitos = []
        with self.lk:
            for r in self.pend:
                mk = marks.get(r["symbol"])
                if not mk:
                    continue
                sinal = 1 if r["lado"] == "LONG" else -1
                mov = (mk[0] / r["preco"] - 1) * 100 * sinal   # % de preço a favor da entrada
                r["mfe_pct"] = round(max(r["mfe_pct"], mov), 4)
                r["mae_pct"] = round(min(r["mae_pct"], mov), 4)
                for m in self.MARCOS:
                    k = f"mov_{m}m_pct"
                    if k not in r and agora - r["ts"] >= m * 60:
                        r[k] = round(mov, 4)
                        r[f"roi_{m}m"] = round(mov * r["alv"], 2)
                        r[f"acertou_{m}m"] = mov > 0
                if "mov_60m_pct" in r:
                    r["mfe_roi"] = round(r["mfe_pct"] * r["alv"], 2)
                    r["mae_roi"] = round(r["mae_pct"] * r["alv"], 2)
                    feitos.append(r)
            if feitos:
                try:
                    with open(MEDICAO_FILE, "a", encoding="utf-8") as f:
                        for r in feitos:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    self.pend = [r for r in self.pend if r not in feitos]
                except Exception as e:
                    log.error(f"MedidorBalanca gravar: {e}")
            self._salvar(forcar=bool(feitos))

    def _salvar(self, forcar=False):
        if not forcar and time.time() - self.ult_save < 30:
            return
        try:
            tmp = MEDICAO_PEND + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.pend, f)
            os.replace(tmp, MEDICAO_PEND)
            self.ult_save = time.time()
        except Exception as e:
            log.error(f"MedidorBalanca salvar: {e}")

    def resumo(self):
        """Acerto de direção aos 5/15/60 min sobre as medições concluídas."""
        res = {m: [0, 0] for m in self.MARCOS}
        try:
            if os.path.exists(MEDICAO_FILE):
                for ln in open(MEDICAO_FILE, encoding="utf-8"):
                    r = json.loads(ln)
                    for m in self.MARCOS:
                        if f"acertou_{m}m" in r:
                            res[m][0] += 1 if r[f"acertou_{m}m"] else 0
                            res[m][1] += 1
        except Exception:
            pass
        with self.lk:
            n_pend = len(self.pend)
        return res, n_pend

MEDIDOR = None


class PaperClient(Client):
    """Client da Binance com dados de mercado REAIS (públicos) e conta/ordens FICTÍCIAS."""

    def __init__(self, reset=False):
        key = sec = None
        try:
            _c = json.load(open(CFG_FILE))
            key, sec = _c.get("binance_api_key"), _c.get("binance_api_secret")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Aviso: config.json ilegível ({e}) — seguindo sem chave")
        self._req_lk = threading.Lock()   # antes do super(): o __init__ do Client já faz uma chamada
        super().__init__(key, sec, requests_params={"timeout": 30})
        self._tem_chave = bool(key and sec)
        self._brackets = {}
        self._sim = SimExchange(self._mark_single, SALDO_INICIAL, reset)
        threading.Thread(target=self._watch, daemon=True).start()

    def _request(self, *a, **kw):
        # python-binance guarda a resposta em self.response (atributo compartilhado): com várias
        # threads, uma chamada pode ler a resposta de outra (preço/velas de OUTRO par). Serializa.
        with self._req_lk:
            return super()._request(*a, **kw)

    def _mark_single(self, symbol):
        r = Client.futures_mark_price(self, symbol=symbol)
        if isinstance(r, list):
            r = r[0]
        return float(r["markPrice"])

    def _watch(self):
        """Vigia TP/STOP/liquidação continuamente (como a exchange faria)."""
        while True:
            time.sleep(WATCH_S)
            try:
                todos = Client.futures_mark_price(self)
                if isinstance(todos, dict):
                    todos = [todos]
                agora = time.time()
                sim = self._sim
                with sim.lk:
                    for m in todos:
                        sim.marks[m["symbol"]] = (float(m["markPrice"]), agora)
                    syms = {k[0] for k in sim.pos} | {o["symbol"] for o in sim.algo.values()}
                    for s in syms:
                        mk = sim.marks.get(s)
                        if not mk:
                            continue
                        sim.check_liq(s, mk[0])
                        sim.check_triggers(s, mk[0])
                    if sim.dirty:
                        sim.salvar()
                if MEDIDOR is not None:
                    MEDIDOR.atualizar(sim.marks)
            except Exception as e:
                log.warning(f"⚠️ [SIM] watcher: {e}")
                time.sleep(3)

    # ── endpoints Algo (ordens condicionais) ──
    def _request_futures_api(self, method, path, *args, **kwargs):
        if path in ("openAlgoOrders", "algoOpenOrders", "algoOrder"):
            return self._sim.algo_api(method, path, kwargs.get("data") or {})
        return super()._request_futures_api(method, path, *args, **kwargs)

    # ── conta / posições ──
    def futures_account_balance(self, **kw):
        r = self._sim.resumo()
        return [{"asset": "USDT", "balance": f"{r['wallet']:.8f}",
                 "availableBalance": f"{r['disp']:.8f}",
                 "crossWalletBalance": f"{r['wallet']:.8f}",
                 "crossUnPnl": f"{r['unreal']:.8f}"}]

    def futures_account(self, **kw):
        r = self._sim.resumo()
        return {"totalWalletBalance": f"{r['wallet']:.8f}",
                "totalUnrealizedProfit": f"{r['unreal']:.8f}",
                "totalMarginBalance": f"{r['wallet'] + r['unreal']:.8f}",
                "availableBalance": f"{r['disp']:.8f}",
                "totalInitialMargin": f"{r['margem']:.8f}",
                "totalMaintMargin": f"{r['manut']:.8f}"}

    def futures_position_information(self, **kw):
        return self._sim.posicoes(kw.get("symbol"))

    def futures_get_position_mode(self, **kw):
        return {"dualSidePosition": True}

    def futures_change_position_mode(self, **kw):
        return {"code": 200, "msg": "success"}

    def futures_change_leverage(self, **kw):
        sym = kw["symbol"]
        lev = int(kw["leverage"])
        with self._sim.lk:
            self._sim.lev[sym] = lev
            self._sim.dirty = True
        return {"symbol": sym, "leverage": lev, "maxNotionalValue": "INF"}

    def futures_change_margin_type(self, **kw):
        return {"code": 200, "msg": "success"}

    def futures_leverage_bracket(self, **kw):
        sym = kw.get("symbol", "")
        if self._tem_chave and sym:
            # leitura real (endpoint de conta só-leitura): mesma alavancagem máxima e faixas do real
            if sym not in self._brackets:
                try:
                    self._brackets[sym] = Client.futures_leverage_bracket(self, symbol=sym)
                except Exception as e:
                    log.warning(f"⚠️ [SIM] bracket real {sym} indisponível ({e}) — usando LEV_POR_PAR")
                    self._brackets[sym] = None
            if self._brackets[sym]:
                return self._brackets[sym]
        return [{"symbol": kw.get("symbol", ""),
                 "brackets": [{"bracket": 1, "initialLeverage": LEV_POR_PAR.get(kw.get("symbol", ""), LEV_PAPER),
                               "notionalCap": 10**12, "notionalFloor": 0,
                               "maintMarginRatio": MMR_PAPER, "cum": 0}]}]

    # ── ordens ──
    def futures_create_order(self, **params):
        # igual à Binance: ordem que ABRE posição precisa de notional >= minNotional (-4164)
        if params.get("type") == "MARKET":
            side, lado = params.get("side"), params.get("positionSide", "BOTH")
            abre = (side == "BUY" and lado == "LONG") or (side == "SELL" and lado == "SHORT")
            if abre:
                f = get_filtros(self, params["symbol"]) or {}
                minimo = f.get("min_notional") or 5.0
                notional = float(params["quantity"]) * self._sim.preco(params["symbol"])
                if notional < minimo:
                    raise Exception(f"APIError(code=-4164): Order's notional must be no smaller than {minimo:g} (unless you choose reduce only).")
        return self._sim.create_order(params)

    def futures_get_open_orders(self, **kw):
        return []   # tudo que é condicional vive na API Algo

    def futures_cancel_order(self, **kw):
        return {"code": 200, "msg": "success"}

    def futures_cancel_all_open_orders(self, **kw):
        return {"code": 200, "msg": "The operation of cancel all open order is done."}

    def futures_get_order(self, **kw):
        cid = kw.get("origClientOrderId")
        with self._sim.lk:
            o = self._sim.orders.get(cid)
        if o:
            return dict(o)
        raise Exception("APIError(code=-2013): Order does not exist.")

    def futures_account_trades(self, **kw):
        sym = kw.get("symbol")
        ini = int(kw.get("startTime", 0) or 0)
        with self._sim.lk:
            return [dict(t) for t in self._sim.trades
                    if (not sym or t["symbol"] == sym) and t["time"] >= ini]

    def futures_income_history(self, **kw):
        return []   # funding não é simulado

# ─── CLIENT ────────────────────────────────────────────────
# --- AJUSTES v1.2: confirmacao, fluxo, 1h, alvo por ATR ---
CONFIRMA_CICLOS = 2      # ciclos seguidos p/ soltar/inverter
FLUXO_PTS       = 8      # pontos do fluxo comprador/vendedor
H1_PTS          = 6      # pontos do filtro de tendencia 1h
ATR_K           = 1.0    # alvo de soltura = ATR_K x ATR(5m) + taxa ida/volta
ROI_MAX_SOLTA   = 0.60   # teto do alvo de soltura (ROI)
TRAIL_MINIMO    = 0.10   # minimo de melhora no ROI para mover o STOP rebalance
ATR_PCT         = {}

def confirmado(h, chave, cond):
    """True so quando cond se mantem por CONFIRMA_CICLOS ciclos seguidos"""
    conf = getattr(h, "conf", None)
    if conf is None:
        conf = h.conf = {}
    conf[chave] = (conf.get(chave, 0) + 1) if cond else 0
    return conf[chave] >= CONFIRMA_CICLOS

def min_roi_par(symbol, alv):
    atr = ATR_PCT.get(symbol)
    if not atr or atr != atr:
        return MIN_ROI
    alvo = ATR_K * atr * alv + 2 * FEES_PCT * alv
    return min(ROI_MAX_SOLTA, max(MIN_ROI, alvo))

def _painel_liquido(hydra):
    try:
        pos = hydra.client.futures_position_information()
        aberto = sum(float(p["unRealizedProfit"]) for p in pos)
        pat = hydra.banca_total() + aberto
        print("║" + f"  PnL aberto: {aberto:+.4f}  Patrimônio: {pat:.4f} USDT".ljust(68) + "║")
    except Exception as e:
        logging.error(f"painel_liquido: {e}")

def get_client(reset=False):
    client = PaperClient(reset=reset)
    adapter = requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40)
    client.session.mount("https://", adapter)
    return client

# ═════════════════════════════════════════════════════════════
#  BLOCO 1 — PERCEPÇÃO E DECISÃO
# ═════════════════════════════════════════════════════════════

def get_sessao():
    h = datetime.now(timezone.utc).hour
    if 13 <= h < 17:
        return "OVERLAP"
    if 13 <= h < 22:
        return "NEWYORK"
    if 8 <= h < 17:
        return "LONDON"
    if 2 <= h < 9:
        return "ASIA"
    return "FORA"

# --- FIX rede: retry com backoff + limite de requisicoes simultaneas de klines ---
_SEM_KLINES = threading.Semaphore(8)

_CACHE_KLINES = {}
_CACHE_LK     = threading.Lock()

def _buscar_klines(client, symbol, interval, limit, tentativas=4):
    """Com USAR_VELA_FECHADA as velas fechadas só mudam quando a vela em formação fecha:
    reaproveita o download até esse instante (mesmos dados, ~20x menos peso na API)."""
    chave = (symbol, interval, limit)
    if USAR_VELA_FECHADA:
        with _CACHE_LK:
            c = _CACHE_KLINES.get(chave)
        if c and time.time() * 1000 < c[0]:
            return c[1]
    kl = _buscar_klines_api(client, symbol, interval, limit, tentativas)
    if USAR_VELA_FECHADA and kl:
        try:
            valido_ate = int(kl[-1][6]) + 1500   # fechamento da vela em formação + 1,5 s
            with _CACHE_LK:
                _CACHE_KLINES[chave] = (valido_ate, kl)
        except Exception:
            pass
    return kl

def _buscar_klines_api(client, symbol, interval, limit, tentativas=4):
    ultimo = None
    for i in range(tentativas):
        try:
            with _SEM_KLINES:
                return client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        except BinanceAPIException as e:
            ultimo = e
            if e.code in (-1003, -1015) or getattr(e, "status_code", 0) in (418, 429):
                time.sleep(2 ** (i + 1))
                continue
            raise
        except Exception as e:
            ultimo = e
            time.sleep(min(8.0, 0.5 * (2 ** i)) + float(np.random.random()) * 0.5)
    raise ultimo

def get_dados(client, symbol, interval, limit=200):
    try:
        klines = _buscar_klines(client, symbol, interval, limit + 1)
        if USAR_VELA_FECHADA:
            klines = klines[:-1]   # descarta a vela em formação
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","vol",
            "ct","qvol","n","tb","tq","ig"
        ])
        for col in ["open","high","low","close","vol","tb"]:
            df[col] = df[col].astype(float)
        df["buy_ratio"] = (df["tb"] / df["vol"].replace(0, np.nan)).rolling(3).mean()

        df["ema9"]   = df["close"].ewm(span=9,   adjust=False).mean()
        df["ema21"]  = df["close"].ewm(span=21,  adjust=False).mean()
        df["ema50"]  = df["close"].ewm(span=50,  adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        delta = df["close"].diff()
        gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        ema12      = df["close"].ewm(span=12, adjust=False).mean()
        ema26      = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["sig"]  = df["macd"].ewm(span=9, adjust=False).mean()
        df["hist"] = df["macd"] - df["sig"]

        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"]  - df["close"].shift(1))
            )
        )
        df["atr"]    = df["tr"].ewm(span=14, adjust=False).mean()
        df["atr_ma"] = df["atr"].rolling(20).mean()

        df["vol_ma"]  = df["vol"].rolling(20).mean()
        df["vol_rat"] = df["vol"] / df["vol_ma"].replace(0, np.nan)

        df["bb_mid"] = df["close"].rolling(20).mean()
        bb_std       = df["close"].rolling(20).std()
        df["bb_up"]  = df["bb_mid"] + 2 * bb_std
        df["bb_dn"]  = df["bb_mid"] - 2 * bb_std
        df["bb_wid"] = (df["bb_up"] - df["bb_dn"]) / df["bb_mid"]
        df["bb_wid_ma"] = df["bb_wid"].rolling(20).mean()

        low14  = df["low"].rolling(14).min()
        high14 = df["high"].rolling(14).max()
        df["stoch"] = 100 * (df["close"] - low14) / (high14 - low14).replace(0, np.nan)

        return df
    except Exception as e:
        logging.error(f"get_dados {symbol} {interval}: {e}")
        return None

def _sincronizado(dfs):
    """5m/15m/1h precisam representar o mesmo instante (última vela fechada de cada TF)."""
    if not USAR_VELA_FECHADA:
        return True
    try:
        f5  = int(dfs['5m'].iloc[-1]["time"])  + 5 * 60_000
        f15 = int(dfs['15m'].iloc[-1]["time"]) + 15 * 60_000
        f1h = int(dfs['1h'].iloc[-1]["time"])  + 60 * 60_000
        return 0 <= f5 - f15 < 15 * 60_000 and 0 <= f5 - f1h < 60 * 60_000
    except Exception:
        return False

def percepcao_multi(client, symbol):
    """dfs["_ok"]=True só se os 3 TFs vieram completos e sincronizados."""
    resultados = {}
    for _tent in range(2):
        resultados = {}
        def ler(tf, dest):
            dest[tf] = get_dados(client, symbol, tf, 500 if tf == '1h' else 200)
        threads = []
        for tf in ['5m', '15m', '1h']:
            t = threading.Thread(target=ler, args=(tf, resultados))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=TIMEOUT_TF)
        completo = (all(not t.is_alive() for t in threads)
                    and all(resultados.get(tf) is not None for tf in ['5m', '15m', '1h']))
        if completo and _sincronizado(resultados):
            resultados["_ok"] = True
            return resultados
    resultados["_ok"] = False
    return resultados

def detectar_regime(dfs):
    try:
        df5  = dfs.get('5m')
        df15 = dfs.get('15m')
        if df5 is None or df15 is None:
            return "DESCONHECIDO"

        r5  = df5.iloc[-1]
        r15 = df15.iloc[-1]

        if r5["vol_rat"] > 3.5:
            return "CAOS"
        wick  = abs(r5["high"] - r5["low"])
        corpo = abs(r5["close"] - r5["open"])
        if corpo > 0 and wick / corpo > 4:
            return "CAOS"
        var_pct = abs(r5["close"] - df5.iloc[-2]["close"]) / df5.iloc[-2]["close"] * 100
        if var_pct > 3:
            return "CAOS"

        bull = 0
        if r5["close"] > r5["ema200"]:  bull += 2
        if r5["ema9"] > r5["ema21"]:    bull += 1
        if r5["ema21"] > r5["ema50"]:   bull += 1
        if r15["ema9"] > r15["ema21"]:  bull += 1
        if r5["rsi"] > 50:              bull += 1
        if r15["rsi"] > 50:             bull += 1
        if r5["hist"] > 0:              bull += 1

        bear = 0
        if r5["close"] < r5["ema200"]:  bear += 2
        if r5["ema9"] < r5["ema21"]:    bear += 1
        if r5["ema21"] < r5["ema50"]:   bear += 1
        if r15["ema9"] < r15["ema21"]:  bear += 1
        if r5["rsi"] < 50:              bear += 1
        if r15["rsi"] < 50:             bear += 1
        if r5["hist"] < 0:              bear += 1

        emas_proximas = abs(r5["ema9"] - r5["ema21"]) / r5["close"] < 0.001
        rsi_neutro    = 40 < r5["rsi"] < 60

        if emas_proximas and rsi_neutro:
            return "RANGE"
        if bull >= 6:
            return "BULL_FORTE"
        if bear >= 6:
            return "BEAR_FORTE"
        if bull >= 4:
            return "BULL"
        if bear >= 4:
            return "BEAR"
        return "RANGE"

    except Exception as e:
        logging.error(f"detectar_regime: {e}")
        return "DESCONHECIDO"

# ─── MEMÓRIA ───────────────────────────────────────────────
memoria = {"trades": [], "stats": {}}

def salvar_memoria():
    try:
        with open(MEM_FILE, 'w') as f:
            json.dump(memoria, f, indent=2)
    except Exception as e:
        logging.error(f"salvar_memoria: {e}")

def carregar_memoria():
    global memoria
    try:
        if os.path.exists(MEM_FILE):
            with open(MEM_FILE) as f:
                memoria = json.load(f)
    except:
        memoria = {"trades": [], "stats": {}}

def registar_trade_memoria(sym, lado, regime, score, sessao, entrada, saida,
                            pnl, duracao_min, resultado):
    trade = {
        "par":          sym,
        "lado":         lado,
        "regime":       regime,
        "score":        score,
        "sessao":       sessao,
        "entrada":      entrada,
        "saida":        saida,
        "pnl":          pnl,
        "mfe":          0.0,
        "mae":          0.0,
        "duracao_min":  duracao_min,
        "resultado":    resultado,
        "hora":         datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    memoria["trades"].append(trade)
    if len(memoria["trades"]) > 500:
        memoria["trades"] = memoria["trades"][-500:]
    analisar_memoria()
    salvar_memoria()

def analisar_memoria():
    trades = memoria["trades"]
    if len(trades) < 10:
        return
    ultimos = trades[-20:]
    wins    = sum(1 for t in ultimos if t["resultado"] == "WIN")
    wr      = wins / len(ultimos) * 100
    por_par = {}
    for t in trades[-50:]:
        p = t["par"]
        if p not in por_par:
            por_par[p] = {"w": 0, "l": 0}
        if t["resultado"] == "WIN":
            por_par[p]["w"] += 1
        else:
            por_par[p]["l"] += 1
    por_regime = {}
    for t in trades[-50:]:
        r = t["regime"]
        if r not in por_regime:
            por_regime[r] = {"w": 0, "l": 0}
        if t["resultado"] == "WIN":
            por_regime[r]["w"] += 1
        else:
            por_regime[r]["l"] += 1
    memoria["stats"] = {
        "win_rate_20":  round(wr, 1),
        "total_trades": len(trades),
        "por_par":      por_par,
        "por_regime":   por_regime,
        "actualizado":  datetime.now().strftime("%H:%M:%S"),
    }

def wr_para_par(sym):
    trades = [t for t in memoria["trades"][-30:] if t["par"] == sym]
    if len(trades) < 3:
        return 50.0
    wins = sum(1 for t in trades if t["resultado"] == "WIN")
    return wins / len(trades) * 100

def score_memoria(sym, regime):
    n_par = len([t for t in memoria["trades"][-30:] if t["par"] == sym])
    wr    = wr_para_par(sym)
    pr    = memoria.get("stats", {}).get("por_regime", {})
    reg   = pr.get(regime, {"w": 0, "l": 0})
    total = reg["w"] + reg["l"]
    wr_reg = (reg["w"] / total * 100) if total > 3 else 50.0
    s_par = 0
    if wr > 65:
        s_par = 10
    elif wr >= 55:
        s_par = 5
    elif wr < 40:
        s_par = -10
    s_reg = 0
    if wr_reg > 60:
        s_reg = 5
    elif wr_reg < 40:
        s_reg = -5
    # efeito proporcional ao tamanho da amostra (evita overfitting com poucos trades)
    return int(round(s_par * min(1.0, n_par / MEM_AMOSTRA_MIN) + s_reg * min(1.0, total / MEM_AMOSTRA_MIN)))

def calcular_score(symbol, dfs, regime, lado, sessao, losses_seguidos):
    score = 0
    detalhes = {}

    try:
        df1  = dfs.get('1m')
        df5  = dfs.get('5m')
        df15 = dfs.get('15m')
        df1h = dfs.get('1h')
        if df5 is None or df15 is None:
            return 0, {}

        r5  = df5.iloc[-1]
        r5b = df5.iloc[-2]
        r15 = df15.iloc[-1]

        long = lado == "LONG"

        t_score = 0
        if long:
            if r5["ema9"] > r5["ema21"] > r5["ema50"]:  t_score += 15
            elif r5["ema9"] > r5["ema21"]:               t_score += 8
            if r15["ema9"] > r15["ema21"]:               t_score += 10
            if r5["close"] > r5["ema200"]:               t_score += 5
        else:
            if r5["ema9"] < r5["ema21"] < r5["ema50"]:  t_score += 15
            elif r5["ema9"] < r5["ema21"]:               t_score += 8
            if r15["ema9"] < r15["ema21"]:               t_score += 10
            if r5["close"] < r5["ema200"]:               t_score += 5
        score += t_score
        detalhes["tendencia"] = t_score

        m_score = 0
        rsi = r5["rsi"]
        if long:
            if 45 <= rsi <= 65:                          m_score += 10
            elif 40 <= rsi < 45 or 65 < rsi <= 70:      m_score += 5
            if r5["hist"] > 0 and r5b["hist"] > 0:      m_score += 10
            elif r5["hist"] > 0:                         m_score += 5
            if r5["stoch"] < 70:                         m_score += 5
        else:
            if 35 <= rsi <= 55:                          m_score += 10
            elif 30 <= rsi < 35 or 55 < rsi <= 60:      m_score += 5
            if r5["hist"] < 0 and r5b["hist"] < 0:      m_score += 10
            elif r5["hist"] < 0:                         m_score += 5
            if r5["stoch"] > 30:                         m_score += 5
        score += m_score
        detalhes["momentum"] = m_score

        v_score = 0
        if r5["vol_rat"] >= 1.5:                         v_score += 10
        elif r5["vol_rat"] >= 1.2:                       v_score += 6
        elif r5["vol_rat"] >= 1.0:                       v_score += 3
        if r15["vol_rat"] >= 1.2:                        v_score += 10
        elif r15["vol_rat"] >= 1.0:                      v_score += 5
        score += v_score
        detalhes["volume"] = v_score

        f_score = 0
        br = r5.get("buy_ratio", np.nan)
        if pd.notna(br):
            if long:
                if br > 0.55:   f_score += FLUXO_PTS
                elif br < 0.45: f_score -= FLUXO_PTS
            else:
                if br < 0.45:   f_score += FLUXO_PTS
                elif br > 0.55: f_score -= FLUXO_PTS
        score += f_score
        detalhes["fluxo"] = f_score

        h_score = 0
        if df1h is not None and len(df1h) >= 200:
            r1h = df1h.iloc[-1]
            up = r1h["ema9"] > r1h["ema21"] and r1h["close"] > r1h["ema200"]
            dn = r1h["ema9"] < r1h["ema21"] and r1h["close"] < r1h["ema200"]
            if long:
                if up:   h_score += H1_PTS
                elif dn: h_score -= H1_PTS
            else:
                if dn:   h_score += H1_PTS
                elif up: h_score -= H1_PTS
        score += h_score
        detalhes["tf1h"] = h_score

        a_score = 0
        atr_ok = r5["atr"] > r5["atr_ma"] * 0.8
        _bwm   = r5.get("bb_wid_ma", np.nan)
        bb_ok  = (r5["bb_wid"] > _bwm * 0.5) if (pd.notna(_bwm) and _bwm > 0) else True
        if atr_ok:   a_score += 8
        if bb_ok:    a_score += 7
        score += a_score
        detalhes["volatilidade"] = a_score

        # indicadores de preço correlacionados: limita a soma p/ não contar a mesma informação várias vezes
        _exc = (t_score + m_score + a_score) - CAP_PRECO
        if _exc > 0:
            score -= _exc
            detalhes["cap_correlacao"] = -_exc

        mem_score = score_memoria(symbol, regime) if MEMORIA_NO_SCORE else 0
        score += mem_score
        detalhes["memoria"] = mem_score

        s_bonus = 0
        if sessao == "OVERLAP":   s_bonus = +5
        elif sessao == "LONDON":  s_bonus = +3
        elif sessao == "NEWYORK": s_bonus = +2
        elif sessao == "ASIA":    s_bonus = -5
        elif sessao == "FORA":    s_bonus = -10
        score += s_bonus
        detalhes["sessao"] = s_bonus

        penalidade = 0
        if regime == "RANGE":       penalidade -= 10
        if losses_seguidos >= 3: penalidade -= 15
        if losses_seguidos >= LOSSES_STOP: penalidade -= 999

        if long and regime in ("BEAR", "BEAR_FORTE"): penalidade -= 20
        if not long and regime in ("BULL", "BULL_FORTE"): penalidade -= 20

        score += penalidade
        detalhes["penalidade"] = penalidade

        score = max(0, min(100, score))
        return score, detalhes

    except Exception as e:
        logging.error(f"calcular_score {symbol}: {e}")
        return 0, {}

def score_choque(client, symbol):
    """Balança de CHOQUE: (100, 0) se houve choque de alta nas últimas CHOQUE_HORAS horas fechadas,
    (0, 100) se de baixa, (0, 0) se nenhum ou os dois. Choque = retorno da hora > CHOQUE_Z desvios
    (desvio das últimas 168 horas) e, com CHOQUE_VOLUME, volume da hora >= 2x a média das 24 anteriores."""
    kl = _buscar_klines(client, symbol, "1h", 260)
    if not kl or len(kl) < 120:
        return 0, 0
    if USAR_VELA_FECHADA:
        kl = kl[:-1]
    df = pd.DataFrame(kl, columns=["time", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tq", "ig"])
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

def get_score_par(client, symbol, sessao, losses_seguidos):
    dfs = percepcao_multi(client, symbol)
    if not dfs.get("_ok"):
        return None   # dados incompletos/dessincronizados: sem decisão neste ciclo
    regime = detectar_regime(dfs)
    try:
        _r5 = dfs['5m'].iloc[-1]
        ATR_PCT[symbol] = float(_r5["atr"] / _r5["close"])
    except Exception:
        pass
    if BALANCA_CHOQUE:
        sl, ss = score_choque(client, symbol)
        return sl, ss, regime
    sl, _ = calcular_score(symbol, dfs, regime, "LONG",  sessao, losses_seguidos)
    ss, _ = calcular_score(symbol, dfs, regime, "SHORT", sessao, losses_seguidos)
    return sl, ss, regime


# ═════════════════════════════════════════════════════════════
#  BLOCO 2 — EXECUÇÃO E GESTÃO
# ═════════════════════════════════════════════════════════════

_ULTIMA_BANCA = {"v": None}
FILTROS      = {}   # symbol -> filtros do exchange
ULTIMA_FECHA = {}   # (symbol, lado) -> orderId da última ordem de fechamento
ULTIMO_DET   = {}   # (symbol, lado) -> detalhe do último PnL calculado

def api_retry(fn, *a, tentativas=3, **kw):
    """Repete chamadas de LEITURA em rate limit / timestamp / rede (nunca p/ criar ordem)."""
    ultimo = None
    for i in range(tentativas):
        try:
            return fn(*a, **kw)
        except BinanceAPIException as e:
            ultimo = e
            if e.code in (-1003, -1015) or getattr(e, "status_code", 0) in (418, 429):
                espera = 2 ** (i + 1)
                log.warning(f"⏳ rate limit ({e.code}) — aguardando {espera}s")
                time.sleep(espera)
                continue
            if e.code == -1021:
                time.sleep(1)
                continue
            raise
        except Exception as e:
            ultimo = e
            time.sleep(1 + i)
    raise ultimo

def get_banca_real(client):
    try:
        for b in api_retry(client.futures_account_balance):
            if b["asset"] == "USDT":
                return float(b["availableBalance"])
    except Exception as e:
        log.error(f"Erro banca: {e}")
    return 0.0

def get_banca_total(client):
    """Se a API falhar devolve o último valor BOM (nunca 0.0 falso)."""
    try:
        for b in api_retry(client.futures_account_balance):
            if b["asset"] == "USDT":
                _ULTIMA_BANCA["v"] = float(b["balance"])
                return _ULTIMA_BANCA["v"]
    except Exception as e:
        log.error(f"Erro banca_total: {e}")
    return _ULTIMA_BANCA["v"] if _ULTIMA_BANCA["v"] is not None else 0.0

def get_alavancagem_max(client, symbol):
    alv = _get_alavancagem_max(client, symbol)
    return min(alv, LEV_TETO) if LEV_TETO else alv

def _get_alavancagem_max(client, symbol):
    try:
        brackets = client.futures_leverage_bracket(symbol=symbol)
        if brackets and len(brackets) > 0:
            b = brackets[0]
            if "brackets" in b and len(b["brackets"]) > 0:
                return int(b["brackets"][0]["initialLeverage"])
    except:
        pass
    if "BTC" in symbol or "ETH" in symbol: return 20
    elif any(x in symbol for x in ["BNB","SOL","XRP","ADA","DOGE"]): return 20
    return 20

def alavancagem_para_notional(client, symbol, margem):
    """Maior L tal que a faixa (bracket) do notional REAL (margem*L) ainda permita L."""
    try:
        info = api_retry(client.futures_leverage_bracket, symbol=symbol)
        brs = info[0]["brackets"] if isinstance(info, list) else info["brackets"]
        brs = sorted(brs, key=lambda b: float(b["notionalFloor"]))
        def permitida(n):
            for b in brs:
                if float(b["notionalFloor"]) <= n <= float(b["notionalCap"]):
                    return int(b["initialLeverage"])
            return int(brs[-1]["initialLeverage"])
        for L in sorted({int(b["initialLeverage"]) for b in brs}, reverse=True):
            if LEV_TETO and L > LEV_TETO:
                continue
            if permitida(margem * L) >= L:
                return L
        return int(brs[-1]["initialLeverage"])
    except Exception as e:
        log.error(f"alavancagem_para_notional {symbol}: {e}")
        return None

def set_alavancagem(client, symbol, alavancagem):
    """True só se a Binance CONFIRMAR a alavancagem pedida."""
    try:
        r = client.futures_change_leverage(symbol=symbol, leverage=alavancagem)
        if int(r.get("leverage", alavancagem)) != int(alavancagem):
            log.error(f"❌ {symbol} leverage pedida {alavancagem}x, Binance devolveu {r.get('leverage')}x")
            return False
        log.info(f"⚡ {symbol} alavancagem {alavancagem}x definida")
        return True
    except Exception as e:
        log.error(f"Erro set_leverage {symbol}: {e}")
        return False

def set_margem_isolada(client, symbol):
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except BinanceAPIException as e:
        if "No need to change margin type" not in str(e):
            log.error(f"Erro margem {symbol}: {e}")

def garantir_margem_isolada(client, symbol):
    if not EXIGIR_ISOLADA:
        return True
    set_margem_isolada(client, symbol)
    try:
        for p in api_retry(client.futures_position_information, symbol=symbol):
            mt = p.get("marginType")
            if mt and str(mt).lower() != "isolated":
                log.error(f"❌ {symbol} margem NÃO está ISOLATED — não abre")
                return False
        return True
    except Exception as e:
        log.error(f"garantir_margem_isolada {symbol}: {e}")
        return False

def verificar_hedge_mode(client):
    """positionSide LONG/SHORT só funciona em Hedge Mode (dualSidePosition)."""
    try:
        r = client.futures_get_position_mode()
        if str(r.get("dualSidePosition")).lower() == "true":
            return True
        log.warning("⚠️ Conta em One-way — tentando ativar Hedge Mode")
        client.futures_change_position_mode(dualSidePosition="true")
        r = client.futures_get_position_mode()
        return str(r.get("dualSidePosition")).lower() == "true"
    except Exception as e:
        log.error(f"❌ verificar_hedge_mode: {e}")
        return False

def get_filtros(client, symbol):
    f = FILTROS.get(symbol)
    if f:
        return f
    try:
        info = api_retry(client.futures_exchange_info)
        for s in info["symbols"]:
            fl = {"step": None, "tick": None, "min_qty": 0.0,
                  "max_qty": float("inf"), "min_notional": 0.0}
            for x in s["filters"]:
                t = x["filterType"]
                if t == "LOT_SIZE":
                    fl["step"]    = float(x["stepSize"])
                    fl["min_qty"] = float(x["minQty"])
                elif t == "MARKET_LOT_SIZE":
                    if float(x["maxQty"]) > 0:
                        fl["max_qty"] = float(x["maxQty"])
                elif t == "PRICE_FILTER":
                    fl["tick"] = float(x["tickSize"])
                elif t == "MIN_NOTIONAL":
                    fl["min_notional"] = float(x.get("notional", x.get("minNotional", 0)))
            FILTROS[s["symbol"]] = fl
    except Exception as e:
        log.error(f"get_filtros: {e}")
    return FILTROS.get(symbol)

def get_step_size(client, symbol):
    f = get_filtros(client, symbol)
    return f["step"] if f else None

def get_tick_size(client, symbol):
    f = get_filtros(client, symbol)
    return f["tick"] if f else None

def validar_ordem(client, symbol, qty, preco):
    """stepSize / minQty / maxQty / minNotional / tickSize do símbolo."""
    f = get_filtros(client, symbol)
    if not f or not f["step"] or not f["tick"]:
        return False, "filtros do símbolo indisponíveis"
    if qty < f["min_qty"]:
        return False, f"qty {qty} < minQty {f['min_qty']}"
    if qty > f["max_qty"]:
        return False, f"qty {qty} > maxQty {f['max_qty']}"
    if qty * preco < f["min_notional"]:
        return False, f"notional {qty * preco:.4f} < minNotional {f['min_notional']}"
    return True, ""

def margem_ok(hydra, symbol, margem_nova):
    """Recusa abrir perna nova se a margem/risco da CONTA passar dos limites."""
    try:
        ac    = api_retry(hydra.client.futures_account)
        eq    = float(ac["totalMarginBalance"])
        disp  = float(ac["availableBalance"])
        usada = float(ac["totalInitialMargin"])
        manut = float(ac["totalMaintMargin"])
        if eq <= 0:
            return False
        if disp < margem_nova * 1.1:
            log.warning(f"⛔ {symbol} margem: disponível {disp:.4f} < necessário {margem_nova * 1.1:.4f}")
            return False
        if (usada + margem_nova) / eq > MAX_USO_MARGEM:
            log.warning(f"⛔ {symbol} margem: uso {(usada + margem_nova) / eq * 100:.0f}% > {MAX_USO_MARGEM * 100:.0f}%")
            return False
        if manut / eq > MAX_MANUT_RATIO:
            log.warning(f"⛔ {symbol} margem: manutenção {manut / eq * 100:.0f}% > {MAX_MANUT_RATIO * 100:.0f}%")
            return False
        return True
    except Exception as e:
        log.error(f"❌ margem_ok {symbol}: {e}")
        return False

def cancelar_tp(client, symbol):
    cancelar_algo(client, symbol)
    try:
        ordens = client.futures_get_open_orders(symbol=symbol)
        for o in ordens:
            if o["type"] in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT"):
                client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
                log.info(f"🗑️ TP cancelado {symbol} orderId={o['orderId']}")
        time.sleep(0.3)
    except Exception as e:
        log.error(f"❌ Erro cancelar_tp {symbol}: {e}")


def _algo_req(client, metodo, caminho, **dados):
    """Chama endpoint Algo (ordens condicionais) da Binance Futures."""
    if metodo == "get":
        return api_retry(client._request_futures_api, metodo, caminho, True, data=dados)
    return client._request_futures_api(metodo, caminho, True, data=dados)


def listar_algo(client, symbol):
    """Ordens condicionais (Algo) abertas. None = consulta falhou."""
    try:
        r = _algo_req(client, "get", "openAlgoOrders", symbol=symbol)
        if isinstance(r, dict):
            r = r.get("orders") or r.get("data") or []
        if not isinstance(r, list):
            log.warning(f"⚠️ {symbol} openAlgoOrders formato inesperado")
            return None
        for o in r:
            if isinstance(o, dict) and not o.get("type"):
                o["type"] = o.get("orderType") or o.get("algoType") or ""
        return r
    except Exception as e:
        log.warning(f"⚠️ {symbol} falha ao listar ordens Algo: {e}")
        return None


def cancelar_algo(client, symbol):
    """Cancela TODAS as ordens condicionais (TP/STOP) do simbolo via API Algo."""
    try:
        lst = listar_algo(client, symbol)
        if lst is None:
            log.error(f"❌ cancelar_algo {symbol}: consulta falhou, nada cancelado")
            return False
        if not lst:
            return True
        _algo_req(client, "delete", "algoOpenOrders", symbol=symbol)
        log.info(f"🗑️ {symbol} {len(lst)} ordem(ns) Algo cancelada(s)")
        return True
    except Exception as e:
        log.error(f"❌ Erro cancelar_algo {symbol}: {e}")
        return False


def cancelar_todas_ordens(client, symbol):
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
        cancelar_algo(client, symbol)
        log.info(f"🗑️ Todas ordens canceladas {symbol}")
        time.sleep(0.3)
    except Exception as e:
        log.error(f"❌ Erro cancelar_todas {symbol}: {e}")


# Verificação de proteção deliberadamente lenta:
# não consultar a cada ciclo para evitar excesso de chamadas.
PROTECAO_CADA_S = 180
_ULTIMA_VERIF_PROTECAO = {}


def _consultar_protecoes_algo(client, symbol):
    """Lista TP/STOP reais (API Algo + ordens comuns). None = consulta falhou."""
    lst = listar_algo(client, symbol)
    if lst is None:
        return None
    try:
        r = client.futures_get_open_orders(symbol=symbol)
        if isinstance(r, list):
            tipos = ["STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"]
            lst = list(lst) + [o for o in r if o.get("type") in tipos]
    except Exception as e:
        log.warning(f"⚠️ {symbol} ordens comuns indisponiveis: {e}")
    return lst


def trail_rebalance(hydra, h):
    """Trailing do STOP de rebalance: roda todo ciclo (ROI da posicao aberta)."""
    if h.estado not in (MEIA_LONG, MEIA_SHORT):
        return
    leg = h.posicao_long if h.estado == MEIA_LONG else h.posicao_short
    if not leg or leg.qty <= 0:
        return
    client = hydra.client
    pos = get_posicao_real(client, h.symbol)
    p = pos.get(leg.lado) if pos else None
    if not p:
        return
    alv = h.alavancagem
    base = (leg.qty * leg.preco_entrada) / alv
    roi = p["pnl"] / base
    if roi > h.roi_ancora + TRAIL_MINIMO:
        log.info(f"TRAIL {h.symbol} {h.roi_ancora*100:+.1f}% -> {roi*100:+.1f}% move STOP")
        if cancelar_stop(client, h.symbol) is False:
            log.warning(f"TRAIL {h.symbol}: STOP antigo nao cancelado, adiado")
            return
        h.roi_ancora = roi
        ok = colocar_rebalance_limit(
            client, h.symbol, leg.lado, leg.qty,
            leg.preco_entrada, alv, roi_ancora=roi)
        # FIX: se falhou, tenta de novo (so se confirmar que NAO existe STOP, p/ nao duplicar)
        for _t in range(2):
            if ok:
                break
            time.sleep(1)
            lst = _consultar_protecoes_algo(client, h.symbol)
            if lst is None:
                break   # nao consegue confirmar: nao arrisca duplicar
            if any(isinstance(o, dict) and str(o.get("type", "")).upper() in ("STOP_MARKET", "STOP") for o in lst):
                ok = True
                break
            ok = colocar_rebalance_limit(
                client, h.symbol, leg.lado, leg.qty,
                leg.preco_entrada, alv, roi_ancora=roi)
        if not ok:
            log.warning(f"TRAIL {h.symbol}: STOP nao recolocado — forcando verificacao de protecao agora")
            _ULTIMA_VERIF_PROTECAO[h.symbol] = 0   # verificar_protecoes_meia roda ja neste ciclo
        salvar_estado(hydra.hedges)


def verificar_protecoes_meia(hydra, h):
    """Confere TP + STOP de rebalance somente em MEIA_*.

    Segurança:
    - no máximo uma consulta por PROTECAO_CADA_S;
    - falha/JSON inesperado => somente log;
    - nunca coloca uma segunda proteção por cima;
    - se faltar proteção confirmadamente, cancela tudo antes;
    - recoloca TP e rebalance de forma única.
    """
    if h.estado not in (MEIA_LONG, MEIA_SHORT):
        return

    leg = h.posicao_long if h.estado == MEIA_LONG else h.posicao_short
    if not leg:
        return

    agora = time.time()
    ultima = _ULTIMA_VERIF_PROTECAO.get(h.symbol, 0)

    if agora - ultima < PROTECAO_CADA_S:
        return

    _ULTIMA_VERIF_PROTECAO[h.symbol] = agora

    client = hydra.client

    # A API Algo é a fonte necessária para TP/STOP.
    algo = _consultar_protecoes_algo(client, h.symbol)

    # Falha ou formato desconhecido:
    # NÃO cancelar nada e NÃO tentar duplicar proteção.
    if algo is None:
        return

    lado = leg.lado

    tp_ok = False
    rebalance_ok = False

    try:
        for o in algo:
            if not isinstance(o, dict):
                log.warning(
                    f"⚠️ {h.symbol} ordem Algo em formato inesperado — "
                    f"proteção NÃO será alterada"
                )
                return

            tipo = str(
                o.get("type")
                or o.get("orderType")
                or ""
            ).upper()

            ps = str(
                o.get("positionSide")
                or ""
            ).upper()

            # TP fecha a própria perna.
            if tipo in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT"):
                if ps == lado:
                    tp_ok = True

            # STOP rebalance abre a perna oposta.
            oposta = "SHORT" if lado == "LONG" else "LONG"
            if tipo in ("STOP_MARKET", "STOP"):
                if ps == oposta:
                    rebalance_ok = True

    except Exception as e:
        log.warning(
            f"⚠️ {h.symbol} erro interpretando ordens Algo: {e} — "
            f"proteção NÃO será alterada"
        )
        return

    if tp_ok and rebalance_ok:
        log.debug(
            f"🛡️ {h.symbol} proteção OK ({lado}) — "
            f"TP + rebalance confirmados"
        )
        return

    faltas = []
    if not tp_ok:
        faltas.append("TP")
    if not rebalance_ok:
        faltas.append("REBALANCE")

    log.warning(
        f"🚨 {h.symbol} proteção incompleta ({', '.join(faltas)}) — "
        f"cancelando antes de reconstruir"
    )

    # Regra fundamental:
    # nunca colocar outra proteção por cima da existente.
    cancelar_todas_ordens(client, h.symbol)

    time.sleep(0.5)

    tp = colocar_tp(
        client,
        h.symbol,
        lado,
        leg.qty,
        leg.preco_entrada,
        h.alavancagem
    )

    reb = colocar_rebalance_limit(
        client,
        h.symbol,
        lado,
        leg.qty,
        leg.preco_entrada,
        h.alavancagem,
        roi_ancora=h.roi_ancora
    )

    if tp and reb:
        log.info(
            f"✅ {h.symbol} proteção reconstruída — "
            f"TP={tp} REBALANCE={reb}"
        )
    else:
        log.error(
            f"🚨 {h.symbol} proteção NÃO foi totalmente reconstruída "
            f"(TP={tp}, REBALANCE={reb})"
        )


def colocar_rebalance_limit(client, symbol, lado, qty, preco_entrada, alv, roi_ancora=0.0, roi_stop=0.05):
    """STOP_MARKET que ABRE a perna oposta (volta ao hedge) quando o ROI da perna solta cai a âncora-5%"""
    try:
        tick = get_tick_size(client, symbol)
        if not tick:
            log.error(f"❌ {symbol} tickSize indisponível — STOP rebalance não colocado")
            return False

        roi_gatilho = roi_ancora - roi_stop

        if lado == "SHORT":
            gatilho       = arredondar_preco(preco_entrada * (1 - roi_gatilho / alv), tick)
            side          = "BUY"
            position_side = "LONG"
        else:
            gatilho       = arredondar_preco(preco_entrada * (1 + roi_gatilho / alv), tick)
            side          = "SELL"
            position_side = "SHORT"

        try:
            client.futures_create_order(
                symbol=symbol,
                side=side,
                positionSide=position_side,
                type="STOP_MARKET",
                stopPrice=_fmt(gatilho),
                quantity=_fmt(qty),
                workingType="MARK_PRICE"
            )
        except Exception as e:
            if "-2021" in str(e):
                log.warning(f"⚠️ STOP rebalance {symbol} já cruzado — abre {position_side} a mercado")
                return bool(abrir_ordem(client, symbol, position_side, qty))
            raise

        log.info(f"🛡️ STOP rebalance {lado} {symbol} gatilho @ {gatilho} abre {position_side} (âncora{roi_ancora*100:+.1f}% -5%)")
        return True
    except Exception as e:
        log.error(f"❌ Erro STOP rebalance {symbol}: {e}")
        return False


def limpar_ordens_hedge(client, symbol):
    """Hedge completo não pode ter TP/LIMIT/STOP pendentes"""
    try:
        ordens = client.futures_get_open_orders(symbol=symbol)
        if ordens:
            log.info(f"🧹 {symbol} hedge completo — cancelando {len(ordens)} ordem(ns) pendente(s)")
            client.futures_cancel_all_open_orders(symbol=symbol)
        cancelar_algo(client, symbol)
    except Exception as e:
        log.error(f"❌ Erro limpar_ordens_hedge {symbol}: {e}")


def cancelar_stop(client, symbol):
    """Cancela so o STOP (rebalance) e preserva o TP. True = ok, False = falhou."""
    ok = True
    try:
        lst = listar_algo(client, symbol)
        if lst is None:
            return False
        for o in lst:
            if str(o.get("type", "")).upper() in ("STOP_MARKET", "STOP"):
                aid = o.get("algoId")
                if aid is None:
                    ok = False
                    continue
                try:
                    _algo_req(client, "delete", "algoOrder", symbol=symbol, algoId=aid)
                    log.info(f"🗑️ STOP Algo cancelado {symbol} algoId={aid}")
                except Exception as e:
                    ok = False
                    log.error(f"❌ Erro cancelar STOP Algo {symbol} {aid}: {e}")
        for o in client.futures_get_open_orders(symbol=symbol):
            if o["type"] in ("STOP_MARKET", "STOP", "LIMIT"):
                client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
                log.info(f"🗑️ Ordem cancelada {symbol} orderId={o['orderId']}")
        time.sleep(0.3)
    except Exception as e:
        log.error(f"❌ Erro cancelar_stop {symbol}: {e}")
        return False
    return ok


def alvo_tp(symbol, alv):
    """Regra única do alvo: TP fixo (TP_ROI); com TP_ADAPTATIVO nunca abaixo do alvo por ATR."""
    if TP_ADAPTATIVO:
        return max(TP_ROI, min_roi_par(symbol, alv))
    return TP_ROI


def colocar_tp(client, symbol, lado, qty, preco_entrada, alv, roi_alvo=None):
    try:
        if roi_alvo is None:
            roi_alvo = alvo_tp(symbol, alv)
        tick = get_tick_size(client, symbol)
        if not tick:
            log.error(f"❌ {symbol} tickSize indisponível — TP não colocado")
            return False

        if lado == "SHORT":
            tp_preco      = arredondar_preco(preco_entrada * (1 - roi_alvo / alv), tick)
            side          = "BUY"
            position_side = "SHORT"
        else:
            tp_preco      = arredondar_preco(preco_entrada * (1 + roi_alvo / alv), tick)
            side          = "SELL"
            position_side = "LONG"

        client.futures_create_order(
            symbol=symbol,
            side=side,
            positionSide=position_side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=_fmt(tp_preco),
            closePosition=True,
            timeInForce="GTE_GTC",
            workingType="MARK_PRICE"
        )
        log.info(f"🎯 TP colocado {lado} {symbol} @ {tp_preco} (ROI alvo {roi_alvo*100:.0f}%)")
        return True
    except Exception as e:
        if "-4130" in str(e):
            log.info(f"🎯 TP já existe {symbol} — ok")
            return True
        log.error(f"❌ Erro TP {symbol}: {e}")
        return False


def arredondar_qty(qty, step):
    """Trunca p/ baixo no stepSize real (Decimal: imune a notação científica)."""
    if not step:
        return 0.0
    d = Decimal(str(step))
    return float((Decimal(str(qty)) / d).to_integral_value(rounding=ROUND_DOWN) * d)

def arredondar_preco(preco, tick):
    if not tick:
        return preco
    d = Decimal(str(tick))
    return float((Decimal(str(preco)) / d).to_integral_value(rounding=ROUND_HALF_UP) * d)

def _fmt(x):
    """Número -> string decimal fixa (nunca '1e-05') para enviar à Binance."""
    return format(Decimal(str(x)), "f")

def get_posicao_real(client, symbol):
    try:
        posicoes = api_retry(client.futures_position_information, symbol=symbol)
        if not posicoes:
            return None
        resultado = {"LONG": None, "SHORT": None}
        for p in posicoes:
            amt  = float(p["positionAmt"])
            lado = p.get("positionSide","")
            if lado == "LONG" and amt > 0:
                resultado["LONG"] = {
                    "amt":   amt,
                    "preco": float(p["entryPrice"]),
                    "pnl":   float(p["unRealizedProfit"]),
                    "ts":    int(p.get("updateTime", 0) or 0),
                }
            elif lado == "SHORT" and amt < 0:
                resultado["SHORT"] = {
                    "amt":   abs(amt),
                    "preco": float(p["entryPrice"]),
                    "pnl":   float(p["unRealizedProfit"]),
                    "ts":    int(p.get("updateTime", 0) or 0),
                }
        return resultado
    except Exception as e:
        log.error(f"Erro posicao_real {symbol}: {e}")
        return None

def _enviar_ordem(client, **p):
    """Ordem com clientOrderId: em timeout/rede consulta se ela chegou a executar."""
    cid = "hy" + str(int(time.time() * 1000)) + str(np.random.randint(100, 999))
    p["newClientOrderId"] = cid
    try:
        return client.futures_create_order(**p)
    except BinanceAPIException:
        raise
    except Exception as e:
        log.warning(f"⚠️ {p.get('symbol')} rede/timeout ao enviar ordem ({e}) — consultando pelo clientOrderId")
        time.sleep(1)
        return client.futures_get_order(symbol=p["symbol"], origClientOrderId=cid)

def _amt_lado(client, symbol, lado):
    pos = get_posicao_real(client, symbol)
    if pos is None:
        return None
    p = pos.get(lado)
    return p["amt"] if p else 0.0

def abrir_ordem(client, symbol, lado, qty):
    """Só devolve a ordem se a Binance CONFIRMAR a perna aberta."""
    side  = "BUY" if lado == "LONG" else "SELL"
    antes = _amt_lado(client, symbol, lado) or 0.0
    try:
        ordem = _enviar_ordem(client, symbol=symbol, side=side, positionSide=lado,
                              type="MARKET", quantity=_fmt(qty))
    except Exception as e:
        log.error(f"❌ Erro abrir {lado} {symbol}: {e}")
        return None
    for _ in range(4):
        time.sleep(0.5)
        depois = _amt_lado(client, symbol, lado)
        if depois is not None and depois >= antes + qty * 0.99:
            log.info(f"✅ ABRIU {lado} {symbol} qty={qty} orderId={ordem.get('orderId')}")
            return ordem
    log.warning(f"⚠️ {symbol} {lado}: abertura NÃO confirmada na Binance (reconciliação decide)")
    return None

def fechar_ordem(client, symbol, lado, qty):
    """Só devolve a ordem se a Binance CONFIRMAR a perna fechada."""
    side  = "SELL" if lado == "LONG" else "BUY"
    antes = _amt_lado(client, symbol, lado)
    try:
        ordem = _enviar_ordem(client, symbol=symbol, side=side, positionSide=lado,
                              type="MARKET", quantity=_fmt(qty))
    except Exception as e:
        log.error(f"❌ Erro fechar {lado} {symbol}: {e}")
        return None
    ULTIMA_FECHA[(symbol, lado)] = ordem.get("orderId")
    if antes is None:
        antes = qty
    for _ in range(4):
        time.sleep(0.5)
        depois = _amt_lado(client, symbol, lado)
        if depois is not None and depois <= max(0.0, antes - qty * 0.99):
            log.info(f"✅ FECHOU {lado} {symbol} qty={qty} orderId={ordem.get('orderId')}")
            return ordem
    log.warning(f"⚠️ {symbol} {lado}: fechamento NÃO confirmado na Binance")
    return None

def fechar_e_confirmar(client, symbol, lado, qty, tentativas=3):
    """True só quando a Binance confirma que a perna não existe mais."""
    for _ in range(tentativas):
        real = _amt_lado(client, symbol, lado)
        if real is not None and real <= 0:
            return True
        if fechar_ordem(client, symbol, lado, real if real else qty):
            return True
        time.sleep(1)
    real = _amt_lado(client, symbol, lado)
    return real is not None and real <= 0

def fechar_tudo(client, symbol):
    try:
        pos = get_posicao_real(client, symbol)
        if pos:
            if pos["LONG"]:
                fechar_ordem(client, symbol, "LONG", pos["LONG"]["amt"])
            if pos["SHORT"]:
                fechar_ordem(client, symbol, "SHORT", pos["SHORT"]["amt"])
        log.info(f"🔒 {symbol} todas as posições fechadas")
    except Exception as e:
        log.error(f"Erro fechar_tudo {symbol}: {e}")

def _comissao(t):
    try:
        cm = abs(float(t.get("commission", 0) or 0))
        if t.get("commissionAsset", "USDT") in ("USDT", "USDC", "BUSD"):
            return cm
        return abs(float(t.get("quoteQty", 0) or 0)) * FEES_PCT   # taxa em BNB etc.: estima
    except Exception:
        return 0.0

def get_pnl_detalhe(client, symbol, lado, ts_ms, order_id=None):
    """PnL da perna: filtra por positionSide + lado de fechamento (+ orderId quando conhecido).
    Slippage já está embutido no realizedPnl (calculado sobre os preços executados)."""
    trades = api_retry(client.futures_account_trades, symbol=symbol, startTime=int(ts_ms))
    fecha = "SELL" if lado == "LONG" else "BUY"
    abre  = "BUY"  if lado == "LONG" else "SELL"
    do_lado = [t for t in trades if t.get("positionSide", lado) == lado]
    t_fecha = [t for t in do_lado if t["side"] == fecha]
    t_abre  = [t for t in do_lado if t["side"] == abre]
    if order_id:
        so = [t for t in t_fecha if str(t.get("orderId")) == str(order_id)]
        if so:
            t_fecha = so
    bruto = sum(float(t["realizedPnl"]) for t in t_fecha)
    taxas = sum(_comissao(t) for t in t_fecha + t_abre)
    return {"bruto": bruto, "taxas": taxas, "liquido": bruto - taxas}

def get_pnl_real(client, symbol, lado, timestamp_entrada_ms):
    """PnL LÍQUIDO da perna (realizado - comissões)."""
    oid = ULTIMA_FECHA.pop((symbol, lado), None)
    try:
        d = get_pnl_detalhe(client, symbol, lado, timestamp_entrada_ms, oid)
        ULTIMO_DET[(symbol, lado)] = d
        return d["liquido"]
    except Exception as e:
        log.error(f"Erro pnl_real {symbol}: {e}")
        return 0.0

def get_funding(client, symbol, ini_ms, fim_ms):
    try:
        inc = api_retry(client.futures_income_history, symbol=symbol, incomeType="FUNDING_FEE",
                        startTime=int(ini_ms), endTime=int(fim_ms), limit=1000)
        return sum(float(i["income"]) for i in inc)
    except Exception as e:
        log.error(f"Erro funding {symbol}: {e}")
        return 0.0

def get_top_pares(client):
    try:
        tickers = client.futures_ticker()
        usdt = [
            t for t in tickers
            if t['symbol'].endswith('USDT')
            and t['symbol'] not in BLACKLIST
            and float(t['quoteVolume']) >= MIN_VOLUME
        ]
        usdt.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        return [t['symbol'] for t in usdt[:TOP_PARES]]
    except Exception as e:
        log.error(f"Erro top pares: {e}")
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]

def get_preco(client, symbol):
    try:
        r = api_retry(client.futures_symbol_ticker, symbol=symbol)
        if r.get("symbol") not in (None, symbol):
            log.warning(f"⚠️ {symbol} ticker devolveu {r.get('symbol')} — preço descartado")
            return None
        return float(r['price'])
    except Exception:
        return None

# ─── ESTADO PERSISTENTE ─────────────────────────────────────
def salvar_estado(hedges):
    dados = {}
    for sym, h in hedges.items():
        dados[sym] = {
            "estado":           h.estado,
            "alavancagem":      h.alavancagem,
            "lucro_embolsado":  h.lucro_embolsado,
            "losses_seguidos":  h.losses_seguidos,
            "ciclos_reentrada": h.ciclos_reentrada,
            "roi_ancora":       h.roi_ancora,
            "conf":             getattr(h, "conf", {}),
            "conf_estado":      getattr(h, "conf_estado", None),
            "ciclo": {
                "id":      getattr(h, "ciclo_id", None),
                "ini":     getattr(h, "ciclo_ini", None),
                "pernas":  getattr(h, "ciclo_pernas", []),
                "fim":     getattr(h, "ciclo_fim", False),
                "entrada": getattr(h, "ciclo_entrada", None),
                "regime":  getattr(h, "ciclo_regime", None),
                "score":   getattr(h, "ciclo_score", None),
                "sessao":  getattr(h, "ciclo_sessao", None),
                "parcial": getattr(h, "ciclo_parcial", False),
            },
            "long": {
                "preco_entrada":  h.posicao_long.preco_entrada,
                "qty":            h.posicao_long.qty,
                "timestamp_ms":   h.posicao_long.timestamp_ms,
            } if h.posicao_long else None,
            "short": {
                "preco_entrada":  h.posicao_short.preco_entrada,
                "qty":            h.posicao_short.qty,
                "timestamp_ms":   h.posicao_short.timestamp_ms,
            } if h.posicao_short else None,
        }
    r = HYDRA_REF
    if r is not None:
        dados["__hydra__"] = {
            "losses_seguidos": r.losses_seguidos, "wins": r.wins, "losses": r.losses,
            "pernas_win": r.pernas_win, "pernas_loss": r.pernas_loss,
            "banca_base": getattr(r, "banca_base", None),
            "pausado_ate": r.pausado_ate.isoformat() if r.pausado_ate else None,
        }
    tmp = ESTADO_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(dados, f, indent=2)
    os.replace(tmp, ESTADO_FILE)

def carregar_estado():
    try:
        if os.path.exists(ESTADO_FILE):
            return json.load(open(ESTADO_FILE))
    except:
        pass
    return {}

def _carregar_ciclos(n=500):
    try:
        if os.path.exists(CICLOS_FILE):
            with open(CICLOS_FILE, encoding="utf-8") as f:
                linhas = [l for l in f.read().splitlines() if l.strip()]
            return [json.loads(l) for l in linhas[-n:]]
    except Exception as e:
        logging.error(f"carregar_ciclos: {e}")
    return []

def _abrir_ciclo(hydra, h, parcial=False):
    agora = int(time.time() * 1000)
    tss = [p.timestamp_ms for p in (h.posicao_long, h.posicao_short) if p]
    h.ciclo_id      = f"{h.symbol}-{agora}"
    h.ciclo_ini     = min(tss) if tss else agora
    h.ciclo_pernas  = []
    h.ciclo_fim     = False
    h.ciclo_parcial = parcial
    h.ciclo_entrada = {
        "long":  {"preco": h.posicao_long.preco_entrada,  "qty": h.posicao_long.qty}  if h.posicao_long  else None,
        "short": {"preco": h.posicao_short.preco_entrada, "qty": h.posicao_short.qty} if h.posicao_short else None,
    }
    h.ciclo_score  = max(getattr(h, "ultimo_score", (0, 0)))   # SCORE = heurística (não é probabilidade)
    h.ciclo_regime = getattr(h, "ultimo_regime", None)
    h.ciclo_sessao = get_sessao()
    log.info(f"🆕 CICLO {h.ciclo_id} aberto ({'parcial' if parcial else 'hedge completo'})")

def _acum_ciclo(hydra, symbol, lado, pnl, motivo, resultado):
    h = hydra.hedges.get(symbol)
    if h is None:
        return
    motivo = motivo or ""
    if not getattr(h, "ciclo_id", None):
        _abrir_ciclo(hydra, h, parcial=True)
    det = ULTIMO_DET.pop((symbol, lado), None)
    bruto = det["bruto"] if det else pnl
    taxas = det["taxas"] if det else 0.0
    h.ciclo_pernas.append({"lado": lado, "motivo": motivo, "resultado": resultado,
                           "bruto": round(bruto, 6), "taxas": round(taxas, 6),
                           "liquido": round(pnl, 6), "hora": datetime.now().strftime("%H:%M:%S")})
    if motivo.startswith("Inversão"):
        h.ciclo_fim = True   # a inversão encerra este ciclo; o hedge novo abre outro

def _fechar_ciclo(hydra, h):
    fim_ms = int(time.time() * 1000)
    ini_ms = int(getattr(h, "ciclo_ini", None) or fim_ms)
    pernas = list(getattr(h, "ciclo_pernas", []) or [])
    cid    = getattr(h, "ciclo_id", None)
    if pernas:
        funding = get_funding(hydra.client, h.symbol, ini_ms, fim_ms)
        bruto   = sum(p["bruto"] for p in pernas)
        taxas   = sum(p["taxas"] for p in pernas)
        liquido = bruto - taxas + funding
        resultado = "WIN" if liquido > 0 else "LOSS"
        ent = getattr(h, "ciclo_entrada", None) or {}
        fmt = "%Y-%m-%d %H:%M:%S"
        rec = {
            "ciclo_id": cid, "par": h.symbol,
            "inicio": datetime.fromtimestamp(ini_ms / 1000).strftime(fmt),
            "fim": datetime.fromtimestamp(fim_ms / 1000).strftime(fmt),
            "duracao_min": round((fim_ms - ini_ms) / 60000, 1),
            "estado_inicial": "PARCIAL" if getattr(h, "ciclo_parcial", False) else "HEDGE_COMPLETO",
            "entrada_long": ent.get("long"), "entrada_short": ent.get("short"),
            "liberacoes": [p["motivo"] for p in pernas],
            "pnl_long":  round(sum(p["liquido"] for p in pernas if p["lado"] == "LONG"), 6),
            "pnl_short": round(sum(p["liquido"] for p in pernas if p["lado"] == "SHORT"), 6),
            "pnl_bruto": round(bruto, 6), "taxas": round(taxas, 6), "funding": round(funding, 6),
            "liquido": round(liquido, 6), "resultado": resultado,
            "score_abertura": getattr(h, "ciclo_score", None),
            "regime": getattr(h, "ciclo_regime", None),
            "notional": round(sum(v["preco"] * v["qty"] for v in (ent.get("long"), ent.get("short")) if v), 4),
            "motivo_final": pernas[-1]["motivo"],
        }
        hydra.ciclos_hist.append(rec)
        hydra.ciclos_hist = hydra.ciclos_hist[-500:]
        try:
            with open(CICLOS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.error(f"gravar ciclo: {e}")
        if UNIDADE_CICLO:
            if resultado == "WIN":
                hydra.wins += 1
                hydra.losses_seguidos = 0
            else:
                hydra.losses += 1
                if SUBSIDIO_FORA_DA_SEQUENCIA and pernas[-1]["motivo"] in ("Subsidio HEDGE", "Desarme HEDGE"):
                    pass   # hedge pago com lucro: realiza perda ja existente, nao e trade perdedor novo
                else:
                    hydra.losses_seguidos += 1
                    if hydra.losses_seguidos >= LOSSES_STOP:
                        hydra.pausar(f"{LOSSES_STOP} ciclos perdedores seguidos")
            ref = ent.get("long") or ent.get("short")
            if getattr(h, "ciclo_regime", None) is not None and ref:
                registar_trade_memoria(h.symbol, "HEDGE", h.ciclo_regime, h.ciclo_score or 0,
                                       h.ciclo_sessao or get_sessao(), ref["preco"],
                                       getattr(h, "ultimo_preco", ref["preco"]), liquido,
                                       max(int((fim_ms - ini_ms) / 60000), 0), resultado)
        log.info(f"🏁 CICLO {cid} {resultado} líquido={liquido:+.4f} (bruto {bruto:+.4f} | taxas {taxas:.4f} | funding {funding:+.4f})")
        hydra.salvar_resultados()
    h.ciclo_id, h.ciclo_pernas, h.ciclo_fim = None, [], False
    h.ciclo_entrada, h.ciclo_parcial = None, False

def _gerir_ciclo(hydra, h):
    """Ciclo só termina sem exposição (ou na inversão); novo ciclo = hedge completo aberto."""
    try:
        ativo   = getattr(h, "ciclo_id", None)
        tem_pos = bool(h.posicao_long or h.posicao_short)
        if ativo and (getattr(h, "ciclo_fim", False) or not tem_pos):
            _fechar_ciclo(hydra, h)
            ativo = None
        if not ativo and h.posicao_long and h.posicao_short:
            _abrir_ciclo(hydra, h)
    except Exception as e:
        log.error(f"_gerir_ciclo {getattr(h, 'symbol', '?')}: {e}")

def calc_metricas(hist):
    n = len(hist)
    if n == 0:
        return {}
    pn = [x["liquido"] for x in hist]
    ganhos = [p for p in pn if p > 0]
    perdas = [p for p in pn if p <= 0]
    sg, sp = sum(ganhos), abs(sum(perdas))
    mg = sg / len(ganhos) if ganhos else 0.0
    mp = sp / len(perdas) if perdas else 0.0
    eq = pico = mdd = 0.0
    for p in pn:
        eq += p
        pico = max(pico, eq)
        mdd = max(mdd, pico - eq)
    return {
        "ciclos": n,
        "win_rate": round(len(ganhos) / n * 100, 1),
        "pnl_liquido": round(sum(pn), 4),
        "profit_factor": round(sg / sp, 2) if sp > 0 else None,
        "expectancy": round(sum(pn) / n, 4),
        "media_ganho": round(mg, 4),
        "media_perda": round(-mp, 4),
        "payoff": round(mg / mp, 2) if mp > 0 else None,
        "max_drawdown": round(mdd, 4),
        "duracao_media_min": round(sum(x.get("duracao_min", 0) for x in hist) / n, 1),
        "exposicao_media": round(sum(x.get("notional", 0) for x in hist) / n, 2),
    }

def _painel_ciclos(hydra):
    try:
        m  = calc_metricas(hydra.ciclos_hist)
        ac = hydra.client.futures_account()
        eq = float(ac["totalMarginBalance"])
        mu = float(ac["totalInitialMargin"])
        v  = lambda x: "—" if x is None else x
        print("║" + f"  Pernas W/L: {hydra.pernas_win}/{hydra.pernas_loss}  Realizado(ciclos): {m.get('pnl_liquido', 0):+.4f}".ljust(68) + "║")
        if m:
            print("║" + f"  PF:{v(m['profit_factor'])} Exp:{m['expectancy']:+.4f} Payoff:{v(m['payoff'])} MaxDD:{m['max_drawdown']:.4f}".ljust(68) + "║")
            print("║" + f"  Dur.média:{m['duracao_media_min']}min  Expos.média:{m['exposicao_media']}".ljust(68) + "║")
        pct = (mu / eq * 100) if eq > 0 else 0
        print("║" + f"  Equity:{eq:.4f}  Margem usada:{mu:.4f} ({pct:.0f}%)".ljust(68) + "║")
    except Exception as e:
        logging.error(f"painel_ciclos: {e}")

class PosicaoReal:
    def __init__(self, lado, preco_entrada, qty, alavancagem, timestamp_ms=None):
        self.lado          = lado
        self.preco_entrada = preco_entrada
        self.qty           = qty
        self.alavancagem   = alavancagem
        self.timestamp_ms  = timestamp_ms or int(time.time() * 1000)
        self.aberta_em     = datetime.now()

class HedgeReal:
    def __init__(self, symbol, alavancagem):
        self.symbol            = symbol
        self.alavancagem       = alavancagem
        self.estado            = AGUARDA
        self.posicao_long      = None
        self.posicao_short     = None
        self.lucro_embolsado   = 0.0
        self.ciclos_reentrada  = 0
        self.losses_seguidos   = 0
        self.roi_ancora        = 0.0   # ROI da perna solta no momento do desmembramento

class HydraCerebro:
    def __init__(self, client):
        self.client          = client
        self.banca_inicial   = get_banca_total(client)
        self.banca_base      = self.banca_inicial   # base do lucro total realizado (persistida)
        self.hedges          = {}
        self.alavancagens    = {}
        self.ciclo           = 0
        self.wins            = 0
        self.losses          = 0
        self.losses_seguidos = 0
        self.historico       = []
        self.pausado_ate     = None
        self.step_sizes      = {}
        self.pernas_win      = 0
        self.pernas_loss     = 0
        self.ciclos_hist     = _carregar_ciclos()
        globals()["HYDRA_REF"] = self

        log.info(f"💰 Banca inicial: {self.banca_inicial:.4f} USDT")

    def em_pausa(self):
        if self.pausado_ate and datetime.now() < self.pausado_ate:
            return True
        self.pausado_ate = None
        return False

    def pausar(self, motivo):
        self.pausado_ate = datetime.now() + timedelta(minutes=PAUSA_MINUTOS)
        log.warning(f"⏸ PAUSA {PAUSA_MINUTOS}min — {motivo}")

    def banca_disponivel(self):
        return get_banca_real(self.client)

    def banca_total(self):
        return get_banca_total(self.client)

    def tamanho_por_hedge(self):
        banca = self.banca_total()
        return max(0.10, banca * RISCO_PCT)

    def registar_win(self, symbol, lado, pnl, motivo="",
                      regime=None, score=None, sessao=None,
                      entrada=None, saida=None, timestamp_ms=None):
        self.pernas_win += 1
        if not UNIDADE_CICLO:
            self.wins += 1
            self.losses_seguidos = 0
        self._registar(symbol, lado, pnl, motivo)
        self._registar_memoria(symbol, lado, pnl, "WIN", regime, score,
                                sessao, entrada, saida, timestamp_ms)
        _acum_ciclo(self, symbol, lado, pnl, motivo, "WIN")

    def registar_loss(self, symbol, lado, pnl, motivo="",
                       regime=None, score=None, sessao=None,
                       entrada=None, saida=None, timestamp_ms=None):
        self.pernas_loss += 1
        if not UNIDADE_CICLO:
            self.losses += 1
            self.losses_seguidos += 1
        self._registar(symbol, lado, pnl, motivo)
        self._registar_memoria(symbol, lado, pnl, "LOSS", regime, score,
                                sessao, entrada, saida, timestamp_ms)
        _acum_ciclo(self, symbol, lado, pnl, motivo, "LOSS")
        if not UNIDADE_CICLO and self.losses_seguidos >= LOSSES_STOP:
            self.pausar(f"{LOSSES_STOP} losses seguidos")

    def _registar_memoria(self, symbol, lado, pnl, resultado, regime, score,
                           sessao, entrada, saida, timestamp_ms):
        if UNIDADE_CICLO:      # memória passa a ser registrada por CICLO (_fechar_ciclo)
            return
        if regime is None or entrada is None:
            return
        duracao = int((time.time() - (timestamp_ms or time.time()*1000)/1000) / 60)
        registar_trade_memoria(
            symbol, lado, regime, score or 0, sessao or get_sessao(),
            entrada, saida if saida is not None else entrada,
            pnl, max(duracao, 0), resultado
        )

    def _registar(self, symbol, lado, pnl, motivo):
        self.historico.append({
            "ciclo":  self.ciclo,
            "symbol": symbol,
            "lado":   lado,
            "pnl":    round(pnl, 4),
            "motivo": motivo,
            "banca":  round(self.banca_total(), 4),
            "hora":   datetime.now().strftime("%H:%M:%S"),
        })
        self.salvar_resultados()

    def verificar_drawdown(self):
        return False  # DESATIVADO: stop de drawdown removido
        banca_atual = self.banca_total()
        if self.banca_inicial <= 0: return False
        drawdown = (self.banca_inicial - banca_atual) / self.banca_inicial
        if drawdown >= DRAWDOWN_STOP:
            log.warning(f"🚨 DRAWDOWN {drawdown*100:.1f}% — fecha tudo!")
            for sym in list(self.hedges.keys()):
                fechar_tudo(self.client, sym)
            self.pausar(f"Drawdown {drawdown*100:.1f}%")
            return True
        return False

    def salvar_resultados(self):
        banca_atual = self.banca_total()
        lucro       = banca_atual - self.banca_inicial
        wr          = round(self.wins/(self.wins+self.losses)*100) if (self.wins+self.losses) > 0 else 0
        with open(RES_FILE, 'w') as f:
            json.dump({
                "actualizado":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "unidade_resultado": "CICLO" if UNIDADE_CICLO else "PERNA",
                "banca_inicial": round(self.banca_inicial, 4),
                "banca_atual":   round(banca_atual, 4),
                "lucro_total":   round(lucro, 4),
                "lucro_pct":     round((lucro/self.banca_inicial)*100, 2) if self.banca_inicial > 0 else 0,
                "wins":          self.wins,
                "losses":        self.losses,
                "win_rate":      wr,
                "pernas_win":    self.pernas_win,
                "pernas_loss":   self.pernas_loss,
                "metricas_ciclos": calc_metricas(self.ciclos_hist),
                "ciclos":        self.ciclo,
                "historico":     self.historico[-100:],
            }, f, indent=2)

def recuperar_estado(hydra):
    log.info("🔄 A recuperar estado após reinício...")
    estado_json = carregar_estado()
    _g = estado_json.pop("__hydra__", None) or {}
    hydra.losses_seguidos = _g.get("losses_seguidos", 0)
    hydra.wins            = _g.get("wins", 0)
    hydra.losses          = _g.get("losses", 0)
    hydra.pernas_win      = _g.get("pernas_win", 0)
    hydra.pernas_loss     = _g.get("pernas_loss", 0)
    hydra.banca_base      = _g.get("banca_base") or hydra.banca_inicial
    if _g.get("pausado_ate"):
        try:
            _p = datetime.fromisoformat(_g["pausado_ate"])
            if _p > datetime.now():
                hydra.pausado_ate = _p
        except Exception:
            pass

    for symbol, dados in estado_json.items():
        pos_real = get_posicao_real(hydra.client, symbol)
        alv      = dados.get("alavancagem", 50)

        h = HedgeReal(symbol, alv)
        h.lucro_embolsado = dados.get("lucro_embolsado", 0)
        h.roi_ancora      = dados.get("roi_ancora", 0.0)
        h.ciclos_reentrada = dados.get("ciclos_reentrada", 0)
        h.losses_seguidos  = dados.get("losses_seguidos", 0)
        h.conf             = dados.get("conf", {}) or {}
        h.conf_estado      = dados.get("conf_estado")
        _c = dados.get("ciclo") or {}
        h.ciclo_id      = _c.get("id")
        h.ciclo_ini     = _c.get("ini")
        h.ciclo_pernas  = _c.get("pernas") or []
        h.ciclo_fim     = _c.get("fim", False)
        h.ciclo_entrada = _c.get("entrada")
        h.ciclo_regime  = _c.get("regime")
        h.ciclo_score   = _c.get("score")
        h.ciclo_sessao  = _c.get("sessao")
        h.ciclo_parcial = _c.get("parcial", False)

        if pos_real and pos_real["LONG"]:
            p = dados.get("long") or {}
            h.posicao_long = PosicaoReal(
                "LONG", pos_real["LONG"]["preco"], pos_real["LONG"]["amt"],
                alv, p.get("timestamp_ms")
            )
            log.info(f"✅ {symbol} LONG recuperado — preco={h.posicao_long.preco_entrada}")

        if pos_real and pos_real["SHORT"]:
            p = dados.get("short") or {}
            h.posicao_short = PosicaoReal(
                "SHORT", pos_real["SHORT"]["preco"], pos_real["SHORT"]["amt"],
                alv, p.get("timestamp_ms")
            )
            log.info(f"✅ {symbol} SHORT recuperado — preco={h.posicao_short.preco_entrada}")

        if h.posicao_long and h.posicao_short:
            h.estado = HEDGE_COMPLETO
        elif h.posicao_long:
            h.estado = MEIA_LONG
        elif h.posicao_short:
            h.estado = MEIA_SHORT
        else:
            h.estado = AGUARDA
            # sem nenhuma perna aberta: TP/STOP restantes são órfãos → cancela
            log.info(f"🧹 {symbol} sem posição ao reiniciar — cancelando ordens órfãs")
            cancelar_todas_ordens(hydra.client, symbol)

        hydra.hedges[symbol] = h

    for symbol in list(hydra.hedges.keys()):
        pos_real = get_posicao_real(hydra.client, symbol)
        h        = hydra.hedges[symbol]
        if pos_real:
            if h.posicao_long and not pos_real["LONG"]:
                log.warning(f"👻 {symbol} LONG fantasma — limpa estado")
                h.posicao_long = None
            if h.posicao_short and not pos_real["SHORT"]:
                log.warning(f"👻 {symbol} SHORT fantasma — limpa estado")
                h.posicao_short = None

    log.info(f"✅ Estado recuperado — {len(hydra.hedges)} pares")

def _parse_pos(lista):
    """positionRisk (todas) -> {symbol: {"LONG":..., "SHORT":...}} só com posições abertas."""
    res = {}
    for p in lista:
        amt = float(p["positionAmt"])
        if amt == 0:
            continue
        lado = p.get("positionSide", "")
        d = res.setdefault(p["symbol"], {"LONG": None, "SHORT": None})
        info = {"amt": abs(amt), "preco": float(p["entryPrice"]),
                "pnl": float(p["unRealizedProfit"]), "ts": int(p.get("updateTime", 0) or 0)}
        if lado == "LONG" and amt > 0:
            d["LONG"] = info
        elif lado == "SHORT" and amt < 0:
            d["SHORT"] = info
    return res

def reconciliar_par(hydra, symbol, pos=None):
    """CAMADA CENTRAL: Binance é a verdade para posições confirmadas.

    IMPORTANTE:
    - adota posições reais ausentes no estado local;
    - corrige qty/preço quando ambos existem;
    - NÃO apaga uma perna local simplesmente porque uma leitura
      isolada da API veio sem essa perna.
    - a detecção de perna sumida fica com ciclo_par_real(), que
      preserva timestamp_ms e fecha a contabilidade do ciclo.
    """
    client = hydra.client
    h = hydra.hedges.get(symbol)
    if h is None:
        return False
    if pos is None:
        pos = get_posicao_real(client, symbol)
        if pos is None:
            return False          # falha de API: não decide nada
    alv = h.alavancagem
    mudou = False
    for lado, attr in (("LONG", "posicao_long"), ("SHORT", "posicao_short")):
        real  = pos.get(lado)
        atual = getattr(h, attr)
        if real and atual is None:
            setattr(h, attr, PosicaoReal(lado, real["preco"], real["amt"], alv, real.get("ts") or None))
            log.warning(f"🧭 {symbol} {lado} na Binance e ausente no estado (órfã) — adotada qty={real['amt']}")
            mudou = True
        elif real and atual and abs(real["amt"] - atual.qty) > max(1e-9, atual.qty * 1e-6):
            log.warning(f"🧭 {symbol} {lado} qty diferente (estado={atual.qty} Binance={real['amt']}) — ajustada")
            atual.qty = real["amt"]
            atual.preco_entrada = real["preco"]
            mudou = True
    if not mudou:
        return False
    if h.posicao_long and h.posicao_short:
        novo = HEDGE_COMPLETO
    elif h.posicao_long:
        novo = MEIA_LONG
    elif h.posicao_short:
        novo = MEIA_SHORT
    else:
        return True
    if novo != h.estado:
        log.warning(f"🧭 {symbol} estado {h.estado} → {novo} (reconciliado com a Binance)")
        h.estado = novo
        h.ciclos_reentrada = 0
        if novo == HEDGE_COMPLETO:
            h.roi_ancora = 0.0
            limpar_ordens_hedge(client, symbol)
        else:
            cancelar_todas_ordens(client, symbol)   # modo direcional: sem TP/STOP
    salvar_estado(hydra.hedges)
    return True

def reconciliar_global(hydra):
    """Reconciliação periódica de todos os pares conhecidos. Devolve os que ganharam posição gerida."""
    adotados = []
    try:
        todas = _parse_pos(api_retry(hydra.client.futures_position_information))
    except Exception as e:
        log.error(f"reconciliar_global: {e}")
        return adotados
    for sym in list(hydra.hedges.keys()):
        if reconciliar_par(hydra, sym, pos=todas.get(sym, {"LONG": None, "SHORT": None})):
            adotados.append(sym)
    avisados = getattr(hydra, "_avisados", set())
    for sym in todas:
        if sym not in hydra.hedges and sym not in avisados:
            avisados.add(sym)
            log.warning(f"🧭 {sym} tem posição na Binance mas não é gerida pelo Hydra — ignorada")
    hydra._avisados = avisados
    return adotados

def ciclo_par_real(hydra, symbol, preco, sl, ss, regime, sessao):
    client = hydra.client

    if symbol not in hydra.hedges:
        alv = hydra.alavancagens.get(symbol, 50)
        hydra.hedges[symbol] = HedgeReal(symbol, alv)

    h   = hydra.hedges[symbol]
    alv = h.alavancagem
    tam = hydra.tamanho_por_hedge()
    h.ciclos_reentrada += 1
    h.ultimo_score, h.ultimo_regime, h.ultimo_preco = (sl, ss), regime, preco
    MIN_ROI = min_roi_par(symbol, alv)
    if getattr(h, "conf_estado", None) != h.estado:
        h.conf = {}
        h.conf_estado = h.estado

    if h.estado in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG):
        h.ativo_antes = True
    elif getattr(h, "ativo_antes", False):
        pos_chk = get_posicao_real(client, symbol)
        if pos_chk is not None and not pos_chk["LONG"] and not pos_chk["SHORT"]:
            cancelar_todas_ordens(client, symbol)
            h.ativo_antes = False

    # ── AGUARDA / CONGELADO ──
    # Limite máximo de hedges simultâneos
    hedges_activos = sum(1 for hh in hydra.hedges.values()
                         if hh.estado in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG))
    if hedges_activos >= MAX_HEDGES and h.estado not in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG):
        h.estado = CONGELADO
        return

    if h.estado in (AGUARDA, CONGELADO):
        if sl < SCORE_ENTRADA and ss < SCORE_ENTRADA:
            h.estado = CONGELADO
            return

        if hydra.em_pausa():
            return

        banca_disp = hydra.banca_disponivel()
        if banca_disp < SALDO_MINIMO:
            log.warning(f"⚠️ Saldo insuficiente: {banca_disp:.4f} USDT")
            return

        if banca_disp < tam * 2 * 1.1:
            log.warning(f"⚠️ {symbol} saldo {banca_disp:.4f} < {tam*2*1.1:.4f} necessário")
            return

        if not margem_ok(hydra, symbol, tam * 2):
            return
        if not garantir_margem_isolada(client, symbol):
            return
        alv_op = alavancagem_para_notional(client, symbol, tam)
        if alv_op and alv_op != alv:
            log.info(f"⚙️ {symbol} alavancagem ajustada ao notional real: {alv}x → {alv_op}x")
            alv = alv_op
            h.alavancagem = alv
        if not set_alavancagem(client, symbol, alv):
            log.warning(f"⛔ {symbol} alavancagem {alv}x NÃO confirmada — não abre")
            return

        step = hydra.step_sizes.get(symbol) or get_step_size(client, symbol)
        hydra.step_sizes[symbol] = step
        qty  = arredondar_qty((tam * alv) / preco, step)

        _ok, _mot = validar_ordem(client, symbol, qty, preco) if qty > 0 else (True, "")
        if not _ok:
            log.warning(f"⛔ {symbol} ordem recusada pelos filtros: {_mot}")
            return
        if qty <= 0:
            log.warning(f"⚠️ {symbol} qty={qty} inválido")
            return

        log.info(f"🐉 {symbol} ABRE HEDGE | L={sl} S={ss} | {alv}x | qty={qty} | tam={tam:.4f} | regime={regime}")

        ts = int(time.time() * 1000)

        ordem_l = abrir_ordem(client, symbol, "LONG", qty)
        if not ordem_l:
            reconciliar_par(hydra, symbol)   # se a perna existir mesmo sem confirmação, adota
            return
        time.sleep(0.3)

        ordem_s = abrir_ordem(client, symbol, "SHORT", qty)
        if not ordem_s:
            log.error(f"❌ {symbol} SHORT falhou — desfazendo o LONG recém-aberto")
            if not fechar_e_confirmar(client, symbol, "LONG", qty):
                log.error(f"❌ {symbol} LONG NÃO confirmado fechado — reconciliando")
                reconciliar_par(hydra, symbol)
            return

        time.sleep(1)
        pos = get_posicao_real(client, symbol)
        if not pos or not (pos["LONG"] and pos["SHORT"]):
            log.warning(f"⚠️ {symbol} abertura não confirmou as 2 pernas — reconciliando")
            reconciliar_par(hydra, symbol)
            return

        preco_l = pos["LONG"]["preco"]
        preco_s = pos["SHORT"]["preco"]

        h.posicao_long  = PosicaoReal("LONG",  preco_l, pos["LONG"]["amt"], alv, ts)
        h.posicao_short = PosicaoReal("SHORT", preco_s, pos["SHORT"]["amt"], alv, ts)
        h.estado        = HEDGE_COMPLETO
        h.ciclos_reentrada = 0
        h.roi_ancora    = 0.0
        salvar_estado(hydra.hedges)

    # ── HEDGE COMPLETO ──
    elif h.estado == HEDGE_COMPLETO:
        pos = get_posicao_real(client, symbol)
        if not pos:
            return  # Proteção de API vazia

        limpar_ordens_hedge(client, symbol)

        long_sumiu  = bool(h.posicao_long)  and not pos["LONG"]
        short_sumiu = bool(h.posicao_short) and not pos["SHORT"]

        if long_sumiu and short_sumiu:
            pnl_l = get_pnl_real(client, symbol, "LONG",  h.posicao_long.timestamp_ms)
            pnl_s = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
            pnl_total = pnl_l + pnl_s
            log.warning(f"👻 {symbol} HEDGE INTEIRO sumiu (liquidação/externo) | LONG={pnl_l:+.4f} SHORT={pnl_s:+.4f}")
            registar = hydra.registar_win if pnl_total >= 0 else hydra.registar_loss
            registar(symbol, "HEDGE", pnl_total, "Liquidação/externo",
                      regime=regime, score=max(sl, ss), sessao=sessao,
                      entrada=h.posicao_long.preco_entrada, saida=preco,
                      timestamp_ms=h.posicao_long.timestamp_ms)
            h.posicao_long  = None
            h.posicao_short = None
            h.estado = AGUARDA
            salvar_estado(hydra.hedges)
            return

        if long_sumiu:
            pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
            log.warning(f"👻 {symbol} LONG sumiu (liquidação/externo) | pnl={pnl_real:+.4f}")
            registar = hydra.registar_win if pnl_real >= 0 else hydra.registar_loss
            registar(symbol, "LONG", pnl_real, "Liquidação/externo",
                      regime=regime, score=sl, sessao=sessao,
                      entrada=h.posicao_long.preco_entrada, saida=preco,
                      timestamp_ms=h.posicao_long.timestamp_ms)
            h.posicao_long = None
            h.estado = MEIA_SHORT
            salvar_estado(hydra.hedges)
            return

        if short_sumiu:
            pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
            log.warning(f"👻 {symbol} SHORT sumiu (liquidação/externo) | pnl={pnl_real:+.4f}")
            registar = hydra.registar_win if pnl_real >= 0 else hydra.registar_loss
            registar(symbol, "SHORT", pnl_real, "Liquidação/externo",
                      regime=regime, score=ss, sessao=sessao,
                      entrada=h.posicao_short.preco_entrada, saida=preco,
                      timestamp_ms=h.posicao_short.timestamp_ms)
            h.posicao_short = None
            h.estado = MEIA_LONG
            salvar_estado(hydra.hedges)
            return

        pnl_l = pos["LONG"]["pnl"]  if pos["LONG"]  else 0
        pnl_s = pos["SHORT"]["pnl"] if pos["SHORT"] else 0

        roi_l = (pnl_l / ((h.posicao_long.qty * h.posicao_long.preco_entrada) / alv)) if h.posicao_long else 0
        roi_s = (pnl_s / ((h.posicao_short.qty * h.posicao_short.preco_entrada) / alv)) if h.posicao_short else 0

        # Balança pesa SHORT (ss-sl >= MARGEM_BALANCA) + LONG lucrativo → solta LONG
        if confirmado(h, "bal_long", (ss - sl) >= MARGEM_BALANCA and roi_l >= MIN_ROI):
            ent_l, ts_l = h.posicao_long.preco_entrada, h.posicao_long.timestamp_ms
            log.info(f"⚖️ {symbol} BALANÇA SOLTA LONG | L={sl} S={ss} diff={ss-sl:.0f}pts | ROI LONG={roi_l*100:.1f}%")
            ordem = fechar_ordem(client, symbol, "LONG", h.posicao_long.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
                colocar_tp(client, symbol, "SHORT", h.posicao_short.qty, h.posicao_short.preco_entrada, alv)
                colocar_rebalance_limit(client, symbol, "SHORT", h.posicao_short.qty, h.posicao_short.preco_entrada, alv, roi_ancora=roi_s)
                h.roi_ancora       = roi_s
                h.posicao_long     = None
                h.estado           = MEIA_SHORT
                h.ciclos_reentrada = 0
                hydra.registar_win(symbol, "LONG", pnl_real, f"Balança diff={ss-sl:.0f}pts",
                                   regime=regime, score=sl, sessao=sessao,
                                   entrada=ent_l, saida=preco, timestamp_ms=ts_l)
                salvar_estado(hydra.hedges)
                return

        # Balança pesa LONG (sl-ss >= MARGEM_BALANCA) + SHORT lucrativo → solta SHORT
        if confirmado(h, "bal_short", (sl - ss) >= MARGEM_BALANCA and roi_s >= MIN_ROI):
            ent_s, ts_s = h.posicao_short.preco_entrada, h.posicao_short.timestamp_ms
            log.info(f"⚖️ {symbol} BALANÇA SOLTA SHORT | L={sl} S={ss} diff={sl-ss:.0f}pts | ROI SHORT={roi_s*100:.1f}%")
            ordem = fechar_ordem(client, symbol, "SHORT", h.posicao_short.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
                colocar_tp(client, symbol, "LONG", h.posicao_long.qty, h.posicao_long.preco_entrada, alv)
                colocar_rebalance_limit(client, symbol, "LONG", h.posicao_long.qty, h.posicao_long.preco_entrada, alv, roi_ancora=roi_l)
                h.roi_ancora        = roi_l
                h.posicao_short     = None
                h.estado            = MEIA_LONG
                h.ciclos_reentrada  = 0
                hydra.registar_win(symbol, "SHORT", pnl_real, f"Balança diff={sl-ss:.0f}pts",
                                   regime=regime, score=ss, sessao=sessao,
                                   entrada=ent_s, saida=preco, timestamp_ms=ts_s)
                salvar_estado(hydra.hedges)
                return

        c_dec_l = confirmado(h, "dec_long",  ss >= SCORE_DECISAO and roi_l >= MIN_ROI)
        c_dec_s = confirmado(h, "dec_short", sl >= SCORE_DECISAO and roi_s >= MIN_ROI)
        if ss >= SCORE_DECISAO:
            if c_dec_l:
                log.info(f"✂️ {symbol} SOLTA LONG | Score SHORT={ss} | ROI LONG={roi_l*100:.1f}%")
                ordem = fechar_ordem(client, symbol, "LONG", h.posicao_long.qty)
                if ordem:
                    time.sleep(1)
                    pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
                    h.lucro_embolsado += pnl_real
                    colocar_tp(client, symbol, "SHORT", h.posicao_short.qty, h.posicao_short.preco_entrada, alv)
                    colocar_rebalance_limit(client, symbol, "SHORT", h.posicao_short.qty, h.posicao_short.preco_entrada, alv, roi_ancora=roi_s)
                    h.roi_ancora = roi_s  # Armazena o ROI do short que ficou solto
                    hydra.registar_win(
                        symbol, "LONG", pnl_real, f"Score SHORT={ss}",
                        regime=regime, score=sl, sessao=sessao,
                        entrada=h.posicao_long.preco_entrada, saida=preco,
                        timestamp_ms=h.posicao_long.timestamp_ms
                    )
                    h.posicao_long  = None
                    h.estado        = MEIA_SHORT
                    h.ciclos_reentrada = 0
                    salvar_estado(hydra.hedges)

        elif sl >= SCORE_DECISAO:
            if c_dec_s:
                log.info(f"✂️ {symbol} SOLTA SHORT | Score LONG={sl} | ROI SHORT={roi_s*100:.1f}%")
                ordem = fechar_ordem(client, symbol, "SHORT", h.posicao_short.qty)
                if ordem:
                    time.sleep(1)
                    pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
                    h.lucro_embolsado += pnl_real
                    colocar_tp(client, symbol, "LONG", h.posicao_long.qty, h.posicao_long.preco_entrada, alv)
                    colocar_rebalance_limit(client, symbol, "LONG", h.posicao_long.qty, h.posicao_long.preco_entrada, alv, roi_ancora=roi_l)
                    h.roi_ancora = roi_l  # Armazena o ROI do long que ficou solto
                    hydra.registar_win(
                        symbol, "SHORT", pnl_real, f"Score LONG={sl}",
                        regime=regime, score=ss, sessao=sessao,
                        entrada=h.posicao_short.preco_entrada, saida=preco,
                        timestamp_ms=h.posicao_short.timestamp_ms
                    )
                    h.posicao_short = None
                    h.estado        = MEIA_LONG
                    h.ciclos_reentrada = 0
                    salvar_estado(hydra.hedges)

    # ── MEIA SHORT ──
    elif h.estado == MEIA_SHORT:
        pos = get_posicao_real(client, symbol)
        if pos is None:
            return  # FIX: API falhou, nao decide (evita WIN falso e cancelar TP/STOP)

        # LIMIT rebalance executado → LONG abriu → HEDGE_COMPLETO
        if pos and pos["LONG"] and not h.posicao_long:
            log.info(f"🔄 {symbol} STOP LONG executado → HEDGE_COMPLETO")
            cancelar_todas_ordens(client, symbol)
            preco_l = pos["LONG"]["preco"]
            qty_l   = pos["LONG"]["amt"]
            h.posicao_long     = PosicaoReal("LONG", preco_l, qty_l, alv)
            h.estado           = HEDGE_COMPLETO
            h.ciclos_reentrada = 0
            h.roi_ancora       = 0.0
            salvar_estado(hydra.hedges)
            return

        if not pos or not pos["SHORT"]:
            pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
            if pnl_real >= 0:
                log.info(f"🏆 {symbol} TP SHORT EXECUTADO → VITÓRIA +{pnl_real:.4f}")
                hydra.registar_win(symbol, "SHORT", pnl_real, "TP Binance executado")
            else:
                log.info(f"❌ {symbol} SHORT sumiu com prejuízo {pnl_real:.4f}")
                hydra.registar_loss(symbol, "SHORT", pnl_real, "Fechado com prejuízo")
            h.posicao_short    = None
            h.estado           = CONGELADO
            h.ciclos_reentrada = 0
            cancelar_todas_ordens(client, symbol)
            salvar_estado(hydra.hedges)
            return

        pnl_s = pos["SHORT"]["pnl"]
        roi_s = (pnl_s / ((h.posicao_short.qty * h.posicao_short.preco_entrada) / alv)) if h.posicao_short.qty > 0 else 0

        # Score confirma SHORT >= 75 + ROI >= 10% → fecha
        # POLÍTICA: decisão por SINAL (score) exige CONFIRMA_CICLOS; proteções objetivas (TP/ROI alvo, rede, STOP) são imediatas
        if confirmado(h, "fecha_short", ss >= SCORE_DECISAO and roi_s >= MIN_ROI):
            log.info(f"✂️ {symbol} MEIA SHORT confirmada | Score SHORT={ss} | ROI={roi_s*100:.1f}%")
            ordem = fechar_ordem(client, symbol, "SHORT", h.posicao_short.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
                cancelar_todas_ordens(client, symbol)
                h.posicao_short    = None
                h.estado           = CONGELADO
                h.ciclos_reentrada = 0
                hydra.registar_win(symbol, "SHORT", pnl_real)
                salvar_estado(hydra.hedges)
            return

        # VITÓRIA — ROI >= 15% fecha imediatamente
        if roi_s >= alvo_tp(symbol, alv):
            log.info(f"🏆 {symbol} VITÓRIA SHORT ROI={roi_s*100:.1f}% → fecha → CONGELADO")
            ordem = fechar_ordem(client, symbol, "SHORT", h.posicao_short.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
                cancelar_todas_ordens(client, symbol)
                h.posicao_short    = None
                h.estado           = CONGELADO
                h.ciclos_reentrada = 0
                hydra.registar_win(symbol, "SHORT", pnl_real)
                salvar_estado(hydra.hedges)
            return

        # Regra 1: Reabertura via Score com Margem de MARGEM_BALANCA pontos
        if confirmado(h, "inv_short", sl >= (ss + MARGEM_BALANCA) and h.ciclos_reentrada >= COOLDOWN_REENTRADA):

            if roi_s >= MIN_ROI:
                log.info(f"🎯 {symbol} INVERSÃO C/ LUCRO | Score LONG={sl} vs SHORT={ss} | ROI SHORT={roi_s*100:.1f}%")
                ordem = fechar_ordem(client, symbol, "SHORT", h.posicao_short.qty)
                if ordem:
                    time.sleep(1)
                    pnl_real = get_pnl_real(client, symbol, "SHORT", h.posicao_short.timestamp_ms)
                    hydra.registar_win(
                        symbol, "SHORT", pnl_real, f"Inversão L={sl}",
                        regime=regime, score=sl, sessao=sessao,
                        entrada=h.posicao_short.preco_entrada, saida=preco,
                        timestamp_ms=h.posicao_short.timestamp_ms
                    )
                    cancelar_todas_ordens(client, symbol)
                    qty = h.posicao_short.qty
                    h.posicao_short = None

                    log.info(f"🔄 {symbol} REABRE HEDGE COMPLETO (Reinício do Ciclo)")
                    ts = int(time.time() * 1000)

                    if not abrir_ordem(client, symbol, "LONG", qty):
                        h.estado = CONGELADO
                        salvar_estado(hydra.hedges)
                    else:
                        time.sleep(0.3)
                        if not abrir_ordem(client, symbol, "SHORT", qty):
                            log.error(f"❌ {symbol} Inversão: SHORT falhou — fecha o LONG recém-aberto")
                            if not fechar_e_confirmar(client, symbol, "LONG", qty):
                                reconciliar_par(hydra, symbol)
                                return
                            cancelar_todas_ordens(client, symbol)
                            h.estado = CONGELADO
                            h.ciclos_reentrada = 0
                            salvar_estado(hydra.hedges)
                            return
                        time.sleep(1)
                        pos2 = get_posicao_real(client, symbol)
                        if not (pos2 and pos2["LONG"] and pos2["SHORT"]):
                            log.warning(f"⚠️ {symbol} inversão não confirmou as 2 pernas — reconciliando")
                            reconciliar_par(hydra, symbol)
                            return
                        if pos2:
                            preco_l = pos2["LONG"]["preco"]
                            preco_s = pos2["SHORT"]["preco"]

                            h.posicao_long  = PosicaoReal("LONG", preco_l, pos2["LONG"]["amt"], alv, ts)
                            h.posicao_short = PosicaoReal("SHORT", preco_s, pos2["SHORT"]["amt"], alv, ts)
                            cancelar_todas_ordens(client, symbol)
                            h.estado = HEDGE_COMPLETO
                            h.ciclos_reentrada = 0
                            h.roi_ancora = 0.0
                            salvar_estado(hydra.hedges)

            else:
                log.info(f"🛡️ {symbol} REBALANCEAMENTO | Score LONG={sl} vs SHORT={ss} | ROI SHORT={roi_s*100:.1f}%")
                step  = hydra.step_sizes.get(symbol) or get_step_size(client, symbol)
                qty   = arredondar_qty((tam * alv) / preco, step)
                banca = hydra.banca_disponivel()

                qty = h.posicao_short.qty
                if banca >= (qty * preco / alv) * 1.1 and margem_ok(hydra, symbol, qty * preco / alv):
                    ordem = abrir_ordem(client, symbol, "LONG", qty)
                    if ordem:
                        time.sleep(1)
                        pos2 = get_posicao_real(client, symbol)
                        if pos2 and pos2["LONG"]:
                            preco_l = pos2["LONG"]["preco"]
                            cancelar_todas_ordens(client, symbol)
                            h.posicao_long  = PosicaoReal("LONG", preco_l, qty, alv)
                            h.estado        = HEDGE_COMPLETO
                            h.ciclos_reentrada = 0
                            h.roi_ancora    = 0.0
                            salvar_estado(hydra.hedges)

        # Regra 2: Rede de Segurança Relativa (-30% a partir do ROI âncora)
        if roi_s < (h.roi_ancora - REDE_SEGURANCA_ROI) and h.ciclos_reentrada >= COOLDOWN_REENTRADA:
            log.info(f"🔄 {symbol} SHORT sangrou além da rede (Âncora: {h.roi_ancora*100:.1f}% | Atual: {roi_s*100:.1f}%) → reabre LONG")
            disp = hydra.banca_disponivel()
            qty  = h.posicao_short.qty
            if disp >= (qty * preco / alv) * 1.1 and margem_ok(hydra, symbol, qty * preco / alv):
                if abrir_ordem(client, symbol, "LONG", qty):
                    time.sleep(1)
                    pos2 = get_posicao_real(client, symbol)
                    if pos2 and pos2["LONG"]:
                        preco_l = pos2["LONG"]["preco"]
                        cancelar_todas_ordens(client, symbol)
                        h.posicao_long     = PosicaoReal("LONG", preco_l, qty, alv)
                        h.estado           = HEDGE_COMPLETO
                        h.ciclos_reentrada = 0
                        h.roi_ancora       = 0.0
                        salvar_estado(hydra.hedges)

    # ── MEIA LONG ──
    elif h.estado == MEIA_LONG:
        pos = get_posicao_real(client, symbol)
        if pos is None:
            return  # FIX: API falhou, nao decide (evita WIN falso e cancelar TP/STOP)

        # LIMIT rebalance executado → SHORT abriu → HEDGE_COMPLETO
        if pos and pos["SHORT"] and not h.posicao_short:
            log.info(f"🔄 {symbol} STOP SHORT executado → HEDGE_COMPLETO")
            cancelar_todas_ordens(client, symbol)
            preco_s = pos["SHORT"]["preco"]
            qty_s   = pos["SHORT"]["amt"]
            h.posicao_short    = PosicaoReal("SHORT", preco_s, qty_s, alv)
            h.estado           = HEDGE_COMPLETO
            h.ciclos_reentrada = 0
            h.roi_ancora       = 0.0
            salvar_estado(hydra.hedges)
            return

        if not pos or not pos["LONG"]:
            pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
            if pnl_real >= 0:
                log.info(f"🏆 {symbol} TP LONG EXECUTADO → VITÓRIA +{pnl_real:.4f}")
                hydra.registar_win(symbol, "LONG", pnl_real, "TP Binance executado")
            else:
                log.info(f"❌ {symbol} LONG sumiu com prejuízo {pnl_real:.4f}")
                hydra.registar_loss(symbol, "LONG", pnl_real, "Fechado com prejuízo")
            h.posicao_long     = None
            h.estado           = CONGELADO
            h.ciclos_reentrada = 0
            cancelar_todas_ordens(client, symbol)
            salvar_estado(hydra.hedges)
            return

        pnl_l = pos["LONG"]["pnl"]
        roi_l = (pnl_l / ((h.posicao_long.qty * h.posicao_long.preco_entrada) / alv)) if h.posicao_long.qty > 0 else 0

        # Score confirma LONG >= 75 + ROI >= 10% → fecha
        if confirmado(h, "fecha_long", sl >= SCORE_DECISAO and roi_l >= MIN_ROI):
            log.info(f"✂️ {symbol} MEIA LONG confirmada | Score LONG={sl} | ROI={roi_l*100:.1f}%")
            ordem = fechar_ordem(client, symbol, "LONG", h.posicao_long.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
                cancelar_todas_ordens(client, symbol)
                h.posicao_long     = None
                h.estado           = CONGELADO
                h.ciclos_reentrada = 0
                hydra.registar_win(symbol, "LONG", pnl_real)
                salvar_estado(hydra.hedges)
            return

        # VITÓRIA — ROI >= 15% fecha imediatamente
        if roi_l >= alvo_tp(symbol, alv):
            log.info(f"🏆 {symbol} VITÓRIA LONG ROI={roi_l*100:.1f}% → fecha → CONGELADO")
            ordem = fechar_ordem(client, symbol, "LONG", h.posicao_long.qty)
            if ordem:
                time.sleep(1)
                pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
                cancelar_todas_ordens(client, symbol)
                h.posicao_long     = None
                h.estado           = CONGELADO
                h.ciclos_reentrada = 0
                hydra.registar_win(symbol, "LONG", pnl_real)
                salvar_estado(hydra.hedges)
            return

        # Regra 1: Reabertura via Score com Margem de MARGEM_BALANCA pontos
        if confirmado(h, "inv_long", ss >= (sl + MARGEM_BALANCA) and h.ciclos_reentrada >= COOLDOWN_REENTRADA):

            if roi_l >= MIN_ROI:
                log.info(f"🎯 {symbol} INVERSÃO C/ LUCRO | Score SHORT={ss} vs LONG={sl} | ROI LONG={roi_l*100:.1f}%")
                ordem = fechar_ordem(client, symbol, "LONG", h.posicao_long.qty)
                if ordem:
                    time.sleep(1)
                    pnl_real = get_pnl_real(client, symbol, "LONG", h.posicao_long.timestamp_ms)
                    hydra.registar_win(
                        symbol, "LONG", pnl_real, f"Inversão S={ss}",
                        regime=regime, score=ss, sessao=sessao,
                        entrada=h.posicao_long.preco_entrada, saida=preco,
                        timestamp_ms=h.posicao_long.timestamp_ms
                    )
                    cancelar_todas_ordens(client, symbol)
                    qty = h.posicao_long.qty
                    h.posicao_long = None

                    log.info(f"🔄 {symbol} REABRE HEDGE COMPLETO (Reinício do Ciclo)")
                    ts = int(time.time() * 1000)

                    if not abrir_ordem(client, symbol, "SHORT", qty):
                        h.estado = CONGELADO
                        salvar_estado(hydra.hedges)
                    else:
                        time.sleep(0.3)
                        if not abrir_ordem(client, symbol, "LONG", qty):
                            log.error(f"❌ {symbol} Inversão: LONG falhou — fecha o SHORT recém-aberto")
                            if not fechar_e_confirmar(client, symbol, "SHORT", qty):
                                reconciliar_par(hydra, symbol)
                                return
                            cancelar_todas_ordens(client, symbol)
                            h.estado = CONGELADO
                            h.ciclos_reentrada = 0
                            salvar_estado(hydra.hedges)
                            return
                        time.sleep(1)
                        pos2 = get_posicao_real(client, symbol)
                        if not (pos2 and pos2["LONG"] and pos2["SHORT"]):
                            log.warning(f"⚠️ {symbol} inversão não confirmou as 2 pernas — reconciliando")
                            reconciliar_par(hydra, symbol)
                            return
                        if pos2:
                            preco_l = pos2["LONG"]["preco"]
                            preco_s = pos2["SHORT"]["preco"]

                            h.posicao_long  = PosicaoReal("LONG", preco_l, pos2["LONG"]["amt"], alv, ts)
                            h.posicao_short = PosicaoReal("SHORT", preco_s, pos2["SHORT"]["amt"], alv, ts)
                            cancelar_todas_ordens(client, symbol)
                            h.estado = HEDGE_COMPLETO
                            h.ciclos_reentrada = 0
                            h.roi_ancora = 0.0
                            salvar_estado(hydra.hedges)

            else:
                log.info(f"🛡️ {symbol} REBALANCEAMENTO | Score SHORT={ss} vs LONG={sl} | ROI LONG={roi_l*100:.1f}%")
                step  = hydra.step_sizes.get(symbol) or get_step_size(client, symbol)
                qty   = arredondar_qty((tam * alv) / preco, step)
                banca = hydra.banca_disponivel()

                qty = h.posicao_long.qty
                if banca >= (qty * preco / alv) * 1.1 and margem_ok(hydra, symbol, qty * preco / alv):
                    ordem = abrir_ordem(client, symbol, "SHORT", qty)
                    if ordem:
                        time.sleep(1)
                        pos2 = get_posicao_real(client, symbol)
                        if pos2 and pos2["SHORT"]:
                            preco_s = pos2["SHORT"]["preco"]
                            cancelar_todas_ordens(client, symbol)
                            h.posicao_short = PosicaoReal("SHORT", preco_s, qty, alv)
                            h.estado        = HEDGE_COMPLETO
                            h.ciclos_reentrada = 0
                            h.roi_ancora    = 0.0
                            salvar_estado(hydra.hedges)

        # Regra 2: Rede de Segurança Relativa (-30% a partir do ROI âncora)
        if roi_l < (h.roi_ancora - REDE_SEGURANCA_ROI) and h.ciclos_reentrada >= COOLDOWN_REENTRADA:
            log.info(f"🔄 {symbol} LONG sangrou além da rede (Âncora: {h.roi_ancora*100:.1f}% | Atual: {roi_l*100:.1f}%) → reabre SHORT")
            disp = hydra.banca_disponivel()
            qty  = h.posicao_long.qty
            if disp >= (qty * preco / alv) * 1.1 and margem_ok(hydra, symbol, qty * preco / alv):
                if abrir_ordem(client, symbol, "SHORT", qty):
                    time.sleep(1)
                    pos2 = get_posicao_real(client, symbol)
                    if pos2 and pos2["SHORT"]:
                        preco_s = pos2["SHORT"]["preco"]
                        cancelar_todas_ordens(client, symbol)
                        h.posicao_short    = PosicaoReal("SHORT", preco_s, qty, alv)
                        h.estado           = HEDGE_COMPLETO
                        h.ciclos_reentrada = 0
                        h.roi_ancora       = 0.0
                        salvar_estado(hydra.hedges)

# ═════════════════════════════════════════════════════════════
#  MODO DIRECIONAL — confia só na BALANÇA (sem TP, sem STOP)
#  • entra só na perna do lado mais pesado
#  • balança vira: perna lucrando → fecha e abre o lado oposto
#                  perna negativa → abre o oposto (hedge) e espera
# ═════════════════════════════════════════════════════════════

def _roi_dir(p_real, leg, alv):
    base = (leg.qty * leg.preco_entrada) / alv
    return (p_real["pnl"] / base) if base > 0 else 0.0

def _abrir_perna_dir(hydra, h, symbol, lado, preco, qty=None):
    """Abre UMA perna. qty=None -> tamanho normal (entrada/virada). qty dado -> cobre perna existente (hedge)."""
    client = hydra.client
    tam = hydra.tamanho_por_hedge()
    if qty is None:
        if hydra.banca_disponivel() < max(SALDO_MINIMO, tam * 1.1):
            log.warning(f"⚠️ {symbol} saldo insuficiente p/ abrir {lado}")
            return None
        if not margem_ok(hydra, symbol, tam):
            return None
        if not garantir_margem_isolada(client, symbol):
            return None
        alv_op = alavancagem_para_notional(client, symbol, tam)
        if alv_op and alv_op != h.alavancagem:
            log.info(f"⚙️ {symbol} alavancagem ajustada: {h.alavancagem}x → {alv_op}x")
            h.alavancagem = alv_op
        if not set_alavancagem(client, symbol, h.alavancagem):
            log.warning(f"⛔ {symbol} alavancagem {h.alavancagem}x NÃO confirmada — não abre")
            return None
        step = hydra.step_sizes.get(symbol) or get_step_size(client, symbol)
        hydra.step_sizes[symbol] = step
        qty = arredondar_qty((tam * h.alavancagem) / preco, step)
        if qty <= 0:
            log.warning(f"⚠️ {symbol} qty={qty} inválido")
            return None
        ok, mot = validar_ordem(client, symbol, qty, preco)
        if not ok:
            log.warning(f"⛔ {symbol} ordem recusada pelos filtros: {mot}")
            return None
    else:
        if not margem_ok(hydra, symbol, qty * preco / h.alavancagem):
            return None
    ts = int(time.time() * 1000)
    if not abrir_ordem(client, symbol, lado, qty):
        reconciliar_par(hydra, symbol)
        return None
    time.sleep(0.5)
    pos = get_posicao_real(client, symbol)
    real = pos.get(lado) if pos else None
    if not real:
        reconciliar_par(hydra, symbol)
        return None
    return PosicaoReal(lado, real["preco"], real["amt"], h.alavancagem, ts)

def _fechar_perna_dir(hydra, h, symbol, lado, motivo, regime, score, sessao, preco):
    """Fecha a perna, contabiliza e limpa o estado. Devolve o PnL ou None se não confirmou."""
    client = hydra.client
    leg = h.posicao_long if lado == "LONG" else h.posicao_short
    if not leg:
        return None
    if not fechar_ordem(client, symbol, lado, leg.qty):
        return None
    if not REENTRA_CHOQUE:
        h.bloq_choque = True
    time.sleep(0.5)
    pnl = get_pnl_real(client, symbol, lado, leg.timestamp_ms)
    reg = hydra.registar_win if pnl >= 0 else hydra.registar_loss
    reg(symbol, lado, pnl, motivo, regime=regime, score=score, sessao=sessao,
        entrada=leg.preco_entrada, saida=preco, timestamp_ms=leg.timestamp_ms)
    if lado == "LONG":
        h.posicao_long = None
    else:
        h.posicao_short = None
    return pnl

def _perna_sumiu_dir(hydra, h, symbol, lado, regime, score, sessao, preco):
    """Perna sumiu da carteira sem ordem do bot (liquidação/externo)."""
    leg = h.posicao_long if lado == "LONG" else h.posicao_short
    pnl = get_pnl_real(hydra.client, symbol, lado, leg.timestamp_ms)
    log.warning(f"👻 {symbol} {lado} sumiu (liquidação/externo) | pnl={pnl:+.4f}")
    reg = hydra.registar_win if pnl >= 0 else hydra.registar_loss
    reg(symbol, lado, pnl, "Liquidação/externo", regime=regime, score=score, sessao=sessao,
        entrada=leg.preco_entrada, saida=preco, timestamp_ms=leg.timestamp_ms)
    if lado == "LONG":
        h.posicao_long = None
    else:
        h.posicao_short = None

def _estado_pelas_pernas(h):
    if h.posicao_long and h.posicao_short:
        return HEDGE_COMPLETO
    if h.posicao_long:
        return MEIA_LONG
    if h.posicao_short:
        return MEIA_SHORT
    return CONGELADO

def alvo_tp_atr(symbol, alv):
    atr = ATR_PCT.get(symbol)
    if not atr or atr != atr:
        return TP_ATR_MIN_ROI
    alvo = TP_ATR_K * atr * alv + 2 * FEES_PCT * alv
    return min(TP_ATR_MAX_ROI, max(TP_ATR_MIN_ROI, alvo))


def _pnl_hedge_liquido(h, pos):
    """PnL somado das 2 pernas (lido da corretora) menos o custo estimado de fechar as duas."""
    pnl = pos["LONG"]["pnl"] + pos["SHORT"]["pnl"]
    custo = (h.posicao_long.qty * h.posicao_long.preco_entrada
             + h.posicao_short.qty * h.posicao_short.preco_entrada) * FEES_PCT
    return pnl - custo

def _fechar_hedge_dir(hydra, h, symbol, motivo):
    """Fecha as 2 pernas de um hedge, poe o par em cooldown e atualiza o estado."""
    regime = getattr(h, "ultimo_regime", None)
    score  = max(getattr(h, "ultimo_score", (0, 0)))
    preco  = getattr(h, "ultimo_preco", 0)
    for lado in ("LONG", "SHORT"):
        if _fechar_perna_dir(hydra, h, symbol, lado, motivo, regime, score, get_sessao(), preco) is None:
            h.estado = _estado_pelas_pernas(h)
            salvar_estado(hydra.hedges)
            return False
    h.estado = CONGELADO
    h.ciclos_reentrada = 0
    h.roi_ancora = 0.0
    h.cooldown_ate = time.time() + COOLDOWN_TP_MIN * 60
    salvar_estado(hydra.hedges)
    return True

def _lucro_total_realizado(hydra):
    """Lucro realizado acumulado da carteira (saldo atual - saldo base); nunca negativo.
    Real: a base e a banca registrada na 1a execucao (persistida no estado), equivalente ao saldo_inicial da simulacao."""
    base = getattr(hydra, "banca_base", None) or hydra.banca_inicial
    return max(0.0, hydra.banca_total() - base)

def checar_desarme_hedges(hydra, lucro_disponivel=0.0):
    """
    1) Fecha HEDGE se o PnL somado (LONG + SHORT), ja descontado o custo de fechar, for positivo.
    2) Com lucro de TP recente, usa ate SUBSIDIO_FRACAO dele para fechar hedges negativos
       (do pior para o menos ruim, o que couber).
    2b) Se o lucro do TP nao cobre nenhum hedge, completa com ate SUBSIDIO_FRACAO_TOTAL do
        lucro total realizado da carteira.
    """
    client = hydra.client
    candidatos = []
    for symbol, h in list(hydra.hedges.items()):
        if h.estado != HEDGE_COMPLETO or not (h.posicao_long and h.posicao_short):
            continue
        pos = get_posicao_real(client, symbol)
        if not pos or not (pos["LONG"] and pos["SHORT"]):
            continue   # API falhou ou perna sumiu: nao decide aqui
        net = _pnl_hedge_liquido(h, pos)
        if net > DESARME_MIN_LUCRO:
            log.info(f"🧹 {symbol} DESARME COMBINADO | PnL liquido={net:+.4f} USDT -> fechando ambos")
            _fechar_hedge_dir(hydra, h, symbol, "Desarme HEDGE")
            continue
        candidatos.append((net, symbol, h))

    if lucro_disponivel <= SUBSIDIO_MIN_LUCRO:
        return
    orc_tp  = lucro_disponivel * SUBSIDIO_FRACAO
    orc_tot = _lucro_total_realizado(hydra) * SUBSIDIO_FRACAO_TOTAL
    while True:
        neg = [c for c in candidatos if c[0] < 0]
        cabem = [c for c in neg if abs(c[0]) <= orc_tp]                 # 1o: so com o lucro do TP
        if not cabem:
            cabem = [c for c in neg if abs(c[0]) <= orc_tp + orc_tot]   # 2o: completa com o lucro total
        if not cabem:
            break
        net, symbol, h = min(cabem, key=lambda c: c[0])                 # o pior que cabe
        candidatos = [c for c in candidatos if c[1] != symbol]
        custo = abs(net)
        do_tp = min(orc_tp, custo)
        do_total = custo - do_tp
        log.info(f"🩸 {symbol} SUBSIDIO DE HEDGE | pagando {net:+.4f} USDT | do lucro do TP {do_tp:.4f} + do lucro total {do_total:.4f}")
        if _fechar_hedge_dir(hydra, h, symbol, "Subsidio HEDGE"):
            orc_tp  -= do_tp
            orc_tot -= do_total

# ═════════════════════════════════════════════════════════════
#  COLHEITA GLOBAL DE LUCRO
# ═════════════════════════════════════════════════════════════
COLHEITA_PCT = 0.035   # PnL aberto SOMADO que dispara a colheita, em % da banca (3.5% de 100 USDT = 3.50)

def colher_lucro_global(hydra):
    """PnL aberto somado >= COLHEITA_PCT x banca: fecha so as pernas positivas cujo lucro paga as taxas
    (abrir + fechar + slippage). As negativas, e as positivas que nao pagam taxa, continuam abertas."""
    client = hydra.client
    ativos = {sym: h for sym, h in hydra.hedges.items()
              if h.estado in (HEDGE_COMPLETO, MEIA_LONG, MEIA_SHORT)}
    if not ativos:
        return
    try:
        todas = _parse_pos(api_retry(client.futures_position_information))
    except Exception as e:
        log.error(f"colher_lucro_global: {e}")
        return
    total = 0.0
    for sym in ativos:
        for lado in ("LONG", "SHORT"):
            real = (todas.get(sym) or {}).get(lado)
            if real:
                total += real["pnl"]
    minimo = COLHEITA_PCT * hydra.banca_total()
    if total < minimo:
        return
    candidatas = []
    for sym, h in ativos.items():
        for lado in ("LONG", "SHORT"):
            real = (todas.get(sym) or {}).get(lado)
            leg = h.posicao_long if lado == "LONG" else h.posicao_short
            if not real or not leg:
                continue
            custo = real["amt"] * real["preco"] * (2 * FEES_PCT + SLIPPAGE_PCT)
            if real["pnl"] > custo:
                candidatas.append((sym, h, lado, real["pnl"], custo))
    if not candidatas:
        return
    log.info(f"💰 COLHEITA GLOBAL | PnL aberto {total:+.4f} >= {minimo:.4f} ({COLHEITA_PCT*100:.1f}% da banca) | fechando {len(candidatas)} perna(s) positivas que pagam taxa")
    fechou = 0
    for sym, h, lado, pnl_aberto, custo in candidatas:
        leg = h.posicao_long if lado == "LONG" else h.posicao_short
        if not leg:
            continue
        pnl = _fechar_perna_dir(hydra, h, sym, lado, "Colheita global",
                                getattr(h, "ultimo_regime", None),
                                max(getattr(h, "ultimo_score", (0, 0))),
                                get_sessao(), getattr(h, "ultimo_preco", 0))
        if pnl is None:
            continue
        fechou += 1
        h.estado = _estado_pelas_pernas(h)
        h.ciclos_reentrada = 0
        h.roi_ancora = 0.0
        if h.estado == CONGELADO:
            h.cooldown_ate = time.time() + COOLDOWN_TP_MIN * 60
        log.info(f"💰 {sym} {lado} colhida | PnL aberto {pnl_aberto:+.4f} (custo {custo:.4f}) | liquido {pnl:+.4f}")
    if fechou:
        salvar_estado(hydra.hedges)

def _trava_pct(symbol, leg):
    """Distância da trava em % de preço: TRAVA_ATR_K x ATR(5m) da ENTRADA, limitada a [MIN, MAX].
    Com TRAVA_ROI definido: trava fixa em ROI (preço = TRAVA_ROI / alavancagem)."""
    if TRAVA_ROI:
        return TRAVA_ROI / max(1, int(getattr(leg, "alavancagem", 1) or 1))
    atr = getattr(leg, "atr_entrada", None) or ATR_PCT.get(symbol)
    if not atr or atr != atr:
        return TRAVA_MAX_PCT
    return min(TRAVA_MAX_PCT, max(TRAVA_MIN_PCT, TRAVA_ATR_K * atr))

def _mov_contra(lado, entrada, preco):
    """Quanto o preço andou CONTRA a perna, em fração (0.01 = 1%)."""
    if not entrada or not preco:
        return 0.0
    return (entrada - preco) / entrada if lado == "LONG" else (preco - entrada) / entrada

def _cortar_perna(hydra, h, symbol, lado, motivo, regime, score, sessao, preco):
    """Fecha só a perna perdedora (sem hedge), congela o par e aplica o cooldown."""
    pnl = _fechar_perna_dir(hydra, h, symbol, lado, motivo, regime, score, sessao, preco)
    if pnl is None:
        return None
    h.estado = CONGELADO
    h.ciclos_reentrada = 0
    h.roi_ancora = 0.0
    h.cooldown_ate = time.time() + COOLDOWN_TP_MIN * 60
    salvar_estado(hydra.hedges)
    return pnl

def ciclo_direcional(hydra, symbol, preco, sl, ss, regime, sessao):
    client = hydra.client
    if symbol not in hydra.hedges:
        hydra.hedges[symbol] = HedgeReal(symbol, hydra.alavancagens.get(symbol, LEV_PAPER))
    h = hydra.hedges[symbol]
    h.ciclos_reentrada += 1
    h.ultimo_score, h.ultimo_regime, h.ultimo_preco = (sl, ss), regime, preco
    if max(sl, ss) < SCORE_ENTRADA:
        h.bloq_choque = False          # sinal apagou: pode entrar no próximo choque
    if getattr(h, "conf_estado", None) != h.estado:
        h.conf = {}
        h.conf_estado = h.estado

    ativos = sum(1 for hh in hydra.hedges.values()
                 if hh.estado in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG))
    if ativos >= MAX_HEDGES and h.estado not in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG):
        h.estado = CONGELADO
        return

    # ── SEM POSIÇÃO: entra só no lado mais pesado ──
    if h.estado in (AGUARDA, CONGELADO):
        if max(sl, ss) < SCORE_ENTRADA or abs(sl - ss) < DIF_ENTRADA:
            h.estado = CONGELADO
            return
        if hydra.em_pausa():
            return
        _h = hydra.hedges.get(symbol)
        if _h and time.time() < getattr(_h, "cooldown_ate", 0):
            return   # cooldown pos-TP: nao reentra ainda
        if not REENTRA_CHOQUE and getattr(h, "bloq_choque", False):
            return   # já operou este choque: espera o sinal apagar
        lado = "LONG" if sl > ss else "SHORT"
        leg = _abrir_perna_dir(hydra, h, symbol, lado, preco)
        if not leg:
            return
        if lado == "LONG":
            h.posicao_long = leg
            h.estado = MEIA_LONG
        else:
            h.posicao_short = leg
            h.estado = MEIA_SHORT
        h.ciclos_reentrada = 0
        h.roi_ancora = 0.0
        leg.atr_entrada = ATR_PCT.get(symbol)
        log.info(f"🎯 {symbol} ENTRA {lado} DIRECIONAL | L={sl} S={ss} | {h.alavancagem}x | qty={leg.qty} | regime={regime}"
                 + (f" | trava {_trava_pct(symbol, leg)*100:.2f}%" if TRAVA_ATR else ""))
        if MEDIDOR is not None:
            MEDIDOR.registrar(symbol, lado, leg.preco_entrada, h.alavancagem, sl, ss, regime, "entrada")
        salvar_estado(hydra.hedges)
        return

    # ── UMA PERNA: fica até a balança virar ──
    if h.estado in (MEIA_LONG, MEIA_SHORT):
        lado   = "LONG" if h.estado == MEIA_LONG else "SHORT"
        oposto = "SHORT" if lado == "LONG" else "LONG"
        leg    = h.posicao_long if lado == "LONG" else h.posicao_short
        if leg is None:
            h.estado = _estado_pelas_pernas(h)
            return
        pos = get_posicao_real(client, symbol)
        if pos is None:
            return   # API falhou: não decide
        perna_oposta_estado = h.posicao_short if oposto == "SHORT" else h.posicao_long
        if pos[oposto] and perna_oposta_estado is None:
            reconciliar_par(hydra, symbol, pos=pos)   # apareceu perna oposta: adota
            return
        if not pos[lado]:
            _perna_sumiu_dir(hydra, h, symbol, lado, regime, (sl if lado == "LONG" else ss), sessao, preco)
            h.estado = _estado_pelas_pernas(h)
            h.ciclos_reentrada = 0
            salvar_estado(hydra.hedges)
            return

        roi = _roi_dir(pos[lado], leg, h.alavancagem)
        alvo_atr = alvo_tp_atr(symbol, h.alavancagem)
        if not SEM_TP and roi >= alvo_atr:
            log.info(f"🏆 {symbol} TP ATR {lado} | ROI={roi*100:+.1f}% >= alvo {alvo_atr*100:.0f}% → fecha e cooldown {COOLDOWN_TP_MIN}min")
            pnl = _fechar_perna_dir(hydra, h, symbol, lado, f"TP ATR roi={roi*100:.0f}%",
                                    regime, (sl if lado == "LONG" else ss), sessao, preco)
            if pnl is not None:
                h.estado = CONGELADO
                h.ciclos_reentrada = 0
                h.roi_ancora = 0.0
                h.cooldown_ate = time.time() + COOLDOWN_TP_MIN * 60
                salvar_estado(hydra.hedges)
                if pnl > 0:
                    checar_desarme_hedges(hydra, lucro_disponivel=pnl)
            return
        if SAIDA_TEMPO_H and time.time() * 1000 - leg.timestamp_ms >= SAIDA_TEMPO_H * 3600 * 1000:
            log.info(f"⏱️ {symbol} SAÍDA POR TEMPO {lado} | {SAIDA_TEMPO_H}h | ROI={roi*100:+.1f}% → fecha a perna")
            _cortar_perna(hydra, h, symbol, lado, f"Tempo {SAIDA_TEMPO_H}h roi={roi*100:.0f}%",
                          regime, (sl if lado == "LONG" else ss), sessao, preco)
            return
        if TRAVA_ATR:
            mov = _mov_contra(lado, leg.preco_entrada, preco)
            lim = _trava_pct(symbol, leg)
            if mov >= lim:
                log.info(f"⛔ {symbol} TRAVA {'ROI' if TRAVA_ROI else 'ATR'} {lado} | preço {mov*100:.2f}% contra >= trava {lim*100:.2f}% "
                         f"| ROI={roi*100:+.1f}% → fecha a perna (sem hedge) e cooldown {COOLDOWN_TP_MIN}min")
                _cortar_perna(hydra, h, symbol, lado, f"Trava {'ROI' if TRAVA_ROI else 'ATR'} {mov*100:.1f}%",
                              regime, (sl if lado == "LONG" else ss), sessao, preco)
                return
        contra = (ss - sl) if lado == "LONG" else (sl - ss)    # >0 = balança pesa para o lado oposto
        virou = confirmado(h, "virar", contra >= DIF_VIRAR and h.ciclos_reentrada >= COOLDOWN_REENTRADA)
        if not virou:
            return

        if roi >= ROI_MIN_DIR:
            log.info(f"🔁 {symbol} BALANÇA VIROU | {lado}→{oposto} | L={sl} S={ss} diff={contra:.0f}pts | ROI {lado}={roi*100:+.1f}%")
            pnl = _fechar_perna_dir(hydra, h, symbol, lado, f"Inversão {oposto} diff={contra:.0f}pts",
                                    regime, (ss if lado == "LONG" else sl), sessao, preco)
            if pnl is None:
                return
            h.estado = CONGELADO
            h.ciclos_reentrada = 0
            h.roi_ancora = 0.0
            nova = _abrir_perna_dir(hydra, h, symbol, oposto, preco)
            if nova:
                if oposto == "LONG":
                    h.posicao_long = nova
                else:
                    h.posicao_short = nova
                h.estado = _estado_pelas_pernas(h)
                nova.atr_entrada = ATR_PCT.get(symbol)
                log.info(f"🎯 {symbol} ABRE {oposto} (virada) | qty={nova.qty}")
                if MEDIDOR is not None:
                    MEDIDOR.registrar(symbol, oposto, nova.preco_entrada, h.alavancagem, sl, ss, regime, "virada")
            salvar_estado(hydra.hedges)
        elif CORTE_SEM_HEDGE:
            log.info(f"✂️ {symbol} BALANÇA VIROU com {lado} negativo | ROI={roi*100:+.1f}% → fecha a perna (sem hedge)")
            _cortar_perna(hydra, h, symbol, lado, f"Corte balança diff={contra:.0f}pts",
                          regime, (sl if lado == "LONG" else ss), sessao, preco)
        else:
            log.info(f"🛡️ {symbol} BALANÇA VIROU com {lado} negativo | ROI={roi*100:+.1f}% → abre {oposto} (hedge) e espera")
            nova = _abrir_perna_dir(hydra, h, symbol, oposto, preco, qty=leg.qty)
            if nova:
                if oposto == "LONG":
                    h.posicao_long = nova
                else:
                    h.posicao_short = nova
                h.estado = HEDGE_COMPLETO
                h.ciclos_reentrada = 0
                h.roi_ancora = 0.0
                salvar_estado(hydra.hedges)
        return

    # ── HEDGE (veio de virada com perna negativa): solta a perna lucrando do lado LEVE ──
    if h.estado == HEDGE_COMPLETO:
        pos = get_posicao_real(client, symbol)
        if pos is None:
            return
        for lado, score_lado in (("LONG", sl), ("SHORT", ss)):
            leg = h.posicao_long if lado == "LONG" else h.posicao_short
            if leg and not pos[lado]:
                _perna_sumiu_dir(hydra, h, symbol, lado, regime, score_lado, sessao, preco)
                h.estado = _estado_pelas_pernas(h)
                h.ciclos_reentrada = 0
                salvar_estado(hydra.hedges)
                return
        if not (h.posicao_long and h.posicao_short and pos["LONG"] and pos["SHORT"]):
            h.estado = _estado_pelas_pernas(h)
            return
        roi_l = _roi_dir(pos["LONG"],  h.posicao_long,  h.alavancagem)
        roi_s = _roi_dir(pos["SHORT"], h.posicao_short, h.alavancagem)
        # short pesado + long (lado leve) lucrando → solta LONG | long pesado + short lucrando → solta SHORT
        c_l = confirmado(h, "hed_long",  (ss - sl) >= DIF_VIRAR and roi_l >= ROI_MIN_DIR)
        c_s = confirmado(h, "hed_short", (sl - ss) >= DIF_VIRAR and roi_s >= ROI_MIN_DIR)
        alvo = "LONG" if c_l else ("SHORT" if c_s else None)
        if alvo:
            diff = abs(sl - ss)
            roi_x = roi_l if alvo == "LONG" else roi_s
            log.info(f"⚖️ {symbol} BALANÇA SOLTA {alvo} | L={sl} S={ss} diff={diff:.0f}pts | ROI {alvo}={roi_x*100:+.1f}%")
            pnl = _fechar_perna_dir(hydra, h, symbol, alvo, f"Balança diff={diff:.0f}pts",
                                    regime, (sl if alvo == "LONG" else ss), sessao, preco)
            if pnl is not None:
                h.estado = _estado_pelas_pernas(h)
                h.ciclos_reentrada = 0
                h.roi_ancora = 0.0
                salvar_estado(hydra.hedges)


# ─── ANÁLISE PARALELA ──────────────────────────────────────
def analisar_par(args):
    client, symbol, sessao, losses_seguidos = args
    try:
        preco = get_preco(client, symbol)
        if not preco:
            return None
        res = get_score_par(client, symbol, sessao, losses_seguidos)
        if res is None:
            log.warning(f"⏭️ {symbol} análise incompleta/dessincronizada — sem decisão neste ciclo")
            return None
        sl, ss, regime = res
        return symbol, preco, sl, ss, regime
    except Exception as e:
        log.error(f"Erro analisar {symbol}: {e}")
        return None

# ─── DISPLAY ────────────────────────────────────────────────
def display(hydra, pares_info):
    os.system('clear')
    banca  = hydra.banca_total()
    lucro  = banca - hydra.banca_inicial
    lp     = (lucro/hydra.banca_inicial)*100 if hydra.banca_inicial > 0 else 0
    wr     = round(hydra.wins/(hydra.wins+hydra.losses)*100) if (hydra.wins+hydra.losses) > 0 else 0
    sl_str = "+" if lucro >= 0 else ""

    print("╔"+"═"*68+"╗")
    print("║"+f"  🐉🧠 HYDRA TESTE {PERFIS[PERFIL]['NOME']}  —  FICTÍCIA".center(68)+"║")
    print("╠"+"═"*68+"╣")
    print(f"║  Banca: {banca:.4f} USDT  Lucro: {sl_str}{lucro:.4f} ({sl_str}{lp:.2f}%)             ║")
    _hd = sum(1 for _h in hydra.hedges.values() if _h.estado in (HEDGE_COMPLETO, MEIA_SHORT, MEIA_LONG))
    print("║" + f"  {'Ciclos' if UNIDADE_CICLO else 'Pernas'} W/L: {hydra.wins}/{hydra.losses} ({wr}%)  Loop: {hydra.ciclo}  Hedges: {_hd}".ljust(68) + "║")
    if hydra.em_pausa():
        print(f"║  ⏸ PAUSADO até {hydra.pausado_ate.strftime('%H:%M:%S')}                                   ║")
    print("╠"+"═"*68+"╣")
    print(f"║  {'PAR':<12}{'ALV':>4}  {'ESTADO':<18}{'LONG PnL':>10}{'SHORT PnL':>10}  ║")
    print("║"+"─"*68+"║")

    icones = {
        AGUARDA:        "⏳ AGUARDA",
        CONGELADO:      "🧊 CONGELADO",
        HEDGE_COMPLETO: "🔄 HEDGE",
        MEIA_SHORT:     "📉 MEIA SHORT",
        MEIA_LONG:      "📈 MEIA LONG",
    }

    for symbol, info in sorted(pares_info.items()):
        h      = hydra.hedges.get(symbol)
        estado = icones.get(h.estado if h else AGUARDA, "⏳")
        preco  = info['preco']
        alv    = hydra.alavancagens.get(symbol, 50)
        sl_s   = ss_s = "     —    "

        if h and h.posicao_long:
            pos = get_posicao_real(hydra.client, symbol)
            if pos and pos["LONG"]:
                sl_s = f"{pos['LONG']['pnl']:+.4f}"
        if h and h.posicao_short:
            pos = get_posicao_real(hydra.client, symbol)
            if pos and pos["SHORT"]:
                ss_s = f"{pos['SHORT']['pnl']:+.4f}"

        print(f"║  {symbol:<12}{alv:>3}x  {estado:<18}{sl_s:>10}{ss_s:>10}  ║")
        print(f"║    Score L:{info['sl']:>5.1f}  S:{info['ss']:>5.1f}  {info['regime']:<12}  Preço:{preco:<14.4f}║")
        print("║"+"─"*68+"║")

    print("╠"+"═"*68+"╣")
    if hydra.historico:
        print("║  Últimos trades:                                                     ║")
        for h in hydra.historico[-4:]:
            s = "+" if h['pnl'] >= 0 else ""
            e = "✅" if h['pnl'] >= 0 else "❌"
            print(f"║  {e} {h['hora']} {h['symbol']:<10} {h['lado']:<6} {s}{h['pnl']:>7.4f} USDT  {h['motivo'][:16]:<16}║")
    print("╠"+"═"*68+"╣")
    _painel_liquido(hydra)
    _painel_ciclos(hydra)
    if MEDIDOR is not None:
        _res, _np = MEDIDOR.resumo()
        _txt = "  ".join(f"{m}m:{(a / n * 100):.0f}% ({n})" if n else f"{m}m:—" for m, (a, n) in _res.items())
        print("║" + f"  Acerto balança  {_txt}  pend:{_np}".ljust(68) + "║")
    print(f"║  Próximo ciclo em {INTERVALO}s  |  CTRL+C para parar                        ║")
    print("╚"+"═"*68+"╝")

# ─── PERFIL: aplica os filtros da balança ──────────────────
for _k, _v in PERFIS[PERFIL].items():
    if _k != "NOME":
        globals()[_k] = _v
SCORE_DECISAO = SCORE_ENTRADA

# ─── MAIN ────────────────────────────────__________________
def main():
    global MEDIDOR
    reset = "--reset" in sys.argv
    if reset:
        for _f in (ESTADO_FILE, RES_FILE, MEM_FILE, SIM_FILE, CICLOS_FILE, MEDICAO_FILE, MEDICAO_PEND):
            try:
                os.remove(_f)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Aviso ao limpar {_f}: {e}")

    print("╔"+"═"*52+"╗")
    print("║"+f"  🐉🧠 HYDRA TESTE — PERFIL {PERFIL}".center(52)+"║")
    print("║"+f"  {PERFIS[PERFIL]['NOME']}".center(52)+"║")
    print("╠"+"═"*52+"╣")
    print(f"║  Carteira fictícia: {SALDO_INICIAL} USDT (inicial)".ljust(53)+"║")
    print(f"║  Risco por hedge:  {int(RISCO_PCT*100)}% da banca".ljust(53)+"║")
    print(f"║  Memória no score: {'SIM' if MEMORIA_NO_SCORE else 'NÃO'}".ljust(53)+"║")
    _tv = (f"SIM (-{TRAVA_ROI*100:.0f}% ROI)" if TRAVA_ROI else
           f"SIM ({TRAVA_ATR_K}x ATR, {TRAVA_MIN_PCT*100:.1f}%–{TRAVA_MAX_PCT*100:.0f}%)") if TRAVA_ATR else "NÃO"
    print(f"║  Trava:            {_tv}".ljust(53)+"║")
    print(f"║  Balança virou c/ perna negativa: {'FECHA' if CORTE_SEM_HEDGE else 'HEDGE'}".ljust(53)+"║")
    if BALANCA_CHOQUE:
        print(f"║  Balança: CHOQUE 1h >= {CHOQUE_Z} desvios por {CHOQUE_HORAS}h{' + volume 2x' if CHOQUE_VOLUME else ''}".ljust(53)+"║")
        print(f"║  Saída: {SAIDA_TEMPO_H}h | TP: {'NÃO' if SEM_TP else 'SIM'} | alav. máx {LEV_TETO or 'par'}x | taxa {FEES_PCT*100:.2f}%".ljust(53)+"║")
    print(f"║  Pasta:            {PASTA}".ljust(53)+"║")
    print(f"║  Top pares:        {TOP_PARES}".ljust(53)+"║")
    print(f"║  Score entrada:    {SCORE_ENTRADA}  (motor: Cérebro1)".ljust(53)+"║")
    print(f"║  ROI mín. p/ soltar perna: {int(MIN_ROI*100)}%".ljust(53)+"║")
    print(f"║  Entrada: score>={SCORE_ENTRADA} e dif>={DIF_ENTRADA} pts (só lado pesado)".ljust(53)+"║")
    print(f"║  Virar de lado: dif>={DIF_VIRAR} pts x{CONFIRMA_CICLOS} ciclos".ljust(53)+"║")
    print(f"║  SEM TP e SEM STOP — só a balança decide".ljust(53)+"║")
    print(f"║  Confirmação: {CONFIRMA_CICLOS} ciclos seguidos".ljust(53)+"║")
    print(f"║  Rede de segurança: -{int(REDE_SEGURANCA_ROI*100)}% (relativo)".ljust(53)+"║")
    print(f"║  Saldo mínimo:     ${SALDO_MINIMO}".ljust(53)+"║")
    print("╠"+"═"*52+"╣")
    print("║  🧪 MODO PAPER — nenhuma ordem real é enviada".ljust(53)+"║")
    print("╚"+"═"*52+"╝\n")

    try:
        client = get_client(reset=reset)
        MEDIDOR = MedidorBalanca()
        print(f"🔑 Alavancagem: {'máxima REAL por par (chave só leitura)' if client._tem_chave else 'LEV_POR_PAR / 20x (sem chave)'}")
        client.futures_ping()
        banca = get_banca_total(client)
        print(f"\n✅ Dados de mercado da Binance conectados (públicos)!")
        print(f"💰 Carteira fictícia: {banca:.4f} USDT\n")
    except Exception as e:
        print(f"❌ Erro conexão: {e}"); sys.exit(1)

    if not verificar_hedge_mode(client):
        print("❌ Hedge Mode indisponível na simulação.")
        sys.exit(1)

    carregar_memoria()
    hydra      = HydraCerebro(client)
    scan_ciclo = 0
    pares      = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]

    recuperar_estado(hydra)

    # Modo direcional: sem TP/STOP. Limpa ordens condicionais antigas das posições abertas.
    for sym, h in hydra.hedges.items():
        if h.estado in (MEIA_SHORT, MEIA_LONG, HEDGE_COMPLETO):
            cancelar_todas_ordens(client, sym)

    log.info("="*60)
    log.info("🐉🧠 HYDRA CÉREBRO DIRECIONAL v1.0 INICIADA")
    log.info(f"   Banca: {hydra.banca_inicial:.4f} USDT")
    log.info("="*60)

    try:
        while True:
            hydra.ciclo += 1

            if hydra.verificar_drawdown():
                time.sleep(PAUSA_MINUTOS * 60)
                hydra.banca_inicial = get_banca_total(client)
                continue

            if scan_ciclo % 20 == 0:
                novos = get_top_pares(client)
                if novos:
                    pares_com_hedge = [
                        s for s, hh in hydra.hedges.items()
                        if hh.estado in (HEDGE_COMPLETO, MEIA_LONG, MEIA_SHORT)
                    ]
                    pares = list(dict.fromkeys(novos + pares_com_hedge))
                for sym in pares:
                    if sym not in hydra.alavancagens:
                        alv = get_alavancagem_max(client, sym)
                        hydra.alavancagens[sym] = alv
            scan_ciclo += 1

            if time.time() - getattr(hydra, "_ult_recon", 0) >= RECON_CADA_S:
                hydra._ult_recon = time.time()
                for _s in reconciliar_global(hydra):
                    if _s not in pares:
                        pares.append(_s)

            sessao = get_sessao()

            pares_info = {}
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {
                    ex.submit(analisar_par, (client, s, sessao, hydra.losses_seguidos)): s
                    for s in pares
                }
                for f in as_completed(futures):
                    res = f.result()
                    if res:
                        symbol, preco, sl, ss, regime = res
                        pares_info[symbol] = {
                            'preco': preco, 'sl': sl,
                            'ss': ss, 'regime': regime,
                        }

            if True:  # pausa so BLOQUEIA novas entradas (ver ciclo_direcional); posicoes abertas continuam geridas

                # Primeiro: pares com análise válida.
                for symbol, info in pares_info.items():
                    try:
                        ciclo_direcional(
                            hydra, symbol,
                            info['preco'], info['sl'],
                            info['ss'], info['regime'], sessao
                        )
                    except Exception as e:
                        log.error(f"Erro ciclo {symbol}: {e}")

                # Segundo: posições GERIDAS que ficaram sem análise.
                #
                # Não usamos score antigo. Não inventamos sinal.
                # Score 0/0 significa "sem sinal".
                #
                # O objetivo aqui é apenas permitir que
                # ciclo_par_real() detecte uma perna que sumiu
                # e continue a gestão objetiva da posição.
                for symbol, h in list(hydra.hedges.items()):
                    if h.estado not in (HEDGE_COMPLETO, MEIA_LONG, MEIA_SHORT):
                        continue

                    if symbol in pares_info:
                        continue

                    try:
                        preco_neutro = get_preco(client, symbol)
                        if preco_neutro is None:
                            log.warning(
                                f"⚠️ {symbol} sem análise e sem preço atual — "
                                f"gestão adiada"
                            )
                            continue

                        ciclo_direcional(
                            hydra,
                            symbol,
                            preco_neutro,
                            0,
                            0,
                            "SEM_DADOS",
                            sessao
                        )

                    except Exception as e:
                        log.error(
                            f"Erro ciclo protegido {symbol}: {e}"
                        )

            # Gestão objetiva/proteções.
            try:
                colher_lucro_global(hydra)
            except Exception as e:
                log.error(f"Erro colheita global: {e}")
            for _h in list(hydra.hedges.values()):
                try:
                    _gerir_ciclo(hydra, _h)
                except Exception as e:
                    log.error(
                        f"Erro gestão/proteção {_h.symbol}: {e}"
                    )
            salvar_estado(hydra.hedges)
            client._sim.salvar()
            display(hydra, pares_info)
            hydra.salvar_resultados()
            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        print("\n\n🐉🧠 HYDRA CÉREBRO PAPER ENCERRADA")
        banca = get_banca_total(client)
        lucro = banca - hydra.banca_inicial
        wr    = round(hydra.wins/(hydra.wins+hydra.losses)*100) if (hydra.wins+hydra.losses) > 0 else 0
        print(f"   Banca final:  {banca:.4f} USDT")
        print(f"   Lucro total:  {lucro:+.4f} USDT")
        print(f"   W/L:          {hydra.wins}/{hydra.losses} ({wr}%)")
        print(f"   Posições:     mantidas abertas na carteira fictícia!")
        print(f"   Estado:       guardado em {ESTADO_FILE}\n")
        salvar_estado(hydra.hedges)
        client._sim.salvar()
        hydra.salvar_resultados()

if __name__ == "__main__":
    main()
