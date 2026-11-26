"""Check that every number in dhan-live/insights.json traces to a computed fact (user, 2026-11-26: the model narrates, code computes).

  python dhan-live/scripts/verify_insights.py [--strict]

Sources a number may come from: data/insights_facts.json (the facts layer), dhan_live_signals.json (entries / exits / add-ons / holds / sizing / closed trades), data/orders_snapshot.json,
data/projection.json and covered_call_signals.json alerts. A number matches when it equals a source value rounded to the displayed precision (one unit of slack), scaled for k (thousands), L (lakhs) or Cr (crores),
with the sign ignored; small whole numbers (12 or less, such as counts) are ignored. Day-of-month and year tokens, instrument codes (1280PE) and the confidence line are ignored. Prints the UNVERIFIED numbers (a WARN, exit 0; --strict exits 1).
ND only: reads dhan-live/ files, imports nothing from zerodha-live/ or icici-live/.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"


def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def leaves(o, out):
    if isinstance(o, dict):
        for v in o.values():
            leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            leaves(v, out)
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)):
        out.add(abs(float(o)))
    elif isinstance(o, str):
        for t in re.findall(r"\d[\d,]*\.?\d*", o):
            try:
                out.add(abs(float(t.replace(",", ""))))
            except ValueError:
                pass


def sources():
    vals = set()
    for p in (DATA / "insights_facts.json", ROOT / "dhan_live_signals.json", DATA / "orders_snapshot.json", DATA / "projection.json"):
        d = load(p)
        if d is not None:
            if p.name == "dhan_live_signals.json":
                d = {k: d.get(k) for k in ("entries", "exits", "addons", "holds", "sizing", "closed_trades", "capital_base", "equity_curve")}
            leaves(d, vals)
    cc = load(ROOT / "covered_call_signals.json") or {}
    leaves(cc.get("alerts"), vals)
    leaves(cc.get("stocks"), vals)                                           # spot, option legs, stop levels
    leaves(load(DATA / "cc_gtts.json"), vals)
    for extra in (DATA / "cc_raw" / "super_orders.txt",):                    # raw stop / target levels of the super orders (ND)
        if extra.exists():
            leaves(extra.read_text(encoding="utf-8"), vals)
    return vals


def text_of(ins):
    parts = [ins.get("headline", ""), ins.get("action", ""), ins.get("maturity", "")]
    parts += [pt.get("text", "") for pt in ins.get("points", [])]
    return "\n".join(parts)


def tokens(txt):
    txt = re.sub(r"\b\d{1,2} " + MONTHS + r"\b", " ", txt)                  # 26 Nov
    txt = re.sub(r"\b" + MONTHS + r" \d{1,2}\b", " ", txt)
    txt = re.sub(r"\b(19|20)\d\d\b", " ", txt)                              # years
    txt = re.sub(r"\b\d+(?:\.\d+)?(?:CE|PE)\b", " ", txt)                   # 1280PE, 4200CE
    txt = re.sub(r"\b\d{1,2}:\d{2}\b", " ", txt)                            # times
    out = []
    for m in re.finditer(r"(?<![\d.,])(\d[\d,]*)(\.\d+)?(\s?(?:k|L|Cr)\b|\s?%|x\b)?", txt):
        whole, frac, unit = m.group(1), m.group(2) or "", (m.group(3) or "").strip()
        try:
            v = float((whole + frac).replace(",", ""))
        except ValueError:
            continue
        out.append((m.group(0).strip(), v, unit, len(frac) - 1 if frac else 0))
    return out


SCALE = {"k": 1e3, "L": 1e5, "Cr": 1e7}


def ok(v, unit, dec, vals):
    """The displayed number must equal a source value rounded to the displayed precision (one unit of slack for floor vs round)."""
    scale = SCALE.get(unit, 1.0)
    tol = 10 ** (-dec) * scale
    target = v * scale
    return any(target - 0.5 * tol - 1e-9 <= s < target + tol + 1e-9 for s in vals)


def main():
    ins = load(ROOT / "insights.json")
    if not ins:
        sys.exit("no insights.json")
    vals = sources()
    bad = []
    for raw, v, unit, dec in tokens(text_of(ins)):
        if v <= 12 and dec == 0 and unit == "":                              # small counts ("3 add-ons", "5 entries"): too ambiguous to verify, ignored
            continue
        if not ok(v, unit, dec, vals):
            bad.append(raw)
    uniq = sorted(set(bad), key=bad.index)
    print(f"VERIFY insights ND: {len(uniq)} unverified number(s)" + (": " + ", ".join(uniq) if uniq else " (every number traces to a fact)"))
    if uniq:
        print("  -> recompute them in compute_insights_facts.py (add the fact) or rephrase; the model must not type a number the facts do not hold")
    sys.exit(1 if (uniq and "--strict" in sys.argv) else 0)


if __name__ == "__main__":
    main()
