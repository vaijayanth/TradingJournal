"""ND add-on (averaging) tests against the live rule (user request 2026-11-26: 'is my averaging method right?').

  python swing-backtest/addon_variants_test.py --data /tmp/claude-0/bt/checkpoints trig:-6 trig:off trig:-10 trig:-15 cool:14 frac:0.25 frac:0.5 frac:1.0 ...

`trig:<pct>` = the add-on fires when the open P&L is at or below <pct>% (-6 = the live rule); `trig:off` = no add-ons at all; `frac:<x>` = add-on size as a fraction of the open quantity (live 0.10), at the live -6% trigger; `cool:<days>` = the live -6% trigger with that many days between adds (live = 7).
Same universe, 252-day-high entry, ladder, costs, 0.1% slippage and 6% idle cash as RESULTS.md (ND, 2016-11-07 to the last bar); only the add-on rule changes.
Output: one row per variant (full-period and 2022+ CAGR / drawdown, profit factor, win rate, average win / loss) and results/addon_variants.csv (the tool rewrites the file each run).
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
    ap.add_argument("--out", default=str(HERE / "results" / "addon_variants.csv"))
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
        sw.ADD_TRIGGER, sw.ADD_COOLDOWN, sw.ADD_FRAC = -6.0, 7, 0.10
        if kind == "trig":
            sw.ADD_TRIGGER = -9999.0 if arg == "off" else float(arg)
        elif kind == "frac":
            sw.ADD_FRAC = float(arg)
        elif kind == "cool":
            sw.ADD_COOLDOWN = int(arg)
        res = sw.run("dhan", data_dir, symbols, t0, 0.001, cash_rate=0.06)
        out, cv, tr = sw.summarise(res, v)
        h2 = cv.loc["2022-01-01":]["eq"]
        yrs = (h2.index[-1] - h2.index[0]).days / 365.25
        rows.append({"variant": v, "cagr%": float(out["cagr%"]), "max_dd%": float(out["max_dd%"]), "cagr_2022+": round(((h2.iloc[-1] / h2.iloc[0]) ** (1 / yrs) - 1) * 100, 1),
                     "dd_2022+": round(((h2 / h2.cummax()) - 1).min() * 100, 1), "pf": float(out["pf"]), "win%": out["win%"], "avg_win%": float(out["avg_win%"]), "avg_loss%": float(out["avg_loss%"]),
                     "closed": out["closed"], "missed_adds": res["missed"]["add"] if isinstance(res, dict) and "missed" in res else None})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
