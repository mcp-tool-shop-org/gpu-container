"""The profiler: hardware + model profiling -> a single, JSON-serializable Profile.

- `schema`   — the Profile contract every downstream component reads.
- `hardware` — detect/measure the rig (GPU, platform, bandwidth, memory).
- `model`    — analyze a model (dense vs MoE, KV growth, per-expert bytes).
- `cli`      — `gpu-container-profile` -> writes profile.json.

Design rule (from docker-knowledge wave-1): a measurement we have NOT taken is `None`,
never a guessed number. The planner must treat `None` as "unknown — refuse to assume",
because honest refusal depends on honest inputs.
"""
from .schema import (  # noqa: F401
    SCHEMA_VERSION,
    BandwidthInfo,
    ExpertInfo,
    GpuInfo,
    HardwareProfile,
    MemoryInfo,
    ModelProfile,
    PlacementPlan,
    PlatformInfo,
    Profile,
    Receipt,
)
