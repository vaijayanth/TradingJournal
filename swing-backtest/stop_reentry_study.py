"""Stop re-entry study (user, 2026-11-27): what happens after (1) a sharp adverse 3-day move without a Supertrend flip, and (2) a fresh flip that follows a sharp move.

Universe: the AZ F&O universe (zerodha-live/data/fno_universe.json), 6 years of daily Yahoo candles, Supertrend(10,3). Run: python swing-backtest/stop_reentry_study.py
Study 1 'spike': Supertrend still red (call side) / green (put side) and the close moved 6%+ against the short option in 3 days; outcomes over the next 20 trading days: the Supertrend flips
against the position, and the price touches +8% / +12% (call) or -8% / -12% (put) of the entry close; compared with every ordinary day (base). 'spike_wait5' = the same entered 5 days later.
Study 2 'spike_flip': a fresh flip whose 3-day move was 6%+ in the flip direction; outcomes for the NEW structure (put after a green flip, call after a red flip) against ordinary flips.
Proxy only: it uses the stock's move, not the option stop or its premium. Results: swing-backtest/RESULTS.md.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
H = 20


def supertrend(h, l, c, n=10, m=3.0):
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / n, adjust=False).mean()
    hl2 = (h + l) / 2
    ub, lb, cv = (hl2 + m * atr).values, (hl2 - m * atr).values, c.values
    fu, fl = ub.copy(), lb.copy()
    dirn, line = np.ones(len(c)), np.full(len(c), np.nan)
    for i in range(1, len(c)):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or cv[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or cv[i - 1] < fl[i - 1]) else fl[i - 1]
        dirn[i] = (-1 if cv[i] < fl[i] else 1) if dirn[i - 1] == 1 else (1 if cv[i] > fu[i] else -1)
        line[i] = fl[i] if dirn[i] == 1 else fu[i]
    return dirn, line


def main():
    uni = json.loads((ROOT / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"]
    data = yf.download([s + ".NS" for s in uni], period="6y", interval="1d", group_by="ticker", auto_adjust=False, threads=True, progress=False)
    s1, s2 = [], []
    for s in uni:
        try:
            d = data[s + ".NS"].dropna()
        except Exception:  # noqa: BLE001
            continue
        if len(d) < 400:
            continue
        dv, _ = supertrend(d["High"], d["Low"], d["Close"])
        cv, hv, lv, n = d["Close"].values, d["High"].values, d["Low"].values, len(d)

        def outcome(j, red):
            seg = slice(j + 1, j + H + 1)
            ext = hv[seg].max() / cv[j] - 1 if red else 1 - lv[seg].min() / cv[j]
            return (dv[seg] != dv[j]).any(), ext
        last = {}                                            # one spike episode per stock and side per 10 trading days (episodes would otherwise overlap)
        for i in range(30, n - H - 6):
            ret3 = cv[i] / cv[i - 3] - 1
            for red in (True, False):                       # call side (red) / put side (green)
                if (dv[i] == -1) != red:
                    continue
                spike = (ret3 if red else -ret3) >= 0.06
                if spike:
                    if i - last.get(red, -99) < 10:
                        continue
                    last[red] = i
                f0, e0 = outcome(i, red)
                s1.append(dict(side="call" if red else "put", kind="spike" if spike else "base", flip=f0, ext=e0))
                if spike and dv[i + 5] == dv[i]:
                    f5, e5 = outcome(i + 5, red)
                    s1.append(dict(side="call" if red else "put", kind="spike_wait5", flip=f5, ext=e5))
            if dv[i] != dv[i - 1]:                           # a fresh flip: green = bull put spread entry, red = sell call entry
                green = dv[i] == 1
                sp = (ret3 >= 0.06) if green else (ret3 <= -0.06)
                f, e = outcome(i, not green)                 # the new structure is exposed to the OTHER direction
                s2.append(dict(side="put" if green else "call", kind="spike_flip" if sp else "normal_flip", back=f, ext=e))
    a, b = pd.DataFrame(s1), pd.DataFrame(s2)
    print(a.groupby(["side", "kind"]).apply(lambda g: pd.Series({"n": len(g), "flip_20d_%": g.flip.mean() * 100, "touch8_%": (g.ext >= .08).mean() * 100,
                                                                   "touch12_%": (g.ext >= .12).mean() * 100})).round(1).to_string())
    print(b.groupby(["side", "kind"]).apply(lambda g: pd.Series({"n": len(g), "flip_back_20d_%": g.back.mean() * 100, "adverse8_%": (g.ext >= .08).mean() * 100,
                                                                   "adverse12_%": (g.ext >= .12).mean() * 100})).round(1).to_string())


if __name__ == "__main__":
    main()
