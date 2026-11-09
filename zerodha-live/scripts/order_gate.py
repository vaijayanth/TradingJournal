"""Order gate for the Zerodha (AZ) ticket builders (none written yet; the future zerodha order skills must call this): nothing is ticketed unless the guardrails say it may be.

load_gate(signals) -> (blocks_by_symbol, cfg)   exits with code 2 (REFUSED) when
  * data/guardrails.json is missing, or was built for a different market date than the signals (run guardrails.py / the refresh), or
  * a GLOBAL block exists (trading halt, stale data, mass-exit anomaly, cross-broker import, NaN in the signals ...).
check_caps(tickets, base, cfg) refuses a batch that is too big (orders or rupees), the last line of defence against a fat-finger "all".

Block ids and their meaning are documented in guardrails.py. WARNs never block here; they are printed so the order skill can show them.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CAP_DEFAULTS = {"max_orders_per_batch": 40, "max_batch_notional_pct_of_base": 25}


def load_gate(signals):
    gp = DATA / "guardrails.json"
    if not gp.exists():
        print("REFUSED: no guardrails result - run /refresh-zerodha (it runs scripts/guardrails.py) or `python zerodha-live/scripts/guardrails.py` first.")
        sys.exit(2)
    g = json.loads(gp.read_text(encoding="utf-8"))
    if g.get("market_data_date") != signals.get("market_data_date") or str(g.get("signals_generated_at"))[:19] != str(signals.get("generated_at"))[:19]:
        print("REFUSED: the guardrails result is for different signals (market data "
              f"{g.get('market_data_date')} vs {signals.get('market_data_date')}); re-run `python zerodha-live/scripts/guardrails.py`.")
        sys.exit(2)
    if g.get("global_block"):
        print("REFUSED by guardrails (nothing may be ordered):")
        for x in g["findings"]:
            if x["level"] == "BLOCK" and x["symbol"] is None:
                print(f"  {x['id']}: {x['msg']}")
        sys.exit(2)
    for x in g["findings"]:
        if x["level"] == "WARN":
            print(f"  guardrail WARN {x['id']}: {x['msg']}")
    cfgp = DATA / "guardrails_config.json"
    cfg = {**CAP_DEFAULTS, **(json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {})}
    return g.get("per_symbol_blocks", {}), cfg


def check_caps(tickets, base, cfg, allow=False):
    n, total = len(tickets), sum(t.get("est_value", 0) for t in tickets)
    problems = []
    if n > cfg["max_orders_per_batch"]:
        problems.append(f"{n} orders in one batch (limit {cfg['max_orders_per_batch']})")
    if base and total > base * cfg["max_batch_notional_pct_of_base"] / 100:
        problems.append(f"batch value Rs{total:,.0f} is over {cfg['max_batch_notional_pct_of_base']}% of the Rs{base:,.0f} capital base")
    if problems and not allow:
        print("REFUSED by the batch caps: " + "; ".join(problems) + ". Pick fewer orders, or the user can pass --allow-big-batch after reviewing.")
        sys.exit(2)
    return problems
