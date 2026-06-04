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


# Effective GGUF bits-per-weight (incl. quant metadata overhead) — llama.cpp quant tables.
# Used to turn a closed-form param count into a realistic on-device byte footprint.
_BPW = {
    "q2_k": 3.35, "q3_k_s": 3.50, "q3_k_m": 3.91, "q3_k_l": 4.27,
    "q4_0": 4.55, "q4_1": 4.78, "q4_k_s": 4.57, "q4_k_m": 4.83,
    "q5_0": 5.54, "q5_1": 6.00, "q5_k_s": 5.52, "q5_k_m": 5.67,
    "q6_k": 6.56, "q8_0": 8.50,
    "iq2_xxs": 2.06, "iq3_xxs": 3.06, "iq4_xs": 4.25, "iq4_nl": 4.50,
    "mxfp4": 4.25, "fp8": 8.0, "f16": 16.0, "bf16": 16.0, "f32": 32.0,
}


def bytes_per_weight(quant: Optional[str], dtype_bytes: float = 2.0) -> float:
    """Bytes per weight for a quant tag (e.g. 'gguf-q4_k_m' -> 0.60), or the dtype default."""
    if quant:
        k = quant.lower().replace("gguf-", "").replace("-", "_").strip()
        if k in _BPW:
            return _BPW[k] / 8.0
    return dtype_bytes


# Quants that quantize ONLY the routed experts, leaving attention/router/embeddings/head near f16
# (notably MXFP4 / gpt-oss). For these the always-resident non-expert weights are far heavier per
# parameter than the headline quant implies, so budgeting the GPU floor at the expert bpw would
# UNDER-count VRAM (the optimistic, OOM-prone direction). The split keeps None-not-guess honest.
_EXPERT_ONLY_QUANTS = {"mxfp4"}


def non_expert_bytes_per_weight(quant: Optional[str], dtype_bytes: float = 2.0) -> float:
    """Bytes/weight for the ALWAYS-RESIDENT (non-expert) tensors.

    Equal to the expert bpw for whole-model quants (Q4_K_M, Q8_0, ...). For expert-only quants
    (MXFP4) the non-expert tensors stay near f16, so this returns 2.0 — a conservative upper bound
    on the GPU floor (slightly over-budgets VRAM, which is the SAFE side for a must-offload plan).
    """
    if quant:
        k = quant.lower().replace("gguf-", "").replace("-", "_").strip()
        if k in _EXPERT_ONLY_QUANTS:
            return max(2.0, _BPW.get(k, 8.0) / 8.0)
    return bytes_per_weight(quant, dtype_bytes)


def estimate_param_split(cfg: dict, num_experts: Optional[int]) -> Optional[dict]:
    """Closed-form param split from a HF config — no safetensors needed.

    Returns the two quantities the placement planner keys off:
      - `expert_total` / `expert_each` — routed-expert params (`--n-cpu-moe` can move these to CPU),
      - `non_expert` — attention + router + embeddings + head + shared experts + dense layers
        (ALWAYS on the GPU), plus `total` and `n_moe_layers`.
    Approximations (documented, receipt-confirmed): SwiGLU expert = 3·H·I; biases/norms omitted
    (sub-1%); a real GGUF may keep embeddings/output at higher precision than the headline quant.
    """
    H = cfg.get("hidden_size")
    L = cfg.get("num_hidden_layers")
    if not (H and L):
        return None
    n_heads = cfg.get("num_attention_heads") or 0
    n_kv = cfg.get("num_key_value_heads") or n_heads
    head_dim = cfg.get("head_dim") or (H // n_heads if n_heads else 0)
    vocab = cfg.get("vocab_size") or 0
    inter = cfg.get("intermediate_size") or 0
    moe_inter = cfg.get("moe_intermediate_size") or inter
    tied = bool(cfg.get("tie_word_embeddings", False))
    n_dense = cfg.get("first_k_dense_replace") or cfg.get("num_dense_layers") or 0
    n_shared = cfg.get("n_shared_experts") or cfg.get("num_shared_experts") or 0
    shared_inter = cfg.get("shared_expert_intermediate_size") or moe_inter

    n_moe_layers = max(0, L - n_dense) if num_experts else 0
    dense_count = L - n_moe_layers  # dense FFN layers (= n_dense for MoE, = L for dense models)

    expert_each = 3 * H * moe_inter if (num_experts and moe_inter) else 0
    expert_total = (num_experts or 0) * expert_each * n_moe_layers

    attn_total = (2 * H * n_heads * head_dim + 2 * H * n_kv * head_dim) * L  # q,o + k,v
    router_total = (num_experts or 0) * H * n_moe_layers
    shared_total = (n_shared * 3 * H * shared_inter) * n_moe_layers if n_shared else 0
    dense_ffn_total = (3 * H * inter) * dense_count
    embed = vocab * H
    head = 0 if tied else vocab * H
    non_expert = attn_total + router_total + shared_total + dense_ffn_total + embed + head
    return {
        "expert_total": int(expert_total), "expert_each": int(expert_each),
        "non_expert": int(non_expert), "total": int(non_expert + expert_total),
        "n_moe_layers": int(n_moe_layers),
    }


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
    split = estimate_param_split(config, num_experts)
    expert = ExpertInfo(
        is_moe=is_moe,
        num_experts=num_experts,
        experts_per_token=experts_per_token,
        shared_params=config.get("n_shared_experts"),
        expert_params_each=(split or {}).get("expert_each") or None,
    )

    kvbpt = None
    if n_layers and n_kv_heads and head_dim:
        kvbpt = kv_bytes_per_token(n_layers, n_kv_heads, head_dim, dtype_bytes)

    return ModelProfile(
        name=name,
        architecture="moe" if is_moe else ("dense" if n_layers else "unknown"),
        total_params=(split or {}).get("total"),
        n_layers=n_layers,
        n_kv_heads=n_kv_heads,
        head_dim=head_dim,
        dtype_bytes=dtype_bytes,
        quant=quant,
        expert=expert,
        kv_bytes_per_token=kvbpt,
        expert_params_total=(split or {}).get("expert_total"),
        non_expert_params=(split or {}).get("non_expert"),
        n_moe_layers=(split or {}).get("n_moe_layers"),
    )
