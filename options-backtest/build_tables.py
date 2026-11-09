"""Turn the per-day bhavcopy files (data/fo/*.csv.gz) into one table per stock (data/sym/<SYMBOL>.pkl) plus the trading-day list.

Columns: date, expiry, strike, typ (CE/PE), settle, close, oi, vol, und (underlying price), lot.
"""
import gzip
import io
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
FO = HERE / "data" / "fo"
SYM = HERE / "data" / "sym"


def main():
    SYM.mkdir(parents=True, exist_ok=True)
    frames = []
    files = sorted(FO.glob("*.csv.gz"))
    for f in files:
        df = pd.read_csv(f, dtype=str)
        if df.empty:
            continue
        frames.append(pd.DataFrame({
            "sym": df["TckrSymb"], "date": pd.to_datetime(df["TradDt"]), "expiry": pd.to_datetime(df["XpryDt"]),
            "strike": df["StrkPric"].astype(float), "typ": df["OptnTp"], "settle": df["SttlmPric"].astype(float),
            "close": df["ClsPric"].astype(float), "oi": df["OpnIntrst"].astype(float), "vol": df["TtlTradgVol"].astype(float),
            "und": df["UndrlygPric"].astype(float), "lot": df["NewBrdLotQty"].astype(float)}))
    all_ = pd.concat(frames, ignore_index=True)
    all_["typ"] = all_["typ"].astype("category")
    print(len(files), "days,", len(all_), "rows,", all_["sym"].nunique(), "symbols,", all_["date"].min().date(), "->", all_["date"].max().date())
    for s, g in all_.groupby("sym"):
        g.drop(columns="sym").reset_index(drop=True).to_pickle(SYM / f"{s}.pkl")
    pd.Series(sorted(all_["date"].unique())).to_pickle(HERE / "data" / "days.pkl")


if __name__ == "__main__":
    main()
