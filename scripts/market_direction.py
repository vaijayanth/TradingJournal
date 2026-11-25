"""Pre-open market direction read for the Indian market (read-only; informational only, it never changes a rule or a signal).

  python scripts/market_direction.py [--gift <GIFT Nifty level>] [--json]

Inputs (all from Yahoo Finance through the allowed hosts, no key needed):
  Nifty 50 (^NSEI) last two closes, Supertrend(10,3) colour and the 200-day average; India VIX (^INDIAVIX);
  global cues: S&P 500 futures (ES=F), Nasdaq 100 futures (NQ=F), Nikkei (^N225), Hang Seng (^HSI), Brent (BZ=F), USD/INR, US 10-year yield (^TNX).
GIFT Nifty is NOT on Yahoo (a script cannot call the broker MCPs), so it is an INPUT: pass `--gift <level>` and optionally `--gift-prev <its previous close>`. Source it
from the Zerodha MCP (`market quote` on `NSEIX:GIFT NIFTY`: live last price with timestamp, plus OHLC whose `close` is its previous close; found 2026-11-25); the Dhan
MCP lists it too (`GIFTNIFTY-INDEX`, IDX_I securityId 5024) but its ohlc returned only the previous close, no live level. Without a level the script says so and reads
the global cues only (confidence LOW). Never guess it.

Bias rules (transparent, deliberately simple):
  gap % = GIFT / last Nifty close - 1 (the reference is the NIFTY 50 CASH close, not GIFT Nifty's own previous close).
  global score = mean % change of S&P futures, Nasdaq futures, Nikkei, Hang Seng versus their previous close.
  flags: Brent up 2% or more, USD/INR up 0.5% or more, US 10y up 2% or more (all negative for India); VIX 20+ or up 10% on the day.
  open bias = the gap if GIFT is given (weak confirmation from the global score), otherwise the global score only.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "swing-backtest"))
from indicators import compute_supertrend  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0"}
CUES = [("S&P 500 fut", "ES=F"), ("Nasdaq fut", "NQ=F"), ("Nikkei", "%5EN225"), ("Hang Seng", "%5EHSI"), ("Brent", "BZ=F"), ("USD/INR", "USDINR=X"), ("US 10y yield", "%5ETNX")]


def chart(sym, rng="2y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={interval}"
    d = json.loads(urlopen(Request(url, headers=UA), timeout=20).read())["chart"]["result"][0]
    return d


def last_two(sym):
    """Latest price and the PREVIOUS DAILY close (Yahoo's chartPreviousClose is the close before the whole range, so it is not used)."""
    d = chart(sym, "10d")
    p = d["meta"].get("regularMarketPrice")
    pairs = [(t, c) for t, c in zip(d["timestamp"], d["indicators"]["quote"][0]["close"]) if c is not None]
    if not p or len(pairs) < 2:
        return p, None, None
    same_day = (pairs[-1][0] // 86400) == (d["meta"].get("regularMarketTime", 0) // 86400)   # the last daily bar IS the latest price's session
    prev = pairs[-2][1] if same_day else pairs[-1][1]
    return p, prev, (p / prev - 1) * 100


def nifty():
    d = chart("%5ENSEI", "2y")
    q = d["indicators"]["quote"][0]
    rows = [(t, o, h, l, c) for t, o, h, l, c in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
    h, l, c = [r[2] for r in rows], [r[3] for r in rows], [r[4] for r in rows]
    dirs, _, _ = compute_supertrend(h, l, c, 10, 3.0)
    sma200 = sum(c[-200:]) / 200
    bar_date = datetime.fromtimestamp(rows[-1][0], tz=timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
    flip = 0
    for k in range(len(dirs) - 1, 0, -1):
        if dirs[k] != dirs[k - 1]:
            break
        flip += 1
    return {"bar_date": bar_date, "last": c[-1], "prev": c[-2], "chg_pct": (c[-1] / c[-2] - 1) * 100, "st": "GREEN" if dirs[-1] == "up" else "RED", "st_age_bars": flip,
            "sma200": sma200, "vs_sma200_pct": (c[-1] / sma200 - 1) * 100}


def label(x, up, down):
    return "UP" if x >= up else "DOWN" if x <= down else "FLAT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gift", type=float, default=None)
    ap.add_argument("--gift-prev", type=float, default=None, help="GIFT Nifty previous close (for its own change)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    n = nifty()
    out = {"nifty": n, "cues": {}, "flags": []}
    try:
        v, vp, vc = last_two("%5EINDIAVIX")
        out["vix"] = {"level": v, "chg_pct": vc}
    except Exception as e:  # noqa: BLE001
        out["vix"] = {"error": str(e)}
    for name, sym in CUES:
        try:
            p, prev, ch = last_two(sym)
            out["cues"][name] = {"price": p, "chg_pct": ch}
        except Exception as e:  # noqa: BLE001
            out["cues"][name] = {"error": str(e)}
    gl = [out["cues"][k]["chg_pct"] for k in ("S&P 500 fut", "Nasdaq fut", "Nikkei", "Hang Seng") if out["cues"].get(k, {}).get("chg_pct") is not None]
    out["global_score_pct"] = sum(gl) / len(gl) if gl else None
    if (out["cues"].get("Brent", {}).get("chg_pct") or 0) >= 2:
        out["flags"].append("Brent up 2%+ (negative for India)")
    if (out["cues"].get("USD/INR", {}).get("chg_pct") or 0) >= 0.5:
        out["flags"].append("USD/INR up 0.5%+ (rupee weaker)")
    if (out["cues"].get("US 10y yield", {}).get("chg_pct") or 0) >= 2:
        out["flags"].append("US 10y yield up 2%+")
    vx = out["vix"]
    if vx.get("level") and (vx["level"] >= 20 or (vx.get("chg_pct") or 0) >= 10):
        out["flags"].append(f"India VIX {vx['level']:.1f} ({vx.get('chg_pct', 0):+.1f}%): elevated")
    if a.gift is not None:
        gap = (a.gift / n["last"] - 1) * 100
        out["gift"] = {"level": a.gift, "gap_pct": gap, "gap_points": a.gift - n["last"], "reference": "Nifty 50 cash close"}
        if a.gift_prev:
            out["gift"]["own_chg_pct"] = (a.gift / a.gift_prev - 1) * 100
            out["gift"]["own_chg_points"] = a.gift - a.gift_prev
            if abs(gap - out["gift"]["own_chg_pct"]) > 0.5:
                out["flags"].append("GIFT's own change and its gap vs the Nifty cash close differ by more than 0.5%: it moved while the cash market was shut, or it carries a futures premium")
        bias = label(gap, 0.25, -0.25)
        conf = "MEDIUM"
        if out["global_score_pct"] is not None and (label(out["global_score_pct"], 0.3, -0.3) != bias and bias != "FLAT"):
            conf = "LOW (global cues disagree with the gap)"
    else:
        out["gift"] = None
        gs = out["global_score_pct"]
        bias = label(gs, 0.3, -0.3) if gs is not None else "UNKNOWN"
        conf = "LOW (no GIFT Nifty level given: global cues only)"
    # no cash session since the previous weekday (holiday or missing data)?
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()
    prevwd = today - timedelta(days=1)
    while prevwd.weekday() >= 5:
        prevwd -= timedelta(days=1)
    if datetime.strptime(n["bar_date"], "%d %b %Y").date() < prevwd:
        out["flags"].append(f"no Nifty cash session since {n['bar_date']} (a holiday or missing data): GIFT moves in between are the whole gap")
    out["open_bias"] = {"direction": bias, "confidence": conf}
    if a.json:
        print(json.dumps(out, indent=1))
        return
    print(f"Nifty 50 ({n['bar_date']} close): {n['last']:.2f} ({n['chg_pct']:+.2f}% that session) | Supertrend {n['st']} for {n['st_age_bars']} bars | {n['vs_sma200_pct']:+.1f}% vs 200-day average")
    if out["gift"]:
        g = out["gift"]
        print(f"GIFT Nifty {g['level']:.2f}: {g['gap_points']:+.1f} pts, {g['gap_pct']:+.2f}% vs the Nifty cash close" + (f" | its own change {g['own_chg_points']:+.1f} pts ({g['own_chg_pct']:+.2f}%)" if "own_chg_pct" in g else ""))
    else:
        print("GIFT Nifty: not provided (pass --gift <level>; read it from the Zerodha MCP `NSEIX:GIFT NIFTY`); never guessed")
    for k, v in out["cues"].items():
        print(f"{k:13s} " + (f"{v['price']:.2f} ({v['chg_pct']:+.2f}%)" if "price" in v and v["chg_pct"] is not None else "n/a"))
    if "level" in out["vix"]:
        print(f"India VIX     {out['vix']['level']:.2f} ({out['vix']['chg_pct']:+.1f}%)")
    print(f"Global score (S&P fut, Nasdaq fut, Nikkei, Hang Seng): {out['global_score_pct']:+.2f}%" if out["global_score_pct"] is not None else "Global score: n/a")
    for f in out["flags"]:
        print("FLAG:", f)
    print(f"OPEN BIAS: {out['open_bias']['direction']}  confidence {out['open_bias']['confidence']}")


if __name__ == "__main__":
    main()
