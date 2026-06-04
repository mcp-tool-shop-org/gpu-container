"""`gpu-container-concentration` — the per-expert-cache de-risk gate, as a command.

Given an activation trace (which experts fired, per layer), score routing CONCENTRATION and answer
the prior question for the per-expert lane: would a hot-expert VRAM cache (the llama.cpp #20757 lane)
actually help, or is routing too uniform to bother? Backs ADR-0001; logic in `activation.py`.

  gpu-container-concentration --trace trace.json
  gpu-container-concentration --imatrix imatrix.gguf --model-name Qwen3-30B-A3B   # needs the `gguf` pkg

`--imatrix` reads a `llama-imatrix` output directly (per-layer `ffn_down_exps.weight.counts`); the
`gguf` package is an OPTIONAL dependency — only that path needs it. `--trace` keeps the core dep-free.

Exit code (ANDON-style, scriptable):
  0 = analyzed; a per-expert cache is NOT justified (routing too uniform — the common 'hold' outcome)
  5 = analyzed; routing concentrates enough that a cache could help (worth weighing #20757)
  2 = usage / input error
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ..errors import GpuContainerError, guard
from .activation import ActivationTrace, analyze_concentration, load_trace


def _trace_from_imatrix(path: str, model_name: str, topk: int) -> ActivationTrace:
    """Build an ActivationTrace from a llama-imatrix `imatrix.gguf` (per-expert `.counts`).

    Raises ValueError on a missing `gguf` package or a non-MoE / unexpected imatrix (the caller maps
    that to exit 2)."""
    try:
        import gguf  # optional dependency — only the --imatrix path needs it
    except ImportError:
        raise ValueError("--imatrix needs the 'gguf' package (pip install gguf); "
                         "or extract a trace.json yourself and pass --trace.")
    reader = gguf.GGUFReader(path)
    counts = {}
    for t in reader.tensors:
        nm = t.name.strip()
        if nm.endswith("ffn_down_exps.weight.counts") and nm.startswith("blk."):
            layer = int(nm.split(".")[1])
            counts[layer] = [int(round(float(x))) for x in list(t.data.flatten())]
    if not counts:
        raise ValueError("no per-expert counts (ffn_down_exps.weight.counts) in this imatrix — "
                         "is it a llama-imatrix .gguf for an MoE model?")
    E = len(next(iter(counts.values())))
    layers = [{"layer_index": L, "expert_counts": counts[L]} for L in sorted(counts)]
    n_tokens = (sum(layers[0]["expert_counts"]) // topk) if topk else 0
    return ActivationTrace.from_dict({
        "model": model_name, "num_experts": E, "experts_per_token": topk,
        "n_tokens": n_tokens, "layers": layers, "source": f"llama-imatrix per-expert counts: {path}",
    })


def _main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-concentration",
        description="Per-expert-cache de-risk gate: does this model's routing concentrate enough to cache?",
    )
    ap.add_argument("--debug", action="store_true", help="show the full traceback on an unexpected error")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--trace", help="ActivationTrace JSON (L×E per-expert counts)")
    src.add_argument("--imatrix", help="llama-imatrix imatrix.gguf (extract per-expert counts; needs `gguf`)")
    ap.add_argument("--model-name", default="model", help="model name (for the --imatrix path / the report)")
    ap.add_argument("--topk", type=int, default=8, help="experts/token, for the --imatrix n_tokens estimate")
    ap.add_argument("--coverage", type=float, default=0.90, help="routing-mass coverage target (default 0.90)")
    ap.add_argument("--threshold", type=float, default=0.50,
                    help="cache_helps if < this fraction of experts cover the target (default 0.50)")
    ap.add_argument("-o", "--out", help="write the report JSON here (default: stdout)")
    args = ap.parse_args(argv)

    if args.imatrix:
        try:
            trace = _trace_from_imatrix(args.imatrix, args.model_name, args.topk)
        except (ValueError, OSError) as e:
            raise GpuContainerError("INPUT_BAD_IMATRIX", str(e),
                                    hint="pass --trace with an L×E counts JSON instead, "
                                         "or `pip install gguf` for the --imatrix path")
    else:
        trace = load_trace(args.trace)
        if trace is None:
            raise GpuContainerError("IO_TRACE_UNREADABLE", f"could not load a trace from {args.trace}",
                                    hint="expected an ActivationTrace JSON "
                                         "(model, num_experts, experts_per_token, layers[])")

    rep = analyze_concentration(trace, coverage_target=args.coverage, cache_helps_threshold=args.threshold)

    js = rep.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(js)

    need = rep.hot_frac_for_coverage * rep.num_experts
    verdict = "CACHE COULD HELP" if rep.cache_helps else "cache NOT justified"
    print(f"{rep.model}: {verdict} — {need:.0f}/{rep.num_experts} experts ({rep.hot_frac_for_coverage:.0%}) "
          f"resident for {rep.coverage_target:.0%} routing coverage; concentration {rep.concentration_score:.2f}, "
          f"top expert {rep.top1_share:.1%} ({rep.n_layers} layers, ~{rep.n_tokens} tok).", file=sys.stderr)
    for n in rep.notes:
        print(f"  note: {n}", file=sys.stderr)

    return 5 if rep.cache_helps else 0


def main(argv: Optional[List[str]] = None) -> int:
    return guard(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
