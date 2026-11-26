"""ND exit-rule and partial-profit tests against the live Supertrend exit (user request 2026-11-26).

  python swing-backtest/exit_variants_test.py --data /tmp/claude-0/bt/checkpoints exit:st exit:sma50 exit:hyb20_50 trim:0.5_0.333 trim:1.0_0.5 ...

`exit:<mode>` = an exit rule from swing_backtest_exits.py (st, sma50, sma20, st_and_sma50, hyb20_30, hyb20_50, hybpct_30_15, hybpct_30_20).
`trim:<gain>_<fraction>` = sell that fraction of the position ONCE the first time the open gain reaches <gain> (0.5 = +50%); the rest keeps the Supertrend exit; `trim:none` = no trim.
Same universe, 252-day-high entry, ladder, costs, 0.1% slippage and 6% idle cash as RESULTS.md (ND, 2016-11-07 to the last bar). Output: one row per variant
(full-period and 2022+ CAGR / drawdown, profit factor, win rate, and for trades that reached +30%: average peak, average exit, giveback of the peak) and results/exit_variants.csv.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swing_backtest_exits as sw  # noqa: E402
from bonde_minervini_test import live_symbols  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=str(HERE / "results" / "exit_variants.csv"))
    ap.add_argument("variants", nargs="+")
    a = ap.parse_args()
    data_dir = Path(a.data)
    symbols = live_symbols(data_dir)
    t0 = pd.Timestamp("2016-11-07")
    raw = sw.load(data_dir, symbols, t0, True)
    sw.load = lambda *x, **k: raw
    rows = []
    for v in a.variants:
        kind, _, arg = v.partition(":")
        sw.EXIT_MODE, sw.TRIM = "st", None
        if kind == "exit":
            sw.EXIT_MODE = arg
        elif arg != "none":
            g, f = arg.split("_")
            sw.TRIM = (float(g), float(f))
        res = sw.run("dhan", data_dir, symbols, t0, 0.001, cash_rate=0.06)
        out, cv, tr = sw.summarise(res, v)
        big = tr[tr["peak"] >= 30]
        give = (big["peak"] - big["pct"]) / big["peak"] * 100
        h2 = cv.loc["2022-01-01":]["eq"]
        yrs = (h2.index[-1] - h2.index[0]).days / 365.25
        rows.append({"variant": v, "cagr%": float(out["cagr%"]), "max_dd%": float(out["max_dd%"]), "cagr_2022+": round(((h2.iloc[-1] / h2.iloc[0]) ** (1 / yrs) - 1) * 100, 1),
                     "dd_2022+": round(((h2 / h2.cummax()) - 1).min() * 100, 1), "pf": float(out["pf"]), "win%": out["win%"], "avg_win%": float(out["avg_win%"]), "avg_loss%": float(out["avg_loss%"]),
                     "hold_win_d": out["avg_hold_win_d"], "closed": out["closed"], "n_peak30": len(big), "avg_peak%": round(big["peak"].mean()), "avg_exit%": round(big["pct"].mean()),
                     "giveback%_of_peak": round(give.mean())})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
