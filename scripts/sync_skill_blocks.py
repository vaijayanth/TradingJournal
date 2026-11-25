"""Keep the shared "Concise output" block identical in every skill that carries it (user-set formatting rules live in ONE place).

  python scripts/sync_skill_blocks.py          # rewrite the block in every skill from .claude/skills/_shared/output-format.md
  python scripts/sync_skill_blocks.py --check  # exit 1 if any skill drifted (used by scripts/check_rules_consistency.py)

A skill opts in by wrapping its block in <!-- shared:output-format:begin --> ... <!-- shared:output-format:end -->. Skills listed in FROZEN keep their own copy
(the user asked that file be left untouched); --check only reports whether their copy still equals the canonical text.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / ".claude" / "skills"
CANON = (SK / "_shared" / "output-format.md").read_text().rstrip("\n")
B, E = "<!-- shared:output-format:begin -->", "<!-- shared:output-format:end -->"
FROZEN = {"zerodha-option-order"}
SECTION = re.compile(r"(?ms)^## Concise output.*?(?=^## |\Z)")


def main(check):
    bad = []
    for p in sorted(SK.glob("*/SKILL.md")):
        name = p.parent.name
        t = p.read_text()
        if name in FROZEN:
            m = SECTION.search(t)
            if m and m.group(0).rstrip("\n") != CANON:
                bad.append(f"{name}: frozen copy differs from the canonical block (left alone on purpose)")
            continue
        if B in t:
            new = re.sub(re.escape(B) + r".*?" + re.escape(E), lambda _: B + "\n" + CANON + "\n" + E, t, flags=re.S)
        else:
            m = SECTION.search(t)
            if not m:
                continue
            new = t[:m.start()] + B + "\n" + CANON + "\n" + E + "\n" + t[m.end():]
        if new != t:
            bad.append(f"{name}: block {'differs' if B in t else 'not yet wrapped'}")
            if not check:
                p.write_text(new)
    return bad


if __name__ == "__main__":
    chk = "--check" in sys.argv
    out = main(chk)
    for o in out:
        print(("DRIFT " if chk else "synced ") + o)
    sys.exit(1 if (chk and any(not o.endswith("(left alone on purpose)") for o in out)) else 0)
