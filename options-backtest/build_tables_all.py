"""Like build_tables.py but memory-safe for the full F&O universe: processes the per-day files in batches of symbols.

Usage: python options-backtest/build_tables_all.py [--src fo_all] [--dst sym_all] [--batch 40]
"""
import argparse
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def read_day(f, syms):
    df = pd.read_csv(f, dtype=str)
    if df.empty:
        return None
    df = df[df["TckrSymb"].isin(syms)]
    if df.empty:
        return None
    return pd.DataFrame({
        "sym": df["TckrSymb"], "date": pd.to_datetime(df["TradDt"]), "expiry": pd.to_datetime(df["XpryDt"]),
        "strike": df["StrkPric"].astype("float32"), "typ": df["OptnTp"], "settle": df["SttlmPric"].astype("float32"),
        "close": df["ClsPric"].astype("float32"), "oi": df["OpnIntrst"].astype("float32"), "vol": df["TtlTradgVol"].astype("float32"),
        "und": df["UndrlygPric"].astype("float32"), "lot": df["NewBrdLotQty"].astype("float32")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="fo_all")
    ap.add_argument("--dst", default="sym_all")
    ap.add_argument("--batch", type=int, default=40)
    a = ap.parse_args()
    files = sorted((DATA / a.src).glob("*.csv.gz"))
    out = DATA / a.dst
    out.mkdir(exist_ok=True)
    # symbol list from the first and last file (names present at either end)
    names = set()
    for f in (files[0], files[len(files) // 2], files[-1]):
        names |= set(pd.read_csv(f, dtype=str, usecols=["TckrSymb"])["TckrSymb"])
    names = sorted(names)
    print(len(files), "days,", len(names), "symbols", flush=True)
    for i in range(0, len(names), a.batch):
        batch = set(names[i:i + a.batch])
        frames = [x for x in (read_day(f, batch) for f in files) if x is not None]
        big = pd.concat(frames, ignore_index=True)
        for s, g in big.groupby("sym"):
            g.drop(columns="sym").reset_index(drop=True).to_pickle(out / f"{s}.pkl")
        print(f"batch {i // a.batch + 1}: {len(batch)} symbols, {len(big)} rows", flush=True)
    pd.Series(sorted({pd.Timestamp(f.name[:8]) for f in files})).to_pickle(DATA / "days_all.pkl")


if __name__ == "__main__":
    main()
