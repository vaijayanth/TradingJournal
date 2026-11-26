"""Rank the Nifty F&O stocks by IV percentile (read-only; reads market-data/iv_history.json written by scripts/ivp_update.py, so it runs in about a second).

  python scripts/ivp_update.py            # first, to bring the history up to the latest bhavcopy
  python scripts/ivp_scan.py [--top 25]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from ivp_update import HIST, stats  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    days = json.loads(HIST.read_text())["days"]
    last, rows = stats(days)
    ranked = sorted(rows.items(), key=lambda kv: (-kv[1]["ivp"], -(kv[1]["ivr"] or 0)))
    print(f"IV percentile, {last} close, {len(ranked)} F&O stocks")
    print(f"{'stock':12s} {'IV%':>6s} {'IVP':>5s} {'IVrank':>7s} {'1y low-high':>12s}")
    for s, r in ranked[:a.top]:
        print(f"{s:12s} {r['iv']:6.1f} {r['ivp']:5d} {(r['ivr'] if r['ivr'] is not None else 0):7d} {r['lo']:5.1f}-{r['hi']:.1f}")


if __name__ == "__main__":
    main()
