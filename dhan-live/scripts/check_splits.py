"""Find stock splits / bonus issues that happened AFTER one of your dh252 fills and are not yet recorded in data/corporate_actions.json.
Read-only: it never changes the ledger, it only writes data/split_check.json, which guardrails.py shows as the I8 warning.

Source: Yahoo Finance split history for every symbol that has a fill. Yahoo reports a bonus issue as a split too (1:1 bonus = ratio 2).
A hit means: the ledger may compare pre-event prices with post-event prices (a fake loss or gain). Fix it by adding the event to data/corporate_actions.json.
Usage: python dhan-live/scripts/check_splits.py   (run by refresh_dhan.py; never exits non-zero, a Yahoo failure just leaves the old file)
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corp_actions import load_actions  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
IST = timezone(timedelta(hours=5, minutes=30))


def splits_of(sym):
    import yfinance as yf
    try:
        s = yf.Ticker(sym + ".NS").splits
        return sym, [(x.date(), float(v)) for x, v in s.items() if float(v) > 0 and float(v) != 1]
    except Exception:
        return sym, None


def main():
    log = json.loads((DATA / "dh252_trade_log.json").read_text(encoding="utf-8"))
    fills = log.get("fills", [])
    first, count_before = {}, {}
    for f in fills:
        first[f["symbol"]] = min(first.get(f["symbol"], f["date"]), f["date"])
    today = datetime.now(IST).date()
    recorded = {(a["symbol"].upper(), a["ex_date"]) for a in load_actions()}
    syms = sorted(first)
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = dict(ex.map(splits_of, syms))
    unrecorded, failed = [], []
    for sym in syms:
        sp = got.get(sym)
        if sp is None:
            failed.append(sym)
            continue
        for d, ratio in sp:
            ds = d.isoformat()
            if date.fromisoformat(first[sym]) < d <= today and (sym.upper(), ds) not in recorded:
                n_before = sum(1 for f in fills if f["symbol"] == sym and f["date"] < ds)
                if n_before:
                    unrecorded.append({"symbol": sym, "ex_date": ds, "ratio": ratio, "fills_before": n_before, "first_fill": first[sym]})
    out = {"generated_at": datetime.now(IST).isoformat(timespec="seconds"), "checked": len(syms), "failed": failed, "recorded": len(recorded), "unrecorded": unrecorded}
    (DATA / "split_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"split check: {len(syms)} symbols, {len(failed)} not checked, unrecorded splits after your buys: "
          + (", ".join(f"{u['symbol']} {u['ratio']:g}:1 on {u['ex_date']}" for u in unrecorded) or "none"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # a Yahoo problem must never stop the refresh
        print(f"split check skipped: {e}")
