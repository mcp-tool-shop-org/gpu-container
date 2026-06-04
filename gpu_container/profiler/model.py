"""Model profiler — analyze a model's architecture + memory growth before loading.

What's REAL here today (closed-form, deterministic — docker-knowledge throughput-prediction
finding "Memory is exact"):
  - KV-cache bytes/token and at a given context (linear in context).
  - dense vs MoE detection, expert structure, from a HuggingFace config dict.

What's STUBBED (needs the file on disk / a download — a later Phase-1 step):
  - total_params and per-layer/per-expert byte accounting from safetensors/GGUF headers.
"""
from __future__ import annotations

from typing import Optional

from .schema import ExpertInfo, ModelProfile

# dtype name -> bytes per element
_DTYPE_BYTES = {
    "float32": 4.0, "float": 4.0, "fp32": 4.0,
    "float16": 2.0, "fp16": 2.0, "half": 2.0,
    "bfloat16": 2.0, "bf16": 2.0,
    "float8": 1.0, "fp8": 1.0, "e4m3": 1.0, "e5m2": 1.0,
}


def kv_bytes_per_token(n_layers: int, n_kv_heads: int, head_dim: int, dtype_bytes: float = 2.0) -> int:
    """Closed-form KV-cache size per token, in bytes.

        bytes/token = 2 (K and V) * n_layers * n_kv_heads * head_dim * dtype_bytes

    Per NVIDIA "Mastering LLM Techniques: Inference Optimization" (docker-knowledge
    throughput-prediction). GQA/MQA shrink this via n_kv_heads < n_attention_heads.
    """
    return int(2 * n_layers * n_kv_heads * head_dim * dtype_bytes)


def _dtype_bytes_from(cfg: dict) -> float:
    td = str(cfg.get("torch_dtype") or cfg.get("dtype") or "bfloat16").lower()
    return _DTYPE_BYTES.get(td, 2.0)


def analyze_config(config: dict, name: Optional[str] = None, quant: Optional[str] = None) -> ModelProfile:
    """Build a ModelProfile from a HuggingFace-style config.json dict.

    Recognizes the common MoE keys across Mixtral / Qwen-MoE / DeepSeek-V2/V3 / OLMoE.
    Fields it cannot determine are left None (never guessed).
    """
    name = name or config.get("_name_or_path") or config.get("model_type") or "unknown"
    n_layers = config.get("num_hidden_layers")
    n_attn_heads = config.get("num_attention_heads")
    n_kv_heads = config.get("num_key_value_heads") or n_attn_heads
    hidden = config.get("hidden_size")
    head_dim = config.get("head_dim")
    if head_dim is None and hidden and n_attn_heads:
        head_dim = hidden // n_attn_heads
    dtype_bytes = _dtype_bytes_from(config)

    # MoE detection — the key name varies by family
    num_experts = (config.get("num_local_experts") or config.get("num_experts")
                   or config.get("n_routed_experts"))
    experts_per_token = (config.get("num_experts_per_tok") or config.get("num_experts_per_token")
                         or config.get("moe_topk"))
    is_moe = num_experts is not None
    expert = ExpertInfo(
        is_moe=is_moe,
        num_experts=num_experts,
        experts_per_token=experts_per_token,
        shared_params=config.get("n_shared_experts"),
    )

    kvbpt = None
    if n_layers and n_kv_heads and head_dim:
        kvbpt = kv_bytes_per_token(n_layers, n_kv_heads, head_dim, dtype_bytes)

    return ModelProfile(
        name=name,
        architecture="moe" if is_moe else ("dense" if n_layers else "unknown"),
        n_layers=n_layers,
        n_kv_heads=n_kv_heads,
        head_dim=head_dim,
        dtype_bytes=dtype_bytes,
        quant=quant,
        expert=expert,
        kv_bytes_per_token=kvbpt,
    )
