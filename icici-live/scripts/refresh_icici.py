"""Refresh the ICICI (DI) data: options master, prices/dividends/signals, option events, covered-call signals. Reads and writes only icici-live/.
Usage: python icici-live/scripts/refresh_icici.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["update_options_master.py", "build_icici_data.py", "fetch_option_events.py", "compute_covered_call.py"]
for s in STEPS:
    print(f"\n$ python {s}")
    r = subprocess.run([sys.executable, str(HERE / s)])
    if r.returncode != 0 and s != "fetch_option_events.py":   # a failed events fetch keeps the old file
        print(f"FAILED: {s}")
        sys.exit(r.returncode)
print("\nDone.")
