"""Plant every SA-FIGURE-STORY guard's own defect; require the guard to FIRE.

Companion to scripts/verify_figure_guards.py, covering the two figures added
in the figure-story pass:

  * the SPARSITY MAP (the paper's central claim, which had no figure), and
  * the CANONICAL SESSION-MATCHED reader contrast (Figure 6 had been drawing
    the SUPERSEDED cross-session +0.1268 while the prose quoted +0.0982).

A guard only ever observed PASSING is not known to discriminate -- three of
this project's recorded defects were in guards, and one printed a correct
verdict from an empty input. So each guard is exercised by planting the exact
defect it exists to catch.

TWO ORDERS OF PLANT, because the first is not enough:
  order 1 -- plant in the rows/artifact. Most guards fire, but several fire
             via an `expect()` pin on a count rather than via the caption
             guard they were aimed at. A guard whose firing is always
             PREEMPTED by another has not been shown to work.
  order 2 -- `expect()` is neutralised, so ONLY the structural caption guards
             can fire, and each plant must be caught by ITS OWN guard.

Each order opens with an UNPLANTED control: without it a "FAIL" could be the
harness being broken rather than a guard firing, and with expect() switched
off a silent pass could mean the guards were switched off too.

Several plants had to be rewritten after they were seen to fire for the wrong
reason -- those rewrites are documented inline, because a plant caught by a
different guard proves nothing about the one it targets.

Nothing on disk is modified: every plant patches a copy in memory.

Run: /Users/bellayang/miniconda3/bin/python3 scripts/verify_story_figure_guards.py
Exit 1 if any guard fails to fire on its own defect.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def run(name: str, script: Path) -> int:
    print("#" * 72)
    print(f"# {name}")
    print("#" * 72)
    r = subprocess.run([PY, str(script)], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)
    return r.returncode


def main() -> int:
    rc = 0
    rc |= run('SPARSITY MAP -- order 1 (plant in the rows)', HERE / "_story_plants_0.py")
    rc |= run('SPARSITY MAP -- order 2 (caption guards isolated)', HERE / "_story_plants_1.py")
    rc |= run('SESSION-MATCHED READER -- orders 1 and 2', HERE / "_story_plants_2.py")
    print()
    if rc:
        print("A GUARD DID NOT FIRE")
        return 1
    print("ALL STORY-FIGURE GUARDS DISCRIMINATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
