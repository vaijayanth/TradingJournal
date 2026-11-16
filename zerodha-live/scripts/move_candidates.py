"""Old-sheet positions that now qualify to move to the new AZ dashboard. Read-only; places and changes nothing.

Rule (user, 2026-11-16): every position still on the old Google Sheet dashboard that is Supertrend GREEN and PROFITABLE (any profit size)
and in the Nifty F&O universe moves to the new dashboard. The user approves the exact list first; this script only finds them.

How: the frozen sheet baseline (data/baseline_from_sheet.json, open_dates / sheet_open_qty, what is left on the sheet after the moves)
crossed with the current Zerodha holdings (average cost), the Supertrend colour and price in covered_call_signals.json (the last close, not
a live quote). Left out: positions already moved (moved_from_sheet.json), excluded symbols, symbols the user keeps on the sheet
(kept_on_sheet), stocks outside the F&O universe, stocks no longer held in Zerodha, and symbols the user declined to move
(data/move_declined.json {"symbols": [...]}).
The baseline is a snapshot from 2026-11-08: rows the user closed or deleted on the sheet since then are not known here, so the user checks.

Usage:
  python zerodha-live/scripts/move_candidates.py            list the candidates (and the others with the reason)
  python zerodha-live/scripts/move_candidates.py --nudge    print ONLY when there are candidates (used by the SessionStart hook)
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def candidates():
    b = load(DATA / "baseline_from_sheet.json")
    cc = load(ROOT / "covered_call_signals.json")
    if not b or not cc:
        return [], [], None
    mv = load(DATA / "moved_from_sheet.json", {}) or {}
    moved, kept = set(mv.get("symbols", [])), set(mv.get("kept_on_sheet", {}))
    excl = set((load(DATA / "excluded_symbols.json", {}) or {}).get("symbols", []))
    declined = set((load(DATA / "move_declined.json", {}) or {}).get("symbols", []))
    uni = set((load(DATA / "fno_universe.json", {}) or {}).get("symbols", []))
    hold = {h["symbol"]: h for h in (load(DATA / "holdings_snapshot.json", {}) or {}).get("holdings", [])}
    px = {s["symbol"]: s for s in cc.get("stocks", [])}
    ok, other = [], []
    for sym in sorted(b.get("sheet_open_qty", {})):
        why = None
        if sym in moved:
            why = "already moved"
        elif sym in excl:
            why = "excluded"
        elif sym in kept:
            why = "kept on the sheet"
        elif sym in declined:
            why = "declined by you"
        elif sym not in uni:
            why = "not in the F&O universe"
        elif sym not in hold:
            why = "no longer held in Zerodha"
        elif sym not in px:
            why = "no signal data"
        if why:
            other.append((sym, why))
            continue
        h, c = hold[sym], px[sym]
        pl = (c["spot"] / h["avg_cost"] - 1) * 100
        row = {"symbol": sym, "sheet_qty": b["sheet_open_qty"][sym], "held_qty": h["qty"], "avg_cost": h["avg_cost"], "price": c["spot"], "pl_pct": round(pl, 2),
               "colour": c["colour"], "entry_date": b["open_dates"].get(sym), "flip_date": c.get("flip_date")}
        if c["colour"] == "green" and pl > 0:
            ok.append(row)
        else:
            other.append((sym, f"{c['colour']}, {pl:+.1f}%"))
    return ok, other, cc.get("market_data_date")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nudge", action="store_true")
    a = ap.parse_args()
    ok, other, md = candidates()
    if a.nudge:
        if not ok:
            return
        print("AZ MOVE CANDIDATES - tell the user in your first reply (they asked to be nudged), list them, and ask whether to move them to the new dashboard:")
        for r in sorted(ok, key=lambda r: -r["pl_pct"]):
            print(f"  - {r['symbol']}: {r['held_qty']} shares, {r['pl_pct']:+.1f}% (avg {r['avg_cost']:g}, price {r['price']:g} at the {md} close), entry {r['entry_date']}, green since {r['flip_date']}")
        print("  Rule: old-sheet position that is Supertrend green AND profitable AND in the F&O universe. Never move without the user's explicit yes on the exact list; "
              "then add them to zerodha-live/data/moved_from_sheet.json (and remove from baseline_from_sheet.json) as on 2026-11-16, and tell the user to delete the sheet rows.")
        return
    print(f"Old-sheet positions that are Supertrend green and profitable (prices: {md} close): {len(ok)}")
    for r in sorted(ok, key=lambda r: -r["pl_pct"]):
        print(f"  {r['symbol']:<12} qty {r['held_qty']:>5} (sheet {r['sheet_qty']})  avg {r['avg_cost']:>9.2f}  price {r['price']:>9.2f}  {r['pl_pct']:>+6.1f}%  entry {r['entry_date']}  green since {r['flip_date']}")
    print(f"Not eligible: {len(other)}")
    for s, why in other:
        print(f"  {s:<12} {why}")


if __name__ == "__main__":
    main()
