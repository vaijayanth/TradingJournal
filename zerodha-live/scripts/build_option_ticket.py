"""Build tickets for NEW option trades on the AZ (Zerodha) account (used by the zerodha-option-order skill). Places nothing.

Three steps, each a mode of this script (nothing here imports from dhan-live):
  list   numbered shortlist of stocks the engine says need an option trade (covered_call_signals.json: status ENTER or FLIP),
         ranked like the Covered Call page: most recent Supertrend flip first, then name.
         Supertrend red = sell a call; green = bull put spread (sell the put, buy a hedge put 2 listed strikes lower);
         the RSI override (above 70 = sell call, below 30 = bull put spread) is already inside `desired` for AZ.
  plan   for one stock: picks the listed strike nearest the user's distance rule (10% away from the stock price for the current-month
         expiry, 15% for a later month; a call above the price, a put below it) and prints QUOTE_INSTRUMENTS=[...] (the short strike, its
         neighbours and the hedge) for the skill to quote through the Zerodha MCP.
  build  with the saved quotes (--quotes <file>): premium, bid/ask, open interest, circuit limits, warnings, the nearest liquid
         alternative, lots, credit, maximum loss, stop (3x) and target (40%) for the later protective GTT, and the exact order payloads
         (hedge BUY first, then the SELL). Writes data/option_ticket.json and prints TICKET_JSON=.
Rules: expiry from the engine's list, expiry week refused, Nifty F&O stocks only (minus excluded_symbols.json), 1-4 lots, tick 0.05,
lot size from data/nfo_options.json. Refuses under data/trading_halt.json halt or a guardrail H1/X1 block. The F5 price-data block and the
other equity-signal blocks do NOT stop an option ticket (user, 2026-11-09): it is built from live option quotes for a stock you pick. The
results / ex-dividend rule is a WARNING only (user, 2026-11-09). Exit code 2 = refuse.
"""
import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))
TICK = 0.05
MAX_LOTS = 4
MIN_OI_LOTS = 20          # below this many lots of open interest the premium is probably thin
WIDE_SPREAD_PCT = 15.0    # bid-ask spread wider than this share of the mid price is flagged
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def refuse(msg):
    print("REFUSED: " + msg)
    sys.exit(2)


def tick(x, up=False):
    n = x / TICK
    return round((math.ceil(n - 1e-9) if up else math.floor(n + 0.5)) * TICK, 2)


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def tradingsymbol(sym, expiry, strike, kind):
    """NFO monthly stock option symbol, e.g. ABB26DEC6500CE."""
    d = date.fromisoformat(expiry)
    k = str(int(strike)) if float(strike) == int(strike) else f"{strike:g}"
    return f"{sym}{d:%y}{MONTHS[d.month - 1]}{k}{kind}"


def default_otm(expiry, today):
    """User rule (2026-11-09): about 10% away for the current-month expiry, about 15% for a later month."""
    return 10.0 if expiry[:7] == today.strftime("%Y-%m") else 15.0


def pick_strike(strikes, spot, kind, otm_pct):
    """The listed strike nearest the target distance, on the out-of-the-money side only; a tie goes to the strike farther from the price."""
    target = spot * (1 + otm_pct / 100) if kind == "CE" else spot * (1 - otm_pct / 100)
    cand = [k for k in strikes if (k > spot if kind == "CE" else k < spot)]
    if not cand:
        refuse(f"no listed {kind} strike on the out-of-the-money side of {spot:g}.")
    return min(cand, key=lambda k: (abs(k - target), -abs(k - spot))), target


def hedge_strike(strikes, short, n):
    """The listed put strike n strikes below the short put."""
    below = sorted(k for k in strikes if k < short)
    if len(below) < n:
        refuse("no listed strike far enough below the short put to hedge it.")
    return below[-n]


def quote_info(q, lot):
    """Premium facts from one Zerodha quote record, plus the reasons it may not be trustworthy."""
    d = q.get("depth") or {}
    buys = [x for x in d.get("buy", []) if x.get("quantity", 0) > 0 and x.get("price", 0) > 0]
    sells = [x for x in d.get("sell", []) if x.get("quantity", 0) > 0 and x.get("price", 0) > 0]
    bid, ask = (buys[0]["price"] if buys else None), (sells[0]["price"] if sells else None)
    ltp, oi, vol = q.get("last_price") or 0, q.get("oi") or 0, q.get("volume") or 0
    why = []
    if bid is None:
        why.append("no bid: a sell order may not fill")
    if ask is None:
        why.append("no ask")
    if bid and ask:
        mid = (bid + ask) / 2
        if mid > 0 and (ask - bid) / mid * 100 > WIDE_SPREAD_PCT:
            why.append(f"wide bid-ask spread ({bid:g} / {ask:g})")
    if lot and oi < MIN_OI_LOTS * lot:
        why.append(f"thin open interest ({oi // lot} lots)")
    if vol == 0:
        why.append("no trades today")
    if ltp and bid and ask and not (bid * 0.8 <= ltp <= ask * 1.2):
        why.append(f"last price {ltp:g} is outside the bid/ask range")
    return {"ltp": ltp, "bid": bid, "ask": ask, "bid_qty": buys[0]["quantity"] if buys else 0, "ask_qty": sells[0]["quantity"] if sells else 0,
            "oi": oi, "oi_lots": (oi // lot) if lot else None, "volume": vol, "last_trade_time": q.get("last_trade_time"),
            "lower_circuit": q.get("lower_circuit_limit"), "upper_circuit": q.get("upper_circuit_limit"), "warn": why}


def suggest_price(info, side):
    """A starting limit price (the user may change it): the middle of the bid-ask, rounded to the tick and kept inside the spread."""
    bid, ask = info["bid"], info["ask"]
    if bid and ask:
        mid = (bid + ask) / 2
        return tick(min(max(mid, bid), ask), up=(side == "BUY"))
    return None


def read_hard_blocks():
    halt = load(DATA / "trading_halt.json", {}) or {}
    if halt.get("halt"):
        refuse(f"trading halt is ON ({halt.get('reason', 'no reason given')}). Nothing may be placed.")
    g = load(DATA / "guardrails.json", {}) or {}
    hard = [f for f in g.get("findings", []) if f.get("level") == "BLOCK" and f.get("symbol") is None and f.get("id") in ("H1", "X1")]
    if hard:
        refuse("guardrails: " + " | ".join(f"{f['id']}: {f.get('msg', '')}" for f in hard)[:400])
    ignored = sorted({f["id"] for f in g.get("findings", []) if f.get("level") == "BLOCK" and f.get("symbol") is None and f.get("id") not in ("H1", "X1")})
    return g, ignored


def universe():
    ex = set((load(DATA / "excluded_symbols.json", {}) or {}).get("symbols", []))
    return {s for s in (load(DATA / "fno_universe.json", {}) or {}).get("symbols", [])} - ex, ex


def cmd_list(a):
    sig = load(ROOT / "covered_call_signals.json")
    if not sig:
        refuse("no covered_call_signals.json - run /refresh-zerodha first.")
    uni, _ = universe()
    rows = [s for s in sig["stocks"] if s.get("status") in ("ENTER", "FLIP") and s.get("desired") in ("CALL", "PUT_SPREAD") and s["symbol"] in uni and s.get("expiries")]
    want = {x.strip().upper() for x in a.symbols.split(",") if x.strip()}
    if want:
        rows = [s for s in rows if s["symbol"] in want]
    rows.sort(key=lambda s: (s.get("flip_trading_days") if s.get("flip_trading_days") is not None else 999, s["symbol"]))
    n = len(rows)
    rows = rows[: a.max]
    print(f"Option signals (covered_call_signals.json, market data {sig.get('market_data_date')}): {n} stocks need an option trade; showing {len(rows)}.")
    print("  Supertrend red = sell call; green = bull put spread. FLIP = an opposite structure is open (close it first; this skill does not).")
    out = []
    for i, s in enumerate(rows, 1):
        e = s["expiries"][0]
        struct = "sell call" if s["desired"] == "CALL" else "bull put spread"
        fd = s.get("flip_trading_days")
        flip = "flipped today" if fd == 0 else (f"flipped {fd}d ago" if fd is not None else "")
        warn = f"  EVENT: {s['event_block']}" if s.get("event_block") else ""
        print(f"  {i:>3}) {s['symbol']:<12} {struct:<16} spot {s['spot']:>9g}  RSI {s.get('rsi', '-'):>5}  {s['colour']:<5} {flip:<16} expiry {e['expiry']} lot {e['lot']}  [{s['status']}]{warn}")
        out.append({"no": i, "symbol": s["symbol"], "structure": "call" if s["desired"] == "CALL" else "put-spread", "expiry": e["expiry"], "lot": e["lot"], "status": s["status"]})
    print("LIST_JSON=" + json.dumps(out))


def common(a):
    sym = a.symbol.upper()
    uni, ex = universe()
    if sym in ex:
        refuse(f"{sym} is excluded (data/excluded_symbols.json).")
    if sym not in uni:
        refuse(f"{sym} is not in the Nifty F&O universe.")
    cfg = load(DATA / "cc_config.json")
    rules = cfg["rules"]
    today = datetime.now(IST).date()
    sig = load(ROOT / "covered_call_signals.json", {}) or {}
    st = next((s for s in sig.get("stocks", []) if s["symbol"] == sym), None)
    structure = a.structure or ({"CALL": "call", "PUT_SPREAD": "put-spread"}.get((st or {}).get("desired")))
    if not structure:
        refuse("no structure: pass --structure call|put-spread (the stock has no engine signal).")
    expiry = a.expiry or ((st or {}).get("expiries") or [{}])[0].get("expiry")
    if not expiry:
        refuse("no expiry: pass --expiry YYYY-MM-DD.")
    days = (date.fromisoformat(expiry) - today).days
    if days <= rules.get("expiry_week_days", 5):
        refuse(f"{expiry} is {days} days away: expiry week, no new option structure (guardrail P1).")
    opt = (load(DATA / "nfo_options.json", {}) or {}).get("symbols", {}).get(sym)
    if not opt or expiry not in opt.get("strikes", {}):
        refuse(f"{sym} has no listed strikes for {expiry} in data/nfo_options.json (run scripts/update_options_master.py).")
    lot = opt["lot"].get(expiry)
    if not lot:
        refuse(f"no lot size for {sym} {expiry}.")
    spot, spot_src = a.spot, "--spot (live)"
    if spot is None:
        lp = load(DATA / "cc_live_prices.json", {}) or {}
        if str(lp.get("fetched_at", ""))[:10] == str(today) and sym in (lp.get("prices") or {}):
            spot, spot_src = lp["prices"][sym], "live price file (today)"
        elif st:
            spot, spot_src = st["spot"], f"last close ({sig.get('market_data_date')})"
        else:
            refuse("no stock price: pass --spot.")
    kind = "CE" if structure == "call" else "PE"
    otm = a.otm_pct if a.otm_pct is not None else default_otm(expiry, today)
    return dict(sym=sym, rules=rules, today=today, st=st, structure=structure, expiry=expiry, opt=opt, lot=lot, spot=float(spot), spot_src=spot_src, kind=kind, otm=otm, days=days)


def cmd_plan(a):
    read_hard_blocks()
    c = common(a)
    strikes = sorted(c["opt"]["strikes"][c["expiry"]][c["kind"]])
    short, target = pick_strike(strikes, c["spot"], c["kind"], c["otm"])
    i = strikes.index(short)
    near = strikes[max(0, i - 2): i + 3]
    inst = [tradingsymbol(c["sym"], c["expiry"], k, c["kind"]) for k in near]
    hedge = None
    if c["structure"] == "put-spread":
        pstr = sorted(c["opt"]["strikes"][c["expiry"]]["PE"])
        hedge = hedge_strike(pstr, short, c["rules"].get("hedge_strikes_below", 2))
        inst.append(tradingsymbol(c["sym"], c["expiry"], hedge, "PE"))
    print(f"{c['sym']} {c['structure']} {c['expiry']}: stock {c['spot']:g} ({c['spot_src']}), rule = strike nearest {c['otm']:g}% "
          f"{'above' if c['kind'] == 'CE' else 'below'} -> target {target:.1f}; listed short strike {short:g}{c['kind']}"
          + (f", hedge {hedge:g}PE ({c['rules'].get('hedge_strikes_below', 2)} listed strikes lower)" if hedge else "") + f"; lot {c['lot']}")
    print("QUOTE_INSTRUMENTS=" + json.dumps(["NFO:" + x for x in dict.fromkeys(inst)]))


def cmd_build(a):
    g, ignored = read_hard_blocks()
    c = common(a)
    if not 1 <= a.lots <= MAX_LOTS:
        refuse(f"lots must be 1-{MAX_LOTS}.")
    qp = Path(a.quotes)
    if not qp.exists() or datetime.fromtimestamp(qp.stat().st_mtime, IST).date() != c["today"]:
        refuse(f"no quotes saved today at {qp}. Run `plan`, pull the QUOTE_INSTRUMENTS with the Zerodha market quote tool and save the raw JSON there.")
    raw = json.loads(qp.read_text(encoding="utf-8"))
    quotes = raw.get("data", raw)
    strikes = sorted(c["opt"]["strikes"][c["expiry"]][c["kind"]])
    short, target = pick_strike(strikes, c["spot"], c["kind"], c["otm"]) if a.short_strike is None else (a.short_strike, None)
    if short not in strikes:
        refuse(f"{short:g} is not a listed {c['kind']} strike for {c['expiry']}.")
    i = strikes.index(short)

    def info_for(k, kind):
        ts = tradingsymbol(c["sym"], c["expiry"], k, kind)
        q = quotes.get("NFO:" + ts)
        if not q:
            refuse(f"no quote for {ts}: pull it (run `plan` for the instrument list).")
        return ts, quote_info(q, c["lot"])

    sts, sinfo = info_for(short, c["kind"])
    legs = [{"role": "short", "tradingsymbol": sts, "strike": short, "type": c["kind"], "pct_from_spot": round((short / c["spot"] - 1) * 100, 1), **sinfo}]
    hedge = None
    if c["structure"] == "put-spread":
        pstr = sorted(c["opt"]["strikes"][c["expiry"]]["PE"])
        hk = hedge_strike(pstr, short, c["rules"].get("hedge_strikes_below", 2))
        hts, hinfo = info_for(hk, "PE")
        hedge = {"role": "hedge", "tradingsymbol": hts, "strike": hk, "type": "PE", "pct_from_spot": round((hk / c["spot"] - 1) * 100, 1), **hinfo}
        legs.append(hedge)
    sp = a.short_limit if a.short_limit else suggest_price(sinfo, "SELL")
    hp = (a.hedge_limit if a.hedge_limit else suggest_price(hedge, "BUY")) if hedge else None
    if sp is None or (hedge and hp is None):
        refuse("no bid/ask to suggest a limit price from; pass --short-limit (and --hedge-limit) after checking the quote.")
    for p_, info_ in ((sp, sinfo), (hp, hedge)):
        if p_ is not None and info_ and info_.get("lower_circuit") and info_.get("upper_circuit") and not (info_["lower_circuit"] <= p_ <= info_["upper_circuit"]):
            refuse(f"price {p_:g} is outside the circuit limits {info_['lower_circuit']:g}-{info_['upper_circuit']:g}.")
    credit = sp - (hp or 0)
    if a.target_credit:
        per_lot = credit * c["lot"]
        a.lots = min(range(1, MAX_LOTS + 1), key=lambda n: abs(n * per_lot - a.target_credit)) if per_lot > 0 else 1
    qty = c["lot"] * a.lots
    rules = c["rules"]
    stop = tick(rules.get("stop_premium_multiple", 3) * sp)
    target_px = max(TICK, tick(sp * (1 - rules.get("profit_exit_decay_pct", 60) / 100)))
    width = (short - hedge["strike"]) if hedge else None
    max_loss = round((width - credit) * qty) if hedge else None
    warn = list(sinfo["warn"]) + [f"hedge: {w}" for w in (hedge["warn"] if hedge else [])]
    if sinfo.get("upper_circuit") and stop > sinfo["upper_circuit"]:
        warn.append(f"the 3x stop ({stop:g}) is above the upper circuit limit ({sinfo['upper_circuit']:g}) and could never trigger"
                    + ("; the hedge limits the loss instead" if hedge else ""))
    ev = None
    if c["st"] and c["st"].get("event_block") and c["expiry"] == (c["st"]["expiries"][0]["expiry"]):
        ev = c["st"]["event_block"]
    else:
        from compute_covered_call import event_block, load_events
        ev = event_block(c["sym"], c["expiry"], load_events(DATA / "option_events.json"), c["today"], rules.get("event_close_days", 15))
    orders = []
    if hedge:
        orders.append({"step": 1, "role": "hedge", "exchange": "NFO", "tradingsymbol": hedge["tradingsymbol"], "transaction_type": "BUY", "quantity": qty,
                       "product": "NRML", "order_type": "LIMIT", "price": hp, "validity": "DAY", "variety": "regular", "tag": "AZOPT"})
    orders.append({"step": len(orders) + 1, "role": "short", "exchange": "NFO", "tradingsymbol": sts, "transaction_type": "SELL", "quantity": qty,
                   "product": "NRML", "order_type": "LIMIT", "price": sp, "validity": "DAY", "variety": "regular", "tag": "AZOPT"})
    ticket = {"symbol": c["sym"], "structure": c["structure"], "expiry": c["expiry"], "spot": c["spot"], "spot_source": c["spot_src"], "otm_pct_asked": c["otm"],
              "lot": c["lot"], "lots": a.lots, "quantity": qty, "legs": legs, "orders": orders, "net_credit_per_share": round(credit, 2), "net_credit_rs": round(credit * qty),
              "max_loss_rs": max_loss, "stop_trigger_for_gtt": stop, "target_trigger_for_gtt": target_px, "warnings": warn, "event_warning": ev,
              "built_at": datetime.now(IST).isoformat(timespec="seconds")}
    (DATA / "option_ticket.json").write_text(json.dumps(ticket, indent=1), encoding="utf-8")
    print(f"{c['sym']} {c['structure']} {c['expiry']}: stock {c['spot']:g} ({c['spot_src']}); rule = strike nearest {c['otm']:g}% {'above' if c['kind'] == 'CE' else 'below'}"
          + (f" -> target {target:.1f}" if target else " (strike chosen by you)"))
    print(f"  SHORT {short:g}{c['kind']} ({legs[0]['pct_from_spot']:+.1f}% from the price)  last {sinfo['ltp']:g}  bid {sinfo['bid']}  ask {sinfo['ask']}  OI {sinfo['oi']:,} ({sinfo['oi_lots']} lots)  volume {sinfo['volume']:,}  circuit {sinfo['lower_circuit']}-{sinfo['upper_circuit']}")
    for w in sinfo["warn"]:
        print(f"    WARNING: {w}")
    if hedge:
        print(f"  HEDGE BUY {hedge['strike']:g}PE ({hedge['pct_from_spot']:+.1f}%)  last {hinfo['ltp']:g}  bid {hinfo['bid']}  ask {hinfo['ask']}  OI {hinfo['oi']:,} ({hinfo['oi_lots']} lots)")
        for w in hinfo["warn"]:
            print(f"    WARNING: {w}")
    if sinfo["warn"]:
        alts = []
        for j in range(max(0, i - 2), min(len(strikes), i + 3)):
            if j == i or (c["kind"] == "CE" and strikes[j] <= c["spot"]) or (c["kind"] == "PE" and strikes[j] >= c["spot"]):
                continue
            q = quotes.get("NFO:" + tradingsymbol(c["sym"], c["expiry"], strikes[j], c["kind"]))
            if q:
                ai = quote_info(q, c["lot"])
                if not ai["warn"]:
                    alts.append((abs(strikes[j] - (target or short)), strikes[j], ai))
        if alts:
            _, k, ai = min(alts)
            print(f"    nearest liquid alternative (quoted): {k:g}{c['kind']} ({(k / c['spot'] - 1) * 100:+.1f}%)  bid {ai['bid']}  ask {ai['ask']}  OI {ai['oi_lots']} lots  (re-run with --short-strike {k:g} to use it)")
    if ev:
        print(f"  WARNING (results / ex-dividend rule): {c['sym']} {c['expiry']} - {ev}. This option would still be open inside the window; the rule says close it 15 days before the event.")
    if ignored:
        print(f"  note: global equity-data block(s) {', '.join(ignored)} do not apply to options; the live quotes are used.")
    print(f"  lot {c['lot']} x {a.lots} = {qty} qty;  net credit {credit:.2f}/share = Rs{round(credit * qty):,}" + (f";  maximum loss Rs{max_loss:,} (spread width {width:g} less the credit)" if hedge else ";  NAKED short call: the loss is unlimited if the stock rallies (the call side is unhedged by your rule)"))
    print(f"  protective GTT afterwards (zerodha-gtt-order): stop {stop:g} ({stop / sp:.1f}x), profit target {target_px:g}")
    for o in orders:
        print(f"  order {o['step']}: {o['transaction_type']} {o['quantity']} {o['tradingsymbol']} LIMIT {o['price']:g} NRML (regular, DAY)")
    print("  Premium comes from live bid/ask: the limit is the middle of the spread, rounded to the tick. Change it only with --short-limit / --hedge-limit.")
    print("TICKET_JSON=" + json.dumps(ticket))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--max", type=int, default=25)
    p.add_argument("--symbols", default="")
    p.set_defaults(fn=cmd_list)
    for name, fn in (("plan", cmd_plan), ("build", cmd_build)):
        p = sub.add_parser(name)
        p.add_argument("--symbol", required=True)
        p.add_argument("--structure", choices=["call", "put-spread"])
        p.add_argument("--expiry")
        p.add_argument("--otm-pct", type=float, default=None, help="default (user rule): 10 for the current month, 15 for a later month")
        p.add_argument("--spot", type=float, help="live stock price from the MCP (otherwise the live price file of today, else the last close)")
        if name == "build":
            p.add_argument("--quotes", required=True)
            p.add_argument("--lots", type=int, default=1)
            p.add_argument("--target-credit", type=float, help="Rs credit wanted: picks the lots (1-4) whose credit is nearest (overrides --lots)")
            p.add_argument("--short-strike", type=float, help="use this listed strike instead of the rule's pick")
            p.add_argument("--short-limit", type=float)
            p.add_argument("--hedge-limit", type=float)
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
