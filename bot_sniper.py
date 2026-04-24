import requests
import pandas as pd
import pandas_ta as ta
import time

# ================= CONFIG =================
SYMBOL = "USOIL"
INTERVAL = "1min"

# =========================================

def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&outputsize=50&apikey=demo"
    data = requests.get(url).json()

    if "values" not in data:
        print("Erro ao buscar dados:", data)
        return None

    df = pd.DataFrame(data["values"])
    df["close"] = df["close"].astype(float)
    df = df[::-1]

    return df

def sniper_logic():
    df = get_data()
    if df is None:
        return

    # Indicadores
    df["rsi"] = ta.rsi(df["close"], length=14)
    bb = ta.bbands(df["close"], length=20)

    rsi = df["rsi"].iloc[-1]
    price = df["close"].iloc[-1]
    bb_low = bb["BBL_20_2.0"].iloc[-1]

    print(f"🛢️ Petróleo | Preço: {price} | RSI: {rsi:.2f}")

    # 🎯 CONDIÇÃO SNIPER
    if rsi < 30 and price <= bb_low:
        print("🚀 SINAL SNIPER DETECTADO (COMPRA)")
        print("👉 Abra o MT5 e execute a ordem manualmente")
    else:
        print("⏳ Aguardando oportunidade...")

# ================= LOOP =================
while True:
    try:
        sniper_logic()
    except Exception as e:
        print("Erro:", e)

    time.sleep(60)
