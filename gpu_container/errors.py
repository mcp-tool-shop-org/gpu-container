"""Structured errors + a CLI guard — the shipcheck B1/B3 contract.

Every user-facing failure carries a stable `{code, message, hint, cause?, retryable?}` shape
(`GpuContainerError`) and renders as a few clean lines — never a raw traceback. `guard()` wraps a
CLI's body so an *unexpected* exception also becomes one clean line + exit 2; the full traceback
appears only with `--debug`.

Error `code`s are namespaced and stable once released (treat like API). Prefixes:
  INPUT_  bad user input / validation      IO_      filesystem / paths
  DEP_    a missing optional dependency     RUNTIME_ unexpected failure
  STATE_  corrupt / stale internal state
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class GpuContainerError(Exception):
    """A user-facing error with a structured, stable shape. Raise it from a CLI body; `guard`
    renders it and returns `exit_code` (default 2 — distinct from the planners' verdict codes)."""
    code: str
    message: str
    hint: Optional[str] = None
    cause: Optional[str] = None
    retryable: bool = False
    exit_code: int = 2

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "hint": self.hint,
                "cause": self.cause, "retryable": self.retryable}

    def render(self) -> str:
        lines = [f"ERROR [{self.code}]: {self.message}"]
        if self.hint:
            lines.append(f"  hint: {self.hint}")
        if self.cause:
            lines.append(f"  cause: {self.cause}")
        if self.retryable:
            lines.append("  retryable: yes")
        return "\n".join(lines)


def guard(run: Callable[[Optional[List[str]]], int], argv: Optional[List[str]] = None) -> int:
    """Run a CLI body, turning failures into clean structured output and never leaking a raw
    traceback unless `--debug` is present.

    - `GpuContainerError` -> render it, return its `exit_code` (an expected error; no trace).
    - any other Exception  -> with `--debug`, re-raise (show the trace); else one clean line + exit 2.
    Normal returns (the verdict codes 0/3/4/5/7) pass straight through. argparse's own usage exits
    (SystemExit) are not caught — they keep argparse's message + exit 2.
    """
    debug = "--debug" in (argv if argv is not None else sys.argv[1:])
    try:
        return run(argv)
    except GpuContainerError as e:
        print(e.render(), file=sys.stderr)
        return e.exit_code
    except KeyboardInterrupt:
        print("ERROR [RUNTIME_INTERRUPTED]: interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001 — deliberate: no raw stack without --debug (gate B3)
        if debug:
            raise
        print(f"ERROR [RUNTIME_UNEXPECTED]: {type(e).__name__}: {e}\n"
              "  hint: re-run with --debug for the full traceback", file=sys.stderr)
        return 2
