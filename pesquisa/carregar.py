"""Lê os zips da data.binance.vision e grava parquet/pickle: velas 1h e funding por par."""
import glob, zipfile, io, os
import pandas as pd

D = os.path.join(os.path.dirname(__file__), "dados")

def _ler_zip(f):
    with zipfile.ZipFile(f) as z:
        raw = z.read(z.namelist()[0])
    txt = raw.decode()
    tem_cab = not txt[:1].isdigit()
    return pd.read_csv(io.StringIO(txt), header=0 if tem_cab else None)

def velas(par):
    partes = []
    for f in sorted(glob.glob(f"{D}/{par}-1h-*.zip")):
        df = _ler_zip(f)
        df = df.iloc[:, :11]
        df.columns = ["time", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tq"]
        partes.append(df)
    df = pd.concat(partes).drop_duplicates("time").sort_values("time")
    df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
    return df.set_index("time")[["open", "high", "low", "close", "vol", "qvol"]].astype(float)

def funding(par):
    partes = [_ler_zip(f) for f in sorted(glob.glob(f"{D}/{par}-fundingRate-*.zip"))]
    df = pd.concat(partes)
    df.columns = ["time", "intervalo", "taxa"]
    df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
    return df.drop_duplicates("time").set_index("time")["taxa"].astype(float).sort_index()

if __name__ == "__main__":
    pares = sorted({os.path.basename(f).split("-")[0] for f in glob.glob(f"{D}/*-1h-*.zip")})
    V = {p: velas(p) for p in pares}
    F = {p: funding(p) for p in pares}
    pd.to_pickle({"velas": V, "funding": F}, os.path.join(D, "base.pkl"))
    for p in pares:
        print(p, V[p].index.min(), V[p].index.max(), len(V[p]), len(F[p]))
