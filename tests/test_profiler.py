"""Profiler skeleton tests — the deterministic parts (KV math, MoE/dense detection,
schema round-trip). Hardware/bandwidth detection is environment-dependent and exercised
by the CLI, not asserted here.
"""
from gpu_container.profiler import (
    GpuInfo,
    HardwareProfile,
    PlatformInfo,
    Profile,
)
from gpu_container.profiler import model as m


def test_kv_bytes_per_token_closed_form():
    # 2 (K,V) * layers * kv_heads * head_dim * dtype_bytes
    assert m.kv_bytes_per_token(32, 32, 128, 2.0) == 2 * 32 * 32 * 128 * 2


def test_analyze_mixtral_is_moe():
    cfg = {
        "model_type": "mixtral", "num_hidden_layers": 32, "num_attention_heads": 32,
        "num_key_value_heads": 8, "hidden_size": 4096,
        "num_local_experts": 8, "num_experts_per_tok": 2, "torch_dtype": "bfloat16",
    }
    mp = m.analyze_config(cfg, name="mixtral-8x7b")
    assert mp.architecture == "moe"
    assert mp.expert.is_moe and mp.expert.num_experts == 8 and mp.expert.experts_per_token == 2
    assert mp.n_kv_heads == 8 and mp.head_dim == 128  # 4096 / 32
    assert mp.kv_bytes_per_token == 2 * 32 * 8 * 128 * 2


def test_analyze_llama_is_dense():
    cfg = {
        "model_type": "llama", "num_hidden_layers": 32, "num_attention_heads": 32,
        "hidden_size": 4096, "torch_dtype": "float16",
    }
    mp = m.analyze_config(cfg)
    assert mp.architecture == "dense"
    assert not mp.expert.is_moe
    assert mp.n_kv_heads == 32                       # falls back to attention heads (no GQA key)
    assert mp.kv_bytes_at(4096) == mp.kv_bytes_per_token * 4096


def test_profile_json_roundtrip_reconstructs_nested_dataclasses():
    p = Profile(
        schema_version="0.1.0", created="2026-06-04",
        hardware=HardwareProfile(
            gpu=GpuInfo(name="RTX 5090", vram_total_mib=32607, compute_capability="12.0"),
            platform=PlatformInfo(os="linux", in_container=True, wsl2=True, uvm_oversubscription=False),
        ),
        notes=["seed"],
    )
    p2 = Profile.from_json(p.to_json())
    assert isinstance(p2, Profile)
    assert isinstance(p2.hardware, HardwareProfile)
    assert isinstance(p2.hardware.gpu, GpuInfo)
    assert p2.hardware.gpu.vram_total_mib == 32607
    assert p2.hardware.platform.wsl2 is True
    assert p2.hardware.platform.uvm_oversubscription is False
