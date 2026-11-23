"""Tests for fetch_fno_ban.parse (run: python zerodha-live/scripts/test_fetch_fno_ban.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_fno_ban import parse  # noqa: E402

F = 0


def check(n, got, want):
    global F
    ok = got == want
    F += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f" got {got} want {want}"))


check("one name", parse("Securities in Ban For Trade Date 23-NOV-2026:\n1,MANAPPURAM\n"), ("23-NOV-2026", ["MANAPPURAM"]))
check("several names", parse("Securities in Ban For Trade Date 24-NOV-2026:\n1,AAA\n2,BBB\n"), ("24-NOV-2026", ["AAA", "BBB"]))
check("none in ban", parse("Securities in Ban For Trade Date 25-NOV-2026:\n"), ("25-NOV-2026", []))
check("blank symbol ignored", parse("Securities in Ban For Trade Date 25-NOV-2026:\n1, \n"), ("25-NOV-2026", []))
check("no header", parse("garbage"), (None, []))
print("ALL PASSED" if not F else f"{F} FAILED")
sys.exit(1 if F else 0)
