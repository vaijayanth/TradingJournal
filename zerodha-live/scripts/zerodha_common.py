"""Helpers used by the Zerodha engine. Vendored from dhan-live/scripts/compute_dh252_live_signals.py so the Zerodha and Dhan
workspaces share NO code: a change to the Dhan engine can never alter a Zerodha signal (and vice versa)."""
import json
from datetime import datetime
from pathlib import Path


def strip_suffix(symbol):
    for suf in (".NS", ".BO"):
        if symbol.endswith(suf):
            return symbol[: -len(suf)]
    return symbol


def load_json(path):
    return json.loads(Path(path).read_text())


def index_week52(market_screens):
    return {strip_suffix(r["symbol"]): r for r in market_screens.get("week52_all", [])}


def index_supertrend(supertrend):
    return {strip_suffix(r["symbol"]): r for r in supertrend.get("entries", [])}


def index_rsi(market_screens):
    return {strip_suffix(r["symbol"]): r["rsi14"] for r in market_screens.get("rsi_all", [])}


def days_since(date_str, today):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return max(0, (today - d).days)


def flip_label(st):
    """Port of index.html's stFlipLabel: 'Flipped to GREEN (Nd)' if a flip
    happened recently, else 'GREEN/RED Nd' for an ongoing streak, else None."""
    if not st:
        return None
    flip_days = st.get("recent_flip_trading_days_ago", st.get("recent_flip_days_ago"))
    if flip_days is not None:
        dir_label = "GREEN" if st.get("recent_flip_direction") == "up" else "RED"
        return f"Flipped to {dir_label} ({flip_days})"
    streak_days = st.get("current_streak_trading_days", st.get("current_streak_days"))
    if streak_days is not None and st.get("color"):
        return f"{st['color'].upper()} {streak_days}d"
    return None


def entry_flip_label(st):
    """Flip text for an ENTRY row - always filled (entries are Supertrend-green by
    definition): recent bullish flip -> 'Flipped to GREEN (N)', else 'GREEN Nd' streak."""
    label = flip_label(st)
    if label:
        return label
    return "GREEN" if st and st.get("color") == "green" else None


def compute_hot_sectors(stmap, entries, sectors, top_n=3):
    """Same 'hot sector' logic as backtester's dh252RenderSignals: a sector is hot if it
    is top-N by (a) fresh 52-week-high entry count or (b) universe-wide count of
    Supertrend bullish turnarounds in the recent window."""
    turn, entry_count = {}, {}
    for sym, st in stmap.items():
        if st.get("recent_bullish_flip_days_ago") is None:
            continue
        sec = sectors.get(sym)
        if sec:
            turn[sec] = turn.get(sec, 0) + 1
    for e in entries:
        sec = sectors.get(e["symbol"])
        if sec:
            entry_count[sec] = entry_count.get(sec, 0) + 1
    top = lambda d: {s for s, _ in sorted(d.items(), key=lambda kv: -kv[1])[:top_n]}
    return turn, entry_count, top(turn), top(entry_count)
