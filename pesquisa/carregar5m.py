"""Junta as velas de 5m em matrizes (tempo x pares) e grava dados5m/base5m.pkl."""
import glob, io, os, zipfile
import numpy as np
import pandas as pd

D = os.path.join(os.path.dirname(__file__), "dados5m")
cols = ["time", "open", "high", "low", "close", "vol"]
por_par = {}
for f in sorted(glob.glob(f"{D}/*-5m-*.zip")):
    par = os.path.basename(f).split("-")[0]
    with zipfile.ZipFile(f) as z:
        txt = z.read(z.namelist()[0]).decode()
    df = pd.read_csv(io.StringIO(txt), header=0 if not txt[:1].isdigit() else None).iloc[:, :6]
    df.columns = cols
    por_par.setdefault(par, []).append(df)
M = {}
for par, partes in por_par.items():
    df = pd.concat(partes).drop_duplicates("time")
    df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
    M[par] = df.set_index("time").sort_index().astype("float32")
idx = pd.date_range(min(v.index.min() for v in M.values()), max(v.index.max() for v in M.values()), freq="5min")
out = {c: pd.DataFrame({p: v[c].reindex(idx) for p, v in M.items()}) for c in ["open", "high", "low", "close", "vol"]}
pd.to_pickle(out, f"{D}/base5m.pkl")
print(out["close"].shape, out["close"].index.min(), out["close"].index.max())
