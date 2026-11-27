"""ICICI (DI) covered call / option-selling signals -> icici-live/covered_call_signals.json.

Rules (user, 2026-11-16: the same as ND's): Supertrend colour only. GREEN -> bull put spread (sell a put, hedge 2 listed strikes lower),
RED -> sell a call. The RSI override is OFF for DI (cc_config.json rules.rsi_override). Covers the DI universe stocks that have listed options.
Exits: short option at 3x the premium sold (EXIT), stock at/through a short strike (BREACH / WARN), Supertrend colour against an open structure (Exit),
a long leg that hedges nothing (Leftover hedge), results / ex-dividend within 15 days (Event close), in-the-money close to expiry (Expiry risk).
Inputs: icici_live_signals.json (price, Supertrend colour, RSI: build_icici_data.py), data/nfo_options.json (lots, expiries: update_options_master.py),
data/option_events.json (fetch_option_events.py), data/cc_positions.json (open option legs from the uploaded ICICIdirect positions export; none yet).
No option quotes are pulled, so strikes and premiums of NEW trades are not computed: a signal says which structure, the lot and the expiry.
Nothing here imports from ND or AZ.

Usage: python icici-live/scripts/compute_covered_call.py   (after build_icici_data.py)
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))



DATA = HERE.parent / "data"


def _ban_symbols(data_dir):
    """Symbols in today's NSE F&O ban list (this broker's own data/fno_ban.json); empty when the list could not be fetched."""
    p = Path(data_dir) / "fno_ban.json"
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set(), None
    return (set(j.get("symbols", [])) if j.get("ok") else set()), j.get("trade_date")


def _st_state(highs, lows, closes, period=10, mult=3.0):
    """Supertrend(10,3) as the backtester computes it: (direction of the last bar, final lower band, final upper band)."""
    n = len(closes)
    if n <= period:
        return None, None, None
    tr = [highs[0] - lows[0]] + [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    atr = [None] * n
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    s = period - 1
    mid = (highs[s] + lows[s]) / 2
    fu, fl = mid + mult * atr[s], mid - mult * atr[s]
    d = "down" if closes[s] <= fu else "up"
    for i in range(s + 1, n):
        mid = (highs[i] + lows[i]) / 2
        bu, bl = mid + mult * atr[i], mid - mult * atr[i]
        fu = bu if (bu < fu or closes[i - 1] > fu) else fu
        fl = bl if (bl > fl or closes[i - 1] < fl) else fl
        d = ("up" if closes[i] > fu else "down") if d == "down" else ("down" if closes[i] < fl else "up")
    return d, fl, fu


def _st_distances(symbols, data_dir, ttl_minutes=30):
    """Distance to the Supertrend flip per stock (user, 2026-11-26): green = % the price can fall to the lower line before the colour turns red, red = % it can rise to the upper line
    before it turns green. Computed from Yahoo daily candles (the last bar can lag a session for some stocks: `bar` says which date it is) and cached in data/st_distance.json
    for ttl_minutes. A failure returns what the cache has (or nothing); it never stops the engine. Information only."""
    cache = Path(data_dir) / "st_distance.json"
    now = datetime.now(timezone.utc)
    rows = {}
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        rows = c.get("rows", {})
        age = (now - datetime.fromisoformat(c["fetched_at"])).total_seconds() / 60
        if age <= ttl_minutes and all(s in rows for s in symbols):
            return rows
    except Exception:  # noqa: BLE001
        pass
    try:
        import yfinance as yf
        df = yf.download([s + ".NS" for s in symbols], period="1y", interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
    except Exception:  # noqa: BLE001
        return rows
    out = {}
    for s in symbols:
        try:
            x = df[s + ".NS"].dropna(subset=["Close"]) if len(symbols) > 1 else df.dropna(subset=["Close"])
            d, fl, fu = _st_state(x["High"].tolist(), x["Low"].tolist(), x["Close"].tolist())
            px = float(x["Close"].iloc[-1])
            if d is None or px <= 0:
                continue
            line = fl if d == "up" else fu
            out[s] = {"colour": "green" if d == "up" else "red", "line": round(float(line), 2), "price": round(px, 2), "dist_pct": round((px - line) / px * 100 if d == "up" else (line - px) / px * 100, 2), "bar": str(x.index[-1].date())}
        except Exception:  # noqa: BLE001
            continue
    if out:
        try:
            cache.write_text(json.dumps({"fetched_at": now.isoformat(timespec="seconds"), "rows": out}, separators=(",", ":")), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return out
    return rows


def _near_flip_alerts(stocks, edge_pct):
    """WARN `Near flip` for a stock with open option legs whose Supertrend is within edge_pct of flipping: a feed difference of a few points could already change the colour."""
    out = []
    for s in stocks:
        d = s.get("st_dist_pct")
        if d is None or not s.get("legs") or d > edge_pct:
            continue
        flip_to = "red" if s.get("st_colour") == "green" else "green"
        out.append({"level": "WARN", "type": "Near flip", "symbol": s["symbol"], "concern": f"Supertrend {s.get('st_colour')} is only {d:.1f}% from turning {flip_to} (line {s.get('st_line'):g}, price {s.get('st_price'):g}, bar {s.get('st_bar')})",
                    "action": f"Watch: a close {'below' if flip_to == 'red' else 'above'} the line flips the structure the colour wants",
                    "text": f"{s['symbol']}: Supertrend within {d:.1f}% of flipping {flip_to}"})
    return out


def _ban_alert(sym, legs, data_dir):
    """F&O ban = EXIT (user, 2026-11-26): a stock in the ban period allows reducing trades only, so an open structure cannot be rolled, added to or replaced: close it."""
    syms, tdate = _ban_symbols(data_dir)
    if sym not in syms or not legs:
        return []
    sh = [l for l in legs if l.get("side") == "SHORT"] or list(legs)
    f = sh[0]
    n = len(legs)
    return [{"expiry": f.get("expiry"), "strike": f.get("strike"), "opt_type": f.get("type") or f.get("opt_type"), "level": "EXIT", "type": "F&O ban", "symbol": sym,
             "concern": f"Stock is in the NSE F&O ban period ({tdate or 'today'}): only reducing trades are allowed, so the {n} open leg{'s' if n > 1 else ''} cannot be rolled or replaced",
             "action": "Close the structure (shorts and hedge) while the ban lasts", "text": f"{sym}: in the F&O ban period - close the open option legs (no rolling or new legs allowed)"}]
OUT = HERE.parent / "covered_call_signals.json"


def desired_structure(colour, rsi, rules):
    if not rules.get("rsi_override", False):
        return ("PUT_SPREAD" if colour == "green" else "CALL"), f"Supertrend {colour}"
    if rsi is not None and rsi > rules["rsi_sell_call_above"]:
        return "CALL", f"RSI {rsi:.1f} > {rules['rsi_sell_call_above']:g}"
    if rsi is not None and rsi < rules["rsi_sell_put_below"]:
        return "PUT_SPREAD", f"RSI {rsi:.1f} < {rules['rsi_sell_put_below']:g}"
    return ("PUT_SPREAD" if colour == "green" else "CALL"), f"Supertrend {colour}"


def strike_zone(l, spot, near_pct):
    """How far the stock is from a leg's strike: beyond_pct > 0 = spot at/past the strike (in the money)."""
    ce = l["type"] == "CE"
    beyond = (spot / l["strike"] - 1) * 100 if ce else (1 - spot / l["strike"]) * 100
    intrinsic = max(0.0, (spot - l["strike"]) if ce else (l["strike"] - spot))
    l["beyond_pct"] = round(beyond, 2)
    l["intrinsic_rs"] = round(intrinsic * l["qty"])
    l["touched"] = beyond >= 0
    l["near"] = (not l["touched"]) and -beyond <= near_pct
    return beyond


def strike_alerts(sym, my_legs, spot, near_pct, stop_alerted):
    """Graded alerts for the stock price against the open legs (spot = the last close in the signals).
    EXIT   = price is through the hedge leg too (the spread is at its maximum loss)
    BREACH = price has reached or passed a short strike
    WARN   = price is within near_pct of a short strike"""
    out = []
    for l in my_legs:
        d = {"expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"], "spot": spot,
             "beyond_pct": l["beyond_pct"], "intrinsic_rs": l["intrinsic_rs"]}
        if l["side"] == "SHORT" and l["touched"]:
            hedges = [h for h in my_legs if h["side"] == "LONG" and h["type"] == l["type"] and h["expiry"] == l["expiry"]
                      and ((h["type"] == "CE" and h["strike"] > l["strike"]) or (h["type"] == "PE" and h["strike"] < l["strike"]))]
            thru = [h for h in hedges if h["touched_h"]]
            base = (f"{sym} {l['expiry']}: price {spot:g} is {abs(l['beyond_pct']):.1f}% {'above' if l['type']=='CE' else 'below'} the short "
                    f"{l['strike']:g}{l['type']} (in the money, intrinsic Rs{l['intrinsic_rs']:,} on {l['qty']} qty)")
            if thru:
                out.append({**d, "level": "EXIT", "type": "Through hedge", "hedge_strike": thru[0]["strike"], "symbol": sym,
                            "concern": f"Price {abs(l['beyond_pct']):.1f}% past the short and through the {thru[0]['strike']:g} hedge: max loss, Rs{l['intrinsic_rs']:,} intrinsic", "action": "Close or roll now", "text": base + f"; it is also through the {thru[0]['strike']:g}{thru[0]['type']} hedge - the spread is at maximum loss, decide now"})
            else:
                out.append({**d, "level": "BREACH", "type": "Beyond strike", "symbol": sym,
                            "concern": f"In the money: price {abs(l['beyond_pct']):.1f}% past the strike, Rs{l['intrinsic_rs']:,} intrinsic", "action": "Roll, close or hold", "text": base + "; decide: roll, close, or hold"})
        elif l["side"] == "SHORT" and l["near"]:
            out.append({**d, "level": "WARN", "type": "Near strike", "symbol": sym,
                            "concern": f"Price {abs(l['beyond_pct']):.1f}% from the short strike", "action": "Watch; plan the roll", "text": f"{sym} {l['expiry']}: price {spot:g} is within {abs(l['beyond_pct']):.1f}% of the short {l['strike']:g}{l['type']}"})
    return out


def structure_alerts(sym, my_legs, shares_held, gtt_active):
    """Alerts about how the open legs are set up (not about price): a short leg without hedge, a short leg without a buy-back GTT."""
    out = []
    groups = {}
    for l in my_legs:
        groups.setdefault((l["type"], l["expiry"]), []).append(l)
    for (typ, exp), ls in groups.items():
        short_q = sum(l["qty"] for l in ls if l["side"] == "SHORT")
        if not short_q:
            continue
        long_q = sum(l["qty"] for l in ls if l["side"] == "LONG")
        if typ == "CE" and not long_q:
            continue   # a plain short call is intentionally unhedged (user, 2026-11-13): its protection is the 3x-premium stop and the Supertrend flip alert
        # a call spread (a long call exists, user 2026-11-26) is checked like the put side: under-hedged and over-hedged quantities are flagged
        cover = long_q
        if cover < short_q:
            strikes = "/".join(f"{l['strike']:g}" for l in ls if l["side"] == "SHORT")
            extra = ""
            out.append({"level": "WARN", "type": "No hedge" if cover == 0 else "Partly hedged", "symbol": sym, "expiry": exp, "strike": ls[0]["strike"], "opt_type": typ,
                        "concern": f"{short_q - cover} of {short_q} qty uncovered (hedge {long_q}{extra})", "action": "Buy a hedge",
                        "text": f"{sym} {exp}: short {strikes}{typ} {short_q} qty, hedge {long_q} qty{extra} - {short_q - cover} qty uncovered"})
        elif long_q > short_q:   # over-hedged (user, 2026-11-26): more long puts than shorts, the extra long qty covers nothing
            strikes = "/".join(f"{l['strike']:g}" for l in ls if l["side"] == "SHORT")
            out.append({"level": "WARN", "type": "Over-hedged", "symbol": sym, "expiry": exp, "strike": ls[0]["strike"], "opt_type": typ,
                        "concern": f"{long_q - short_q} of {long_q} hedge qty has no short to cover (short {short_q})", "action": "Sell the extra long puts or confirm it is deliberate",
                        "text": f"{sym} {exp}: short {strikes}{typ} {short_q} qty, hedge {long_q} qty - {long_q - short_q} qty over-hedged"})
    if gtt_active is not None:
        for l in my_legs:
            if l["side"] == "SHORT" and l.get("tradingsymbol") and l["tradingsymbol"] not in gtt_active:
                out.append({"level": "WARN", "type": "No GTT placed", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"],
                            "concern": "No buy-back GTT on this short", "action": f"Place GTT at {l['stop_at']:g} (3x premium)",
                            "text": f"{sym} {l['expiry']} short {l['strike']:g}{l['type']}: no active buy-back GTT (3x premium stop = {l['stop_at']})"})
    return out


def leftover_hedge_alerts(sym, my_legs, today):
    """A LONG option leg that hedges nothing (user, 2026-11-14): no short in the same stock, expiry and type (the short was closed or expired and the
    hedge was left open), or a long that is not on the protective side of any short (put: not below it, call: not above it). It is the same rule the
    Open positions table uses for 'Long ...' and 'long N not a hedge'. Informational: sell it or let it expire (a profitable one: book it or hold)."""
    out = []
    groups = {}
    for l in my_legs:
        groups.setdefault((l["type"], l["expiry"]), []).append(l)
    for (typ, exp), ls in groups.items():
        shorts = [l for l in ls if l["side"] == "SHORT"]
        longs = [l for l in ls if l["side"] == "LONG"]
        if not longs:
            continue
        if shorts:
            s_min, s_max = min(l["strike"] for l in shorts), max(l["strike"] for l in shorts)
            stray = [l for l in longs if (l["strike"] >= s_max if typ == "PE" else l["strike"] <= s_min)]
        else:
            stray = longs
        days = (date.fromisoformat(exp) - today).days
        for l in stray:
            pnl = l.get("pnl_rs") or 0
            sh = "/".join("%g" % s["strike"] for s in shorts)
            why = (f"is not beyond the short {sh}{typ}: it hedges nothing" if shorts else "has no short against it")
            concern = f"Long {l['strike']:g}{typ} ({l['qty']} qty) {why} - P&L Rs{pnl:,.0f}, {days}d to expiry"
            action = "In profit: book it or let it run" if pnl > 0 else "Sell it or let it expire"
            out.append({"level": "WARN", "type": "Leftover hedge", "symbol": sym, "expiry": exp, "strike": l["strike"], "opt_type": typ, "qty": l["qty"],
                        "concern": concern, "action": action, "text": f"{sym} {exp}: {concern} - {action.lower()}"})
    return out


def expiry_alerts(sym, my_legs, spot, shares_held, rules):
    """Stock options are settled by physical delivery at expiry: an in-the-money leg close to expiry means shares to deliver (short call, long put)
    or to buy and pay for (short put, long call). Flag every in-the-money leg within expiry_risk_days of expiry; closing it earlier avoids the delivery."""
    out = []
    window = rules.get("expiry_risk_days", 7)
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    for l in my_legs:
        if not l.get("touched"):
            continue
        days = (date.fromisoformat(l["expiry"]) - today).days
        if days < 0 or days > window:
            continue
        side = "short" if l["side"] == "SHORT" else "long"
        delivers = (l["side"] == "SHORT") == (l["type"] == "CE")      # short call / long put: you deliver shares; short put / long call: you take delivery
        value = l["qty"] * l["strike"]
        what = (f"deliver {l['qty']} shares" + (f" (you hold {shares_held})" if shares_held is not None and l["type"] == "CE" else "")) if delivers else f"buy {l['qty']} shares (about Rs{value / 100000:.1f} lakh)"
        out.append({"level": "BREACH" if days <= 3 else "WARN", "type": "Expiry risk", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"],
                    "concern": f"{side.title()} {l['strike']:g}{l['type']} is in the money {days}d before expiry: physical settlement, you would {what}",
                    "action": "Close it before expiry" if days > 1 else "Close it today",
                    "text": f"{sym} {l['expiry']} {side} {l['strike']:g}{l['type']} in the money, {days} days to expiry: physical settlement"})
    return out


def load_events(path):
    """Upcoming results / ex-dividend dates (fetch_option_events.py). Missing file = no event rule can be applied (the page says so)."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def upcoming_events(sym, events, today):
    """[(label, date, estimated)] for the stock's next results and ex-dividend dates that are still ahead, soonest first."""
    s = (events.get("stocks") or {}).get(sym) or {}
    out = []
    if s.get("earnings"):
        out.append(("Results", date.fromisoformat(s["earnings"]), s.get("earnings_source") != "yahoo calendar"))
    if s.get("ex_div"):
        out.append(("Ex-dividend", date.fromisoformat(s["ex_div"]), bool(s.get("ex_div_estimated"))))
    return sorted((e for e in out if e[1] >= today), key=lambda e: e[1])


def event_alerts(sym, my_legs, events, today, days):
    """User rule (2026-11-09): close EVERY open option 15 days before the stock's results or ex-dividend date, whatever the expiry or structure.
    BREACH = already inside the window (close now), WARN = the window opens within 7 days."""
    ev = upcoming_events(sym, events, today)
    if not ev or not my_legs:
        return []
    label, d, est = ev[0]
    cutoff = d - timedelta(days=days)
    to_go = (d - today).days
    out = []
    for l in my_legs:
        if today >= cutoff:
            lvl, concern, action = "BREACH", f"{label} {d:%d %b}{' (estimated)' if est else ''} is {to_go}d away: inside the {days}-day window", "Close it now (event rule)"
        elif (cutoff - today).days <= 7:
            lvl, concern, action = "WARN", f"{label} {d:%d %b}{' (estimated)' if est else ''}: the {days}-day window opens {cutoff:%d %b}", f"Close by {cutoff:%d %b}"
        else:
            continue
        out.append({"level": lvl, "type": "Event close", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l.get("qty"),
                    "concern": concern, "action": action, "text": f"{sym} {l['expiry']} {l['side'].lower()} {l['strike']:g}{l['type']}: {concern} - {action.lower()}"})
    return out


def event_block(sym, expiry, events, today, days):
    """Reason a NEW option expiring on `expiry` is not allowed: its life would reach the 15-day window before the next results / ex-dividend date."""
    if not expiry:
        return None
    exp = date.fromisoformat(expiry)
    for label, d, est in upcoming_events(sym, events, today):
        if exp > d - timedelta(days=days):
            return f"{label} {d:%d %b %Y}{' (estimated)' if est else ''}: the {days}-day close window starts {d - timedelta(days=days):%d %b}, before this expiry"
    return None


def main():
    cfg = load_json(DATA / "cc_config.json"); rules = cfg["rules"]
    sig = load_json(HERE.parent / "icici_live_signals.json")
    px = {r["symbol"]: r for r in sig["stocks"]}
    market_date = sig["market_data_date"]
    master = load_json(DATA / "nfo_options.json")["symbols"] if (DATA / "nfo_options.json").exists() else {}
    universe = load_json(DATA / "icici_universe.json")["symbols"]
    uni = [s for s in universe if s in master]
    no_options = [s for s in universe if s not in master]
    mdate = datetime.strptime(market_date, "%Y-%m-%d").date()
    min_days = rules.get("expiry_min_days", 30)

    def pick_expiry(listed):
        ok = [e for e in sorted(listed) if (datetime.strptime(e, "%Y-%m-%d").date() - mdate).days >= min_days]
        return ok[0] if ok else (sorted(listed)[-1] if listed else None)
    all_exp = sorted({e for m in master.values() for e in m["lot"]})
    expiries = [pick_expiry(all_exp)] if all_exp else []
    pos_file = DATA / "cc_positions.json"
    pos = load_json(pos_file) if pos_file.exists() else {"legs": [], "ignored_legs": 0, "fetched_at": None}
    legs_by = {}
    for l in pos["legs"]:
        if l["symbol"] in uni:
            legs_by.setdefault(l["symbol"], []).append(l)
    tags_file = DATA / "cc_tags.json"
    tags = load_json(tags_file).get("tags", {}) if tags_file.exists() else {}
    mult = rules["stop_premium_multiple"]
    events = load_events(DATA / "option_events.json")
    ev_days = rules.get("event_close_days", 15)
    ist_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    hs = DATA / "holdings_snapshot.json"
    held_qty = {h["symbol"]: h["qty"] for h in load_json(hs).get("holdings", [])} if hs.exists() else {}
    stocks, no_data, alerts, new_tags = [], [], [], False
    for sym in uni:
        e = px.get(sym)
        if not e or not e.get("colour") or e.get("short_history_days"):
            no_data.append(sym)
            continue
        spot, colour = e["price"], e["colour"]
        kind, basis = desired_structure(colour, e.get("rsi"), rules)
        flip_days = e.get("flip_trading_days")
        lots = (master.get(sym) or {}).get("lot", {})
        my = [dict(l) for l in legs_by.get(sym, [])]
        spot_now = spot
        for l in my:
            l["lot"] = lots.get(l["expiry"])
            l["lots"] = round(l["qty"] / l["lot"], 2) if l["lot"] else None
            l["dist_pct"] = round((l["strike"] / spot_now - 1) * 100, 2)
            if l["side"] == "SHORT":
                l["stop_at"] = round(mult * l["avg"], 2)
                l["stop_hit"] = l["ltp"] >= l["stop_at"]
                if l["stop_hit"]:
                    alerts.append({"level": "EXIT", "type": "3× premium", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} >= {mult}x sold {l['avg']} - close it",
                                   "concern": f"Premium {l['ltp']:g} is {l['ltp'] / l['avg']:.1f}x the {l['avg']:g} sold", "action": "Close now (3x stop hit)"})
                elif l["ltp"] >= l["avg"] * rules.get("near_stop_multiple", 2.5):
                    alerts.append({"level": "WARN", "type": "Near 3× stop", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"],
                                   "concern": f"Premium {l['ltp']:g} is {l['ltp'] / l['avg']:.1f}x the {l['avg']:g} sold (stop at {l['stop_at']:g})", "action": "Watch: close or tighten before the 3x stop",
                                   "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} is {l['ltp'] / l['avg']:.1f}x sold {l['avg']}, near the {mult}x stop {l['stop_at']}"})
                elif l["ltp"] <= l["avg"] * (1 - rules.get("profit_exit_decay_pct", 60) / 100):
                    alerts.append({"level": "PROFIT", "type": "Profit Exit", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"],
                                   "concern": f"Premium decayed {(1 - l['ltp'] / l['avg']) * 100:.0f}% (sold {l['avg']:g}, now {l['ltp']:g})", "action": "Book profit: buy back",
                                   "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium decayed {(1 - l['ltp'] / l['avg']) * 100:.0f}% (sold {l['avg']:g}, now {l['ltp']:g}) - book the profit"})
            strike_zone(l, spot_now, rules.get("near_strike_pct", 2))
            l["touched_h"] = l["touched"] if l["side"] == "LONG" else False
        alerts.extend(strike_alerts(sym, my, spot_now, rules.get("near_strike_pct", 2), None))
        alerts.extend(structure_alerts(sym, my, held_qty.get(sym, 0), None))
        alerts.extend(leftover_hedge_alerts(sym, my, date.fromisoformat(ist_today)))
        alerts.extend(expiry_alerts(sym, my, spot_now, held_qty.get(sym, 0), rules))
        alerts.extend(event_alerts(sym, my, events, date.fromisoformat(ist_today), ev_days))
        alerts.extend(_ban_alert(sym, my, DATA))
        shorts = [l for l in my if l["side"] == "SHORT"]
        has_call = any(l["type"] == "CE" for l in shorts)
        has_put_spread = any(s["type"] == "PE" and any(b["type"] == "PE" and b["side"] == "LONG" and b["expiry"] == s["expiry"] and b["strike"] < s["strike"] for b in my) for s in shorts)
        if my and sym not in tags:  # first time legs are seen: the Supertrend colour now is the entry colour
            tags[sym] = {"entry_colour": colour, "first_seen": market_date, "source": "first_seen"}
            new_tags = True
        have = has_put_spread if kind == "PUT_SPREAD" else has_call
        col_rule = "PUT_SPREAD" if colour == "green" else "CALL"
        opp_legs = [l for l in shorts if l["type"] == ("PE" if col_rule == "CALL" else "CE")]
        opposite = bool(opp_legs)
        tag = tags.get(sym)
        # The stored entry colour only matters while the structure it opened is still open; with no opposite short open the note is stale: re-stamp it (no Exit with nothing to close).
        if my and tag and tag.get("entry_colour") and tag["entry_colour"] != colour and not opposite:
            tags[sym] = tag = {"entry_colour": colour, "first_seen": tag.get("first_seen") or market_date, "source": "restamped", "was": tag["entry_colour"], "restamped": market_date}
            new_tags = True
        flipped = bool(my and tag and tag.get("entry_colour") and tag["entry_colour"] != colour)
        if opposite and not flipped:
            leg_txt = ", ".join(f"{l['strike']:g}{l['type']} {l['expiry']}" for l in opp_legs)
            opp_note = (f"Supertrend is {colour.upper()}: the open {'short put / put spread' if col_rule == 'CALL' else 'short call'} ({leg_txt}) is the opposite of the colour rule - close it and "
                        f"{'sell the call' if col_rule == 'CALL' else 'open the bull put spread'}.")
        if flipped or opposite:
            status = "FLIP"
            note = opp_note if (opposite and not flipped) else (f"Supertrend turned {colour.upper()} since entry ({tag['entry_colour']}): close the "
                    f"{'put spread' if colour == 'red' else 'short call'} and open the {'short call' if colour == 'red' else 'bull put spread'}.")
            exit_concern = (f"Supertrend turned {colour.upper()} since entry" if flipped else f"Supertrend {colour.upper()} but the {'short put / put spread' if col_rule == 'CALL' else 'short call'} is still open")
            exit_action = "Close it and sell the call" if (col_rule == "CALL") else "Close it and open the bull put spread"
            leg_f = {"expiry": opp_legs[0]["expiry"], "strike": opp_legs[0]["strike"], "opt_type": opp_legs[0]["type"]} if opp_legs else {}
            if len(opp_legs) > 1:
                exit_concern += f" ({len(opp_legs)} legs)"
            alerts.append({**leg_f, "level": "EXIT", "type": "Exit", "symbol": sym, "concern": exit_concern, "action": exit_action, "text": f"{sym}: {note}"})
        elif have:
            status, note = "HOLD", f"Open structure matches the rule ({basis})."
        else:
            status, note = "ENTER", f"{basis}: {'bull put spread' if kind == 'PUT_SPREAD' else 'sell call'}" + (" (you hold other legs in this stock)" if my else "")
        ex = pick_expiry(list(lots)) if lots else None
        stocks.append({
            "symbol": sym, "spot": spot, "colour": colour, "rsi": e.get("rsi"), "basis": basis, "desired": kind,
            "flip_date": e.get("flip_date"), "flip_trading_days": flip_days,
            "expiries": [{"expiry": ex, "lot": lots.get(ex)}] if lots else [], "rsi_override": basis.startswith("RSI"),
            "status": status, "note": note, "legs": my,
            "events": [{"label": a, "date": b.isoformat(), "estimated": c} for a, b, c in upcoming_events(sym, events, date.fromisoformat(ist_today))],
            "event_block": event_block(sym, ex, events, date.fromisoformat(ist_today), ev_days) if status in ("ENTER", "FLIP") else None,
        })
    if new_tags:
        tags_file.write_text(json.dumps({"_note": "Supertrend colour when a stock's tracked option legs were first seen = the entry colour for the FLIP exit. Edit by hand if the real entry colour differed.", "tags": tags}, indent=1))
    order = {"EXIT": 0, "BREACH": 1, "WARN": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 9))
    calls = sum(1 for s in stocks if s["desired"] == "CALL")
    n = lambda k: sum(1 for s in stocks if s["status"] == k)
    # IV percentile (user, 2026-11-26): this broker's own data/ivp.json, written by scripts/ivp_update.py (information only, no rule uses it)
    ivp_file = DATA / "ivp.json"
    ivp_rows = json.loads(ivp_file.read_text()).get("rows", {}) if ivp_file.exists() else {}
    ivp_asof = json.loads(ivp_file.read_text()).get("as_of") if ivp_file.exists() else None
    for s_ in stocks:
        r_ = ivp_rows.get(s_.get("symbol"))
        if r_:
            s_["ivp"], s_["iv"], s_["ivr"] = r_["ivp"], r_["iv"], r_["ivr"]
            s_["iv_tier"], s_["iv_tier_rank"] = r_.get("tier"), r_.get("tier_rank")   # structural IV tier A-E (user, 2026-11-27)
    _std = _st_distances(sorted({s_["symbol"] for s_ in stocks if s_.get("colour") and s_.get("symbol")}), DATA)
    for s_ in stocks:
        r_ = _std.get(s_.get("symbol"))
        if r_:
            s_["st_colour"], s_["st_line"], s_["st_price"], s_["st_dist_pct"], s_["st_bar"] = r_["colour"], r_["line"], r_["price"], r_["dist_pct"], r_["bar"]
    alerts.extend(_near_flip_alerts(stocks, rules.get("near_flip_pct", 1.5)))
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "live_prices_at": None, "gtt_scan_at": None, "gtt_checked_at": None, "rules": rules,
              "show_expiries": expiries, "stocks": stocks, "ivp_as_of": ivp_asof, "alerts": alerts, "events_file_at": events.get("generated_at"), "events_missing": events.get("missing", []), "no_data": no_data,
              "no_options": no_options, "excluded": [],
              "positions": {"fetched_at": pos.get("fetched_at"), "track_from": cfg.get("track_from"), "legs": sum(len(s["legs"]) for s in stocks),
                            "ignored_legs": pos.get("ignored_legs", 0)},
              "counts": {"call": calls, "put_spread": len(stocks) - calls, "rsi_override": sum(1 for s in stocks if s["rsi_override"]),
                         "enter": n("ENTER"), "hold": n("HOLD"), "flip": n("FLIP")}}
    OUT.write_text(json.dumps(result, indent=1))
    print(f"DI covered call: {len(stocks)} stocks with options | sell call {calls} | bull put spread {len(stocks) - calls} | no options: {no_options} | "
          f"open legs tracked {result['positions']['legs']} | alerts {len(alerts)} | market data {market_date}")
    for a in alerts:
        print(f"  {a['level']:5} {a['text']}")


if __name__ == "__main__":
    main()
