import json, sys
from pathlib import Path
import v1_backtest as v
names=json.load(open('../zerodha-live/data/fno_universe.json'))['symbols']
ok=bad=0
for n in names:
    try:
        df=v.load_ohlc(n)
    except Exception as e:
        df=None
    if df is None or len(df)<60: bad+=1; print('NO',n,flush=True)
    else: ok+=1
print('done ok',ok,'bad',bad)
