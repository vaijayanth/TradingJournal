"""Does stopping NEW entries while Nifty is in a downtrend improve the ND / AZ books? (user test, 2026-11-24)

  python swing-backtest/nifty_gate_test.py <checkpoints dir> [nd|az]

Reruns the stock engine (swing_backtest.run) with an entry gate read from the Nifty 50 index at the same day's close. Exits are never blocked.
  base        no gate (the live rules)
  A entries   no new entries while Nifty Supertrend(10,3) is red
  A + adds    ... and no add-ons either
  B entries   no new entries while Nifty is red AND below its 200-day average (deeper downtrend)
ND = dhan engine, live universe, Rs20L, cash 6%.  AZ = az engine, entry window 3 sessions (the live rule since 2026-11-23), Rs30L, cash 6%.
Same costs, slippage and ladder as RESULTS.md. Output: results/nifty_gate_<book>.csv and a printed table.
"""
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swing_backtest as sb  # noqa: E402
from indicators import compute_supertrend  # noqa: E402


def nifty_regimes():
    n = yf.download("^NSEI", period="max", progress=False, auto_adjust=False)
    n.columns = [c[0] for c in n.columns]
    n = n.dropna()
    d, _, _ = compute_supertrend(n["High"].tolist(), n["Low"].tolist(), n["Close"].tolist())
    red = pd.Series(d, index=n.index).eq("down")
    below = n["Close"] < n["Close"].rolling(200).mean()
    return {"A": red, "B": red & below}


def load_symbols(data_dir, book):
    import json
    man = pd.read_csv(data_dir / "manifest.csv")
    valid = man[man["status"] == "VALIDATED"]["symbol"].tolist()
    root = HERE.parent
    if book == "az":
        uni = json.loads((root / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"]
        ex = set(json.loads((root / "zerodha-live" / "data" / "excluded_symbols.json").read_text())["symbols"])
        want = {s + ".NS" for s in uni if s not in ex}
        return [s for s in valid if s in want]
    ex = json.loads((root / "dhan-live" / "data" / "excluded_universe.json").read_text())
    sfx = tuple(x.upper() for x in ex.get("suffixes", []))
    perm = {x.upper() for x in ex.get("symbols", [])}
    etf = {"LIQUIDCASE", "GOLDBEES", "MIDCAPETF", "NIFTYIETF", "MON100", "MASPTOP50", "MAFANG", "MOM100", "SILVERBEES"}
    def keep(sym):
        b = sym.split(".")[0].upper()
        return not (b in perm or b in etf or b.endswith(("ETF", "IETF", "BEES")) or (sfx and b.endswith(sfx)))
    return [x for x in valid if keep(x)]


def main():
    data_dir = Path(sys.argv[1])
    books = [sys.argv[2]] if len(sys.argv) > 2 else ["nd", "az"]
    regs = nifty_regimes()
    rows = []
    for book in books:
        strat = "dhan" if book == "nd" else "az"
        symbols = load_symbols(data_dir, strat)
        kw = dict(cash_rate=0.06, **({"flip_window": 3} if strat == "az" else {}))
        cases = [("base", None, False), ("A entries", regs["A"], False), ("A + adds", regs["A"], True), ("B entries", regs["B"], False)]
        for name, reg, adds in cases:
            block = None if reg is None else {d: True for d, v in reg.items() if v}
            res = sb.run(strat, data_dir, symbols, pd.Timestamp("2016-11-07"), 0.001, block=block, block_adds=adds, **kw)
            out, _, _ = sb.summarise(res, f"{book} {name}")
            rows.append({"book": book.upper(), "case": name, "cagr": out["cagr%"], "maxdd": out["max_dd%"], "cagr_dd": round(out["cagr%"] / abs(out["max_dd%"]), 2), "closed": out["closed"], "win%": out["win%"], "pf": out["pf"], "final": out["final_equity"]})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "results" / f"nifty_gate_{'_'.join(books)}.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
