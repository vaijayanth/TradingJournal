"""Find stock splits / bonus issues that happened AFTER one of your dh252 fills and are not yet recorded in data/corporate_actions.json.
It writes data/split_check.json, which guardrails.py shows as I8. Since 2026-11-18 (user) it also RECORDS the event by itself when Dhan's
holdings prove the shares were credited: the holdings quantity equals floor(ledger qty before the ex-date x ratio) plus the net of the fills
on / after it (a fractional share is paid in cash, PASHUPATI). Anything that does not match exactly stays unrecorded and I8 BLOCKS that stock.

Source: Yahoo Finance split history for every symbol that has a fill. Yahoo reports a bonus issue as a split too (1:1 bonus = ratio 2).
A hit means: the ledger may compare pre-event prices with post-event prices (a fake loss or gain). Fix it by adding the event to data/corporate_actions.json.
Usage: python dhan-live/scripts/check_splits.py   (run by refresh_dhan.py; never exits non-zero, a Yahoo failure just leaves the old file)
"""
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corp_actions import adjust_fills, load_actions  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
IST = timezone(timedelta(hours=5, minutes=30))


def splits_of(sym):
    import yfinance as yf
    try:
        s = yf.Ticker(sym + ".NS").splits
        return sym, [(x.date(), float(v)) for x, v in s.items() if float(v) > 0 and float(v) != 1]
    except Exception:
        return sym, None


def match_holdings(fills, actions, symbol, ex_date, ratio, holdings_qty):
    """Does Dhan's holdings quantity show that this split was credited? fills = the raw ledger fills of ONE symbol, actions = the already
    recorded actions. Returns (outcome, expected_qty, uncredited_qty): 'match' (holdings == floor(pre x ratio) + net after), 'uncredited'
    (holdings == the unadjusted quantity: the broker did not apply it) or 'mismatch' (anything else). pre_net <= 0 returns ('none', 0, 0)."""
    adj = adjust_fills([f for f in fills if f["symbol"].upper() == symbol.upper()], actions)

    def net(rows):
        return sum(f["qty"] if f.get("action", "BUY") == "BUY" else -f["qty"] for f in rows)

    pre = net([f for f in adj if f["date"] < ex_date])
    after = net([f for f in adj if f["date"] >= ex_date])
    if pre <= 1e-9:
        return "none", 0, 0
    expected = math.floor(pre * ratio + 1e-9) + after
    uncredited = pre + after
    if abs(holdings_qty - expected) < 1e-6:
        return "match", expected, uncredited
    if abs(holdings_qty - uncredited) < 1e-6:
        return "uncredited", expected, uncredited
    return "mismatch", expected, uncredited


def record_action(path, symbol, ex_date, ratio, holdings_qty, today):
    """Append an auto-recorded split to corporate_actions.json (keeps the note and the existing actions)."""
    d = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {"actions": []}
    d.setdefault("actions", []).append({"symbol": symbol, "ex_date": ex_date, "ratio": ratio, "type": "split", "auto_recorded": today, "holdings_qty": holdings_qty})
    Path(path).write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


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
    hp = DATA / "holdings_snapshot.json"
    held = {h["symbol"]: h["qty"] for h in json.loads(hp.read_text(encoding="utf-8")).get("holdings", [])} if hp.exists() else {}
    actions = load_actions()
    unrecorded, auto, failed = [], [], []
    for sym in syms:
        sp = got.get(sym)
        if sp is None:
            failed.append(sym)
            continue
        for d, ratio in sp:
            ds = d.isoformat()
            if date.fromisoformat(first[sym]) < d <= today and (sym.upper(), ds) not in recorded:
                n_before = sum(1 for f in fills if f["symbol"] == sym and f["date"] < ds)
                if not n_before:
                    continue
                outcome, expected, uncredited = match_holdings(fills, actions, sym, ds, ratio, held.get(sym, 0))
                if outcome == "none":
                    continue          # nothing was held on the ex-date: the ledger is not affected
                row = {"symbol": sym, "ex_date": ds, "ratio": ratio, "fills_before": n_before, "first_fill": first[sym],
                       "holdings_qty": held.get(sym), "expected_if_credited": expected, "unadjusted_qty": uncredited, "outcome": outcome}
                if outcome == "match" and sym in held:
                    record_action(DATA / "corporate_actions.json", sym, ds, ratio, held[sym], today.isoformat())
                    actions = load_actions()
                    recorded.add((sym.upper(), ds))
                    auto.append(row)
                else:
                    unrecorded.append(row)
    out = {"generated_at": datetime.now(IST).isoformat(timespec="seconds"), "checked": len(syms), "failed": failed, "recorded": len(recorded), "auto_recorded": auto, "unrecorded": unrecorded}
    (DATA / "split_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"split check: {len(syms)} symbols, {len(failed)} not checked, unrecorded splits after your buys: "
          + (", ".join(f"{u['symbol']} {u['ratio']:g}:1 on {u['ex_date']} ({u['outcome']})" for u in unrecorded) or "none")
          + ("; AUTO-RECORDED: " + ", ".join(f"{u['symbol']} {u['ratio']:g}:1 on {u['ex_date']}" for u in auto) if auto else ""))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # a Yahoo problem must never stop the refresh
        print(f"split check skipped: {e}")
