"""Download NSE F&O daily bhavcopy (new format, from 2024) and keep only stock-option rows for a chosen universe.

Usage: python options-backtest/fetch_bhavcopy.py [--start 2024-01-02] [--end 2026-11-06] [--universe-n 45]
Writes options-backtest/data/fo/<YYYYMMDD>.csv.gz (columns below) and data/universe.json. Resumable: days already saved are skipped; holidays (404) are
recorded in data/fo/_holidays.txt. The universe = the user's 10 ND stocks + the most liquid stocks by option open interest on the latest file.
Source: https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip (public NSE archive).
"""
import argparse
import csv
import gzip
import io
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = DATA / "fo"
URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
ND = ["MCX", "SHRIRAMFIN", "CGPOWER", "BSE", "DIXON", "HCLTECH", "INFY", "BANKINDIA", "BPCL", "CUMMINSIND"]
KEEP = ["TradDt", "TckrSymb", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric", "LwPric", "ClsPric", "LastPric", "UndrlygPric", "SttlmPric", "OpnIntrst", "TtlTradgVol", "NewBrdLotQty"]


def get(d):
    req = Request(URL.format(d=d), headers={"User-Agent": UA, "Referer": "https://www.nseindia.com/"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=60) as r:
                return r.read()
        except HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + attempt * 3)
        except Exception:
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"failed {d}")


def rows_of(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    return csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8"))


def pick_universe(n):
    p = DATA / "universe.json"
    if p.exists():
        return json.loads(p.read_text())["symbols"]
    d = date(2026, 11, 6)
    blob = None
    while blob is None:
        blob = get(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    oi = {}
    for r in rows_of(blob):
        if r["FinInstrmTp"] == "STO":
            oi[r["TckrSymb"]] = oi.get(r["TckrSymb"], 0) + int(float(r["OpnIntrst"] or 0))
    top = [s for s, _ in sorted(oi.items(), key=lambda x: -x[1])[:n]]
    syms = sorted(set(top) | set(ND))
    p.write_text(json.dumps({"symbols": syms, "nd": ND}, indent=1))
    return syms


def fetch_day(d, syms):
    f = OUT / f"{d}.csv.gz"
    if f.exists():
        return d, "have"
    blob = get(d)
    if blob is None:
        return d, "holiday"
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(KEEP)
    for r in rows_of(blob):
        if r["FinInstrmTp"] == "STO" and r["TckrSymb"] in syms:
            w.writerow([r[k] for k in KEEP])
    with gzip.open(f, "wt", encoding="utf-8") as g:
        g.write(out.getvalue())
    return d, "saved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-01-02")
    ap.add_argument("--end", default="2026-11-06")
    ap.add_argument("--universe-n", type=int, default=45)
    ap.add_argument("--symbols-file", help="JSON with a \"symbols\" list (e.g. zerodha-live/data/fno_universe.json): keep these instead of the top-N")
    ap.add_argument("--outdir", default="fo")
    a = ap.parse_args()
    global OUT
    OUT = DATA / a.outdir
    OUT.mkdir(parents=True, exist_ok=True)
    syms = set(json.loads(Path(a.symbols_file).read_text())["symbols"]) if a.symbols_file else set(pick_universe(a.universe_n))
    print(len(syms), "symbols:", sorted(syms))
    days, d = [], datetime.strptime(a.start, "%Y-%m-%d").date()
    end = datetime.strptime(a.end, "%Y-%m-%d").date()
    while d <= end:
        if d.weekday() < 5:
            days.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    hol = OUT / "_holidays.txt"
    known_hol = set(hol.read_text().split()) if hol.exists() else set()
    todo = [x for x in days if x not in known_hol]
    saved = holidays = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, (d, st) in enumerate(ex.map(lambda x: fetch_day(x, syms), todo), 1):
            if st == "holiday":
                known_hol.add(d)
                holidays += 1
            elif st == "saved":
                saved += 1
            if i % 50 == 0:
                print(f"{i}/{len(todo)} saved {saved} holidays {holidays}", flush=True)
                hol.write_text("\n".join(sorted(known_hol)))
    hol.write_text("\n".join(sorted(known_hol)))
    print(f"done: saved {saved}, holidays/no file {holidays}, total days on disk {len(list(OUT.glob('*.csv.gz')))}")


if __name__ == "__main__":
    main()
