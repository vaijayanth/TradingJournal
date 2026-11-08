"""Freeze the Zerodha history that the NEW dashboard starts from: the Google Sheet (TRADES), F&O stocks only.

Why: the new Zerodha dashboard reads open positions from the Zerodha MCP (holdings), but the MCP tradebook is today-only, so
the closed-trade history and the trade count that sets the position size have to come from somewhere once. That is the
sheet your old dashboard already reads. This script copies it ONCE as of a cut-off date; from the cut-off on, new trades are
tracked from MCP fills (data/zerodha_trade_log.json) and the sheet is never re-read, so nothing is counted twice.

Scope decision (user, 2026-11-09): the new dashboard covers Nifty F&O stocks only. Sheet trades in other stocks are left out
completely (they still show on the old sheet dashboard). Which stocks are "F&O" is taken from data/fno_universe.json at the
time this runs.

Writes data/baseline_from_sheet.json. Refuses to overwrite an existing baseline unless --force (re-freezing later would
double count trades made since the cut-off).

Usage: python zerodha-live/scripts/freeze_baseline.py [--cutoff YYYY-MM-DD] [--force]
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "baseline_from_sheet.json"
SHEET_URL = "https://script.google.com/macros/s/AKfycbwh85dD1AlNlMFRk4M4A8yCA5YAs5gvnCIMgq6ixQUhdxmes-CqU3OYOdxtzDRLRgLq/exec"
COLS = dict(sheet="TRADES", headerRows="1", flagCol="B", stockCol="E", openDateCol="C", closeDateCol="D", ema200Col="F", ema50Col="G",
            cmpCol="J", sevenDayLowCol="K", stopLossCol="L", initRiskRsCol="M", initRiskPctCol="N", qtyCol="Q", entryPriceCol="R",
            setupTypeCol="S", plPctCol="X", notionalPlCol="W", finalExitPriceCol="AC", finalPlCol="AD", finalPlPctCol="AE",
            ageCol="AF", portfolioCell="AH3", initialCapCell="AH2")
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def iso(d):  # "21-Apr-2026" -> "2026-04-21"
    try:
        dd, mon, yy = d.split("-")
        return f"{yy}-{MON[mon]:02d}-{int(dd):02d}"
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", help="cut-off date YYYY-MM-DD (default: the backtester's latest market date)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        print(f"REFUSED: {OUT.name} already exists (frozen {json.loads(OUT.read_text()).get('cutoff_date')}). Re-freezing would double count "
              f"trades made since then; use --force only if you mean to start over.")
        return 2
    uni = set(json.loads((DATA / "fno_universe.json").read_text())["symbols"])
    cutoff = args.cutoff
    if not cutoff:
        st = DATA.parent.parent / "dhan-live" / "data" / "cache" / "supertrend_full.json"
        cutoff = json.loads(st.read_text()).get("latest_market_date") if st.exists() else datetime.now(timezone.utc).date().isoformat()
    req = urllib.request.Request(SHEET_URL + "?" + urllib.parse.urlencode(COLS), headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=90).read())
    if not d.get("success"):
        print("REFUSED: the sheet feed returned an error:", d.get("error"))
        return 2

    closed = []
    for t in d["closed"]:
        if t["stock"] not in uni:
            continue
        closed.append({"symbol": t["stock"], "entry_date": iso(t["openDate"]), "exit_date": iso(t["closeDate"]), "qty": t["qty"],
                       "entry": t["entryPrice"], "exit": t["finalExitPrice"], "pl_rs": round(t["finalPl"], 2),
                       "pl_pct": t["finalPlPct"], "hold_days": t["age"]})
    open_rows = [t for t in d["open"] if t["stock"] in uni]
    open_dates, last_buy, sheet_qty = {}, {}, {}
    for t in open_rows:
        s, od = t["stock"], iso(t["openDate"])
        if od:
            open_dates[s] = min(open_dates.get(s, od), od)
            last_buy[s] = max(last_buy.get(s, od), od)
        sheet_qty[s] = sheet_qty.get(s, 0) + t["qty"]
    out = {
        "frozen_at": datetime.now(timezone.utc).isoformat(), "cutoff_date": cutoff,
        "source": "Google Sheet TRADES via the Apps Script feed (the old dashboard's source), F&O stocks only",
        "note": "Frozen ONCE. New trades after cutoff_date come from Zerodha MCP fills; never re-read the sheet (double counting).",
        "universe_month": json.loads((DATA / "fno_universe.json").read_text())["month"],
        "sheet_totals": {"open_rows": len(d["open"]), "closed_rows": len(d["closed"]), "portfolio_value": d.get("portfolioValue"),
                         "initial_capital": d.get("initialCapital")},
        "in_universe": {"open_rows": len(open_rows), "open_stocks": len(sheet_qty), "closed_trades": len(closed)},
        "realised_pl_rs": round(sum(c["pl_rs"] for c in closed), 2),
        "closed": sorted(closed, key=lambda c: c["exit_date"] or ""),
        "open_dates": open_dates, "last_buy": last_buy, "sheet_open_qty": sheet_qty,
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(f"baseline frozen at cutoff {cutoff}: {len(closed)} closed F&O trades (realised Rs{out['realised_pl_rs']:,.0f}), "
          f"{len(open_rows)} open sheet rows over {len(sheet_qty)} F&O stocks; {len(d['closed']) - len(closed)} closed and "
          f"{len(d['open']) - len(open_rows)} open non-F&O rows left out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
