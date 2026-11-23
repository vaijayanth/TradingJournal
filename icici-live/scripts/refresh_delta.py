#!/usr/bin/env python3
"""Refresh delta check (user, 2026-11-23): which inputs changed since the last refresh?

  python refresh_delta.py          -> prints one line per input group: CHANGED / same / new, and the plan
  python refresh_delta.py --save   -> stores the fingerprints in data/last_run.json (run at the END of a good refresh)

A fingerprint is a hash of the STRUCTURE of an input file (symbols, quantities, averages, order ids, GTT ids,
ban list, market data date) with timestamps and price-driven fields (ltp, cmp, p&l ...) removed, so a refresh in
which only prices moved reads as 'same'. Read-only apart from --save. Own copy per broker (no shared code).
"""
import hashlib, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
ROOT = os.path.join(HERE, '..')
STATE = os.path.join(DATA, 'last_run.json')
# group -> files (relative to the broker folder)
GROUPS = {
    'positions': ['data/cc_positions.json'],
    'ban': ['data/fno_ban.json'],
}
VOLATILE = re.compile(r'(^|_)(at|ltp|last_price|cmp|price|pnl|pl|pl_pct|pnl_pct|pnl_rs|day_change.*|change.*|close_price|m2m|unrealised|realised|value|current.*|market_value|stamp|date_fetched|source.*)$', re.I)
KEEP = {'order_id', 'trigger_id', 'id', 'qty', 'quantity', 'avg', 'average_price', 'symbol', 'tradingsymbol', 'status', 'side', 'transaction_type', 'trade_date'}


def norm(o):
    if isinstance(o, dict):
        return {k: norm(v) for k, v in sorted(o.items()) if k in KEEP or not VOLATILE.search(k)}
    if isinstance(o, list):
        items = [norm(x) for x in o]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
    return o


def fp(group):
    parts = []
    for rel in GROUPS[group]:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            parts.append('missing:' + rel); continue
        try:
            if not rel.endswith('.json'):   # raw MCP text (Dhan): whole-text hash, so any change reads as CHANGED (the safe side)
                parts.append(open(p, encoding='utf-8', errors='replace').read()); continue
            parts.append(json.dumps(norm(json.load(open(p, encoding='utf-8'))), sort_keys=True))
        except Exception as e:
            parts.append('unreadable:%s:%s' % (rel, e))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]


def market_date():
    for f in ('zerodha_live_signals.json', 'dhan_live_signals.json', 'icici_live_signals.json'):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            try:
                d = json.load(open(p, encoding='utf-8'))
                return d.get('market_data_date') or (d.get('meta') or {}).get('market_data_date')
            except Exception:
                pass
    return None


def current():
    c = {g: fp(g) for g in GROUPS}
    c['market_data_date'] = market_date()
    return c


def main():
    cur = current()
    if '--save' in sys.argv:
        os.makedirs(DATA, exist_ok=True)
        json.dump(cur, open(STATE, 'w'), indent=1)
        print('saved', STATE); return
    old = json.load(open(STATE)) if os.path.exists(STATE) else {}
    res = {}
    for k, v in cur.items():
        res[k] = 'new' if k not in old else ('same' if old[k] == v else 'CHANGED')
        print('%-18s %s' % (k, res[k]))
    inputs_same = all(res[g] == 'same' for g in GROUPS)
    print('PLAN: ' + ('nothing structural changed since the last run: reuse insights, report only the price-driven alerts, skip the commit if there is no file diff'
                      if inputs_same else 'changed: ' + ', '.join(g for g in GROUPS if res[g] != 'same')))
    if '--json' in sys.argv:
        print(json.dumps(res))


if __name__ == '__main__':
    main()
