"""Corporate actions (stock splits and bonus issues) for the ND (dh252) fill ledger.

A split or bonus changes the share count and the price without changing what you own: 9 shares bought at Rs109.05 before a 2.5-for-1 split are
22.5 shares at Rs43.62 after it. A fill ledger that mixes pre-split buys with post-split sells shows a fake -67% loss (PASHUPATI, 2026-11-13).
data/corporate_actions.json lists the events:  {"actions": [{"symbol": "PASHUPATI", "ex_date": "2026-11-13", "ratio": 2.5, "type": "split"}]}
(ratio = new shares per old share: a 2.5-for-1 split is 2.5, a 1:1 bonus is 2). adjust_fills() rewrites every fill dated BEFORE the ex-date
(quantity x ratio, price / ratio, value unchanged) so quantities and prices are in post-event units; fills on or after the ex-date are already post-event.
Used by compute_dh252_live_signals.py (ledger, closed trades, equity curve) and guardrails.py (fill ledger vs holdings). check_splits.py finds
splits that are not recorded here yet. Imports nothing from the other brokers.
"""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load_actions(path=None):
    p = Path(path) if path else DATA / "corporate_actions.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return [a for a in d.get("actions", []) if a.get("symbol") and a.get("ex_date") and float(a.get("ratio", 0) or 0) > 0 and float(a["ratio"]) != 1]


def adjust_fills(fills, actions=None):
    """Return the fills in post-event units. Fills for symbols with no recorded action are returned untouched (same objects)."""
    actions = load_actions() if actions is None else actions
    if not actions:
        return fills
    by = {}
    for a in actions:
        by.setdefault(a["symbol"].upper(), []).append(a)
    out = []
    for f in fills:
        acts = [a for a in by.get(f["symbol"].upper(), []) if f["date"] < a["ex_date"]]
        if not acts:
            out.append(f)
            continue
        r = 1.0
        for a in acts:
            r *= float(a["ratio"])
        g = dict(f)
        g["value"] = f.get("value", f["price"] * f["qty"])
        g["qty"] = f["qty"] * r
        g["price"] = f["price"] / r
        g["adjusted_for"] = ", ".join(f"{a.get('type', 'split')} {float(a['ratio']):g}:1 on {a['ex_date']}" for a in acts)
        out.append(g)
    out.extend(_fraction_settlements(out, actions))
    return out


def _fraction_settlements(adjusted, actions):
    """A split that leaves a fractional holding is settled in cash by the broker: 9 shares x 2.5 = 22.5 -> 22 shares + cash for 0.5
    (PASHUPATI, 2026-11-13: Dhan holds 13 = 22 - 9 sold, the ledger said 13.5). Add one synthetic SELL of the fraction dated the ex-date,
    priced at the first real fill on or after the ex-date (else the average buy price) so the ledger matches the broker's whole shares."""
    extra = []
    for a in actions:
        sym, ex = a["symbol"].upper(), a["ex_date"]
        pre = [f for f in adjusted if f["symbol"].upper() == sym and f["date"] < ex]
        net = sum(f["qty"] if f.get("action", "BUY") == "BUY" else -f["qty"] for f in pre)
        frac = net - math.floor(net + 1e-9)
        if net <= 0 or frac < 1e-6 or frac > 1 - 1e-6:
            continue
        after = sorted((f for f in adjusted if f["symbol"].upper() == sym and f["date"] >= ex), key=lambda f: f["date"])
        buys = [f for f in pre if f.get("action", "BUY") == "BUY"]
        avg = sum(f.get("value", f["price"] * f["qty"]) for f in buys) / sum(f["qty"] for f in buys)
        price = after[0]["price"] if after else avg
        extra.append({"symbol": a["symbol"], "date": ex, "action": "SELL", "qty": round(frac, 6), "price": round(price, 4),
                      "value": round(frac * price, 4), "source": "fractional_cash_settlement",
                      "adjusted_for": f"cash for the fractional share after {a.get('type', 'split')} {float(a['ratio']):g}:1 on {ex}"})
    return extra
