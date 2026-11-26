"""Consistency check: the trading numbers live in ONE rules file per broker; every other copy must agree (user, 2026-11-25, audit step 3).

  python scripts/check_rules_consistency.py        # exit 0 = consistent, 1 = at least one disagreement

Sources of truth: dhan-live/data/rules.json (ND) and zerodha-live/data/rules.json (AZ). Checked against: the engine constants, the AZ cross-check window,
the guardrails' effective settings and guardrails_config.json (no conflicting duplicate keys), the `rules` block of each published signals file,
the page copy and fallbacks in index.html, the strategy table in CLAUDE.md, the AZ order skill, the shared skill blocks (scripts/sync_skill_blocks.py)
and the skill hold list (.claude/skills/_shared/holds.md). ND and AZ stay separate: each broker's modules are loaded on their own, nothing is shared.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems, notes = [], []


def bad(msg):
    problems.append(msg)


def load_mod(broker, name, alias):
    sdir = str(ROOT / broker / "scripts")
    sys.path.insert(0, sdir)
    try:
        spec = importlib.util.spec_from_file_location(alias, ROOT / broker / "scripts" / f"{name}.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.remove(sdir)


def rules(broker):
    return json.loads((ROOT / broker / "data" / "rules.json").read_text())


def check_equal(label, got, want):
    if got != want:
        bad(f"{label}: {got!r} != rules.json {want!r}")


def broker_checks(broker, tag):
    r = rules(broker)
    sig_file = {"dhan-live": "dhan_live_signals.json", "zerodha-live": "zerodha_live_signals.json"}[broker]
    engine = {"dhan-live": "compute_dh252_live_signals", "zerodha-live": "compute_zerodha_live_signals"}[broker]
    eng = load_mod(broker, engine, f"{tag}_engine")
    for const, key in [("ADD_TRIGGER_PCT", "add_trigger_pct"), ("ADD_FRACTION", "add_fraction"), ("ADD_COOLDOWN_DAYS", "add_cooldown_days"), ("BASE_POSITION_RS", "base_position_rs"),
                       ("POSITION_INCREMENT_RS", "position_increment_rs"), ("POSITION_INCREMENT_TRADES", "position_increment_trades")]:
        check_equal(f"{tag} engine {const}", getattr(eng, const), r[key])
    if broker == "zerodha-live":
        check_equal("AZ engine ENTRY_WINDOW_TRADING_DAYS", eng.ENTRY_WINDOW_TRADING_DAYS, r["entry_window_trading_days"])
        check_equal("AZ engine STARTING_CAPITAL", eng.STARTING_CAPITAL, r["starting_capital"])
        cc = load_mod(broker, "crosscheck_signals", "az_crosscheck")
        check_equal("AZ crosscheck ENTRY_WINDOW", cc.ENTRY_WINDOW, r["entry_window_trading_days"])
    else:
        check_equal("ND engine SIZE_DOUBLE_POSITIONS_THRESHOLD", eng.SIZE_DOUBLE_POSITIONS_THRESHOLD, r["size_double_positions_threshold"])
    g = load_mod(broker, "guardrails", f"{tag}_guard")
    for k, v in g.RULE_CFG.items():
        want = r["entry_window_trading_days"] if k == "entry_window_days" else r[k]
        check_equal(f"{tag} guardrails {k}", v, want)
    gc = json.loads((ROOT / broker / "data" / "guardrails_config.json").read_text())
    for k, key in [("add_trigger_pct", "add_trigger_pct"), ("add_cooldown_days", "add_cooldown_days"), ("entry_window_days", "entry_window_trading_days")]:
        if k in gc and key in r and gc[k] != r[key]:
            bad(f"{tag} guardrails_config.json {k}={gc[k]} conflicts with rules.json ({r[key]}); delete the duplicate key")
    sig = json.loads((ROOT / broker / sig_file).read_text()).get("rules", {})
    if "add_on_off_from" in sig and sig["add_on_off_from"] != r.get("add_on_off_from"):
        bad(f"{tag} {sig_file} rules.add_on_off_from={sig['add_on_off_from']} != rules.json {r.get('add_on_off_from')} (regenerate with the refresh)")
    for k in ("add_trigger_pct", "add_fraction", "add_cooldown_days"):
        if k in sig and sig[k] != r[k]:
            bad(f"{tag} {sig_file} rules.{k}={sig[k]} != rules.json {r[k]} (regenerate with the refresh)")
    if broker == "zerodha-live" and sig.get("entry_window_trading_days") not in (None, r["entry_window_trading_days"]):
        bad(f"AZ {sig_file} rules.entry_window_trading_days={sig.get('entry_window_trading_days')} != rules.json {r['entry_window_trading_days']} (regenerate with the refresh)")
    return r


def doc_checks(nd, az):
    html = (ROOT / "index.html").read_text()
    for m in re.finditer(r"(?:flipped to green in|within) the last (\d+) trading days", html):
        if int(m.group(1)) != az["entry_window_trading_days"]:
            bad(f"index.html page copy says 'last {m.group(1)} trading days' but AZ rules.json entry_window_trading_days = {az['entry_window_trading_days']}")
    for m in re.finditer(r"addTriggerPct: *(-?\d+(?:\.\d+)?)", html):
        v = float(m.group(1))
        if v not in (nd["add_trigger_pct"], az["add_trigger_pct"]):
            bad(f"index.html fallback addTriggerPct {v} matches neither rules.json")
    md = (ROOT / "CLAUDE.md").read_text()
    row = next((l for l in md.splitlines() if l.startswith("| Entry |")), "")
    m = re.search(r"within the last (\d+) trading days", row)
    if not m:
        bad("CLAUDE.md strategy table: AZ entry window text not found (expected 'within the last N trading days' in the '| Entry |' row)")
    elif int(m.group(1)) != az["entry_window_trading_days"]:
        bad(f"CLAUDE.md strategy table says last {m.group(1)} trading days, AZ rules.json says {az['entry_window_trading_days']}")
    row = next((l for l in md.splitlines() if l.startswith("| Add-on |")), "")
    cells = [c.strip() for c in row.strip().strip("|").split("|")][1:]
    for cell, who, tag in zip(cells, (nd, az), ("ND", "AZ")):
        off = who.get("add_on_off_from")
        if off:
            if not (cell.lower().startswith("off") and off in cell):
                bad(f"CLAUDE.md strategy table {tag} add-on cell must say 'off from {off}' (rules.json add_on_off_from)")
        else:
            m = re.search(r"<= *(-?\d+(?:\.\d+)?)%", cell)
            if not m or float(m.group(1)) != who["add_trigger_pct"]:
                bad(f"CLAUDE.md strategy table {tag} add-on cell does not show the rules.json trigger {who['add_trigger_pct']}%")
    row = next((l for l in md.splitlines() if l.startswith("| Sizing |")), "")
    for needle, who in (("Rs1,000 + Rs1,000", nd), ("Rs20,000 + Rs5,000", az)):
        if needle not in row:
            bad(f"CLAUDE.md strategy table sizing row lacks '{needle}'")
    skill = (ROOT / ".claude" / "skills" / "zerodha-order" / "SKILL.md").read_text()
    for m in re.finditer(r"flipped to green within the last (\d+) trading days", skill):
        if int(m.group(1)) != az["entry_window_trading_days"]:
            bad(f"zerodha-order skill says last {m.group(1)} trading days, AZ rules.json says {az['entry_window_trading_days']}")


def skill_checks():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_skill_blocks.py"), "--check"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        (notes if "left alone on purpose" in line else problems).append("skills: " + line)
    for p in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        if p.parent.name in ("zerodha-option-order",):
            continue
        t = p.read_text()
        if "zerodha-option-order" in t and "ON HOLD" not in t:
            bad(f"skill {p.parent.name} mentions the held skill zerodha-option-order without the words ON HOLD (see .claude/skills/_shared/holds.md)")


def main():
    nd = broker_checks("dhan-live", "ND")
    az = broker_checks("zerodha-live", "AZ")
    doc_checks(nd, az)
    skill_checks()
    for n in notes:
        print("note:", n)
    if problems:
        print(f"{len(problems)} DISAGREEMENT(S):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("rules consistent: engines, cross-check, guardrails, signals files, page, CLAUDE.md table, skills, skill blocks, holds")


if __name__ == "__main__":
    main()
