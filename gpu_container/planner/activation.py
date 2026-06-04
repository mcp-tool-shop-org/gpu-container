"""Activation-trace concentration analysis — does per-expert caching even help?

The throughput half ([`calibration.py`]) turns receipts into a tok/s forecast. THIS module answers a
PRIOR, go/no-go question for the per-expert lane: given a captured activation trace (which experts
fired, per layer, over a representative workload), is the routing CONCENTRATED enough that a small
hot-expert VRAM cache would hit often — or is it so uniform that the cache (llama.cpp #20757) isn't
worth building?

It is the de-risk gate for ADR-0001 (`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`):
build the runtime expert cache only where the trace shows a small fraction of experts captures most
of the routing.

Grounded in docker-knowledge wave-4 (moe-placement):
  - Per-LAYER *total* activation is ~uniform — every token hits every layer's top-k experts — so the
    signal is PER-EXPERT concentration WITHIN a layer, not which layer. Only the runtime cache can
    exploit per-expert skew; `-ot` is per-layer (llamacpp-experts-fused-per-layer-not-per-expert).
  - Skew is request-level and flattens to uniform across diverse prompts (MoE-Infinity,
    arXiv:2401.14361) — so concentration is WORKLOAD-DEPENDENT: a trace is only valid for the
    workload it was cut from. The report says so; a diverse-prompt trace reads LESS concentrated.
  - The trace is an L×E count matrix captured via an eval-callback (activation-trace-via-eval-callback);
    THIS module only CONSUMES it. None-not-guess: no trace -> no verdict (the planner stays per-layer).

Two measures, deliberately:
  - `hot_frac_for_coverage` — the fraction of a layer's experts that must be resident to capture
    `coverage_target` (default 90%) of its routing. The ACTIONABLE number; maps straight to #20757
    `--moe-expert-cache-size`.
  - `concentration_score = 1 - normalized_entropy` — a threshold-free [0,1] skew measure
    (0 = uniform, 1 = one expert), robust to the arbitrary coverage target.

`cache_helps` is a convenience gate on the numbers, never a substitute for them.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from statistics import median
from typing import List, Optional

DEFAULT_COVERAGE_TARGET = 0.90
# If fewer than this fraction of a layer's experts cover `coverage_target` of its routing, a hot-expert
# cache buys real VRAM back — so a cache "helps". Tunable; the numbers are reported regardless.
DEFAULT_CACHE_HELPS_THRESHOLD = 0.50


@dataclass
class LayerActivation:
    """One MoE layer's routing counts: expert_counts[i] = tokens routed to expert i in this layer."""
    layer_index: int
    expert_counts: List[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.expert_counts)


@dataclass
class ActivationTrace:
    """An L×E activation trace captured over a representative workload (the eval-callback's output).

    Persists only measured facts; concentration is DERIVED by `analyze_concentration` so the verdict
    is always re-derivable from the counts, never a number we can silently get wrong.
    """
    model: str
    num_experts: int                 # E (routed experts per MoE layer)
    experts_per_token: int           # top-k (sanity: each layer total ~= n_tokens * k)
    n_tokens: int                    # decode tokens the trace covers
    layers: List[LayerActivation] = field(default_factory=list)
    gate_weighted: bool = False      # counts are gate-mass-weighted (else raw selection counts)
    created: Optional[str] = None    # ISO date (passed in; the capture harness has no clock)
    rig: Optional[str] = None
    source: Optional[str] = None     # provenance (which workload / run produced it)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "ActivationTrace":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        kw = {k: v for k, v in d.items() if k in known}
        kw["layers"] = [
            LayerActivation(layer_index=l.get("layer_index"),
                            expert_counts=[int(c) for c in (l.get("expert_counts") or [])])
            for l in (d.get("layers") or []) if isinstance(l, dict)
        ]
        return cls(**kw)

    @classmethod
    def from_json(cls, s: str) -> "ActivationTrace":
        return cls.from_dict(json.loads(s))


@dataclass
class LayerConcentration:
    layer_index: int
    total_mass: int                  # sanity: ~= n_tokens * top_k (per-layer totals are ~uniform)
    top1_share: float                # routing share of the single hottest expert
    hot_frac_for_coverage: float     # fraction of experts needed to reach coverage_target
    concentration_score: float       # 1 - normalized entropy (0 = uniform, 1 = fully concentrated)


@dataclass
class ConcentrationReport:
    """The de-risk verdict: would a per-expert cache help, and by how much, for THIS workload."""
    model: str
    num_experts: int
    n_layers: int                    # layers with routing mass that were analyzed
    n_tokens: int
    coverage_target: float
    threshold: float
    cache_helps: bool
    hot_frac_for_coverage: float     # median over layers — the headline cache-size number
    concentration_score: float       # mean over layers
    top1_share: float                # median over layers
    per_layer: List[LayerConcentration] = field(default_factory=list)
    basis: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _normalized_entropy(counts: List[int]) -> float:
    """Shannon entropy of the routing distribution, normalized to [0,1] by log(E).

    1.0 = perfectly uniform (every expert equally used); 0.0 = all mass on one expert. Caller
    guarantees total > 0. A single expert (or a single active expert) is fully concentrated (0.0)."""
    total = sum(counts)
    nz = [c for c in counts if c > 0]
    E = len(counts)
    if E <= 1 or len(nz) <= 1:
        return 0.0
    H = -sum((c / total) * math.log(c / total) for c in nz)
    return H / math.log(E)


def _hot_frac_for_coverage(counts: List[int], target: float) -> float:
    """Fraction of experts (resident, hottest-first) needed to capture `target` of routing mass.

    Low = concentrated (a small cache covers most routing); ~target = uniform (no cache win)."""
    total = sum(counts)
    E = len(counts)
    if total <= 0 or E <= 0:
        return 1.0
    need = target * total
    cum = 0
    for i, c in enumerate(sorted(counts, reverse=True), start=1):
        cum += c
        if cum >= need:
            return i / E
    return 1.0


def analyze_layer(layer: LayerActivation, coverage_target: float) -> Optional[LayerConcentration]:
    """Per-layer concentration, or None for a zero-mass layer (skipped, never guessed)."""
    counts = layer.expert_counts
    total = sum(counts)
    if total <= 0 or not counts:
        return None
    return LayerConcentration(
        layer_index=layer.layer_index,
        total_mass=total,
        top1_share=max(counts) / total,
        hot_frac_for_coverage=_hot_frac_for_coverage(counts, coverage_target),
        concentration_score=1.0 - _normalized_entropy(counts),
    )


def analyze_concentration(
    trace: ActivationTrace,
    coverage_target: float = DEFAULT_COVERAGE_TARGET,
    cache_helps_threshold: float = DEFAULT_CACHE_HELPS_THRESHOLD,
) -> ConcentrationReport:
    """Aggregate a trace into the per-expert-cache de-risk verdict. Never raises; honest on empty data."""
    per_layer = [c for c in (analyze_layer(l, coverage_target) for l in trace.layers) if c is not None]
    notes: List[str] = []

    if not per_layer:
        return ConcentrationReport(
            model=trace.model, num_experts=trace.num_experts, n_layers=0, n_tokens=trace.n_tokens,
            coverage_target=coverage_target, threshold=cache_helps_threshold,
            cache_helps=False, hot_frac_for_coverage=1.0, concentration_score=0.0, top1_share=0.0,
            per_layer=[], basis="no layers with routing mass — cannot assess (treated as 'cache not justified')",
            notes=["empty or zero-mass trace — capture a real workload trace before deciding"],
        )

    hot = float(median(c.hot_frac_for_coverage for c in per_layer))
    conc = sum(c.concentration_score for c in per_layer) / len(per_layer)
    top1 = float(median(c.top1_share for c in per_layer))
    cache_helps = hot < cache_helps_threshold

    # Sanity: per-layer totals should be ~uniform (every token hits every layer's top-k). A large
    # spread hints at a malformed trace, a wrong experts_per_token/n_tokens, or unequal expert counts.
    masses = [c.total_mass for c in per_layer]
    if max(masses) and (max(masses) - min(masses)) / max(masses) > 0.2:
        notes.append("per-layer totals vary >20% — check experts_per_token/n_tokens, or layers may "
                     "carry differing expert counts")
    notes.append("concentration is WORKLOAD-DEPENDENT: request-level skew flattens across diverse "
                 "prompts (MoE-Infinity); this verdict is valid only for the workload this trace covers")

    basis = (f"{len(per_layer)} layers; hot_frac = median experts for {coverage_target:.0%} routing "
             f"coverage; concentration = 1 - normalized_entropy (mean); "
             f"cache_helps = hot_frac < {cache_helps_threshold:.0%}")

    return ConcentrationReport(
        model=trace.model, num_experts=trace.num_experts, n_layers=len(per_layer),
        n_tokens=trace.n_tokens, coverage_target=coverage_target, threshold=cache_helps_threshold,
        cache_helps=cache_helps, hot_frac_for_coverage=hot, concentration_score=conc,
        top1_share=top1, per_layer=per_layer, basis=basis, notes=notes,
    )


def load_trace(path) -> Optional[ActivationTrace]:
    """Load a trace JSON (the capture harness's output). Returns None on any error — never raises."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return ActivationTrace.from_dict(json.load(f))
    except (OSError, ValueError, TypeError):
        return None
