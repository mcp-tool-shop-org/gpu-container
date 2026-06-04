"""gpu-container — a model-aware inference memory-placement planner for single-GPU rigs.

Phase 1 starts with the profiler (this package's `profiler` module): it emits the
profile JSON that every downstream component (planner, receipt) reads. Knowledge that
grounds the measurement methodology lives in the docker-knowledge KB
(readouts/docker-knowledge), seeded by the feasibility study-swarm.
"""

__version__ = "0.1.1"
