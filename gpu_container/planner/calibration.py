"""Receipt-driven recalibration — turn measured receipts into a calibrated forecast.

The planner emits a roofline CEILING (peak bandwidth, zero overhead): a true upper bound on
decode tok/s, but real decode runs at a fraction of it (Qwen3-30B-A3B realized 41% in-VRAM,
56-61% offloaded — milestone 2-3 live receipt). This module closes that static-prediction gap:

    receipt  ->  CalibrationPoint (realized efficiency at a known shape)
              ->  CalibrationStore (a JSON dir; append-only, auditable)
              ->  CalibrationModel (efficiency = f(regime, offload-fraction), with a band)
              ->  planner emits  ceiling x efficiency  +/- band   (the calibrated forecast)

Two regimes, because they are bound by different things (placement.py `basis`):
  - `in_vram`  (N = 0): overhead-bound — small-active MoE spends most of its time NOT moving
    bytes, so realized efficiency is low (~41%) and roughly flat.
  - `offload`  (N > 0): CPU-RAM-bandwidth-bound — the roofline fits better (~56-61%) and tracks
    the offload fraction N / n_moe_layers.

Sparse-data-honest by construction: we bucket by regime and interpolate within `offload` only
when there are >= 2 distinct offload fractions; otherwise we report the regime's central
efficiency. The band never narrows below +/-`default_margin` (we cannot claim more confidence
than the data supports), and it always contains every observed point in the regime. With NO
points for a regime, `estimate()` returns None and the planner falls back to the raw ceiling --
the honest "uncalibrated" path. This mirrors the feasibility verdict's calibration #2: the
+/-10% receipt is scoped to the regimes we have measured; everywhere else is ceiling + band.

The model never grades its own forecast: the points come from llama-bench (a real GPU run, a
DIFFERENT mechanism than the planner's closed form) -- the EXTERNAL_VERIFIER discipline.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from statistics import median
from typing import Iterable, List, Optional

# Bundled seed: the measured Qwen3-30B-A3B receipts that ship with the package so a known shape
# is calibrated out-of-the-box. Lives next to this module.
_SEED_PATH = os.path.join(os.path.dirname(__file__), "calibration_seed.json")

DEFAULT_MARGIN = 0.25  # +/-25% efficiency band (feasibility #11: heavy offload can miss 2-3x; this
                       # is the *calibrated* band, far tighter than that worst case, but never tighter
                       # than the data supports)


@dataclass
class CalibrationPoint:
    """One receipt's realized efficiency, tagged with the shape it was measured at.

    `efficiency`, `regime`, and `offload_fraction` are DERIVED (properties) -- we persist only the
    measured facts (ceiling, measured tok/s, the N/L shape, the bandwidth assumptions) so a point is
    auditable and re-derivable, never a number we can silently get wrong.
    """
    model: str
    n_cpu_moe: int
    n_moe_layers: int
    ceiling_tok_s: float
    measured_tok_s: float
    quant: Optional[str] = None
    cpu_bw_gbps: Optional[float] = None
    vram_bw_gbps: Optional[float] = None
    ctx_len: Optional[int] = None
    created: Optional[str] = None        # ISO date (passed in; runners have no clock)
    rig: Optional[str] = None
    source: Optional[str] = None         # provenance (which run / receipt)

    @property
    def regime(self) -> str:
        return "in_vram" if self.n_cpu_moe == 0 else "offload"

    @property
    def offload_fraction(self) -> float:
        return (self.n_cpu_moe / self.n_moe_layers) if self.n_moe_layers else 0.0

    @property
    def efficiency(self) -> Optional[float]:
        if not self.ceiling_tok_s:
            return None
        return self.measured_tok_s / self.ceiling_tok_s

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationPoint":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class EfficiencyEstimate:
    """A calibrated efficiency (measured / ceiling) for a shape, with an honest band."""
    efficiency: float        # central estimate
    low: float               # band low (efficiency units)
    high: float              # band high (efficiency units, capped at 1.0 -- can't beat the ceiling)
    n_samples: int
    regime: str
    basis: str               # human-readable provenance of the estimate


class CalibrationStore:
    """Append-only JSON-directory persistence for calibration points.

    A point is one `.json` file (so concurrent writers never clobber each other); a file may also
    hold a LIST of points (the bundled seed is one such file). Reading tolerates both shapes and
    skips anything malformed -- a corrupt point degrades the calibration, it never crashes a plan.
    """

    def __init__(self, path: str):
        self.path = path

    def add(self, point: CalibrationPoint, filename: Optional[str] = None) -> str:
        os.makedirs(self.path, exist_ok=True)
        if filename is None:
            # Stable, collision-resistant name from the shape + provenance (no clock dependency).
            stamp = (point.created or "nodate").replace(":", "-")
            safe_model = "".join(c if c.isalnum() else "-" for c in point.model)[:40]
            filename = f"{stamp}_{safe_model}_n{point.n_cpu_moe}.json"
        dest = os.path.join(self.path, filename)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(point.to_dict(), f, indent=2, ensure_ascii=False)
        return dest

    def points(self) -> List[CalibrationPoint]:
        out: List[CalibrationPoint] = []
        if not os.path.isdir(self.path):
            return out
        for name in sorted(os.listdir(self.path)):
            if not name.endswith(".json"):
                continue
            out.extend(_load_points_file(os.path.join(self.path, name)))
        return out


def _load_points_file(path: str) -> List[CalibrationPoint]:
    """Load a JSON file holding either one point (dict) or many (list). Never raises on bad data."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    records = data if isinstance(data, list) else [data]
    out: List[CalibrationPoint] = []
    for rec in records:
        if isinstance(rec, dict):
            try:
                out.append(CalibrationPoint.from_dict(rec))
            except (TypeError, ValueError):
                continue
    return out


def load_seed_points() -> List[CalibrationPoint]:
    """The measured receipts bundled with the package (Qwen3-30B-A3B, milestone 2-3)."""
    return _load_points_file(_SEED_PATH)


class CalibrationModel:
    """Fits realized efficiency from calibration points, bucketed by regime.

    `estimate(regime, offload_fraction)` returns an `EfficiencyEstimate` or None (no data for that
    regime -> the planner falls back to the ceiling). Within `offload`, it interpolates piecewise-
    linearly over the offload fraction when >= 2 distinct fractions are known; otherwise it uses the
    regime's median efficiency. The band is +/-`margin`, widened so it always contains every observed
    point in the regime, and capped at efficiency 1.0.
    """

    def __init__(self, points: Iterable[CalibrationPoint], margin: float = DEFAULT_MARGIN):
        self.points = [p for p in points if p.efficiency is not None]
        self.margin = margin

    @classmethod
    def from_seed(cls, extra: Optional[Iterable[CalibrationPoint]] = None,
                  margin: float = DEFAULT_MARGIN) -> "CalibrationModel":
        pts = list(load_seed_points())
        if extra:
            pts.extend(extra)
        return cls(pts, margin=margin)

    def has_data(self) -> bool:
        return bool(self.points)

    def estimate(self, regime: str, offload_fraction: float = 0.0) -> Optional[EfficiencyEstimate]:
        pts = [p for p in self.points if p.regime == regime]
        if not pts:
            return None
        effs = [p.efficiency for p in pts]  # type: ignore[misc]  (filtered to non-None in __init__)

        # group efficiencies by offload fraction (average repeated runs at the same fraction)
        by_frac = defaultdict(list)
        for p in pts:
            by_frac[round(p.offload_fraction, 4)].append(p.efficiency)
        curve = sorted((f, sum(v) / len(v)) for f, v in by_frac.items())

        if regime == "offload" and len(curve) >= 2:
            central = _interp(curve, offload_fraction)
            basis = (f"calibrated: piecewise-linear over {len(curve)} offload fractions "
                     f"({len(pts)} receipt(s)) at frac={offload_fraction:.2f}")
        else:
            central = float(median(effs))
            basis = f"calibrated: median of {len(pts)} '{regime}' receipt(s)"

        # band: never tighter than +/-margin, always contains every observed point in the regime
        spread = max((abs(e - central) / central for e in effs), default=0.0) if central else 0.0
        rel = max(self.margin, spread)
        low = max(central * (1.0 - rel), 1e-4)
        high = min(central * (1.0 + rel), 1.0)
        return EfficiencyEstimate(efficiency=central, low=low, high=high,
                                  n_samples=len(pts), regime=regime, basis=basis)


def _interp(curve: List[tuple], x: float) -> float:
    """Piecewise-linear interpolation over a sorted [(x, y), ...] curve, clamped at both ends
    (NO extrapolation -- beyond the measured fractions we hold the nearest observed efficiency)."""
    if x <= curve[0][0]:
        return curve[0][1]
    if x >= curve[-1][0]:
        return curve[-1][1]
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + t * (y1 - y0)
    return curve[-1][1]
