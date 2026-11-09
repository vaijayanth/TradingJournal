"""Build a ticket for a NEW Dhan (ND) option position placed as a SUPER order (used by the dhan-superorder skill, Part 3).

Usage:
  python dhan-live/scripts/build_option_ticket.py --symbol INFY --structure call|put-spread --expiry 2026-12-29 [--lots 1] [--otm-pct 10]
Input: the option chain for that stock and expiry, saved verbatim from the Dhan MCP (market_data_agent_tool optionchain) as
  data/cc_raw/chains/<SYMBOL>_<EXPIRY>.txt   (the script refuses a chain that was not saved today)

What it picks (user rule 2026-11-09): the listed strike nearest to `otm-pct` percent away from the stock price in the chain header
(a call above the price, a put below it). A put spread also buys the hedge `hedge_strikes_below` listed strikes under the short put.
It shows the premium (the chain's last traded price: the Dhan chain has no bid/ask, so the skill adds a live quote for the chosen
contract), the credit, the lot, the quantity and the super order legs: stop = stop_premium_multiple x the premium, target = the
premium decayed profit_exit_decay_pct (60%) i.e. 40% of it, trailing jump 0.05 (all rounded to the 0.05 tick).
Refuses: trading_halt.json halt, a global guardrail block, expiry week, a stock outside the covered-call universe, no lot size.
Warns: a price that looks stale (out of line with its neighbouring strikes) or thin open interest.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))
TICK = 0.05
MAX_LOTS = 4
MIN_OI = 20000        # below this, the premium is probably thin / stale


def tick(x, up=False):
    import math
    n = x / TICK
    return round((math.ceil(n - 1e-9) if up else math.floor(n + 0.5)) * TICK, 2)


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def parse_chain(text):
    spot = re.search(r"underlying LTP ₹([\d,.]+)", text)
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*([\d.]+)\s*\|\s*([\d.]+)\s+(\d+)\s+([\d.]+)\s*\|\s*([\d.]+)\s+(\d+)\s+([\d.]+)", line)
        if m:
            k, cl, co, ci, pl, po, pi = m.groups()
            rows.append({"strike": float(k), "ce_ltp": float(cl), "ce_oi": int(co), "ce_iv": float(ci), "pe_ltp": float(pl), "pe_oi": int(po), "pe_iv": float(pi)})
    return float(spot.group(1).replace(",", "")) if spot else None, rows


def stale_flag(rows, i, kind):
    """A premium out of line with its neighbours (calls must not rise with the strike, puts must not fall) or with thin OI."""
    ltp, oi = (rows[i]["ce_ltp"], rows[i]["ce_oi"]) if kind == "CE" else (rows[i]["pe_ltp"], rows[i]["pe_oi"])
    key = "ce_ltp" if kind == "CE" else "pe_ltp"
    why = []
    if oi < MIN_OI:
        why.append(f"thin open interest ({oi:,})")
    for j in (i - 1, i + 1):
        if 0 <= j < len(rows):
            lo, hi = (j, i) if j < i else (i, j)
            a, b = rows[lo][key], rows[hi][key]
            if (kind == "CE" and a < b) or (kind == "PE" and a > b):
                why.append(f"price out of line with the {rows[j]['strike']:g} strike")
                break
    return why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--structure", choices=["call", "put-spread"], required=True)
    ap.add_argument("--expiry", required=True, help="YYYY-MM-DD, one of the expiries in data/cc_config.json")
    ap.add_argument("--lots", type=int, default=1)
    ap.add_argument("--otm-pct", type=float, default=10.0)
    ap.add_argument("--chain")
    ap.add_argument("--preview", action="store_true", help="show the pick and the premium even when the guardrails block placing; writes no ticket")
    a = ap.parse_args()
    sym = a.symbol.upper()

    if (load(DATA / "trading_halt.json", {}) or {}).get("halt"):
        sys.exit("REFUSED: trading halt is ON. Nothing may be placed.")
    g = load(DATA / "guardrails.json", {})
    blocked_note = None
    if g.get("global_block"):
        blk = [f["msg"] for f in g.get("findings", []) if f["level"] == "BLOCK" and f.get("symbol") is None]
        blocked_note = "guardrails block placing (prices suspect): " + " | ".join(blk)[:300]
        if not a.preview:
            sys.exit("REFUSED by guardrails (prices suspect, nothing may be opened): " + " | ".join(blk)[:400])
    if sym in (g.get("per_symbol_blocks") or {}) and not a.preview:
        sys.exit(f"REFUSED: {sym} is blocked by the guardrails: {g['per_symbol_blocks'][sym]}")
    cfg = load(DATA / "cc_config.json")
    uni, rules = cfg["universe"], cfg["rules"]
    if sym not in uni:
        sys.exit(f"REFUSED: {sym} is not in the covered-call universe ({', '.join(uni)}).")
    if a.expiry not in cfg.get("expiries", []):
        sys.exit(f"REFUSED: {a.expiry} is not a known expiry ({cfg.get('expiries')}).")
    days = (date.fromisoformat(a.expiry) - datetime.now(IST).date()).days
    if days <= rules.get("expiry_week_days", 5):
        sys.exit(f"REFUSED: {a.expiry} is {days} days away: expiry week, no new option structure (guardrail P1).")
    if not 1 <= a.lots <= MAX_LOTS:
        sys.exit(f"REFUSED: lots must be 1-{MAX_LOTS}.")
    lots_by = (load(DATA / "nse_lots.json", {}) or {}).get("lots", {}).get(sym, {})
    lot = lots_by.get(a.expiry[:7]) or uni[sym].get("lot")
    if not lot:
        sys.exit(f"REFUSED: no lot size for {sym} in {a.expiry[:7]}.")

    cp = Path(a.chain) if a.chain else DATA / "cc_raw" / "chains" / f"{sym}_{a.expiry}.txt"
    if not cp.exists() or datetime.fromtimestamp(cp.stat().st_mtime, IST).date() != datetime.now(IST).date():
        sys.exit(f"REFUSED: no option chain saved today at {cp}. Pull it (market_data_agent_tool optionchain, UnderlyingScrip {uni[sym]['security_id']}, "
                 f"UnderlyingSeg NSE_EQ, Expiry {a.expiry}) and save the raw text there.")
    spot, rows = parse_chain(cp.read_text(encoding="utf-8"))
    if not spot or not rows:
        sys.exit("REFUSED: the chain file could not be read (no underlying price or no strike rows).")

    kind = "CE" if a.structure == "call" else "PE"
    target = spot * (1 + a.otm_pct / 100) if kind == "CE" else spot * (1 - a.otm_pct / 100)
    # dead rows (no open interest: old or adjusted-away series, e.g. after a split/bonus) are never candidates
    rows = [r for r in rows if (r["ce_oi"] > 0 and r["ce_ltp"] > 0 if kind == "CE" else r["pe_oi"] > 0 and r["pe_ltp"] > 0)]
    if not rows:
        sys.exit("REFUSED: no live strikes (open interest > 0) in the chain.")
    i = min(range(len(rows)), key=lambda j: (abs(rows[j]["strike"] - target), -abs(rows[j]["strike"] - spot)))
    r = rows[i]
    prem = r["ce_ltp"] if kind == "CE" else r["pe_ltp"]
    legs = [{"role": "short", "type": kind, "strike": r["strike"], "ltp": prem, "oi": r["ce_oi"] if kind == "CE" else r["pe_oi"],
             "iv": r["ce_iv"] if kind == "CE" else r["pe_iv"], "pct_from_spot": round((r["strike"] / spot - 1) * 100, 1), "warn": stale_flag(rows, i, kind)}]
    hedge = None
    if a.structure == "put-spread":
        h = i - rules.get("hedge_strikes_below", 2)
        if h < 0:
            sys.exit("REFUSED: no listed strike far enough below to hedge.")
        hr = rows[h]
        hedge = {"role": "hedge", "type": "PE", "strike": hr["strike"], "ltp": hr["pe_ltp"], "oi": hr["pe_oi"], "iv": hr["pe_iv"],
                 "pct_from_spot": round((hr["strike"] / spot - 1) * 100, 1), "warn": stale_flag(rows, h, "PE")}
        legs.append(hedge)
    qty = lot * a.lots
    stop = tick(rules.get("stop_premium_multiple", 3) * prem)
    target_px = max(TICK, tick(prem * (1 - rules.get("profit_exit_decay_pct", 60) / 100)))
    credit = prem - (hedge["ltp"] if hedge else 0)
    ticket = {"symbol": sym, "structure": a.structure, "expiry": a.expiry, "spot": spot, "otm_pct_asked": a.otm_pct, "lot": lot, "lots": a.lots, "quantity": qty,
              "legs": legs, "super_order": {"transactionType": "SELL", "exchangeSegment": "NSE_FNO", "orderType": "LIMIT", "productType": "MARGIN", "price": prem,
                                             "stopLossPrice": stop, "targetPrice": target_px, "trailingJump": 0.05},
              "net_credit_per_share": round(credit, 2), "net_credit_rs": round(credit * qty)}
    if not a.preview:
        (DATA / "option_ticket.json").write_text(json.dumps(ticket, indent=1))
    print(f"{sym} {a.structure} {a.expiry}: stock {spot:g}, rule = strike nearest {a.otm_pct:g}% {'above' if kind == 'CE' else 'below'} -> target {target:.1f}")
    print(f"  SHORT {r['strike']:g}{kind}  ({legs[0]['pct_from_spot']:+.1f}% from the price)  premium (last traded) Rs{prem:g}  OI {legs[0]['oi']:,}  IV {legs[0]['iv']:g}")
    for w in legs[0]["warn"]:
        print(f"    WARNING: {w}")
    if hedge:
        print(f"  HEDGE BUY {hedge['strike']:g}PE ({hedge['pct_from_spot']:+.1f}%)  premium Rs{hedge['ltp']:g}  OI {hedge['oi']:,}")
        for w in hedge["warn"]:
            print(f"    WARNING: {w}")
    if legs[0]["warn"]:   # offer the nearest strike that has real open interest and a price in line with its neighbours
        okc = [j for j in range(len(rows)) if j != i and not stale_flag(rows, j, kind)]
        if okc:
            j = min(okc, key=lambda x: abs(rows[x]["strike"] - target))
            alt = rows[j]
            print(f"    nearest liquid alternative: {alt['strike']:g}{kind} ({(alt['strike'] / spot - 1) * 100:+.1f}%)  premium Rs{(alt['ce_ltp'] if kind == 'CE' else alt['pe_ltp']):g}  OI {(alt['ce_oi'] if kind == 'CE' else alt['pe_oi']):,}")
    print(f"  lot {lot} x {a.lots} = {qty} qty;  net credit Rs{credit:g}/share = Rs{round(credit * qty):,}")
    print(f"  super order: SELL LIMIT {prem:g}, stop {stop:g} ({stop / prem:.1f}x), target {target_px:g}, trailing jump 0.05")
    print("  Premium is the chain's last price, not a bid/ask: get a live quote for the contract before the limit price is agreed.")
    if a.preview:
        print("PREVIEW ONLY - not placeable" + (f": {blocked_note}" if blocked_note else "") + ". No ticket was written.")
    else:
        print("TICKET_JSON=" + json.dumps(ticket))


if __name__ == "__main__":
    main()
