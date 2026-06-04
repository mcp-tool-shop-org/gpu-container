#!/usr/bin/env python3
"""verify — test + smoke (+ optional build) in one command (shipcheck gate D1).

    python scripts/verify.py            # run the test suite + a CLI smoke of all 5 commands
    python scripts/verify.py --build    # also build the wheel + sdist (needs `pip install build`)

Exit 0 only if every step passes. Cross-platform: invokes everything via the current
interpreter (`python -m ...`), so it needs no console scripts on PATH and runs the same on
the Windows host and an ubuntu CI runner.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile

PY = sys.executable


def run(label: str, cmd: list[str], ok_codes=(0,)) -> bool:
    print(f"\n=== {label} ===\n$ {' '.join(cmd)}", flush=True)
    rc = subprocess.run(cmd).returncode
    ok = rc in ok_codes
    print(f"--- {label}: {'ok' if ok else 'FAIL'} (exit {rc})")
    return ok


def main(argv: list[str]) -> int:
    results: list[tuple[str, bool]] = []

    results.append(("tests", run("tests", [PY, "-m", "pytest", "-q"])))

    # CLI smoke — every command must import + parse (argparse --help exits 0).
    for mod in ("profiler.cli", "planner.cli", "planner.receipt_cli",
                "planner.concentration_cli", "watchdog"):
        results.append((f"{mod} --help",
                        run(f"{mod} --help", [PY, "-m", f"gpu_container.{mod}", "--help"])))

    # watchdog one-shot actually reads the rig; ok/warn/abort (0/5/7) all mean "it ran".
    results.append(("watchdog --json",
                    run("watchdog --json", [PY, "-m", "gpu_container.watchdog", "--json"],
                        ok_codes=(0, 5, 7))))

    if "--build" in argv:
        with tempfile.TemporaryDirectory() as d:
            results.append(("build", run("build", [PY, "-m", "build", "--outdir", d])))

    print("\n==== verify summary ====")
    ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print(f"==== {'ALL PASS' if ok else 'FAILURES — see above'} ====")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
