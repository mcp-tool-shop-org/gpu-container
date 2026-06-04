"""The placement planner: a profile + model -> an explicit tiered placement plan for a runtime.

Phase-1 target: llama.cpp `--n-cpu-moe N` (the first N MoE layers' expert weights live in CPU
RAM and are computed on CPU; attention/router/shared/embeddings/head stay on the GPU — the
KTransformers-style "compute where the weights are", NOT per-token PCIe streaming; verified in
tensor-engine-knowledge). The planner finds the minimal N that fits VRAM, predicts the memory
map + decode throughput, and REFUSES below the >1 tok/s floor with a contrastive frame.
"""
from .calibration import (  # noqa: F401
    CalibrationModel,
    CalibrationPoint,
    CalibrationStore,
    EfficiencyEstimate,
    load_seed_points,
)
from .placement import DEFAULT_CPU_BW_GBPS, DEFAULT_VRAM_BW_GBPS, plan_llama_cpp  # noqa: F401
from .receipt import build_receipt, parse_llama_bench, plan_to_calibration_point  # noqa: F401
