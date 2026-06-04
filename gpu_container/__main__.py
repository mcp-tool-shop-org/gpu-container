"""Unified `gpu-container <command>` entry — the single-binary / npm-launcher dispatcher.

`pip install gpu-container` lays down five console scripts (`gpu-container-profile`, `-plan`,
`-receipt`, `-concentration`, `-watchdog`). This dispatcher exposes the same five as subcommands of
one `gpu-container` command, which is what the PyInstaller binary and the npm launcher run:

    gpu-container profile ...
    gpu-container plan ...
    gpu-container watchdog run -- <cmd...>

Subcommand modules are imported lazily so a fast path (`--help`) never imports the whole package,
and so a frozen binary only pulls what the chosen command needs.
"""
from __future__ import annotations

import sys
from typing import List, Optional

# Absolute (not `from . import`): this module is the PyInstaller --onefile entry, run as a top-level
# `__main__` with no parent package — a relative import raises "attempted relative import with no
# known parent package" in the frozen binary (it works under `python -m`, which is the trap).
from gpu_container import __version__

_SUB = {
    "profile": "gpu_container.profiler.cli",
    "plan": "gpu_container.planner.cli",
    "receipt": "gpu_container.planner.receipt_cli",
    "concentration": "gpu_container.planner.concentration_cli",
    "watchdog": "gpu_container.watchdog",
}

_USAGE = (
    "usage: gpu-container <command> [args...]\n\n"
    "commands:\n"
    "  profile        profile the rig (+ model) -> profile.json\n"
    "  plan           plan an MoE placement (llama.cpp --n-cpu-moe) from a profile\n"
    "  receipt        verify a plan against a real llama-bench run\n"
    "  concentration  per-expert-cache de-risk gate (routing concentration)\n"
    "  watchdog       rig-safety control plane (monitor, or `run -- <cmd>`)\n\n"
    "run `gpu-container <command> --help` for per-command help.\n"
    "(each command is also installed standalone as `gpu-container-<command>`.)"
)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(_USAGE)
        return 0
    if argv[0] in ("-V", "--version"):
        print(__version__)   # static — works in a frozen binary (no importlib.metadata lookup)
        return 0
    cmd, rest = argv[0], argv[1:]
    mod = _SUB.get(cmd)
    if mod is None:
        print(f"gpu-container: unknown command '{cmd}'\n\n{_USAGE}", file=sys.stderr)
        return 2
    import importlib
    return importlib.import_module(mod).main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
