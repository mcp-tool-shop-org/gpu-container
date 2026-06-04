"""Planner tests: closed-form param split against known MoE footprints, and the
fit / offload / refuse-on-floor / refuse-on-capacity decision paths.

These are pure math (no GPU/model/runtime needed) — they pin the load-bearing placement
decision. The throughput number is a roofline ceiling validated live by the receipt, so we
assert its REFUSAL behavior (ceiling < floor) and ordering, not an absolute tok/s.
"""
from gpu_container.planner import plan_llama_cpp
from gpu_container.planner.receipt import _pick, build_receipt, parse_llama_bench
from gpu_container.profiler import model as m
from gpu_container.profiler.schema import (
    GpuInfo,
    HardwareProfile,
    MemoryInfo,
    PlacementPlan,
    PlatformInfo,
    Profile,
)

# Mixtral-8x7B (46.7B): 32 layers, hidden 4096, expert FFN 14336, 8 experts top-2.
MIXTRAL = {
    "model_type": "mixtral", "num_hidden_layers": 32, "hidden_size": 4096,
    "intermediate_size": 14336, "num_attention_heads": 32, "num_key_value_heads": 8,
    "num_local_experts": 8, "num_experts_per_tok": 2, "vocab_size": 32000, "torch_dtype": "bfloat16",
}
# Qwen3-30B-A3B (~30.5B): 48 layers, hidden 2048, moe FFN 768, 128 experts top-8.
QWEN3_MOE = {
    "model_type": "qwen3_moe", "num_hidden_layers": 48, "hidden_size": 2048,
    "moe_intermediate_size": 768, "intermediate_size": 768, "num_attention_heads": 32,
    "num_key_value_heads": 4, "head_dim": 128, "num_experts": 128, "num_experts_per_tok": 8,
    "vocab_size": 151936, "torch_dtype": "bfloat16",
}


def _profile(vram_free_mib=30000, ram_gib=60.0, cpu_bw=None):
    return Profile(
        schema_version="0.1.0", created="2026-06-04",
        hardware=HardwareProfile(
            gpu=GpuInfo(name="RTX 5090", vram_total_mib=32607, vram_free_mib=vram_free_mib),
            platform=PlatformInfo(os="linux", in_container=True, wsl2=True),
            memory=MemoryInfo(ram_total_gib=ram_gib, ram_available_gib=ram_gib, cpu_mem_bw_gbps=cpu_bw),
        ),
    )


def test_param_split_mixtral_matches_published_size():
    mp = m.analyze_config(MIXTRAL, name="mixtral-8x7b")
    assert mp.n_moe_layers == 32
    assert mp.expert.expert_params_each == 3 * 4096 * 14336
    # Mixtral-8x7B is 46.7B params — closed-form within 3%
    assert 45.0e9 <= mp.total_params <= 48.0e9
    assert mp.expert_params_total > mp.non_expert_params  # experts dominate


def test_param_split_qwen3_matches_published_size():
    mp = m.analyze_config(QWEN3_MOE, name="qwen3-30b-a3b")
    assert mp.n_moe_layers == 48
    # Qwen3-30B-A3B is ~30.5B — within 3%
    assert 29.0e9 <= mp.total_params <= 32.0e9


def test_qwen3_q4_fits_fully_in_vram():
    prof = _profile(vram_free_mib=30000, cpu_bw=80.0)
    prof.model = m.analyze_config(QWEN3_MOE, name="qwen3-30b-a3b", quant="gguf-q4_k_m")
    plan = plan_llama_cpp(prof, ctx_len=4096)
    assert plan.fits and plan.verdict == "ship"
    assert plan.n_cpu_moe == 0                     # ~18 GB fits 30 GB free -> no offload
    assert plan.vram_used_mib < 30000
    assert plan.predicted_decode_tok_s > 1.0
    assert "-ngl 99 --n-cpu-moe 0" in plan.llama_flags
    assert "-fa on" in plan.llama_flags            # tri-state flash-attn; bare -fa is rejected by current llama.cpp


def test_mixtral_q8_needs_cpu_offload_but_ships():
    # Mixtral Q8 ~50 GB > 32 GB VRAM -> must push expert layers to CPU RAM, but 64 GB RAM holds them.
    prof = _profile(vram_free_mib=30000, ram_gib=60.0, cpu_bw=80.0)
    prof.model = m.analyze_config(MIXTRAL, name="mixtral-8x7b", quant="gguf-q8_0")
    plan = plan_llama_cpp(prof, ctx_len=4096)
    assert plan.fits and plan.verdict == "ship"
    assert plan.n_cpu_moe > 0                       # offload required
    assert plan.ram_used_mib > 0


def test_refuse_when_nonexpert_alone_exceeds_vram():
    # Tiny VRAM budget: even all experts on CPU (--cpu-moe), the resident footprint won't fit.
    prof = _profile(vram_free_mib=2000, cpu_bw=80.0)
    prof.model = m.analyze_config(MIXTRAL, name="mixtral-8x7b", quant="gguf-q4_k_m")
    plan = plan_llama_cpp(prof, ctx_len=4096)
    assert not plan.fits and plan.verdict == "refuse"
    assert plan.n_cpu_moe == plan.n_moe_layers       # tried pushing everything to CPU
    assert "REFUSE" in plan.message


def test_refuse_below_floor_even_if_memory_fits():
    # VRAM just big enough to force ALL experts to CPU (N == n_moe_layers); a starved CPU-RAM
    # bandwidth then pushes even the roofline ceiling under 1 tok/s -> refuse on speed, not memory.
    prof = _profile(vram_free_mib=2500, ram_gib=60.0, cpu_bw=1.0)
    prof.model = m.analyze_config(QWEN3_MOE, name="qwen3-30b-a3b", quant="gguf-q4_k_m")
    plan = plan_llama_cpp(prof, ctx_len=4096, floor_tok_s=1.0)
    assert plan.fits and plan.verdict == "refuse"    # fits in memory, refused on speed
    assert plan.n_cpu_moe == plan.n_moe_layers       # everything pushed to CPU
    assert plan.predicted_decode_tok_s < 1.0
    assert "ceiling" in plan.message.lower()


def test_parse_llama_bench_and_build_receipt():
    js = ('[{"test":"pp512","avg_ts":2000.0,"n_cpu_moe":0,"n_gpu_layers":99},'
          '{"test":"tg128","avg_ts":140.0,"n_cpu_moe":0,"n_gpu_layers":99}]')
    rows = parse_llama_bench("load log...\n" + js + "\ntrailing log")
    assert len(rows) == 2
    assert _pick(rows, "tg") == 140.0 and _pick(rows, "pp") == 2000.0

    # ceiling 400, measured 140 -> realized 35%, signed error negative, floor cleared
    plan = PlacementPlan(fits=True, verdict="ship", n_cpu_moe=0,
                         predicted_decode_tok_s=400.0, vram_used_mib=18000.0, floor_tok_s=1.0)
    rec = build_receipt(plan, decode_tok_s=140.0, prefill_tok_s=2000.0, vram_used_mib=18500.0,
                        method="llama-bench")
    assert rec.measured_decode_tok_s == 140.0 and rec.cleared_floor is True
    assert rec.decode_error_pct == round(100 * (140 - 400) / 400, 1)  # -65.0
    assert any("realized" in n for n in rec.notes)


def test_dense_model_refused_from_moe_lane():
    prof = _profile()
    prof.model = m.analyze_config(
        {"model_type": "llama", "num_hidden_layers": 32, "hidden_size": 4096,
         "intermediate_size": 14336, "num_attention_heads": 32, "vocab_size": 32000},
        name="llama-7b",
    )
    plan = plan_llama_cpp(prof)
    assert not plan.fits and plan.verdict == "refuse"
    assert "MoE" in plan.message
