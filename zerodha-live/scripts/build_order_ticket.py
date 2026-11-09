"""Build AZ (Zerodha) stock order tickets from zerodha_live_signals.json - the single source of what may be traded.

Only stocks that currently have a signal can appear (no options, no excluded symbols, nothing the user types in by hand).
Quantities come from the engine, never from the caller:
  entry : each entry signal (Supertrend flipped to green within the entry window, no holding in the account), qty = qty_to_buy
          (Rs20,000 tier floored to whole shares, min 1), BUY
  addon : each add-on signal (green and down 6% or more, 1/10 of the quantity, weekly cooldown), qty = add_qty, BUY
  buy   : entry + add-on signals in ONE numbered list (what /zerodha-order-entry shows for one-shot picking)
  exit  : each exit signal (Supertrend red after the grandfather cut-off, any profit or loss), qty = the WHOLE open position, SELL
          (what /zerodha-order-exit shows). Each exit ticket carries the position's avg_cost and entry_date (for zerodha_trades.py pending)
          and a warning when a short CALL is open on the stock (selling the shares would leave it uncovered).
The ticket is information for the order skills (zerodha-order-entry / zerodha-order-exit); this script places nothing.

Usage:
  python zerodha-live/scripts/build_order_ticket.py buy|entry|addon|exit        # numbered list
  python zerodha-live/scripts/build_order_ticket.py buy --pick 3,7,12-15        # tickets for those numbers
  python zerodha-live/scripts/build_order_ticket.py buy --symbols A,B           # or by symbol (must have a signal)
  python zerodha-live/scripts/build_order_ticket.py buy --override A,B          # include signals the cross-check flagged (deliberate)
Every signal must pass data/signal_crosscheck.json (crosscheck_signals.py --mode flip: Supertrend recomputed from complete Yahoo
history). Flagged signals are listed as BLOCKED and are not selectable unless named in --override.
Numbers are stable for a given signal file (entries in file order, then add-ons). Prints a table and a final TICKETS_JSON= line.
Exit code 2 = refuse (stale data, guardrail block, stock without a signal, bad pick). Nothing here imports from dhan-live.
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from order_gate import check_caps, load_gate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_STALE_DAYS = 3


def parse_pick(text, n):
    nums = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            nums.update(range(int(a), int(b) + 1))
        else:
            nums.add(int(part))
    bad = sorted(x for x in nums if x < 1 or x > n)
    if bad:
        print(f"REFUSED: pick numbers {bad} are not in the list (1-{n}).")
        sys.exit(2)
    return nums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["buy", "entry", "addon", "exit"])
    ap.add_argument("--pick", default="", help="numbers from the printed list, e.g. 3,7,12-15")
    ap.add_argument("--symbols", default="", help="comma list: restrict to these signal stocks (must already have a signal)")
    ap.add_argument("--override", default="", help="comma list of cross-check-FLAGGED symbols to include anyway")
    ap.add_argument("--crosscheck", default=str(ROOT / "data" / "signal_crosscheck.json"))
    ap.add_argument("--signals", default=str(ROOT / "zerodha_live_signals.json"))
    ap.add_argument("--holdings", default=str(ROOT / "data" / "holdings_snapshot.json"))
    ap.add_argument("--excluded", default=str(ROOT / "data" / "excluded_symbols.json"))
    ap.add_argument("--all-days", action="store_true", help="list entry signals from every flip day in the window (default: only the freshest flip day that has an orderable signal)")
    ap.add_argument("--allow-big-batch", action="store_true", help="user-approved: skip the batch size / value caps")
    args = ap.parse_args()

    sig = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    held = {h["symbol"]: h for h in json.loads(Path(args.holdings).read_text(encoding="utf-8"))["holdings"]}
    ex_p = Path(args.excluded)
    excluded = set(json.loads(ex_p.read_text(encoding="utf-8")).get("symbols", [])) if ex_p.exists() else set()
    md = sig.get("market_data_date")
    age = (date.today() - datetime.strptime(md, "%Y-%m-%d").date()).days if md else None
    if age is None or age > MAX_STALE_DAYS:
        print(f"REFUSED: signal data is {age} days old (market data {md}); run /refresh-zerodha first.")
        sys.exit(2)

    gate_blocks, gate_cfg = load_gate(sig)   # guardrails: halt / stale data / mass exit ... refuse everything; per-stock blocks below

    cc_path = Path(args.crosscheck)
    if not cc_path.exists():
        print("REFUSED: no signal cross-check found - run /refresh-zerodha (it runs crosscheck_signals.py --mode flip) first.")
        sys.exit(2)
    cc = json.loads(cc_path.read_text(encoding="utf-8"))
    if cc.get("market_data_date") != md:
        print(f"REFUSED: the cross-check is for market data {cc.get('market_data_date')} but the signals are {md}; re-run /refresh-zerodha.")
        sys.exit(2)
    flagged = {(x["kind"], x["symbol"]): x["reasons"] for x in cc["results"] if not x["ok"]}
    covered = {(x["kind"], x["symbol"]) for x in cc["results"]}
    override = {s.strip().upper() for s in args.override.split(",") if s.strip()}

    srcs = {"entry": sig.get("entries", []), "addon": sig.get("addons", []), "exit": sig.get("exits", [])}
    legs_p = ROOT / "data" / "cc_positions.json"
    short_calls = {}
    if legs_p.exists():
        for l in json.loads(legs_p.read_text(encoding="utf-8")).get("legs", []):
            if l.get("side") == "SHORT" and l.get("type") == "CE":
                short_calls.setdefault(l["symbol"], []).append(f"{l['tradingsymbol']} x{l['qty']}")
    kinds = ["entry", "addon"] if args.kind == "buy" else [args.kind]
    all_symbols = {(k, r["symbol"]) for k in kinds for r in srcs[k]}
    want = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
    unknown = want - {s for _, s in all_symbols}
    if unknown:
        print(f"REFUSED: no current {'/'.join(kinds)} signal for {sorted(unknown)} - nothing is placed for stocks without a signal.")
        sys.exit(2)

    tickets, skipped, blocked = [], [], []
    for kind in kinds:
        for r in srcs[kind]:
            s = r["symbol"]
            if s in excluded:
                skipped.append((s, "excluded symbol (data/excluded_symbols.json)")); continue
            h = held.get(s)
            if kind == "entry":
                qty = r.get("qty_to_buy") or 0
                if h and h["qty"] > 0:
                    skipped.append((s, "already held in the account")); continue
                ref, why = r["close"], f"Supertrend {r['supertrend_color']}, {r.get('flip_label')} (flip {r.get('flip_date')})"
            elif kind == "exit":
                qty = r["qty"]
                if not h or h["qty"] != qty:
                    skipped.append((s, f"signal qty {qty} != holdings qty {h['qty'] if h else 0} - refresh holdings first")); continue
                ref = r["cmp"]
                why = f"Supertrend red ({r.get('flip_label')}), P&L {r['pl_pct']:.1f}% - exit the whole position"
            else:
                qty = r.get("add_qty") or 0
                if not h or h["qty"] != r["qty"]:
                    skipped.append((s, f"signal qty {r['qty']} != holdings qty {h['qty'] if h else 0} - refresh holdings first")); continue
                ref = r["cmp"]
                why = (f"add-on: P&L {r['pl_pct']:.1f}% (at or beyond -6%), Supertrend {r['supertrend_color']}, "
                       f"{r.get('cooldown_days_since_last_buy')}d since last buy")
            if qty < 1:
                skipped.append((s, "quantity < 1 share")); continue
            if s in gate_blocks:
                blocked.append((kind, s, "guardrail: " + "; ".join(gate_blocks[s]))); continue
            bad = flagged.get((kind, s))
            if bad is None and (kind, s) not in covered:
                bad = ["not covered by the cross-check"]
            if bad and s not in override:
                blocked.append((kind, s, "; ".join(bad))); continue
            extra = {}
            if kind == "exit":
                extra = {"avg_cost": r["avg_cost"], "entry_date": r.get("entry_date"), "pl_pct": r["pl_pct"]}
                if s in short_calls:
                    extra["warning"] = "short CALL open on this stock (" + ", ".join(short_calls[s]) + "): selling the shares leaves it uncovered"
            tickets.append({**extra, "kind": kind, "symbol": s, "side": "SELL" if kind == "exit" else "BUY", "qty": int(qty), "ref_price": ref,
                            "est_value": round(qty * ref, 2), "reason": why, "market_data_date": md,
                            "crosscheck": "OVERRIDDEN: " + "; ".join(bad) if bad else "ok",
                            "flip_days_ago": r.get("recent_bullish_flip_days_ago") if kind == "entry" else None})
    # user rule (2026-11-09): order only the freshest flips. If today's flips (age 0) have orderable signals, list only those; if there are none,
    # the freshest day that has some (yesterday = 1, then 2 ...). Add-ons are not flip signals and are always listed.
    older = []
    if not args.all_days:
        ages = [t["flip_days_ago"] for t in tickets if t["kind"] == "entry" and t["flip_days_ago"] is not None]
        if ages:
            fresh = min(ages)
            older = [t for t in tickets if t["kind"] == "entry" and t["flip_days_ago"] is not None and t["flip_days_ago"] != fresh]
            tickets = [t for t in tickets if t not in older]
            fresh_note = f"entry signals shown: flips {'today' if fresh == 0 else str(fresh) + ' trading day(s) ago'} only ({len(older)} older flip(s) hidden; --all-days shows them)"
    for i, t in enumerate(tickets, 1):
        t["no"] = i

    chosen = tickets
    if args.pick:
        nums = parse_pick(args.pick, len(tickets))
        chosen = [t for t in tickets if t["no"] in nums]
    if want:
        chosen = [t for t in chosen if t["symbol"] in want]

    if args.pick or want:
        for pr in check_caps(chosen, (sig.get("capital_base") or {}).get("initial_capital"), gate_cfg, args.allow_big_batch):
            print("  BATCH CAP OVERRIDDEN by the user: " + pr)
    label = "selected" if (args.pick or want) else "available"
    print(f"{args.kind.upper()} signals dated {md} ({age}d old) - {len(chosen)} {label}" + ("" if (args.pick or want) else " (numbered):"))
    for t in chosen:
        print(f"  {t['no']:>2}) {t['side']:4} {t['symbol']:12} x{t['qty']:<4} ref Rs{t['ref_price']:<9} ~Rs{t['est_value']:<9} [{t['kind']}] {t['reason']}")
    if older:
        print("  " + fresh_note)
    for t in chosen:
        if t.get("warning"):
            print(f"  WARNING {t['symbol']}: {t['warning']}")
    for s, why in skipped:
        print(f"  skipped {s}: {why}")
    for kind, s, why in blocked:
        print(f"  BLOCKED [{kind}] {s}: {why}")
    if args.pick or want:
        print(f"  total ~Rs{sum(t['est_value'] for t in chosen):,.2f}")
    print("TICKETS_JSON=" + json.dumps(chosen))


if __name__ == "__main__":
    main()
