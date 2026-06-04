"""Profile schema — the contract every downstream component (planner, receipt) reads.

A `Profile` = `HardwareProfile` + optional `ModelProfile` + provenance, fully
JSON-serializable. Measurement fields are `Optional` and default to `None`: a value
of `None` means "not measured / unknown", and the planner MUST NOT treat it as zero
or assume a spec-sheet number (docker-knowledge wave-1, lane `hw-measurement`: honest
refusal depends on honest inputs; consumer cards are PCIe-bound and NVMe random-QD1 is
far below sequential, so guessing here silently corrupts every downstream plan).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, List, Optional

SCHEMA_VERSION = "0.1.0"


@dataclass
class GpuInfo:
    name: str
    vram_total_mib: Optional[int] = None
    vram_free_mib: Optional[int] = None
    vram_reserved_mib: Optional[int] = None     # driver-reserved (pynvml v2 only); v1 folds this into 'used'
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None   # e.g. "12.0" for sm_120 (desktop Blackwell)
    pcie_gen: Optional[int] = None
    pcie_width: Optional[int] = None            # lanes, e.g. 16
    vram_source: Optional[str] = None           # "pynvml-v2" | "pynvml-v1" | "nvidia-smi" (provenance)


@dataclass
class PlatformInfo:
    os: str                                     # "windows" | "linux"
    in_container: bool = False
    wsl2: bool = False
    container_runtime: Optional[str] = None     # "docker" | None
    nvidia_runtime: Optional[bool] = None       # NVIDIA Container Toolkit wired in
    # The load-bearing positioning (docker-knowledge lane `container-runtime`):
    # CUDA UVM oversubscription is unavailable on windows/wsl2 -> explicit placement only.
    uvm_oversubscription: Optional[bool] = None


@dataclass
class BandwidthInfo:
    """Measured, never spec-sheet. None until benchmarked (hardened in docker-knowledge wave-2)."""
    pcie_h2d_gbps: Optional[float] = None              # achieved pinned (~50-55 on Gen5; never the 64 theoretical)
    pcie_d2h_gbps: Optional[float] = None              # measured separately — asymmetry is real
    nvme_seq_read_gbps: Optional[float] = None         # optimistic ceiling only
    nvme_rand_qd1_read_iops: Optional[float] = None   # the one a sequential assumption gets wrong
    nvme_rand_qd1_read_mbps: Optional[float] = None   # what cold-expert / KV-spill streaming math keys off
    method: Optional[str] = None                       # how it was measured (provenance summary)
    details: Optional[dict] = None                     # structured provenance: buffer sizes, fs, samples, flags


@dataclass
class MemoryInfo:
    ram_total_gib: Optional[float] = None
    ram_available_gib: Optional[float] = None
    pinnable_ceiling_gib: Optional[float] = None       # WSL2 limits this (docker-knowledge container-runtime)
    pinnable_method: Optional[str] = None              # how the ceiling was probed (provenance)
    pinnable_capped: Optional[bool] = None             # True => probe hit its max; ceiling is a lower bound
    cpu_mem_bw_gbps: Optional[float] = None            # measured CPU RAM bandwidth — the MoE-offload throughput input
    cpu_mem_bw_method: Optional[str] = None            # how it was measured (provenance)


@dataclass
class HardwareProfile:
    gpu: GpuInfo
    platform: PlatformInfo
    bandwidth: BandwidthInfo = field(default_factory=lambda: BandwidthInfo())
    memory: MemoryInfo = field(default_factory=lambda: MemoryInfo())


@dataclass
class ExpertInfo:
    is_moe: bool = False
    num_experts: Optional[int] = None
    experts_per_token: Optional[int] = None     # top-k
    shared_params: Optional[int] = None
    expert_params_each: Optional[int] = None


@dataclass
class ModelProfile:
    name: str
    architecture: str = "unknown"               # "dense" | "moe" | "unknown"
    total_params: Optional[int] = None
    n_layers: Optional[int] = None
    n_kv_heads: Optional[int] = None
    head_dim: Optional[int] = None
    dtype_bytes: float = 2.0                     # fp16/bf16 default
    quant: Optional[str] = None                  # "gguf-q4_k_m" | "gptq" | "awq" | "fp8" | None
    expert: ExpertInfo = field(default_factory=ExpertInfo)
    kv_bytes_per_token: Optional[int] = None     # closed-form; see model.kv_bytes_per_token()
    # Closed-form param split (model.analyze_config) — the planner's placement math keys off these.
    # `expert_params_total` is the part `--n-cpu-moe` can move to CPU; `non_expert_params` (attention,
    # router, embeddings, head, shared experts, dense layers) ALWAYS stays on the GPU.
    expert_params_total: Optional[int] = None
    non_expert_params: Optional[int] = None
    n_moe_layers: Optional[int] = None           # layers that actually carry routed experts

    def kv_bytes_at(self, context_tokens: int, batch: int = 1) -> Optional[int]:
        """KV-cache bytes at a given context — linear in context (docker-knowledge throughput-prediction)."""
        if self.kv_bytes_per_token is None:
            return None
        return self.kv_bytes_per_token * context_tokens * batch


@dataclass
class Profile:
    schema_version: str
    created: str                                 # ISO date, passed in (workflows/runners have no clock)
    hardware: HardwareProfile
    model: Optional[ModelProfile] = None
    notes: List[str] = field(default_factory=list)

    # --- serialization -------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return _build(cls, d)

    @classmethod
    def from_json(cls, s: str) -> "Profile":
        return cls.from_dict(json.loads(s))


@dataclass
class PlacementPlan:
    """The planner's output: how to place an MoE model across VRAM/RAM for a runtime, with a
    predicted memory map + throughput and an honest ship/refuse verdict (>1 tok/s floor)."""
    fits: bool
    verdict: str                                 # "ship" | "refuse"
    runtime: str = "llama.cpp"
    n_cpu_moe: Optional[int] = None              # the --n-cpu-moe value (MoE layers whose experts -> CPU RAM)
    n_moe_layers: Optional[int] = None
    llama_flags: Optional[str] = None            # the exact flag string to launch with
    vram_budget_mib: Optional[float] = None
    vram_used_mib: Optional[float] = None
    ram_used_mib: Optional[float] = None         # CPU-resident expert bytes (regular host RAM)
    predicted_decode_tok_s: Optional[float] = None
    throughput_basis: Optional[str] = None       # "in-VRAM (±10%)" | "cpu-offload estimate — confirmed by receipt"
    floor_tok_s: float = 1.0
    message: Optional[str] = None                # plan summary / contrastive refusal frame
    assumptions: Optional[dict] = None           # cpu_mem_bw_gbps, vram_bw_gbps, bpw, ctx, overhead_mib

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class Receipt:
    """The measured proof — a DIFFERENT mechanism (measurement) verifying the planner's forecast."""
    runtime: str = "llama.cpp"
    n_cpu_moe: Optional[int] = None
    measured_decode_tok_s: Optional[float] = None
    measured_prefill_tok_s: Optional[float] = None
    measured_vram_used_mib: Optional[float] = None
    predicted_decode_tok_s: Optional[float] = None
    decode_error_pct: Optional[float] = None     # 100*(measured-predicted)/measured
    cleared_floor: Optional[bool] = None
    method: Optional[str] = None                 # how it was measured (provenance)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _build(dc_type: Any, value: Any) -> Any:
    """Recursively reconstruct a (possibly nested) dataclass from plain dicts.

    Tolerant: ignores unknown keys and leaves missing fields at their defaults, so an
    older profile.json still loads against a newer schema.
    """
    if not is_dataclass(dc_type) or value is None:
        return value
    kwargs = {}
    type_by_name = {f.name: f.type for f in fields(dc_type)}
    known = set(type_by_name)
    for k, v in value.items():
        if k not in known:
            continue
        ftype = type_by_name[k]
        # nested dataclass fields are referenced by their global type here
        nested = _GLOBALS.get(_strip_optional(ftype))
        kwargs[k] = _build(nested, v) if (nested and isinstance(v, dict)) else v
    return dc_type(**kwargs)


def _strip_optional(t: Any) -> str:
    """Best-effort: map a field's type annotation to a bare dataclass name for nesting."""
    s = t if isinstance(t, str) else getattr(t, "__name__", str(t))
    # annotations may arrive as "Optional[ExpertInfo]" / "ExpertInfo" depending on import style
    for name in _GLOBALS:
        if name in s:
            return name
    return s


_GLOBALS = {
    "GpuInfo": GpuInfo, "PlatformInfo": PlatformInfo, "BandwidthInfo": BandwidthInfo,
    "MemoryInfo": MemoryInfo, "HardwareProfile": HardwareProfile, "ExpertInfo": ExpertInfo,
    "ModelProfile": ModelProfile,
}
